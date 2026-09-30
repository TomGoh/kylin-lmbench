/*
 * frames2.c - random-access latency as a function of WHICH 1 GiB physical
 * slot the pages come from, measured inside one process.
 *
 * Why: under protected mode the host runs on a stage-2 identity map made of
 * 1 GiB blocks where a whole GiB slot is ordinary RAM, and of 2 MiB blocks or
 * 4 KiB pages where the slot is only partly RAM or contains pages owned by
 * the hypervisor.  A page walk for a page under a 1 GiB block needs one
 * stage-2 descriptor per stage-2 translation; under smaller leaves it needs
 * two or three, read from larger tables.  If the extra cost of protected mode
 * in the random chase is the stage-2 part of the walk, slots with smaller
 * stage-2 leaves should be slower and should show more cache refills per
 * access, in the same boot and the same mode.
 *
 * What it does: builds a pool of 4 KiB anonymous pages, reads their PFNs,
 * and for every GiB slot that holds enough pool pages maps <size_mb> of them
 * (lowest PFNs of the slot) into a fresh virtually contiguous range with
 * mremap(), runs the lmbench random chase over that range, then moves the
 * same pages to a second fresh range and measures again (pass 2: same data
 * frames, newly allocated page-table pages).
 *
 * usage: frames2 <size_mb> <pool_mb> <events,hex,...> [seed] [pick low|even] [regions file]
 *   pick even: take every k-th pool page of the slot instead of the lowest ones
 *   regions file: one hexadecimal 2 MiB region number (PFN >> 9) per line, as
 *     written by vm-frames.py for the memory of a running VM.  With it, every
 *     slot is measured separately for pool pages that share a 2 MiB region
 *     with the VM (class=shared) and for pool pages that do not (class=clear).
 *     Pages given to a protected VM are taken out of the host stage-2 map one
 *     4 KiB page at a time, so the host pages of a shared region are mapped
 *     with 4 KiB stage-2 leaves, the others with 2 MiB or 1 GiB blocks.
 * Needs CAP_SYS_ADMIN (PFNs from /proc/self/pagemap).  One line per slot, class and pass.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/perf_event.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

#define PAGE 4096UL
#define STRIDE 16UL
#define MAXEV 8
#define REPS 5

static double now_ns(void)
{
	struct timespec ts;

	clock_gettime(CLOCK_MONOTONIC, &ts);
	return ts.tv_sec * 1e9 + ts.tv_nsec;
}

static int perf_open(uint64_t config)
{
	struct perf_event_attr a;

	memset(&a, 0, sizeof(a));
	a.type = PERF_TYPE_RAW;
	a.size = sizeof(a);
	a.config = config;
	a.disabled = 1;
	a.exclude_kernel = 1;
	a.exclude_hv = 1;
	a.read_format = PERF_FORMAT_TOTAL_TIME_ENABLED | PERF_FORMAT_TOTAL_TIME_RUNNING;
	return syscall(SYS_perf_event_open, &a, 0, -1, -1, 0);
}

static char **chase(char **p, size_t hops)
{
	size_t i;

	for (i = 0; i < hops; i++)
		p = (char **)*p;
	return p;
}

static int cmp_d(const void *a, const void *b)
{
	double x = *(const double *)a, y = *(const double *)b;

	return (x > y) - (x < y);
}

struct fr {
	uint64_t pfn;
	size_t idx;
};

static int cmp_fr(const void *a, const void *b)
{
	const struct fr *x = a, *y = b;

	return (x->pfn > y->pfn) - (x->pfn < y->pfn);
}

static uint64_t pfn_of(int pm, void *va)
{
	uint64_t e = 0;

	if (pread(pm, &e, 8, ((uint64_t)va / PAGE) * 8) != 8 || !(e >> 63))
		return 0;
	return e & ((1ULL << 55) - 1);
}

static size_t *permutation(size_t max, size_t scale, unsigned seed)
{
	size_t i, v, r;
	size_t *res = malloc(max * sizeof(size_t));

	for (i = 0; i < max; i++)
		res[i] = i * scale;
	srand(seed);
	r = ((size_t)seed << 6) ^ rand() ^ ((size_t)rand() << 10);
	for (i = max - 1; i > 0; i--) {
		r = (r << 1) ^ rand();
		v = res[r % (i + 1)];
		res[r % (i + 1)] = res[i];
		res[i] = v;
	}
	return res;
}

static size_t *words_initialize(size_t max, size_t scale)
{
	size_t i, j, nbits;
	size_t *words = calloc(max, sizeof(size_t));

	for (i = max >> 1, nbits = 0; i != 0; i >>= 1, nbits++)
		;
	for (i = 0; i < max; i++) {
		for (j = 0; j < nbits; j++)
			if (i & (1UL << j))
				words[i] |= (1UL << (nbits - j - 1));
		words[i] *= scale;
	}
	return words;
}

static int nev, fd[MAXEV];
static uint64_t evcfg[MAXEV];

static uint64_t *shared_reg;	/* sorted 2 MiB region numbers that hold VM pages */
static size_t nshared;

