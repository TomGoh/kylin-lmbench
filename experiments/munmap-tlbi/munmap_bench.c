// munmap_after_write_touch 微基准，可切换 backing 以验证"walk 数是否是成本驱动":
//   file       : MAP_SHARED ext4 文件（4K 页，同 mmap_split_bench）
//   anon_base  : 匿名 + MADV_NOHUGEPAGE（4K 页）
//   anon_huge  : 匿名 + MADV_HUGEPAGE（2M 大页 → 1/512 的 PTE 数）
// 用法: munmap_bench <file|anon_base|anon_huge> <mb> <iters> [path]
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <time.h>
#include <sys/mman.h>

static double now(void)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + t.tv_nsec / 1e9;
}

int main(int argc, char **argv)
{
    const char *mode = argc > 1 ? argv[1] : "file";
    size_t mb = argc > 2 ? (size_t)atoi(argv[2]) : 64;
    int iters = argc > 3 ? atoi(argv[3]) : 100;
    const char *path = argc > 4 ? argv[4] : "/tmp/mb.bin";
    size_t sz = mb << 20;
    int is_file = !strcmp(mode, "file");
    int fd = -1;

    if (is_file) {
        fd = open(path, O_RDWR);
        if (fd < 0) { perror("open"); return 1; }
    }

    double t0 = now();
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
        for (size_t i = 0; i < sz; i += 4096)
            ((volatile char *)p)[i] = 1;
        munmap(p, sz);
    }
    double t1 = now();
    printf("%-10s %zuMB x%d : %.3f s total, %.1f us/iter\n",
           mode, mb, iters, t1 - t0, (t1 - t0) / iters * 1e6);
    if (fd >= 0) close(fd);
    return 0;
}
