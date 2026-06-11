/*
 * mmap_split_bench.c - split lmbench lat_mmap into smaller timed phases.
 *
 * Usage:
 *   mmap_split_bench <mode> <size_mb> <iters> <file> [touch_divisor] [stride_kb] [warmups]
 *
 * Default touch geometry matches lmbench lat_mmap:
 *   touch_bytes = size / 10
 *   stride      = 16 KB
 */

#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#ifndef MAP_POPULATE
#define MAP_POPULATE 0
#endif

static volatile uint64_t sink;

struct cfg {
    const char *mode;
    const char *path;
    double size_mb_arg;
    size_t size;
    int iters;
    int touch_divisor;
    int warmups;
    size_t stride;
    size_t touch_bytes;
    size_t touches;
};

static void die(const char *what)
{
    perror(what);
    exit(1);
}

static double now_ns(void)
{
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0)
        die("clock_gettime");
    return (double)ts.tv_sec * 1e9 + (double)ts.tv_nsec;
}

static uint64_t parse_u64(const char *s, const char *name)
{
    char *end = NULL;
    errno = 0;
    unsigned long long v = strtoull(s, &end, 0);
    if (errno || !end || *end != '\0') {
        fprintf(stderr, "invalid %s: %s\n", name, s);
        exit(2);
    }
    return (uint64_t)v;
}

static int open_checked(const char *path, size_t size)
{
    int fd = open(path, O_RDWR);
    if (fd < 0)
        die("open");

    struct stat st;
    if (fstat(fd, &st) != 0)
        die("fstat");
    if ((size_t)st.st_size < size) {
        fprintf(stderr, "backing file too small: %s has %zu bytes, need %zu\n",
                path, (size_t)st.st_size, size);
        exit(1);
    }
    return fd;
}

static char *map_checked(int fd, const struct cfg *c, int populate)
{
    int flags = MAP_SHARED;
    if (populate)
        flags |= MAP_POPULATE;
    char *p = mmap(NULL, c->size, PROT_READ | PROT_WRITE, flags, fd, 0);
    if (p == MAP_FAILED)
        die("mmap");
    return p;
}

static void unmap_checked(char *p, size_t size)
{
    if (munmap(p, size) != 0)
        die("munmap");
}

static void write_touch(char *p, const struct cfg *c)
{
    char v = (char)(c->size & 0xff);
    char *end = p + c->touch_bytes;
    for (char *q = p; q < end; q += c->stride)
        *q = v;
}

static void read_touch(char *p, const struct cfg *c)
{
    uint64_t local = sink;
    char *end = p + c->touch_bytes;
    for (char *q = p; q < end; q += c->stride)
        local += (unsigned char)*q;
    sink = local;
}

static void emit(const struct cfg *c, const char *timed, double total_ns)
{
    double per_iter_ns = total_ns / (double)c->iters;
    double touches_total = (double)c->touches * (double)c->iters;
    int touch_is_timed =
        strncmp(timed, "read_touch_", 11) == 0 ||
        strncmp(timed, "write_touch_", 12) == 0 ||
        strcmp(timed, "mmap_write_touch_unmap") == 0 ||
        strcmp(timed, "mmap_read_touch_unmap") == 0;
    double per_touch_ns = touch_is_timed && touches_total > 0 ? total_ns / touches_total : 0.0;

    printf("mode,size_mb,iters,warmups,timed,touch_divisor,stride_kb,touch_bytes,touches_per_iter,total_ns,per_iter_ns,per_iter_us,per_touch_ns,sink\n");
    printf("%s,%.9g,%d,%d,%s,%d,%.9g,%zu,%zu,%.0f,%.3f,%.6f,%.3f,%" PRIu64 "\n",
           c->mode,
           c->size_mb_arg,
           c->iters,
           c->warmups,
           timed,
           c->touch_divisor,
           (double)c->stride / 1024.0,
           c->touch_bytes,
           c->touches,
           total_ns,
           per_iter_ns,
           per_iter_ns / 1000.0,
           per_touch_ns,
           (uint64_t)sink);
}

static double bench_openclose(const struct cfg *c)
{
    double t0 = now_ns();
    for (int i = 0; i < c->iters; ++i) {
        int fd = open_checked(c->path, c->size);
        if (close(fd) != 0)
            die("close");
    }
    return now_ns() - t0;
}