static int cmp_u64(const void *a, const void *b)
{
	uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b;

	return (x > y) - (x < y);
}

static int is_shared(uint64_t pfn)
{
	uint64_t key = pfn >> 9;

	return nshared && bsearch(&key, shared_reg, nshared, sizeof(uint64_t), cmp_u64) != NULL;
}

static void load_regions(const char *path)
{
	FILE *f = fopen(path, "r");
	size_t cap = 1024;
	unsigned long long v;

	if (!f) {
		perror(path);
		exit(1);
	}
	shared_reg = malloc(cap * sizeof(uint64_t));
	while (fscanf(f, "%llx", &v) == 1) {
		if (nshared == cap)
			shared_reg = realloc(shared_reg, (cap *= 2) * sizeof(uint64_t));
		shared_reg[nshared++] = v;
	}
	fclose(f);
	qsort(shared_reg, nshared, sizeof(uint64_t), cmp_u64);
}

/* lmbench thrash_initialize with len == maxlen over dst, then the timed chase; prints the fields */
static void measure(char *dst, size_t npages, size_t *pages, size_t *words)
{
	size_t nwords = PAGE / STRIDE, k, j, hops;
	uint64_t cnt[MAXEV][3];
	double rep[REPS], t0, t1, total_hops = 0;
	char **p;
	int i;

	for (k = 0; k < npages - 1; k++) {
		size_t cpage = pages[k], npage = pages[k + 1];

		for (j = 0; j < nwords; j++) {
			size_t cur = cpage + words[(k + j) % nwords];
			size_t next = npage + words[(k + j + 1) % nwords];

			*(char **)&dst[cur] = &dst[next];
		}
	}
	{
		size_t cpage = pages[k], npage = pages[0];

		for (j = 0; j < nwords; j++) {
			size_t cur = cpage + words[(k + j) % nwords];
			size_t next = npage + words[(j + 1) % nwords];

			*(char **)&dst[cur] = &dst[next];
		}
	}
	p = (char **)&dst[pages[0]];

	hops = npages * nwords;		/* one full cycle */
	p = chase(p, hops);		/* warm up */
	/* small working sets: as many whole cycles as fit in about 100 ms */
	t0 = now_ns();
	p = chase(p, hops);
	t1 = now_ns();
	if (t1 - t0 < 100e6)
		hops *= (size_t)(100e6 / (t1 - t0)) + 1;
	for (i = 0; i < nev; i++)
		if (fd[i] >= 0) {
			ioctl(fd[i], PERF_EVENT_IOC_RESET, 0);
			ioctl(fd[i], PERF_EVENT_IOC_ENABLE, 0);
		}
	for (i = 0; i < REPS; i++) {
		t0 = now_ns();
		p = chase(p, hops);
		t1 = now_ns();
		rep[i] = (t1 - t0) / hops;
		total_hops += hops;
	}
	for (i = 0; i < nev; i++)
		if (fd[i] >= 0) {
			ioctl(fd[i], PERF_EVENT_IOC_DISABLE, 0);
			if (read(fd[i], cnt[i], sizeof(cnt[i])) != sizeof(cnt[i]))
				cnt[i][0] = cnt[i][1] = cnt[i][2] = 0;
		}
	qsort(rep, REPS, sizeof(double), cmp_d);
	printf(" ns_min=%.3f ns_med=%.3f ns_max=%.3f", rep[0], rep[REPS / 2], rep[REPS - 1]);
	for (i = 0; i < nev; i++) {
		if (fd[i] < 0) {
			printf(" ev%llx=na", (unsigned long long)evcfg[i]);
			continue;
		}
		printf(" ev%llx=%.6f", (unsigned long long)evcfg[i],
		       (double)cnt[i][0] * (cnt[i][2] ? (double)cnt[i][1] / cnt[i][2] : 1.0) / total_hops);
	}
	printf(" sink=%p\n", (void *)p);
	fflush(stdout);
}

