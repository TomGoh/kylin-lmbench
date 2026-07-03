// huge_check: verify THP huge-page engagement before trusting a "collapsed gap".
// Maps + touches a region, then prints the huge-page lines from /proc/self/smaps_rollup.
//
// Usage:
//   huge_check anon  <mb> [-]    [touch_mb] [stride_kb]  -> MAP_PRIVATE|ANON + MADV_HUGEPAGE
//   huge_check shmem <mb> <path> [touch_mb] [stride_kb]  -> MAP_SHARED on a tmpfs file
//
// touch_mb/stride_kb mirror munmap_only's touch geometry so the gate covers the EXACT
// region the teardown experiment touches (default: full map, 4 KB stride).
//
// A nonzero AnonHugePages / ShmemPmdMapped means huge pages actually formed; 0 means the
// "huge" variant silently fell back to 4 KB (alignment / fragmentation) and the run is invalid.
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdint.h>
#include <sys/mman.h>

int main(int argc, char **argv)
{
	if (argc < 3) {
		fprintf(stderr, "usage: %s <anon|shmem> <mb> [path]\n", argv[0]);
		return 2;
	}
	const char *mode = argv[1];
	size_t mb = strtoul(argv[2], NULL, 10);
	size_t len = mb << 20;
	double touch_mb = argc > 4 ? strtod(argv[4], NULL) : (double)mb;
	size_t stride = (argc > 5 ? strtoul(argv[5], NULL, 10) : 4) * 1024;
	size_t tb = (size_t)(touch_mb * 1024.0 * 1024.0);
	if (tb > len) tb = len;
	char *p;

	if (!strcmp(mode, "anon")) {
		size_t aln = 2UL << 20;   /* match munmap_only's 2 MB-aligned anon mapping */
		char *raw = mmap(NULL, len + aln, PROT_READ | PROT_WRITE,
				 MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
		if (raw == MAP_FAILED) { perror("mmap"); return 1; }
		uintptr_t a = ((uintptr_t)raw + aln - 1) & ~(aln - 1);
		if (a != (uintptr_t)raw)
			munmap(raw, a - (uintptr_t)raw);
		if ((uintptr_t)raw + len + aln > a + len)
			munmap((char *)(a + len), (uintptr_t)raw + len + aln - (a + len));
		p = (char *)a;
		madvise(p, len, MADV_HUGEPAGE);
	} else {
		const char *path = argc > 3 ? argv[3] : "/dev/shm/huge_check.bin";
		int fd = open(path, O_RDWR | O_CREAT, 0644);
		if (fd < 0) { perror("open"); return 1; }
		if (ftruncate(fd, len)) { perror("ftruncate"); return 1; }
		p = mmap(NULL, len, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
		if (p == MAP_FAILED) { perror("mmap"); return 1; }
	}

	for (size_t i = 0; i < tb; i += stride)   /* fault in / let huge pages form */
		p[i] = 1;

	FILE *f = fopen("/proc/self/smaps_rollup", "r");
	char line[256];
	printf("huge_check %s mb=%zu touch=%.3fMB stride=%zuK :\n",
	       mode, mb, touch_mb, stride / 1024);
	while (f && fgets(line, sizeof line, f)) {
		if (!strncmp(line, "AnonHugePages:", 14) ||
		    !strncmp(line, "ShmemPmdMapped:", 15) ||
		    !strncmp(line, "FilePmdMapped:", 14))
			fputs(line, stdout);
	}
	if (f) fclose(f);
	return 0;
}