static double bench_mmap_unmap(const struct cfg *c, int populate)
{
    int fd = open_checked(c->path, c->size);
    double t0 = now_ns();
    for (int i = 0; i < c->iters; ++i) {
        char *p = map_checked(fd, c, populate);
        unmap_checked(p, c->size);
    }
    double t1 = now_ns();
    close(fd);
    return t1 - t0;
}

static double bench_mmap_touch_unmap(const struct cfg *c, int do_write)
{
    int fd = open_checked(c->path, c->size);
    double t0 = now_ns();
    for (int i = 0; i < c->iters; ++i) {
        char *p = map_checked(fd, c, 0);
        if (do_write)
            write_touch(p, c);
        else
            read_touch(p, c);
        unmap_checked(p, c->size);
    }
    double t1 = now_ns();
    close(fd);
    return t1 - t0;
}

static double bench_touch_cold(const struct cfg *c, int do_write)
{
    int fd = open_checked(c->path, c->size);
    double total = 0.0;
    for (int i = 0; i < c->iters; ++i) {
        char *p = map_checked(fd, c, 0);
        double t0 = now_ns();
        if (do_write)
            write_touch(p, c);
        else
            read_touch(p, c);
        total += now_ns() - t0;
        unmap_checked(p, c->size);
    }
    close(fd);
    return total;
}

static double bench_touch_hot(const struct cfg *c, int do_write)
{
    int fd = open_checked(c->path, c->size);
    char *p = map_checked(fd, c, 0);

    /* Establish stage-1/page-cache state before measuring hot touches. */
    write_touch(p, c);

    double t0 = now_ns();
    for (int i = 0; i < c->iters; ++i) {
        if (do_write)
            write_touch(p, c);
        else
            read_touch(p, c);
    }
    double t1 = now_ns();

    unmap_checked(p, c->size);
    close(fd);
    return t1 - t0;
}

static double bench_munmap_only(const struct cfg *c, int touch_kind)
{
    int fd = open_checked(c->path, c->size);
    double total = 0.0;
    for (int i = 0; i < c->iters; ++i) {
        char *p = map_checked(fd, c, 0);
        if (touch_kind == 1)
            write_touch(p, c);
        else if (touch_kind == 2)
            read_touch(p, c);

        double t0 = now_ns();
        unmap_checked(p, c->size);
        total += now_ns() - t0;
    }
    close(fd);
    return total;
}

static void warmup_once(const struct cfg *c)
{
    int fd;
    char *p;

    if (strcmp(c->mode, "openclose") == 0) {
        fd = open_checked(c->path, c->size);
        if (close(fd) != 0)
            die("close");
        return;
    }

    fd = open_checked(c->path, c->size);

    if (strcmp(c->mode, "mmap_unmap") == 0) {
        p = map_checked(fd, c, 0);
        unmap_checked(p, c->size);
    } else if (strcmp(c->mode, "mmap_populate_unmap") == 0) {
        p = map_checked(fd, c, 1);
        unmap_checked(p, c->size);
    } else if (strcmp(c->mode, "mmap_write_touch_unmap") == 0 ||
               strcmp(c->mode, "write_touch_cold") == 0) {
        p = map_checked(fd, c, 0);
        write_touch(p, c);
        unmap_checked(p, c->size);
    } else if (strcmp(c->mode, "mmap_read_touch_unmap") == 0 ||
               strcmp(c->mode, "read_touch_cold") == 0) {
        p = map_checked(fd, c, 0);
        read_touch(p, c);
        unmap_checked(p, c->size);
    } else if (strcmp(c->mode, "write_touch_hot") == 0) {
        p = map_checked(fd, c, 0);
        write_touch(p, c);
        write_touch(p, c);
        unmap_checked(p, c->size);
    } else if (strcmp(c->mode, "read_touch_hot") == 0) {
        p = map_checked(fd, c, 0);
        write_touch(p, c);
        read_touch(p, c);
        unmap_checked(p, c->size);
    } else if (strcmp(c->mode, "munmap_after_no_touch") == 0) {
        p = map_checked(fd, c, 0);
        unmap_checked(p, c->size);
    } else if (strcmp(c->mode, "munmap_after_write_touch") == 0) {
        p = map_checked(fd, c, 0);
        write_touch(p, c);
        unmap_checked(p, c->size);
    } else if (strcmp(c->mode, "munmap_after_read_touch") == 0) {
        p = map_checked(fd, c, 0);
        read_touch(p, c);
        unmap_checked(p, c->size);
    }

    close(fd);
}

