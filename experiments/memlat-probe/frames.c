/*
 * frames.c - does the PHYSICAL LOCATION of the pages change random-access latency?
 *
 * Builds a pool of 4 KiB anonymous pages, reads PFNs, selects a frame set by a
 * policy, maps exactly those frames into a fresh virtually-contiguous range
 * with mremap(), and runs the lmbench random chase (thrash_initialize,
 * size == maxlen) over it.
 *
 * policies:
 *   compact   : longest runs of consecutive PFNs first (fewest 2 MiB regions)
 *   scatter   : every (pool/size)-th frame of the PFN-sorted pool (max spread)
 *   region:N  : frames from the N-th most populated 1 GiB physical region of the
 *               pool, lowest PFNs first
 *   low / high: the lowest / highest PFNs of the pool
 *
 * usage: frames <size_mb> <stride> <pool_mb> <events,hex,...> <policy> [seed]
 * Needs CAP_SYS_ADMIN (PFNs from /proc/self/pagemap).
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
#define MAXEV 8
#define REPS 11

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

struct run {
	size_t start, len;
};

static int cmp_run(const void *a, const void *b)
{
	const struct run *x = a, *y = b;

	return (x->len < y->len) - (x->len > y->len);
}

struct reg {
	uint64_t gb;
	size_t start, n;
};

static int cmp_reg(const void *a, const void *b)
{
	const struct reg *x = a, *y = b;

	return (x->n < y->n) - (x->n > y->n);
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

int main(int argc, char **argv)
{
	size_t len, stride, pool_len, npages, npool, k, j, nruns = 0, nreg = 0, got = 0, hops, nwords;
	uint64_t evcfg[MAXEV], cnt[MAXEV][3], prev = 0;
	int nev = 0, fd[MAXEV], i, pm;
	char *pool, *dst, *tok, *evs, **p;
	const char *policy;
	struct fr *fr, *sel;
	size_t *pages, *words;
	double rep[REPS], t0, t1, total_hops = 0;
	size_t contig = 0, gb_regions = 0, mb2_regions = 0;
	unsigned seed;

	if (argc < 6) {
		fprintf(stderr, "usage: %s <size_mb> <stride> <pool_mb> <events> <policy> [seed]\n", argv[0]);
		return 2;
	}
	len = (size_t)(atof(argv[1]) * 1024 * 1024);
	stride = strtoul(argv[2], NULL, 0);
	pool_len = (size_t)(atof(argv[3]) * 1024 * 1024);
	evs = strdup(argv[4]);
	policy = argv[5];
	seed = argc > 6 ? strtoul(argv[6], NULL, 0) : (unsigned)getpid();
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

	if (!strcmp(policy, "compact")) {
		struct run *runs = malloc(npool * sizeof(*runs));

		for (k = 0; k < npool;) {
			j = k + 1;
			while (j < npool && fr[j].pfn == fr[j - 1].pfn + 1)
				j++;
			runs[nruns].start = k;
			runs[nruns].len = j - k;
			nruns++;
			k = j;
		}
		qsort(runs, nruns, sizeof(*runs), cmp_run);
		for (k = 0; k < nruns && got < npages; k++) {
			size_t take = runs[k].len;

			if (take > npages - got)
				take = npages - got;
			for (j = 0; j < take; j++)
				sel[got++] = fr[runs[k].start + j];
		}
	} else if (!strcmp(policy, "scatter")) {
		for (k = 0; k < npages; k++)
			sel[got++] = fr[k * npool / npages];
	} else if (!strcmp(policy, "low")) {
		for (k = 0; k < npages; k++)
			sel[got++] = fr[k];
	} else if (!strcmp(policy, "high")) {
		for (k = 0; k < npages; k++)
			sel[got++] = fr[npool - npages + k];
	} else if (!strncmp(policy, "region:", 7)) {
		struct reg *regs = malloc(npool * sizeof(*regs));
		size_t want = strtoul(policy + 7, NULL, 0);

		for (k = 0; k < npool;) {
			j = k + 1;
			while (j < npool && (fr[j].pfn >> 18) == (fr[k].pfn >> 18))
				j++;
			regs[nreg].gb = fr[k].pfn >> 18;
			regs[nreg].start = k;
			regs[nreg].n = j - k;
			nreg++;
			k = j;
		}
		qsort(regs, nreg, sizeof(*regs), cmp_reg);
		if (want >= nreg || regs[want].n < npages) {
			printf("policy=%s unavailable (regions=%zu, frames_in_region=%zu, need=%zu)\n",
			       policy, nreg, want < nreg ? regs[want].n : 0, npages);
			return 0;
		}
		for (k = 0; k < npages; k++)
			sel[got++] = fr[regs[want].start + k];
	} else {
		fprintf(stderr, "unknown policy\n");
		return 2;
	}
	qsort(sel, npages, sizeof(*sel), cmp_fr);

	dst = mmap(NULL, len, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0);
	if (dst == MAP_FAILED) {
		perror("mmap dst");
		return 1;
	}
	/* virtual order: ascending PFN (the chase below visits pages in random order anyway) */
	for (k = 0; k < npages; k++)
		if (mremap(pool + sel[k].idx * PAGE, PAGE, PAGE, MREMAP_MAYMOVE | MREMAP_FIXED, dst + k * PAGE) == MAP_FAILED) {
			perror("mremap");
			return 1;
		}
	/* give the rest of the pool back so that it does not sit in the caches/LRU */
	munmap(pool, pool_len);

	for (k = 0; k < npages; k++) {
		uint64_t f = pfn_of(pm, dst + k * PAGE);

		if (k && f == prev + 1) contig++;
		if (!k || (f >> 18) != (prev >> 18)) gb_regions++;
		if (!k || (f >> 9) != (prev >> 9)) mb2_regions++;
		prev = f;
	}

	/* lmbench thrash_initialize with len == maxlen */
	pages = permutation(npages, PAGE, seed);
	nwords = PAGE / stride;
	words = words_initialize(nwords, stride);
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

	hops = npages * nwords;
	if (hops < 2000000)
		hops = 2000000;
	p = chase(p, hops);
	t0 = now_ns();
	p = chase(p, 1000000);
	t1 = now_ns();
	hops = (size_t)(120e6 / ((t1 - t0) / 1e6));
	if (hops < 1000000)
		hops = 1000000;

	for (i = 0; i < nev; i++) {
		fd[i] = perf_open(evcfg[i]);
		if (fd[i] >= 0) {
			ioctl(fd[i], PERF_EVENT_IOC_RESET, 0);
			ioctl(fd[i], PERF_EVENT_IOC_ENABLE, 0);
		}
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

	printf("policy=%s size_mb=%.3f stride=%zu pages=%zu pool_pages=%zu pfn_min=0x%llx pfn_max=0x%llx span_mb=%.0f contig_frac=%.4f gb_regions=%zu mb2_regions=%zu ns_min=%.3f ns_med=%.3f ns_max=%.3f",
	       policy, len / 1048576.0, stride, npages, npool,
	       (unsigned long long)sel[0].pfn, (unsigned long long)sel[npages - 1].pfn,
	       (double)(sel[npages - 1].pfn - sel[0].pfn) * 4096.0 / 1048576.0,
	       (double)contig / (npages - 1), gb_regions, mb2_regions,
	       rep[0], rep[REPS / 2], rep[REPS - 1]);
	for (i = 0; i < nev; i++) {
		if (fd[i] < 0) {
			printf(" ev%llx=na", (unsigned long long)evcfg[i]);
			continue;
		}
		printf(" ev%llx=%.6f", (unsigned long long)evcfg[i],
		       (double)cnt[i][0] * (cnt[i][2] ? (double)cnt[i][1] / cnt[i][2] : 1.0) / total_hops);
	}
	printf(" sink=%p\n", (void *)p);
	return 0;
}
