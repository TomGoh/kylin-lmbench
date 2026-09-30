/*
 * probe3.c - lat_mem_rd access patterns with lmbench's rewrite-before-every-
 * interval behaviour, and a reading of the interconnect (NoC) frequency around
 * every timed interval.
 *
 * lmbench's lat_mem_rd rebuilds the pointer chain before every timed interval
 * (benchmp_interval() calls the initialize routine each time), so every
 * interval is preceded by a burst of writes to all lines of the working set.
 * probe.c and probe2.c build the chain once and then only read.  The
 * difference matters when a frequency governor reacts to bus traffic.
 *
 * usage: probe3 <seq|rand> <size_mb> <stride> <maxlen_mb> <events,hex,...> <rebuild 0|1> [seed]
 *   CHASE_UNROLL=1 in the environment: time lmbench's own loop body (100 load
 *   instructions in a row) instead of one load instruction in a loop.
 *
 * The buffer always uses 4 KiB pages (MADV_NOHUGEPAGE).  Prints one key=value
 * line.  Fields beyond those of probe.c:
 *   chase=    loop or unrolled (see CHASE_UNROLL)
 *   rebuild=  1: the chain is rewritten before every interval, as lmbench does
 *   reps=     the 11 interval times in the order they were taken (ns per hop)
 *   noc0=     /sys/class/devfreq/nocfreq/cur_freq before the first interval
 *   noc=      the same, read right after each interval (na if no such device)
 * PMU counts cover the timed intervals only.
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
#define NOC "/sys/class/devfreq/nocfreq/cur_freq"

static double now_ns(void)
{
	struct timespec ts;

	clock_gettime(CLOCK_MONOTONIC, &ts);
	return ts.tv_sec * 1e9 + ts.tv_nsec;
}

static long noc_freq(void)
{
	char b[32];
	int fd = open(NOC, O_RDONLY);
	ssize_t n;

	if (fd < 0)
		return -1;
	n = read(fd, b, sizeof(b) - 1);
	close(fd);
	if (n <= 0)
		return -1;
	b[n] = 0;
	return atol(b);
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

/* shuffle of page offsets, same as probe.c */
static size_t *permutation(size_t max, size_t scale, unsigned seed)
{
	size_t i, v, r;
	size_t *res = malloc(max * sizeof(size_t));

	if (!res)
		return NULL;
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

/* bit-reversal order of word offsets inside a page, as lmbench words_initialize() */
static size_t *words_initialize(size_t max, size_t scale)
{
	size_t i, j, nbits;
	size_t *words = calloc(max, sizeof(size_t));

	if (!words)
		return NULL;
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

static int cmp_u64(const void *a, const void *b)
{
	uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b;

	return (x > y) - (x < y);
}

static int rnd;
static char *addr;
static size_t len, stride, npages, nwords;
static size_t *pages, *words;

/* write every pointer of the chain; returns the chain head */
static char **build_chain(void)
{
	size_t k, j;

	if (!rnd) {
		/* stride_initialize */
		for (k = stride; k < len; k += stride)
			*(char **)&addr[k - stride] = &addr[k];
		*(char **)&addr[k - stride] = &addr[0];
		return (char **)addr;
	}
	/* thrash_initialize, page-aligned branch */
	for (k = 0; k < npages - 1; k++) {
		size_t cpage = pages[k], npage = pages[k + 1];

		for (j = 0; j < nwords; j++) {
			size_t cur = cpage + words[(k + j) % nwords];
			size_t next = npage + words[(k + j + 1) % nwords];

			*(char **)&addr[cur] = &addr[next];
		}
	}
	{
		size_t cpage = pages[k], npage = pages[0];

		for (j = 0; j < nwords; j++) {
			size_t cur = cpage + words[(k + j) % nwords];
			size_t next = npage + words[(j + 1) % nwords];

			*(char **)&addr[cur] = &addr[next];
		}
	}
	return (char **)&addr[pages[0]];
}

int main(int argc, char **argv)
{
	int rebuild, nev = 0, fd[MAXEV], i, pm;
	size_t maxlen, nmpages, k, hops, cycle;
	uint64_t evcfg[MAXEV], cnt[MAXEV][3];
	char *raw, **p, *tok, *evs;
	double t0, t1, rep[REPS], sorted[REPS], total_hops = 0;
	long noc[REPS], noc0;
	unsigned seed;

	if (argc < 7) {
		fprintf(stderr, "usage: %s <seq|rand> <size_mb> <stride> <maxlen_mb> <events> <rebuild 0|1> [seed]\n", argv[0]);
		return 2;
	}
	rnd = !strcmp(argv[1], "rand");
	len = (size_t)(atof(argv[2]) * 1024 * 1024);
	stride = strtoul(argv[3], NULL, 0);
	maxlen = (size_t)(atof(argv[4]) * 1024 * 1024);
	evs = strdup(argv[5]);
	rebuild = atoi(argv[6]);
	seed = argc > 7 ? strtoul(argv[7], NULL, 0) : 0;
	if (!seed)
		seed = (unsigned)getpid();
	unroll = getenv("CHASE_UNROLL") && atoi(getenv("CHASE_UNROLL"));
	for (tok = strtok(evs, ","); tok && nev < MAXEV; tok = strtok(NULL, ","))
		evcfg[nev++] = strtoull(tok, NULL, 16);

	len -= len % PAGE;
	npages = len / PAGE;
	nmpages = maxlen / PAGE;
	if (!npages || npages > nmpages || !stride) {
		fprintf(stderr, "bad size\n");
		return 2;
	}

	raw = mmap(NULL, maxlen + 2 * PAGE, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
	if (raw == MAP_FAILED) {
		perror("mmap");
		return 1;
	}
	madvise(raw, maxlen + 2 * PAGE, MADV_NOHUGEPAGE);
	addr = raw;

	if (rnd) {
		pages = permutation(nmpages, PAGE, seed);
		nwords = PAGE / stride;
		words = words_initialize(nwords, stride);
		if (!pages || !words)
			return 1;
	}
	p = build_chain();
	cycle = len / stride;

	/* physical frame introspection (needs CAP_SYS_ADMIN, otherwise PFN reads 0) */
	{
		uint64_t *pfn = calloc(npages, sizeof(uint64_t));
		size_t have = 0, contig = 0, rcontig = 0, gb_regions = 0, mb2_regions = 0;

		pm = open("/proc/self/pagemap", O_RDONLY);
		if (pm >= 0 && pfn) {
			for (k = 0; k < npages; k++) {
				uint64_t e = 0;
				uint64_t va = (uint64_t)(addr + (rnd ? pages[k] : k * PAGE));

				if (pread(pm, &e, 8, (va / PAGE) * 8) == 8 && (e >> 63)) {
					pfn[k] = e & ((1ULL << 55) - 1);
					if (pfn[k])
						have++;
				}
			}
			close(pm);
		}
		if (have == npages) {
			if (!rnd)
				for (k = 0; k + 1 < npages; k++) {
					if (pfn[k + 1] == pfn[k] + 1)
						contig++;
					if (pfn[k + 1] + 1 == pfn[k])
						rcontig++;
				}
			qsort(pfn, npages, sizeof(uint64_t), cmp_u64);
			for (k = 0; k < npages; k++) {
				if (k == 0 || (pfn[k] >> 18) != (pfn[k - 1] >> 18)) gb_regions++;
				if (k == 0 || (pfn[k] >> 9) != (pfn[k - 1] >> 9)) mb2_regions++;
			}
			printf("pfn=ok contig_frac=%.4f rcontig_frac=%.4f gb_regions=%zu mb2_regions=%zu ",
			       npages > 1 ? (double)contig / (npages - 1) : 0.0,
			       npages > 1 ? (double)rcontig / (npages - 1) : 0.0, gb_regions, mb2_regions);
		} else {
			printf("pfn=na ");
		}
		free(pfn);
	}

	/* warm up: one lap, at least 2M hops */
	hops = cycle < 2000000 ? 2000000 : cycle;
	p = chase(p, hops);

	/*
	 * One interval lasts about 110 ms, as in lmbench, and is a whole number
	 * of laps; for large random working sets one lap is longer than that and
	 * the interval is one lap (64 MB: about 0.7 s).
	 */
	t0 = now_ns();
	p = chase(p, 1000000);
	t1 = now_ns();
	hops = (size_t)(110e6 / ((t1 - t0) / 1e6));
	hops = (hops / cycle + 1) * cycle;
	if (unroll)
		hops = (hops + 99) / 100 * 100;

	for (i = 0; i < nev; i++) {
		fd[i] = perf_open(evcfg[i]);
		if (fd[i] < 0)
			fprintf(stderr, "perf_open(0x%llx): %s\n", (unsigned long long)evcfg[i], strerror(errno));
	}
	for (i = 0; i < nev; i++)
		if (fd[i] >= 0)
			ioctl(fd[i], PERF_EVENT_IOC_RESET, 0);
	noc0 = noc_freq();
	for (i = 0; i < REPS; i++) {
		int j;

		if (rebuild)
			p = build_chain();
		for (j = 0; j < nev; j++)
			if (fd[j] >= 0)
				ioctl(fd[j], PERF_EVENT_IOC_ENABLE, 0);
		t0 = now_ns();
		p = chase(p, hops);
		t1 = now_ns();
		for (j = 0; j < nev; j++)
			if (fd[j] >= 0)
				ioctl(fd[j], PERF_EVENT_IOC_DISABLE, 0);
		rep[i] = (t1 - t0) / hops;
		noc[i] = noc_freq();
		total_hops += hops;
	}
	for (i = 0; i < nev; i++)
		if (fd[i] >= 0 && read(fd[i], cnt[i], sizeof(cnt[i])) != sizeof(cnt[i]))
			cnt[i][0] = cnt[i][1] = cnt[i][2] = 0;
	memcpy(sorted, rep, sizeof(rep));
	qsort(sorted, REPS, sizeof(double), cmp_d);

	printf("mode=%s chase=%s rebuild=%d size_mb=%.3f stride=%zu pages=%zu seed=%u hops=%.0f ns_min=%.3f ns_med=%.3f ns_max=%.3f",
	       rnd ? "rand" : "seq", unroll ? "unrolled" : "loop", rebuild, len / 1048576.0, stride, npages, seed, total_hops,
	       sorted[0], sorted[REPS / 2], sorted[REPS - 1]);
	for (i = 0; i < nev; i++) {
		if (fd[i] < 0) {
			printf(" ev%llx=na", (unsigned long long)evcfg[i]);
			continue;
		}
		printf(" ev%llx=%.6f", (unsigned long long)evcfg[i],
		       (double)cnt[i][0] * (cnt[i][2] ? (double)cnt[i][1] / cnt[i][2] : 1.0) / total_hops);
		if (cnt[i][1] != cnt[i][2])
			printf("(mux%.2f)", cnt[i][1] ? (double)cnt[i][2] / cnt[i][1] : 0.0);
	}
	printf(" reps=");
	for (i = 0; i < REPS; i++)
		printf("%s%.3f", i ? "," : "", rep[i]);
	if (noc0 < 0) {
		printf(" noc0=na noc=na");
	} else {
		printf(" noc0=%ld noc=", noc0);
		for (i = 0; i < REPS; i++)
			printf("%s%ld", i ? "," : "", noc[i]);
	}
	printf(" sink=%p\n", (void *)p);
	return 0;
}
