/*
 * thplayout.c - the layout experiment of layout.c without root.
 *
 * layout.c reads frame numbers, which needs CAP_SYS_ADMIN.  Here physical
 * adjacency is obtained by construction: the pool is faulted in as
 * transparent huge pages, so every 2 MiB of it is one physically contiguous
 * block; then every 4 KiB page is moved with mremap() into a fresh virtual
 * range.  Moving single pages splits the 2 MiB mappings into 4 KiB
 * page-table entries while the frames stay where they are.  The order in
 * which the pages are laid out in the new range is the experiment:
 *   sorted   : the order of the pool (ascending physical address inside
 *              every 2 MiB block)
 *   reversed : the reverse of it
 *   shuffled : a random permutation of all pages
 *   aligned  : as sorted, but without the one-page offset described below
 * The new range starts one page after a 2 MiB boundary and is marked
 * MADV_NOHUGEPAGE.  The kernel therefore does not collapse it back into huge
 * pages, and on arm64 kernels with contiguous-PTE support (6.9 and later) it
 * does not fold sixteen consecutive entries into one 64 KiB mapping either,
 * because virtual and physical alignment never coincide: every layout is
 * mapped by plain 4 KiB entries.  "aligned" leaves the offset out, so that
 * such a kernel may fold; it shows what the offset avoids.
 *
 * For each layout the lmbench sequential chase (stride_initialize) is timed
 * as layout.c does: chain written once, 11 intervals of about 120 ms.
 *
 * usage: thplayout <size_mb> <stride> <layout,layout,...> [seed] [events,hex,...]
 *   CHASE_UNROLL=1 in the environment: lmbench's loop body (100 loads in a row)
 * One line per layout:
 *   thp_kb=    AnonHugePages of the pool before it was taken apart (from
 *              /proc/self/smaps).  The layouts mean what they say only if
 *              this equals the size of the working set.
 *   contig_frac=, rcontig_frac=  (root only) fraction of virtually adjacent
 *              pages that are physically adjacent, ascending and descending
 *   l1_ns=, cyc_est=  time per hop of a chase inside the L1 cache (4 cycles
 *              on FTC862) and the result expressed in those cycles
 * Needs transparent_hugepage/enabled = always or madvise.  No root.
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
#define HPAGE (2UL << 20)
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

/* lmbench's benchmark_loads() body: 100 load instructions in a row */
#define ONE	p = (char **)*p;
#define FIVE	ONE ONE ONE ONE ONE
#define TEN	FIVE FIVE
#define FIFTY	TEN TEN TEN TEN TEN
#define HUNDRED	FIFTY FIFTY

static int unroll;	/* CHASE_UNROLL=1 in the environment */

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

static uint64_t pfn_of(int pm, void *va)
{
	uint64_t e = 0;

	if (pm < 0 || pread(pm, &e, 8, ((uint64_t)va / PAGE) * 8) != 8 || !(e >> 63))
		return 0;
	return e & ((1ULL << 55) - 1);
}

/* AnonHugePages (kB) of the mapping that starts at addr */
static long thp_kb(const char *addr)
{
	FILE *f = fopen("/proc/self/smaps", "r");
	char line[256], perms[8];
	unsigned long start, end;
	long kb = -1;
	int in = 0;

	if (!f)
		return -1;
	while (fgets(line, sizeof(line), f)) {
		/* a mapping starts with "start-end perms ..."; the lines after it describe it */
		if (sscanf(line, "%lx-%lx %7s", &start, &end, perms) == 3)
			in = start == (unsigned long)addr;
		else if (in && sscanf(line, "AnonHugePages: %ld kB", &kb) == 1)
			break;
	}
	fclose(f);
	return kb;
}

