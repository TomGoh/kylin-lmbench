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
 * usage: frames2 <size_mb> <pool_mb> <events,hex,...> [seed] [pick low|even] [regions file|-] [mode] [order] [mix]
 *   pick even: take every k-th pool page of the slot instead of the lowest ones
 *   mode: rand (default, lmbench -t pattern), seq<stride>, e.g. seq256 (lmbench
 *     sequential pattern with that stride), or tlb<L>, e.g. tlb1: a chase that
 *     moves to another page on every hop and uses only L cache lines of each
 *     page (L = 1..64).  With tlb1 over 4096 pages the data are 4096 lines
 *     (256 KiB, inside the L2 cache) while every hop needs a page walk, so the
 *     time per hop is dominated by address translation; tlb4 over 1024 pages
 *     touches the same number of lines within the reach of the second-level
 *     TLB and serves as the no-walk reference.
 *   order: sorted (default: virtual order = ascending physical address) or
 *     shuffled (the same pages in a random virtual order)
 *   regions file: one hexadecimal 2 MiB region number (PFN >> 9) per line, as
 *     written by vm-frames.py for the memory of a running VM.  With it, every
 *     slot is measured separately for pool pages that share a 2 MiB region
 *     with the VM (class=shared) and for pool pages that do not (class=clear).
 *     Pages given to a protected VM are taken out of the host stage-2 map one
 *     4 KiB page at a time, so the host pages of a shared region are mapped
 *     with 4 KiB stage-2 leaves, the others with 2 MiB or 1 GiB blocks.
 *   mix: <slot A>:<slot B>:<percent>, slot numbers in hexadecimal (PFN >> 18),
 *     e.g. 0x8b:0x88:25.  Instead of one set per slot, measures a single set
 *     with that percentage of its pages taken from slot A and the rest from
 *     slot B (pages of class clear when a regions file is given); the output
 *     line then starts with mix= instead of slot=.
 *   CHASE_UNROLL=1 in the environment: time lmbench's own loop body (100 load
 *     instructions in a row) instead of one load instruction in a loop; the
 *     output line then ends with chase=unrolled.
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

/* lmbench's benchmark_loads() body: 100 load instructions in a row */
#define ONE	p = (char **)*p;
#define FIVE	ONE ONE ONE ONE ONE
#define TEN	FIVE FIVE
#define FIFTY	TEN TEN TEN TEN TEN
#define HUNDRED	FIFTY FIFTY

static int unroll;	/* CHASE_UNROLL=1 in the environment */

/*
 * Default: one load instruction in a loop.  Unrolled: lmbench's form, where
 * the same instruction address sees only every 100th element of the chain.
 */
static char **chase(char **p, size_t hops)
{
	size_t i;

	if (unroll) {
		for (i = 0; i < hops / 100; i++) {
			HUNDRED;
		}
		return p;
	}
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

static size_t seq_stride;	/* 0: random chase; otherwise sequential chase with this stride */
static size_t tlb_lines;	/* > 0: one page per hop, this many cache lines used per page */

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

	if (tlb_lines) {
		/*
		 * Pages in the order of pages[] (a random permutation), tlb_lines
		 * rounds; in round j page k is touched at cache line (37k + 17j) mod 64,
		 * so consecutive hops are on different pages and the lines of the
		 * working set are spread over all cache sets.
		 */
		size_t L = tlb_lines;

		for (j = 0; j < L; j++)
			for (k = 0; k < npages; k++) {
				size_t nj = k + 1 < npages ? j : (j + 1) % L, nk = (k + 1) % npages;
				char *cur = dst + pages[k] + ((37 * k + 17 * j) % 64) * 64;
				char *next = dst + pages[nk] + ((37 * nk + 17 * nj) % 64) * 64;

				*(char **)cur = next;
			}
		p = (char **)(dst + pages[0]);
		hops = npages * L;
		goto timed;
	}
	if (seq_stride) {
		/* lmbench stride_initialize over the whole range */
		size_t len = npages * PAGE;

		for (k = seq_stride; k < len; k += seq_stride)
			*(char **)&dst[k - seq_stride] = &dst[k];
		*(char **)&dst[k - seq_stride] = &dst[0];
		p = (char **)dst;
		hops = len / seq_stride;
		goto timed;
	}
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
timed:
	p = chase(p, hops);		/* warm up */
	/* small working sets: as many whole cycles as fit in about 100 ms */
	t0 = now_ns();
	p = chase(p, hops);
	t1 = now_ns();
	if (t1 - t0 < 100e6)
		hops *= (size_t)(100e6 / (t1 - t0)) + 1;
	if (unroll)
		hops = (hops + 99) / 100 * 100;
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
	printf(" chase=%s sink=%p\n", unroll ? "unrolled" : "loop", (void *)p);
	fflush(stdout);
}

