/*
 * probe.c - reproduce lmbench lat_mem_rd access patterns (stride / thrash)
 * with hardware counters and physical-page introspection.
 *
 * The chain construction follows lmbench 3.0-a9 src/lib_mem.c:
 *   stride_initialize(): addr[i-stride] -> addr[i], ascending first touch
 *   thrash_initialize(): pages taken from a random permutation of ALL pages
 *                        of the maxlen buffer, one hop = next page in that
 *                        order and next word in bit-reversed order
 *
 * usage: probe <seq|rand> <size_mb> <stride> <maxlen_mb> <thp 0|1> <events,hex,...> [seed] [touch none|asc|desc|rand]
 * touch: order in which the used pages are first written BEFORE the chain is built
 *        (controls which physical frame each virtual page gets); none = lmbench behaviour
 * Prints one key=value line.
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

/* Fisher-Yates shuffle of page offsets, as lmbench permutation() */
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

static int cmp_u64(const void *a, const void *b)
{
	uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b;

	return (x > y) - (x < y);
}

int main(int argc, char **argv)
{
	int rnd, thp, nev = 0, fd[MAXEV], i, pm;
	size_t len, stride, maxlen, npages, nmpages, nwords, k, j, hops;
	uint64_t evcfg[MAXEV], cnt[MAXEV][3];
	size_t *pages = NULL, *words = NULL, *used;
	char *raw, *addr, **p, *tok, *evs;
	double t0, t1, rep[REPS], total_hops = 0;
	unsigned seed;
	const char *touch;

	if (argc < 7) {
		fprintf(stderr, "usage: %s <seq|rand> <size_mb> <stride> <maxlen_mb> <thp> <events> [seed]\n", argv[0]);
		return 2;
	}
	rnd = !strcmp(argv[1], "rand");
	len = (size_t)(atof(argv[2]) * 1024 * 1024);
	stride = strtoul(argv[3], NULL, 0);
	maxlen = (size_t)(atof(argv[4]) * 1024 * 1024);
	thp = atoi(argv[5]);
	evs = strdup(argv[6]);
	seed = argc > 7 ? strtoul(argv[7], NULL, 0) : (unsigned)getpid();
	if (!seed)
		seed = (unsigned)getpid();
	touch = argc > 8 ? argv[8] : "none";
	for (tok = strtok(evs, ","); tok && nev < MAXEV; tok = strtok(NULL, ","))
		evcfg[nev++] = strtoull(tok, NULL, 16);

	len -= len % PAGE;
	npages = len / PAGE;
	nmpages = maxlen / PAGE;
	if (!npages || npages > nmpages) {
		fprintf(stderr, "bad size\n");
		return 2;
	}

	raw = mmap(NULL, maxlen + 2 * PAGE, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
	if (raw == MAP_FAILED) {
		perror("mmap");
		return 1;
	}
	madvise(raw, maxlen + 2 * PAGE, thp ? MADV_HUGEPAGE : MADV_NOHUGEPAGE);
	addr = raw;

	if (strcmp(touch, "none")) {
		size_t *ord = malloc(npages * sizeof(size_t));

		for (k = 0; k < npages; k++)
			ord[k] = k;
		if (!strcmp(touch, "desc")) {
			for (k = 0; k < npages; k++)
				ord[k] = npages - 1 - k;
		} else if (!strcmp(touch, "rand")) {
			srand(seed ^ 0x5bd1e995);
			for (k = npages - 1; k > 0; k--) {
				size_t r = ((size_t)rand() << 15 ^ (size_t)rand()) % (k + 1), v = ord[r];

				ord[r] = ord[k];
				ord[k] = v;
			}
		}
		for (k = 0; k < npages; k++)
			addr[ord[k] * PAGE] = 1;
		free(ord);
	}

	used = malloc(npages * sizeof(size_t));
	if (!rnd) {
		/* stride_initialize */
		for (k = stride; k < len; k += stride)
			*(char **)&addr[k - stride] = &addr[k];
		*(char **)&addr[k - stride] = &addr[0];
		p = (char **)addr;
		for (k = 0; k < npages; k++)
			used[k] = k * PAGE;
	} else {
		/* thrash_initialize, page-aligned branch */
		pages = permutation(nmpages, PAGE, seed);
		nwords = PAGE / stride;
		words = words_initialize(nwords, stride);
		if (!pages || !words)
			return 1;
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
		p = (char **)&addr[pages[0]];
		for (k = 0; k < npages; k++)
			used[k] = pages[k];
	}

	/* physical frame introspection (needs CAP_SYS_ADMIN, otherwise PFN reads 0) */
	{
		uint64_t *pfn = calloc(npages, sizeof(uint64_t));
		unsigned color[128] = { 0 };
		size_t have = 0, contig = 0, rcontig = 0, over16_pages = 0, thrash_pages = 0, maxc = 0;
		uint64_t pmin = ~0ULL, pmax = 0;
		size_t gb_regions = 0, mb2_regions = 0;

		pm = open("/proc/self/pagemap", O_RDONLY);
		if (pm >= 0 && pfn) {
			for (k = 0; k < npages; k++) {
				uint64_t e = 0;
				uint64_t va = (uint64_t)(addr + used[k]);

				if (pread(pm, &e, 8, (va / PAGE) * 8) == 8 && (e >> 63)) {
					pfn[k] = e & ((1ULL << 55) - 1);
					if (pfn[k])
						have++;
				}
			}
			close(pm);
		}
		if (have == npages) {
			/* sort a copy to count distinct 1G / 2M frames and contiguity in VA order */
			uint64_t *s = malloc(npages * sizeof(uint64_t));

			for (k = 0; k < npages; k++) {
				color[pfn[k] % 128]++;
				if (pfn[k] < pmin) pmin = pfn[k];
				if (pfn[k] > pmax) pmax = pfn[k];
			}
			if (!rnd)
				for (k = 0; k + 1 < npages; k++) {
					if (pfn[k + 1] == pfn[k] + 1)
						contig++;
					if (pfn[k + 1] + 1 == pfn[k])
						rcontig++;
				}
			for (k = 0; k < 128; k++) {
				if (color[k] > maxc) maxc = color[k];
				if (color[k] > 16) {
					over16_pages += color[k] - 16;
					thrash_pages += color[k];
				}
			}
			memcpy(s, pfn, npages * sizeof(uint64_t));
			qsort(s, npages, sizeof(uint64_t), cmp_u64);
			for (k = 0; k < npages; k++) {
				if (k == 0 || (s[k] >> 18) != (s[k - 1] >> 18)) gb_regions++;
				if (k == 0 || (s[k] >> 9) != (s[k - 1] >> 9)) mb2_regions++;
			}
			free(s);
			printf("pfn=ok pfn_min=0x%llx pfn_max=0x%llx contig_frac=%.4f rcontig_frac=%.4f color_max=%zu over16_pages=%zu thrash_pages_frac=%.4f gb_regions=%zu mb2_regions=%zu ",
			       (unsigned long long)pmin, (unsigned long long)pmax,
			       npages > 1 ? (double)contig / (npages - 1) : 0.0,
			       npages > 1 ? (double)rcontig / (npages - 1) : 0.0, maxc, over16_pages,
			       (double)thrash_pages / npages, gb_regions, mb2_regions);
		} else {
			printf("pfn=na ");
		}
		free(pfn);
	}

	/* warm up: one lap over the pages (rand) or the chain (seq), at least 2M hops */
	hops = rnd ? npages * (PAGE / stride) : len / stride;
	if (hops < 2000000)
		hops = 2000000;
	p = chase(p, hops);

	/* calibrate so that one repetition lasts roughly 120 ms */
	t0 = now_ns();
	p = chase(p, 1000000);
	t1 = now_ns();
	hops = (size_t)(120e6 / ((t1 - t0) / 1e6));
	if (hops < 1000000)
		hops = 1000000;

	for (i = 0; i < nev; i++) {
		fd[i] = perf_open(evcfg[i]);
		if (fd[i] < 0)
			fprintf(stderr, "perf_open(0x%llx): %s\n", (unsigned long long)evcfg[i], strerror(errno));
	}
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

	printf("mode=%s touch=%s size_mb=%.3f stride=%zu pages=%zu thp=%d seed=%u hops=%.0f ns_min=%.3f ns_med=%.3f ns_max=%.3f",
	       rnd ? "rand" : "seq", touch, len / 1048576.0, stride, npages, thp, seed, total_hops,
	       rep[0], rep[REPS / 2], rep[REPS - 1]);
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
	printf(" sink=%p\n", (void *)p);
	return 0;
}
