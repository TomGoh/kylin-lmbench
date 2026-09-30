/*
 * nothp.c - run a command with transparent huge pages disabled for it and
 * its children, without touching the system-wide setting.
 *
 * usage: nothp <command> [args...]
 *
 * lmbench's lat_mem_rd gets its buffer from malloc().  On a system whose THP
 * setting is "always" that buffer is backed by 2 MiB pages, which removes the
 * page walks the test is meant to include.  The June N90 runs were taken with
 * THP set to "never"; this wrapper gives one process tree the same behaviour.
 */
#include <stdio.h>
#include <sys/prctl.h>
#include <unistd.h>

#ifndef PR_SET_THP_DISABLE
#define PR_SET_THP_DISABLE 41
#endif

int main(int argc, char **argv)
{
	if (argc < 2) {
		fprintf(stderr, "usage: %s <command> [args...]\n", argv[0]);
		return 2;
	}
	if (prctl(PR_SET_THP_DISABLE, 1, 0, 0, 0)) {
		perror("prctl(PR_SET_THP_DISABLE)");
		return 1;
	}
	execvp(argv[1], argv + 1);
	perror(argv[1]);
	return 1;
}