static char *pool;
static int pm, shuffled;
static size_t *vord, *pages, *words;

/*
 * Map the npages selected frames (ascending PFN order) into a fresh range,
 * measure, move them to a second fresh range, measure again.  head is the
 * start of the output line (which pages these are).
 */
static int run_set(const char *head, struct fr *sel, size_t npages, size_t n)
{
	size_t len = npages * PAGE, k, contig = 0, mb2 = 0, vachg = 0;
	uint64_t prev = 0;
	char *dst, *dst2;
	int pass;

	dst = mmap(NULL, len, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0);
	dst2 = mmap(NULL, len, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0);
	if (dst == MAP_FAILED || dst2 == MAP_FAILED) {
		perror("mmap dst");
		return 1;
	}
	for (k = 0; k < npages; k++)
		if (mremap(pool + sel[k].idx * PAGE, PAGE, PAGE, MREMAP_MAYMOVE | MREMAP_FIXED, dst + vord[k] * PAGE) == MAP_FAILED) {
			perror("mremap");
			return 1;
		}
	/* distinct 2 MiB regions of the set (sel[] is in ascending PFN order) */
	for (k = 0; k < npages; k++)
		if (!k || (sel[k].pfn >> 9) != (sel[k - 1].pfn >> 9))
			mb2++;
	/* in virtual order: physically adjacent neighbours (either direction), and changes of 2 MiB region */
	for (k = 0; k < npages; k++) {
		uint64_t f = pfn_of(pm, dst + k * PAGE);

		if (k && (f == prev + 1 || f + 1 == prev)) contig++;
		if (k && (f >> 9) != (prev >> 9)) vachg++;
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
		printf("%s mode=%s stride=%zu order=%s frames_in_class=%zu pass=%d size_mb=%.0f pfn_min=0x%llx pfn_max=0x%llx contig_frac=%.4f mb2_regions=%zu va_region_changes=%zu",
		       head, tlb_lines ? "tlb" : seq_stride ? "seq" : "rand",
		       tlb_lines ? tlb_lines : seq_stride ? seq_stride : STRIDE, shuffled ? "shuffled" : "sorted", n, pass,
		       len / 1048576.0, (unsigned long long)sel[0].pfn, (unsigned long long)sel[npages - 1].pfn,
		       (double)contig / (npages - 1), mb2, vachg);
		measure(d, npages, pages, words);
	}
	munmap(dst, len);
	munmap(dst2, len);
	return 0;
}

