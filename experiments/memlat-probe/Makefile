CC ?= gcc
CFLAGS ?= -O2 -Wall

PROGS := probe probe2 layout frames

all: $(PROGS)

%: %.c
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f $(PROGS)

.PHONY: all clean
