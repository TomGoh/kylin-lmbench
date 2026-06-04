/*
 * lat_mmap_precise.c —— ns 精度版本的 lat_mmap，语义和 lmbench/src/lat_mmap.c 一致
 *
 * 与 lmbench 的差别 = 仅在时钟与输出精度上：
 *   - 时钟：clock_gettime(CLOCK_MONOTONIC) 而非 gettimeofday()
 *   - 输出：纳秒，不做 lmbench micromb() 的 %.0f 整数 round
 *
 * 与 lmbench/src/lat_mmap.c 完全一致的语义：
 *   - file-backed MAP_SHARED（不是 anonymous private）
 *   - PSIZE = 16 KB，N = 10
 *   - 顺序触摸 size/N 字节，stride = PSIZE
 *   - 每次 iter 都 mmap + 触摸 + munmap
 *
 * 用法:
 *   lat_mmap_precise <size_mb> <iterations> <backing_file>
 *
 * backing_file 必须 >= size_mb*1024*1024 字节。
 * 程序自己负责创建/扩容/最终保留（不删除，可复用）。
 *
 * 输出（一行）：
 *   size_mb=<X> iters=<N> total_ns=<总纳秒> per_iter_ns=<X.XXX> per_iter_us=<X.XXXXXX>
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <time.h>
#include <string.h>
#include <errno.h>

#define PSIZE  (16 << 10)   /* 16 KB —— 与 lmbench/src/lat_mmap.c 一致 */
#define N      10           /* 触摸前 1/N 的字节 —— 与 lmbench 一致 */

int main(int argc, char *argv[]) {
    if (argc < 4) {
        fprintf(stderr, "Usage: %s <size_mb> <iterations> <backing_file>\n", argv[0]);
        return 1;
    }

    double size_mb_arg = atof(argv[1]);
    size_t size = (size_t)(size_mb_arg * 1024.0 * 1024.0);
    int iters = atoi(argv[2]);
    const char *fname = argv[3];

    if (size < PSIZE * 2 || iters < 1) {
        fprintf(stderr, "invalid size or iters\n");
        return 1;
    }

    /* 打开/创建 backing file。**要求 caller 先用 lmdd 把 file 写满**
     * （和 lmbench scripts/lmbench 一致：of=$FILE move=${MB}m fsync=1）。
     * 如果 file 不存在或太小直接退出 —— 自己用 write() pre-fill 出来的 file
     * 处于一种和 lmdd 不同的 page-cache 状态，会让测量比真值大 ~4×（实测）。
     */
    int fd = open(fname, O_RDWR);
    if (fd < 0) { perror("open backing file"); return 1; }
    struct stat st;
    if (fstat(fd, &st) < 0) { perror("fstat"); return 1; }
    if ((size_t)st.st_size < size) {
        fprintf(stderr,
            "ERROR: backing file %s size=%zu < required %zu bytes.\n"
            "       请先用 lmdd 写满该文件，例如：\n"
            "         lmdd of=%s move=%zum fsync=1 print=3\n",
            fname, (size_t)st.st_size, size, fname, size / (1u<<20) + 1);
        return 1;
    }

    /* 预热：mmap + 触摸前 size/N 字节（warm page cache + VMA / TLB） */
    char *warm = mmap(NULL, size, PROT_READ|PROT_WRITE, MAP_FILE|MAP_SHARED, fd, 0);
    if (warm == MAP_FAILED) { perror("warmup mmap"); return 1; }
    char wc = (char)(size & 0xff);
    char *wend = warm + (size / N);
    for (char *q = warm; q < wend; q += PSIZE) *q = wc;
    munmap(warm, size);

    struct timespec t0, t1;
    clock_gettime(CLOCK_MONOTONIC, &t0);

    for (int i = 0; i < iters; i++) {
        char *p = mmap(NULL, size, PROT_READ|PROT_WRITE, MAP_FILE|MAP_SHARED, fd, 0);
        if (p == MAP_FAILED) {
            perror("mmap");
            return 1;
        }
        /* 触摸前 size/N 字节，stride = PSIZE，逐字节写一个字符 —— 与 lmbench 完全一致 */
        char c = (char)(size & 0xff);
        char *end = p + (size / N);
        for (char *q = p; q < end; q += PSIZE) {
            *q = c;
        }
        munmap(p, size);
    }

    clock_gettime(CLOCK_MONOTONIC, &t1);
    close(fd);

    double total_ns = (double)(t1.tv_sec - t0.tv_sec) * 1e9
                    + (double)(t1.tv_nsec - t0.tv_nsec);
    double per_iter_ns = total_ns / iters;

    printf("size_mb=%g iters=%d total_ns=%.0f per_iter_ns=%.3f per_iter_us=%.6f\n",
           size_mb_arg, iters, total_ns, per_iter_ns, per_iter_ns / 1000.0);

    return 0;
}