int main(int argc, char **argv)
{
	size_t len, pool_len, npages, npool, k, s, e;
	int i, even, mix_pct = -1;
	unsigned long long mix_a = 0, mix_b = 0;
	char *tok, *evs, head[128];
	struct fr *fr, *sel;
	unsigned seed;

	if (argc < 4) {
		fprintf(stderr, "usage: %s <size_mb> <pool_mb> <events> [seed] [pick low|even] [regions file|-] [rand|seq<stride>|tlb<lines>] [sorted|shuffled] [<slot a>:<slot b>:<percent of a>]\n", argv[0]);
		return 2;
	}
	len = (size_t)(atof(argv[1]) * 1024 * 1024);
	pool_len = (size_t)(atof(argv[2]) * 1024 * 1024);
	evs = strdup(argv[3]);
	seed = argc > 4 ? strtoul(argv[4], NULL, 0) : 1;
	even = argc > 5 && !strcmp(argv[5], "even");
	if (argc > 6 && strcmp(argv[6], "-"))
		load_regions(argv[6]);
	if (argc > 7 && !strncmp(argv[7], "seq", 3))
		seq_stride = strtoul(argv[7] + 3, NULL, 0);
	if (argc > 7 && !strncmp(argv[7], "tlb", 3)) {
		tlb_lines = strtoul(argv[7] + 3, NULL, 0);
		if (tlb_lines < 1 || tlb_lines > 64)
			return 2;
	}
	shuffled = argc > 8 && !strcmp(argv[8], "shuffled");
	if (argc > 9 && sscanf(argv[9], "%llx:%llx:%d", &mix_a, &mix_b, &mix_pct) != 3)
		return 2;
	if (argc > 9 && (mix_pct < 0 || mix_pct > 100))
		return 2;
	unroll = getenv("CHASE_UNROLL") && atoi(getenv("CHASE_UNROLL"));
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
	/* vord[k] = virtual page index given to the k-th selected frame (frames are in ascending PFN order) */
	vord = malloc(npages * sizeof(size_t));
	for (k = 0; k < npages; k++)
		vord[k] = k;
	if (shuffled) {
		srand(seed ^ 0x9e3779b9);
		for (k = npages - 1; k > 0; k--) {
			size_t r = ((size_t)rand() << 15 ^ (size_t)rand()) % (k + 1), v = vord[r];

			vord[r] = vord[k];
			vord[k] = v;
		}
	}
	for (i = 0; i < nev; i++)
		fd[i] = perf_open(evcfg[i]);

	printf("# pool_pages=%zu size_pages=%zu pick=%s slots:", npool, npages, even ? "even" : "low");
	for (s = 0; s < npool; s = e) {
		for (e = s + 1; e < npool && (fr[e].pfn >> 18) == (fr[s].pfn >> 18); e++)
			;
		printf(" 0x%llx:%zu", (unsigned long long)(fr[s].pfn >> 18), e - s);
	}
	printf("\n");

	if (mix_pct >= 0) {
		/* one set: want[0] pages of slot A and want[1] pages of slot B, each taken the way the per-slot sets are */
		unsigned long long slot[2] = { mix_a, mix_b };
		size_t want[2], n[2] = { 0, 0 }, *cand[2];
		int t;

		want[0] = (npages * mix_pct + 50) / 100;
		want[1] = npages - want[0];
		for (t = 0; t < 2; t++) {
			cand[t] = malloc(npool * sizeof(size_t));
			for (k = 0; k < npool; k++)
				if ((fr[k].pfn >> 18) == slot[t] && !is_shared(fr[k].pfn))
					cand[t][n[t]++] = k;
			if (n[t] < want[t]) {
				fprintf(stderr, "mix: slot 0x%llx has %zu pool pages, %zu needed\n", slot[t], n[t], want[t]);
				return 1;
			}
		}
		for (k = 0; k < want[0]; k++)
			sel[k] = fr[cand[0][even ? k * n[0] / want[0] : k]];
		for (k = 0; k < want[1]; k++)
			sel[want[0] + k] = fr[cand[1][even ? k * n[1] / want[1] : k]];
		qsort(sel, npages, sizeof(*sel), cmp_fr);
		snprintf(head, sizeof(head), "mix=0x%llx:0x%llx pct_a=%d n_a=%zu n_b=%zu class=%s",
			 mix_a, mix_b, mix_pct, want[0], want[1], nshared ? "clear" : "all");
		return run_set(head, sel, npages, n[0] + n[1]);
	}

	for (s = 0; s < npool; s = e) {
		int cls, ncls = nshared ? 2 : 1;

		for (e = s + 1; e < npool && (fr[e].pfn >> 18) == (fr[s].pfn >> 18); e++)
			;
		/* class 0: all pages of the slot (no regions file) or pages in regions without VM pages; class 1: shared */
		for (cls = 0; cls < ncls; cls++) {
			size_t n = 0;
			size_t *cand = malloc((e - s) * sizeof(size_t));

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

			snprintf(head, sizeof(head), "slot=0x%llx phys=0x%llx class=%s",
				 (unsigned long long)(sel[0].pfn >> 18), (unsigned long long)((sel[0].pfn >> 18) << 30),
				 !nshared ? "all" : cls ? "shared" : "clear");
			if (run_set(head, sel, npages, n))
				return 1;
		}
	}
	return 0;
}
