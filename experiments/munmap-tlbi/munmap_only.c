// 只给 munmap 计时；可控触摸范围与 stride，用于 TLBI 阈值扫描。
// 用法: munmap_only <file|anon_base|anon_huge> <mb> <iters> [path] [touch_mb] [stride_kb]
//   touch_mb : 只触摸前 touch_mb MB（默认=mb）
//   stride_kb: 触摸步长 KB（默认 4=密集；16=稀疏，同原 benchmark）
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <time.h>
#include <sys/mman.h>

static double now_ns(void)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (double)t.tv_sec * 1e9 + (double)t.tv_nsec;
}

int main(int argc, char **argv)
{
    const char *mode = argc > 1 ? argv[1] : "file";
    size_t mb = argc > 2 ? (size_t)atoi(argv[2]) : 64;
    int iters = argc > 3 ? atoi(argv[3]) : 100;
    const char *path = argc > 4 ? argv[4] : "/tmp/mb.bin";
    double touch_mb = argc > 5 ? atof(argv[5]) : (double)mb;
    size_t stride = (argc > 6 ? (size_t)atoi(argv[6]) : 4) * 1024;
    size_t sz = mb << 20;
    size_t tb = (size_t)(touch_mb * 1024.0 * 1024.0);
    if (tb > sz) tb = sz;
    int is_file = !strcmp(mode, "file");
    int fd = -1;
    double mtot = 0, mmin = 1e18;

    if (is_file) {
        fd = open(path, O_RDWR);
        if (fd < 0) { perror("open"); return 1; }
    }

    for (int it = 0; it < iters; it++) {
        char *p;
        if (is_file) {
            p = mmap(NULL, sz, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
        } else {
            p = mmap(NULL, sz, PROT_READ | PROT_WRITE,
                     MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
            if (p != MAP_FAILED)
                madvise(p, sz, !strcmp(mode, "anon_huge") ? MADV_HUGEPAGE
                                                          : MADV_NOHUGEPAGE);
        }
        if (p == MAP_FAILED) { perror("mmap"); return 1; }
        for (size_t i = 0; i < tb; i += stride)
            ((volatile char *)p)[i] = 1;

        double t0 = now_ns();
        munmap(p, sz);
        double d = now_ns() - t0;
        mtot += d;
        if (d < mmin) mmin = d;
    }
    printf("%-10s mb=%zu touch=%.3fMB stride=%zuK : munmap mean=%.1f us  min=%.1f us\n",
           mode, mb, touch_mb, stride / 1024, mtot / iters / 1e3, mmin / 1e3);
    if (fd >= 0) close(fd);
    return 0;
}
