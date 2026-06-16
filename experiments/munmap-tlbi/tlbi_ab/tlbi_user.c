// SPDX-License-Identifier: GPL-2.0
/* Userspace driver for tlbi_ab user-VA mode: mmap + touch a buffer (so its nG
 * combined entries exist, exactly what munmap tears down), then hand its VA to
 * the module to time IS-vs-NSH invalidation of those user entries.
 * Run under `taskset -c 0` so the module's measurement runs on the bench core.
 *   ./tlbi_user <nslots> [reps] [iters] [dsb_per_slot] [memwork] */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>

int main(int argc, char **argv)
{
	int nslots = argc > 1 ? atoi(argv[1]) : 512;
	int reps   = argc > 2 ? atoi(argv[2]) : 2;
	int iters  = argc > 3 ? atoi(argv[3]) : 50;
	int dps    = argc > 4 ? atoi(argv[4]) : 0;
	int mw     = argc > 5 ? atoi(argv[5]) : 0;
	size_t sz  = (size_t)nslots * 4096;
	char cmd[128], res[640];
	int fd, n, r;

	char *buf = mmap(NULL, sz, PROT_READ | PROT_WRITE,
			 MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
	if (buf == MAP_FAILED) { perror("mmap"); return 1; }
	for (size_t i = 0; i < sz; i += 4096)
		buf[i] = 1;			/* fault in -> PTEs + TLB entries */

	n = snprintf(cmd, sizeof(cmd), "%lu %d %d %d %d %d",
		     (unsigned long)buf, nslots, reps, iters, dps, mw);
	fd = open("/proc/tlbi_ab", O_WRONLY);
	if (fd < 0) { perror("open w"); return 1; }
	if (write(fd, cmd, n) < 0) { perror("write"); return 1; }
	close(fd);

	fd = open("/proc/tlbi_ab", O_RDONLY);
	if (fd < 0) { perror("open r"); return 1; }
	r = read(fd, res, sizeof(res) - 1);
	res[r > 0 ? r : 0] = '\0';
	close(fd);
	printf("%s", res);
	return 0;
}
