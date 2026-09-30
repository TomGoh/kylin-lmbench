/*
 * layout.c - same physical frames, different virtual order.
 *
 * Takes a pool of 4 KiB anonymous pages, reads their PFNs, picks the most
 * physically contiguous subset, and uses mremap() to lay those SAME frames out
 * in a new virtual range in a chosen order:
 *   sorted   : virtual order == ascending physical order
 *   reversed : virtual order == descending physical order
 *   shuffled : random order
 * For each layout it runs the lmbench sequential pointer chase
 * (stride_initialize) and reports ns/access plus PMU rates.
 *
 * Only the virtual->physical ordering changes between layouts: the frame set,
 * hence page colours and DRAM location, is identical.
 *
 * usage: layout <size_mb> <stride> <pool_mb> <events,hex,...> <layout,layout,...> [seed]
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
	size_t idx;	/* page index inside the pool */
};

static int cmp_fr(const void *a, const void *b)
{
	const struct fr *x = a, *y = b;

	return (x->pfn > y->pfn) - (x->pfn < y->pfn);
}

struct run {
	size_t start, len;	/* into the PFN-sorted frame array */
};

static int cmp_run(const void *a, const void *b)
{
	const struct run *x = a, *y = b;

	return (x->len < y->len) - (x->len > y->len);	/* longest first */
}

static uint64_t pfn_of(int pm, void *va)
{
	uint64_t e = 0;

	if (pread(pm, &e, 8, ((uint64_t)va / PAGE) * 8) != 8 || !(e >> 63))
		return 0;
	return e & ((1ULL << 55) - 1);
}

