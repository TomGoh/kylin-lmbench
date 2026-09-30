/*
 * bgload.c - background memory traffic on another core.
 *
 * usage: bgload <r|w> <size_mb> <seconds>
 *   r  read the buffer sequentially, one load per cache line, over and over
 *   w  write one word per cache line, over and over
 * Prints the rate it achieved (MB/s) when it stops.  Pin it with taskset.
 * The buffer uses 4 KiB pages (MADV_NOHUGEPAGE).
 */
#define _GNU_SOURCE
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <time.h>

static double now_s(void)
{
	struct timespec ts;

	clock_gettime(CLOCK_MONOTONIC, &ts);
	return ts.tv_sec + ts.tv_nsec / 1e9;
}

int main(int argc, char **argv)
{
	size_t len, i, passes = 0;
	double secs, t0, t;
	volatile uint64_t *buf;
	uint64_t sum = 0;
	int wr;

	if (argc < 4) {
		fprintf(stderr, "usage: %s <r|w> <size_mb> <seconds>\n", argv[0]);
		return 2;
	}
	wr = argv[1][0] == 'w';
	len = (size_t)atol(argv[2]) << 20;
	secs = atof(argv[3]);
	buf = mmap(NULL, len, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
	if (buf == MAP_FAILED) {
		perror("mmap");
		return 1;
	}
	madvise((void *)buf, len, MADV_NOHUGEPAGE);
	for (i = 0; i < len / 8; i += 512)
		buf[i] = i;

	t0 = now_s();
	do {
		if (wr)
			for (i = 0; i < len / 8; i += 8)
				buf[i] = passes;
		else
			for (i = 0; i < len / 8; i += 8)
				sum += buf[i];
		passes++;
		t = now_s();
	} while (t - t0 < secs);
	printf("bgload mode=%s size_mb=%zu passes=%zu seconds=%.2f mb_per_s=%.0f sum=%llu\n",
	       wr ? "w" : "r", len >> 20, passes, t - t0, passes * (double)(len >> 20) / (t - t0),
	       (unsigned long long)sum);
	return 0;
}
