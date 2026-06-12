// 测 MAP_SHARED 文件映射在 host stage-1 的页大小（读 /proc/self/smaps）。
// 与 mmap_split_bench 的 munmap_after_write_touch 同样的 open(O_RDWR)+MAP_SHARED+写触摸。
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>

int main(int argc, char **argv)
{
    const char *path = argc > 1 ? argv[1] : "/tmp/s1test.bin";
    size_t mb = argc > 2 ? (size_t)atoi(argv[2]) : 64;
    size_t sz = mb << 20;

    int fd = open(path, O_RDWR);
    if (fd < 0) { perror("open"); return 1; }
    char *p = mmap(NULL, sz, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (p == MAP_FAILED) { perror("mmap"); return 1; }

    /* 写触摸每 4K，一如 benchmark */
    for (size_t i = 0; i < sz; i += 4096)
        ((volatile char *)p)[i] = 1;

    unsigned long start = (unsigned long)p;
    printf("== mmap MAP_SHARED %zuMB %s @ %lx ==\n", mb, path, start);

    FILE *f = fopen("/proc/self/smaps", "r");
    char line[512];
    int in = 0;
    while (fgets(line, sizeof line, f)) {
        unsigned long a, b;
        if (sscanf(line, "%lx-%lx", &a, &b) == 2) {
            in = (a == start);
            if (in) fputs(line, stdout);
            continue;
        }
        if (in && (strstr(line, "KernelPageSize") || strstr(line, "MMUPageSize") ||
                   strstr(line, "FilePmdMapped") || strstr(line, "AnonHugePages") ||
                   strstr(line, "ShmemPmdMapped") || strstr(line, "THPeligible") ||
                   strstr(line, "Rss:")))
            fputs(line, stdout);
    }
    fclose(f);
    munmap(p, sz);
    return 0;
}
