CC ?= cc
CFLAGS ?= -O2 -Wall -Wextra

BIN := mmap_split_bench

.PHONY: all clean

all: $(BIN)

$(BIN): mmap_split_bench.c
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f $(BIN)
