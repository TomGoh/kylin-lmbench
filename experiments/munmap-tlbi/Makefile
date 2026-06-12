CC ?= cc
CFLAGS ?= -O2 -Wall -Wextra

BINS := munmap_only munmap_bench s1pagesize

.PHONY: all clean

all: $(BINS)

munmap_only: munmap_only.c
	$(CC) $(CFLAGS) -o $@ $<

munmap_bench: munmap_bench.c
	$(CC) $(CFLAGS) -o $@ $<

s1pagesize: s1pagesize.c
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f $(BINS)