int main(int argc, char **argv)
{
	size_t len, pool_len, npages, npool, k, s, e;
	int i, pm, even;
	char *pool, *tok, *evs;
	struct fr *fr, *sel;
	size_t *pages, *words;
	unsigned seed;

	if (argc < 4) {
		fprintf(stderr, "usage: %s <size_mb> <pool_mb> <events> [seed] [pick low|even] [regions file]\n", argv[0]);
		return 2;
	}
	len = (size_t)(atof(argv[1]) * 1024 * 1024);
	pool_len = (size_t)(atof(argv[2]) * 1024 * 1024);
	evs = strdup(argv[3]);
	seed = argc > 4 ? strtoul(argv[4], NULL, 0) : 1;
	even = argc > 5 && !strcmp(argv[5], "even");
	if (argc > 6)
		load_regions(argv[6]);
	for (tok = strtok(evs, ","); tok && nev < MAXEV; tok = strtok(NULL, ","))
		evcfg[nev++] = strtoull(tok, NULL, 16);
	npages = len / PAGE;
	npool = pool_len / PAGE;
	if (!npages || npool < npages)
		return 2;

	pool = mmap(NULL, pool_len, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
	if (pool == MAP_FAILED) {
		perror("mmap pool");
		return 1;
	}
	madvise(pool, pool_len, MADV_NOHUGEPAGE);
	for (k = 0; k < npool; k++)
		pool[k * PAGE] = 1;
	pm = open("/proc/self/pagemap", O_RDONLY);
	if (pm < 0) {
		perror("pagemap");
		return 1;
	}
	fr = malloc(npool * sizeof(*fr));
	for (k = 0; k < npool; k++) {
		fr[k].pfn = pfn_of(pm, pool + k * PAGE);
		fr[k].idx = k;
		if (!fr[k].pfn) {
			fprintf(stderr, "no PFN (need root)\n");
			return 1;
		}
	}
	qsort(fr, npool, sizeof(*fr), cmp_fr);
	sel = malloc(npages * sizeof(*sel));
	pages = permutation(npages, PAGE, seed);
	words = words_initialize(PAGE / STRIDE, STRIDE);
	for (i = 0; i < nev; i++)
		fd[i] = perf_open(evcfg[i]);

	printf("# pool_pages=%zu size_pages=%zu pick=%s slots:", npool, npages, even ? "even" : "low");
	for (s = 0; s < npool; s = e) {
		for (e = s + 1; e < npool && (fr[e].pfn >> 18) == (fr[s].pfn >> 18); e++)
			;
		printf(" 0x%llx:%zu", (unsigned long long)(fr[s].pfn >> 18), e - s);
	}
	printf("\n");

	for (s = 0; s < npool; s = e) {
		int cls, ncls = nshared ? 2 : 1;

		for (e = s + 1; e < npool && (fr[e].pfn >> 18) == (fr[s].pfn >> 18); e++)
			;
		/* class 0: all pages of the slot (no regions file) or pages in regions without VM pages; class 1: shared */
		for (cls = 0; cls < ncls; cls++) {
			size_t n = 0, contig = 0, mb2 = 0;
			size_t *cand = malloc((e - s) * sizeof(size_t));
			uint64_t prev = 0;
			char *dst, *dst2;
			int pass;

			/* the pool pages of this slot that belong to the class, in ascending PFN order */
			for (k = s; k < e; k++)
				if (!nshared || is_shared(fr[k].pfn) == cls)
					cand[n++] = k;
			if (n < npages) {
				free(cand);
				continue;
			}
			for (k = 0; k < npages; k++)
				sel[k] = fr[cand[even ? k * n / npages : k]];
			free(cand);

			dst = mmap(NULL, len, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0);
			dst2 = mmap(NULL, len, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0);
			if (dst == MAP_FAILED || dst2 == MAP_FAILED) {
				perror("mmap dst");
				return 1;
			}
			for (k = 0; k < npages; k++)
				if (mremap(pool + sel[k].idx * PAGE, PAGE, PAGE, MREMAP_MAYMOVE | MREMAP_FIXED, dst + k * PAGE) == MAP_FAILED) {
					perror("mremap");
					return 1;
				}
			for (k = 0; k < npages; k++) {
				uint64_t f = pfn_of(pm, dst + k * PAGE);

				if (k && f == prev + 1) contig++;
				if (!k || (f >> 9) != (prev >> 9)) mb2++;
				prev = f;
			}
			for (pass = 1; pass <= 2; pass++) {
				char *d = pass == 1 ? dst : dst2;

				if (pass == 2)
					for (k = 0; k < npages; k++)
						if (mremap(dst + k * PAGE, PAGE, PAGE, MREMAP_MAYMOVE | MREMAP_FIXED, dst2 + k * PAGE) == MAP_FAILED) {
							perror("mremap 2");
							return 1;
						}
				printf("slot=0x%llx phys=0x%llx class=%s frames_in_class=%zu pass=%d size_mb=%.0f pfn_min=0x%llx pfn_max=0x%llx contig_frac=%.4f mb2_regions=%zu",
				       (unsigned long long)(sel[0].pfn >> 18), (unsigned long long)((sel[0].pfn >> 18) << 30),
				       !nshared ? "all" : cls ? "shared" : "clear", n, pass,
				       len / 1048576.0, (unsigned long long)sel[0].pfn, (unsigned long long)sel[npages - 1].pfn,
				       (double)contig / (npages - 1), mb2);
				measure(d, npages, pages, words);
			}
			munmap(dst, len);
			munmap(dst2, len);
		}
	}
	return 0;
}