static void usage(const char *prog)
{
    fprintf(stderr,
            "Usage: %s <mode> <size_mb> <iters> <file> [touch_divisor] [stride_kb] [warmups]\n"
            "Modes:\n"
            "  openclose\n"
            "  mmap_unmap\n"
            "  mmap_populate_unmap\n"
            "  mmap_write_touch_unmap\n"
            "  mmap_read_touch_unmap\n"
            "  write_touch_cold\n"
            "  read_touch_cold\n"
            "  write_touch_hot\n"
            "  read_touch_hot\n"
            "  munmap_after_no_touch\n"
            "  munmap_after_write_touch\n"
            "  munmap_after_read_touch\n",
            prog);
}

int main(int argc, char **argv)
{
    if (argc < 5) {
        usage(argv[0]);
        return 2;
    }

    struct cfg c;
    memset(&c, 0, sizeof(c));
    c.mode = argv[1];
    c.size_mb_arg = atof(argv[2]);
    c.size = (size_t)(c.size_mb_arg * 1024.0 * 1024.0);
    c.iters = (int)parse_u64(argv[3], "iters");
    c.path = argv[4];
    c.touch_divisor = argc > 5 ? (int)parse_u64(argv[5], "touch_divisor") : 10;
    c.stride = (argc > 6 ? (size_t)parse_u64(argv[6], "stride_kb") : 16) * 1024;
    c.warmups = argc > 7 ? (int)parse_u64(argv[7], "warmups") : 1;

    if (c.size == 0 || c.iters <= 0 || c.touch_divisor <= 0 || c.stride == 0 || c.warmups < 0) {
        usage(argv[0]);
        return 2;
    }
    c.touch_bytes = c.size / (size_t)c.touch_divisor;
    if (c.touch_bytes == 0)
        c.touch_bytes = c.size;
    c.touches = (c.touch_bytes + c.stride - 1) / c.stride;

    double total_ns;
    const char *timed = c.mode;

    for (int i = 0; i < c.warmups; ++i)
        warmup_once(&c);

    if (strcmp(c.mode, "openclose") == 0)
        total_ns = bench_openclose(&c);
    else if (strcmp(c.mode, "mmap_unmap") == 0)
        total_ns = bench_mmap_unmap(&c, 0);
    else if (strcmp(c.mode, "mmap_populate_unmap") == 0)
        total_ns = bench_mmap_unmap(&c, 1);
    else if (strcmp(c.mode, "mmap_write_touch_unmap") == 0)
        total_ns = bench_mmap_touch_unmap(&c, 1);
    else if (strcmp(c.mode, "mmap_read_touch_unmap") == 0)
        total_ns = bench_mmap_touch_unmap(&c, 0);
    else if (strcmp(c.mode, "write_touch_cold") == 0)
        total_ns = bench_touch_cold(&c, 1);
    else if (strcmp(c.mode, "read_touch_cold") == 0)
        total_ns = bench_touch_cold(&c, 0);
    else if (strcmp(c.mode, "write_touch_hot") == 0)
        total_ns = bench_touch_hot(&c, 1);
    else if (strcmp(c.mode, "read_touch_hot") == 0)
        total_ns = bench_touch_hot(&c, 0);
    else if (strcmp(c.mode, "munmap_after_no_touch") == 0)
        total_ns = bench_munmap_only(&c, 0);
    else if (strcmp(c.mode, "munmap_after_write_touch") == 0)
        total_ns = bench_munmap_only(&c, 1);
    else if (strcmp(c.mode, "munmap_after_read_touch") == 0)
        total_ns = bench_munmap_only(&c, 2);
    else {
        usage(argv[0]);
        return 2;
    }

    emit(&c, timed, total_ns);
    return 0;
}