int main(int argc, char **argv)
{
	size_t len, stride, npages, k, hops, nlay = 0;
	uint64_t evcfg[MAXEV];
	int nev = 0, fd[MAXEV], i, pm;
	char *raw, *pool, *cur = NULL, *curmap = NULL, *tok, *evs, *lays, *layout[16];
	size_t *idx, *pos;
	unsigned seed;
	long thp;
	double l1 = 1e30;

	if (argc < 4) {
		fprintf(stderr, "usage: %s <size_mb> <stride> <layouts> [seed] [events]\n", argv[0]);
		return 2;
	}
	len = (size_t)(atof(argv[1]) * 1024 * 1024);
	stride = strtoul(argv[2], NULL, 0);
	lays = strdup(argv[3]);
	seed = argc > 4 ? strtoul(argv[4], NULL, 0) : (unsigned)getpid();
	evs = strdup(argc > 5 ? argv[5] : "");
	unroll = getenv("CHASE_UNROLL") && atoi(getenv("CHASE_UNROLL"));
	for (tok = strtok(evs, ","); tok && nev < MAXEV; tok = strtok(NULL, ","))
		evcfg[nev++] = strtoull(tok, NULL, 16);
	for (tok = strtok(lays, ","); tok && nlay < 16; tok = strtok(NULL, ","))
		layout[nlay++] = tok;
	len -= len % HPAGE;
	npages = len / PAGE;
	if (!npages || !stride)
		return 2;

	/* the pool: a 2 MiB-aligned range of its own, faulted in as huge pages */
	raw = mmap(NULL, len + HPAGE, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0);
	if (raw == MAP_FAILED) {
		perror("mmap");
		return 1;
	}
	pool = (char *)(((uintptr_t)raw + HPAGE - 1) & ~(HPAGE - 1));
	pool = mmap(pool, len, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, -1, 0);
	if (pool == MAP_FAILED) {
		perror("mmap pool");
		return 1;
	}
	madvise(pool, len, MADV_HUGEPAGE);
	for (k = 0; k < npages; k++)
		pool[k * PAGE] = 1;
	thp = thp_kb(pool);

	pm = open("/proc/self/pagemap", O_RDONLY);
	idx = malloc(npages * sizeof(size_t));	/* idx[k]: where pool page k lives now (page index in cur) */
	pos = malloc(npages * sizeof(size_t));
	for (k = 0; k < npages; k++)
		idx[k] = k;
	for (i = 0; i < nev; i++) {
		fd[i] = perf_open(evcfg[i]);
		if (fd[i] < 0)
			fprintf(stderr, "perf_open(0x%llx): %s\n", (unsigned long long)evcfg[i], strerror(errno));
	}

	/* reference: a chase inside the L1 cache */
	{
		static char l1buf[24576];
		size_t n = sizeof(l1buf) / 256;
		char **q = (char **)l1buf;
		double t0, t1;

		for (k = 0; k < n; k++)
			*(char **)(l1buf + k * 256) = l1buf + ((k + 1) % n) * 256;
		q = chase(q, 1000000);
		for (i = 0; i < 7; i++) {
			t0 = now_ns();
			q = chase(q, 5000000);
			t1 = now_ns();
			if ((t1 - t0) / 5000000 < l1)
				l1 = (t1 - t0) / 5000000;
		}
		if (!q)
			return 1;
	}

	for (size_t l = 0; l < nlay; l++) {
		char *map, *dst, **p;
		uint64_t cnt[MAXEV][3], prev = 0;
		double rep[REPS], t0, t1, total_hops = 0;
		size_t contig = 0, rcontig = 0, have = 0;
		int off = strcmp(layout[l], "aligned") != 0;

		/* position of pool page k in the new range */
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

		map = mmap(NULL, len + 2 * HPAGE, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0);
		if (map == MAP_FAILED) {
			perror("mmap dst");
			return 1;
		}
		dst = (char *)(((uintptr_t)map + HPAGE - 1) & ~(HPAGE - 1)) + (off ? PAGE : 0);
		for (k = 0; k < npages; k++) {
			char *src = (cur ? cur : pool) + idx[k] * PAGE;

			if (mremap(src, PAGE, PAGE, MREMAP_MAYMOVE | MREMAP_FIXED, dst + pos[k] * PAGE) == MAP_FAILED) {
				perror("mremap");
				return 1;
			}
		}
		madvise(dst, len, MADV_NOHUGEPAGE);
		for (k = 0; k < npages; k++)
			idx[k] = pos[k];
		if (curmap)
			munmap(curmap, len + 2 * HPAGE);
		cur = dst;
		curmap = map;

		for (k = 0; k < npages; k++) {
			uint64_t f = pfn_of(pm, dst + k * PAGE);

			if (f)
				have++;
			if (k && f && prev) {
				if (f == prev + 1) contig++;
				if (f + 1 == prev) rcontig++;
			}
			prev = f;
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

		printf("layout=%s size_mb=%.3f stride=%zu pages=%zu thp_kb=%ld chase=%s", layout[l], len / 1048576.0, stride,
		       npages, thp, unroll ? "unrolled" : "loop");
		if (have == npages)
			printf(" contig_frac=%.4f rcontig_frac=%.4f", (double)contig / (npages - 1), (double)rcontig / (npages - 1));
		else
			printf(" contig_frac=na rcontig_frac=na");
		printf(" ns_min=%.3f ns_med=%.3f ns_max=%.3f", rep[0], rep[REPS / 2], rep[REPS - 1]);
		for (i = 0; i < nev; i++) {
			if (fd[i] < 0) {
				printf(" ev%llx=na", (unsigned long long)evcfg[i]);
				continue;
			}
			printf(" ev%llx=%.6f", (unsigned long long)evcfg[i],
			       (double)cnt[i][0] * (cnt[i][2] ? (double)cnt[i][1] / cnt[i][2] : 1.0) / total_hops);
		}
		printf(" l1_ns=%.4f cyc_est=%.3f sink=%p\n", l1, 4.0 * rep[0] / l1, (void *)p);
		fflush(stdout);
	}
	return 0;
}