int main(int argc, char **argv)
{
	size_t len, stride, pool_len, npages, npool, k, nruns = 0, got = 0, hops, nlay = 0;
	uint64_t evcfg[MAXEV];
	int nev = 0, fd[MAXEV], i, pm;
	char *pool, *cur = NULL, *tok, *evs, *lays, *layout[16];
	struct fr *fr, *sel;
	struct run *runs;
	size_t *pos;
	unsigned seed;

	if (argc < 6) {
		fprintf(stderr, "usage: %s <size_mb> <stride> <pool_mb> <events> <layouts> [seed]\n", argv[0]);
		return 2;
	}
	len = (size_t)(atof(argv[1]) * 1024 * 1024);
	stride = strtoul(argv[2], NULL, 0);
	pool_len = (size_t)(atof(argv[3]) * 1024 * 1024);
	evs = strdup(argv[4]);
	lays = strdup(argv[5]);
	seed = argc > 6 ? strtoul(argv[6], NULL, 0) : (unsigned)getpid();
	for (tok = strtok(evs, ","); tok && nev < MAXEV; tok = strtok(NULL, ","))
		evcfg[nev++] = strtoull(tok, NULL, 16);
	for (tok = strtok(lays, ","); tok && nlay < 16; tok = strtok(NULL, ","))
		layout[nlay++] = tok;

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

	/* runs of consecutive PFNs, longest first, until npages frames are chosen */
	runs = malloc(npool * sizeof(*runs));
	for (k = 0; k < npool;) {
		size_t j = k + 1;

		while (j < npool && fr[j].pfn == fr[j - 1].pfn + 1)
			j++;
		runs[nruns].start = k;
		runs[nruns].len = j - k;
		nruns++;
		k = j;
	}
	qsort(runs, nruns, sizeof(*runs), cmp_run);
	sel = malloc(npages * sizeof(*sel));
	for (k = 0; k < nruns && got < npages; k++) {
		size_t take = runs[k].len, j;

		if (take > npages - got)
			take = npages - got;
		for (j = 0; j < take; j++)
			sel[got++] = fr[runs[k].start + j];
	}
	qsort(sel, npages, sizeof(*sel), cmp_fr);	/* ascending physical order */
	printf("# pool_pages=%zu runs_in_pool=%zu longest_run=%zu selected=%zu pfn_min=0x%llx pfn_max=0x%llx\n",
	       npool, nruns, runs[0].len, npages,
	       (unsigned long long)sel[0].pfn, (unsigned long long)sel[npages - 1].pfn);

	pos = malloc(npages * sizeof(size_t));
	for (i = 0; i < nev; i++) {
		fd[i] = perf_open(evcfg[i]);
		if (fd[i] < 0)
			fprintf(stderr, "perf_open(0x%llx): %s\n", (unsigned long long)evcfg[i], strerror(errno));
	}

	for (size_t l = 0; l < nlay; l++) {
		char *dst, **p;
		uint64_t cnt[MAXEV][3], prev;
		double rep[REPS], t0, t1, total_hops = 0;
		size_t contig = 0, rcontig = 0;
		unsigned color[128] = { 0 }, maxc = 0;
		size_t thrash_pages = 0;

		/* position of the i-th frame (ascending PFN) in the new virtual range */
		for (k = 0; k < npages; k++)
			pos[k] = k;
		if (!strcmp(layout[l], "reversed")) {
			for (k = 0; k < npages; k++)
				pos[k] = npages - 1 - k;
		} else if (!strcmp(layout[l], "shuffled")) {
			srand(seed + 7919 * (unsigned)l);
			for (k = npages - 1; k > 0; k--) {
				size_t r = (((size_t)rand() << 15) ^ (size_t)rand()) % (k + 1), v = pos[r];

				pos[r] = pos[k];
				pos[k] = v;
			}
		}

		dst = mmap(NULL, len, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0);
		if (dst == MAP_FAILED) {
			perror("mmap dst");
			return 1;
		}
		for (k = 0; k < npages; k++) {
			/* where does frame k currently live? first round: in the pool; later: previous dst */
			char *src = cur ? cur + sel[k].idx * PAGE : pool + sel[k].idx * PAGE;

			if (mremap(src, PAGE, PAGE, MREMAP_MAYMOVE | MREMAP_FIXED, dst + pos[k] * PAGE) == MAP_FAILED) {
				perror("mremap");
				return 1;
			}
		}
		/* from now on, frame k lives at index pos[k] of dst */
		for (k = 0; k < npages; k++)
			sel[k].idx = pos[k];
		if (cur)
			munmap(cur, len);
		cur = dst;

		/* verify layout from pagemap */
		prev = 0;
		for (k = 0; k < npages; k++) {
			uint64_t f = pfn_of(pm, dst + k * PAGE);

			color[f % 128]++;
			if (k) {
				if (f == prev + 1) contig++;
				if (f + 1 == prev) rcontig++;
			}
			prev = f;
		}
		for (k = 0; k < 128; k++) {
			if (color[k] > maxc) maxc = color[k];
			if (color[k] > 16) thrash_pages += color[k];
		}

		/* lmbench stride_initialize */
		for (k = stride; k < len; k += stride)
			*(char **)&dst[k - stride] = &dst[k];
		*(char **)&dst[k - stride] = &dst[0];
		p = (char **)dst;

		hops = len / stride;
		if (hops < 2000000)
			hops = 2000000;
		p = chase(p, hops);
		t0 = now_ns();
		p = chase(p, 1000000);
		t1 = now_ns();
		hops = (size_t)(120e6 / ((t1 - t0) / 1e6));
		if (hops < 1000000)
			hops = 1000000;

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

		printf("layout=%s size_mb=%.3f stride=%zu pages=%zu contig_frac=%.4f rcontig_frac=%.4f color_max=%u thrash_pages_frac=%.4f ns_min=%.3f ns_med=%.3f ns_max=%.3f",
		       layout[l], len / 1048576.0, stride, npages,
		       (double)contig / (npages - 1), (double)rcontig / (npages - 1), maxc,
		       (double)thrash_pages / npages, rep[0], rep[REPS / 2], rep[REPS - 1]);
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
	return 0;
}
