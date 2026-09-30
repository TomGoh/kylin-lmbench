/*
 * nocsample.c - log the interconnect (NoC) frequency at a fixed interval
 * without forking: one line "<seconds.millis> <cur_freq>" per sample.
 *
 * usage: nocsample <interval_ms> <output file>      (runs until killed)
 */
#define _GNU_SOURCE
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>

int main(int argc, char **argv)
{
	struct timespec ts, nap;
	char b[32];
	long ms;
	FILE *out;

	if (argc < 3) {
		fprintf(stderr, "usage: %s <interval_ms> <output file>\n", argv[0]);
		return 2;
	}
	ms = atol(argv[1]);
	out = fopen(argv[2], "a");
	if (!out || ms <= 0)
		return 1;
	nap.tv_sec = ms / 1000;
	nap.tv_nsec = (ms % 1000) * 1000000L;
	for (;;) {
		int fd = open("/sys/class/devfreq/nocfreq/cur_freq", O_RDONLY);
		ssize_t n = fd < 0 ? -1 : read(fd, b, sizeof(b) - 1);

		if (fd >= 0)
			close(fd);
		clock_gettime(CLOCK_REALTIME, &ts);
		fprintf(out, "%ld.%03ld %ld\n", (long)ts.tv_sec, ts.tv_nsec / 1000000L, n > 0 ? (b[n] = 0, atol(b)) : -1L);
		fflush(out);
		nanosleep(&nap, NULL);
	}
}
