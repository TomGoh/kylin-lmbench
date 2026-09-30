/*
 * layoutshim.c - give an unmodified program a large malloc() buffer whose
 * physical layout is chosen, so that lmbench's own lat_mem_rd can be timed
 * on physically sorted and on physically shuffled pages.
 *
 * Built as a shared object and loaded with LD_PRELOAD.  It replaces malloc()
 * only for requests of 32 MB or more (lat_mem_rd asks for its whole maximum
 * length at once: 64 MB plus two pages); everything else goes to the C
 * library.  The large buffer is made the way thplayout.c makes its ranges:
 * a pool is faulted in as transparent huge pages, so every 2 MiB of it is one
 * physically contiguous block; then every 4 KiB page is moved with mremap()
 * into the final range, which starts one page after a 2 MiB boundary and is
 * marked MADV_NOHUGEPAGE.  The final range is therefore mapped by plain
 * 4 KiB page-table entries (no huge pages, no contiguous-PTE folding) and
 * the order of its frames is known by construction.
 *
 * Environment:
 *   LAYOUT=sorted     virtual order = order of the pool (ascending physical
 *                     address inside every 2 MiB block); the default
 *   LAYOUT=reversed   the reverse
 *   LAYOUT=shuffled   a random permutation of the pages
 *   SHUFFLE_MB=<n>    with shuffled: permute only within consecutive chunks
 *                     of n MB of the pool, so that the first n MB of the
 *                     buffer use the same frames as with sorted, in another
 *                     order.  Default: the whole buffer is one chunk.
 *   SHIM_SEED=<n>     seed of the permutation (default 1)
 *   SHIM_LOG=<file>   append one line per buffer: process id, layout, how
 *                     much of the pool was backed by huge pages, and (root
 *                     only) the adjacency actually obtained over the first
 *                     1024, 2048, 4096 pages and over all pages
 *
 * The program must NOT run under nothp: the pool needs huge pages
 * (transparent_hugepage/enabled = always, or madvise).  The measured buffer
 * uses 4 KiB pages all the same.
 *
 *   gcc -O2 -Wall -shared -fPIC -o layoutshim.so layoutshim.c
 *   LAYOUT=shuffled SHUFFLE_MB=8 LD_PRELOAD=./layoutshim.so ./lat_mem_rd -P 1 64 256
 */
#define _GNU_SOURCE
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

#define PAGE 4096UL
#define HPAGE (2UL << 20)
#define BIG (32UL << 20)

extern void *__libc_malloc(size_t);
extern void __libc_free(void *);

static char *region;
static size_t region_len;

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
		if (sscanf(line, "%lx-%lx %7s", &start, &end, perms) == 3)
			in = start == (unsigned long)addr;
		else if (in && sscanf(line, "AnonHugePages: %ld kB", &kb) == 1)
			break;
	}
	fclose(f);
	return kb;
}

static uint64_t pfn_of(int pm, const void *va)
{
	uint64_t e = 0;

	if (pm < 0 || pread(pm, &e, 8, ((uint64_t)va / PAGE) * 8) != 8 || !(e >> 63))
		return 0;
	return e & ((1ULL << 55) - 1);
}

static void log_layout(const char *path, const char *layout, size_t chunk, long thp, size_t npages)
{
	static const size_t cut[] = { 1024, 2048, 4096, 0 };
	FILE *f = fopen(path, "a");
	int pm = open("/proc/self/pagemap", O_RDONLY);
	size_t i, k;

	if (!f)
		return;
	fprintf(f, "pid=%d layout=%s shuffle_pages=%zu pages=%zu thp_kb=%ld", (int)getpid(), layout, chunk, npages, thp);
	for (i = 0; i < sizeof(cut) / sizeof(cut[0]); i++) {
		size_t n = cut[i] && cut[i] < npages ? cut[i] : npages, asc = 0, desc = 0, have = 0;
		uint64_t prev = 0;

		for (k = 0; k < n; k++) {
			uint64_t fr = pfn_of(pm, region + k * PAGE);

			if (fr)
				have++;
			if (k && fr && prev) {
				if (fr == prev + 1) asc++;
				if (fr + 1 == prev) desc++;
			}
			prev = fr;
		}
		if (have == n)
			fprintf(f, " adj%zu=%.4f/%.4f", n, (double)asc / (n - 1), (double)desc / (n - 1));
		else
			fprintf(f, " adj%zu=na", n);
	}
	fprintf(f, "\n");
	fclose(f);
	if (pm >= 0)
		close(pm);
}

static void *build(size_t want)
{
	const char *layout = getenv("LAYOUT") ? getenv("LAYOUT") : "sorted";
	size_t len = (want + HPAGE - 1) & ~(HPAGE - 1), npages = len / PAGE, k, chunk;
	unsigned seed = getenv("SHIM_SEED") ? strtoul(getenv("SHIM_SEED"), NULL, 0) : 1;
	char *raw, *pool, *map, *dst;
	size_t *src;	/* src[k]: pool page that goes to position k */
	long thp;

	raw = mmap(NULL, len + HPAGE, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0);
	if (raw == MAP_FAILED)
		return NULL;
	pool = (char *)(((uintptr_t)raw + HPAGE - 1) & ~(HPAGE - 1));
	pool = mmap(pool, len, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, -1, 0);
	if (pool == MAP_FAILED)
		return NULL;
	madvise(pool, len, MADV_HUGEPAGE);
	for (k = 0; k < npages; k++)
		pool[k * PAGE] = 1;
	thp = thp_kb(pool);

	src = __libc_malloc(npages * sizeof(size_t));
	for (k = 0; k < npages; k++)
		src[k] = k;
	chunk = npages;
	if (!strcmp(layout, "reversed")) {
		for (k = 0; k < npages; k++)
			src[k] = npages - 1 - k;
	} else if (!strcmp(layout, "shuffled")) {
		size_t c;

		if (getenv("SHUFFLE_MB") && atof(getenv("SHUFFLE_MB")) > 0)
			chunk = (size_t)(atof(getenv("SHUFFLE_MB")) * 1048576) / PAGE;
		if (chunk > npages)
			chunk = npages;
		srand(seed);
		for (c = 0; c < npages; c += chunk) {
			size_t n = npages - c < chunk ? npages - c : chunk;

			for (k = n - 1; k > 0; k--) {
				size_t r = (((size_t)rand() << 15) ^ (size_t)rand()) % (k + 1), v = src[c + r];

				src[c + r] = src[c + k];
				src[c + k] = v;
			}
		}
	}

	map = mmap(NULL, len + 2 * HPAGE, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0);
	if (map == MAP_FAILED)
		return NULL;
	dst = (char *)(((uintptr_t)map + HPAGE - 1) & ~(HPAGE - 1)) + PAGE;
	for (k = 0; k < npages; k++)
		if (mremap(pool + src[k] * PAGE, PAGE, PAGE, MREMAP_MAYMOVE | MREMAP_FIXED, dst + k * PAGE) == MAP_FAILED)
			return NULL;
	madvise(dst, len, MADV_NOHUGEPAGE);
	__libc_free(src);

	region = dst;
	region_len = len;
	if (getenv("SHIM_LOG"))
		log_layout(getenv("SHIM_LOG"), layout, chunk, thp, npages);
	return dst;
}

void *malloc(size_t n)
{
	void *p;

	if (n < BIG || region)
		return __libc_malloc(n);
	p = build(n);
	return p ? p : __libc_malloc(n);
}

void free(void *p)
{
	/* the large buffer is released when the process exits */
	if (region && (char *)p >= region && (char *)p < region + region_len)
		return;
	__libc_free(p);
}
