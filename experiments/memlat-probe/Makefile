CC ?= gcc
CFLAGS ?= -O2 -Wall

PROGS := probe probe2 probe3 layout thplayout frames frames2 bgload nocsample nothp

all: $(PROGS)

%: %.c
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f $(PROGS) lat_mem_rd bw_mem

.PHONY: all clean
