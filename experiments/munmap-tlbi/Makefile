CC ?= cc
CFLAGS ?= -O2 -Wall -Wextra
ANDROID_API ?= 35
ANDROID_NDK_HOME ?= $(HOME)/android/android-ndk-r27c
ANDROID_CC ?= $(ANDROID_NDK_HOME)/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android$(ANDROID_API)-clang

BINS := munmap_only munmap_bench s1pagesize op_sweep pixel_madv_entry_slope

.PHONY: all clean android

all: $(BINS)

android: pixel_madv_entry_slope.android

munmap_only: munmap_only.c
	$(CC) $(CFLAGS) -o $@ $<

op_sweep: op_sweep.c
	$(CC) $(CFLAGS) -o $@ $<

pixel_madv_entry_slope: pixel_madv_entry_slope.c
	$(CC) $(CFLAGS) -o $@ $<

pixel_madv_entry_slope.android: pixel_madv_entry_slope.c
	$(ANDROID_CC) $(CFLAGS) -o $@ $<

munmap_bench: munmap_bench.c
	$(CC) $(CFLAGS) -o $@ $<

s1pagesize: s1pagesize.c
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f $(BINS) pixel_madv_entry_slope.android
