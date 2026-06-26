// pixel_madv_entry_slope.c — Pixel pKVM/nVHE userspace per-entry teardown probe.
//
// The timed operation is either:
//   single  : N calls to madvise(base + i * page_size, page_size, MADV_DONTNEED)
//   batched : one call to madvise(base, N * page_size, MADV_DONTNEED)
//
// Setup (mmap + optional write touch) is outside the timed window. Each CSV row is
// one timed run for one N. Run protected/nvhe boot pairs and fit elapsed_ns vs pages.
#define _GNU_SOURCE
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <sched.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <time.h>
#include <unistd.h>

enum run_mode {
    MODE_SINGLE,
    MODE_BATCHED,
};

enum touch_mode {
    TOUCH_TOUCHED,
    TOUCH_UNTOUCHED,
};

struct options {
    enum run_mode mode;
    enum touch_mode touch;
    size_t *pages;
    size_t pages_len;
    int runs;
    unsigned int seed;
    int shuffle;
    int no_hugepage;
    int cpu;
};

static void usage(const char *argv0)
{
    fprintf(stderr,
        "usage: %s --mode <single|batched> --touch <touched|untouched> [options]\n"
        "\n"
        "options:\n"
        "  --pages LIST       comma-separated page counts (default 256,512,1024,2048,4096,8192)\n"
        "  --runs N           timed runs per page count (default 30)\n"
        "  --seed N           RNG seed for N-order shuffle (default current time)\n"
        "  --cpu N            pin this process to CPU N before running\n"
        "  --no-shuffle       keep page-count order as provided\n"
        "  --allow-hugepage   do not call MADV_NOHUGEPAGE on mappings\n"
        "  -h, --help         show this help\n",
        argv0);
}

static uint64_t now_ns(void)
{
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) {
        perror("clock_gettime");
        exit(1);
    }
    return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}

static long minor_faults(void)
{
    struct rusage ru;
    if (getrusage(RUSAGE_SELF, &ru) != 0) {
        perror("getrusage");
        exit(1);
    }
    return ru.ru_minflt;
}

static int parse_positive_int(const char *s, int *out)
{
    char *end = NULL;
    long v;

    errno = 0;
    v = strtol(s, &end, 10);
    if (errno || end == s || *end != '\0' || v <= 0 || v > 2147483647L)
        return -1;
    *out = (int)v;
    return 0;
}

static int parse_nonnegative_int(const char *s, int *out)
{
    char *end = NULL;
    long v;

    errno = 0;
    v = strtol(s, &end, 10);
    if (errno || end == s || *end != '\0' || v < 0 || v > 2147483647L)
        return -1;
    *out = (int)v;
    return 0;
}

static int parse_uint(const char *s, unsigned int *out)
{
    char *end = NULL;
    unsigned long v;

    errno = 0;
    v = strtoul(s, &end, 10);
    if (errno || end == s || *end != '\0' || v > 0xfffffffful)
        return -1;
    *out = (unsigned int)v;
    return 0;
}

static int parse_pages_list(const char *s, size_t **pages_out, size_t *len_out)
{
    char *copy, *tok, *save = NULL;
    size_t cap = 8, len = 0;
    size_t *pages;

    copy = strdup(s);
    if (!copy)
        return -1;
    pages = calloc(cap, sizeof(*pages));
    if (!pages) {
        free(copy);
        return -1;
    }

    for (tok = strtok_r(copy, ",", &save); tok; tok = strtok_r(NULL, ",", &save)) {
        char *end = NULL;
        unsigned long long v;

        errno = 0;
        v = strtoull(tok, &end, 10);
        if (errno || end == tok || *end != '\0' || v == 0) {
            free(copy);
            free(pages);
            return -1;
        }
        if (len == cap) {
            size_t new_cap = cap * 2;
            size_t *new_pages = realloc(pages, new_cap * sizeof(*pages));
            if (!new_pages) {
                free(copy);
                free(pages);
                return -1;
            }
            pages = new_pages;
            cap = new_cap;
        }
        pages[len++] = (size_t)v;
    }

    free(copy);
    if (len == 0) {
        free(pages);
        return -1;
    }
    *pages_out = pages;
    *len_out = len;
    return 0;
}

static void shuffle_pages(size_t *pages, size_t len)
{
    if (len < 2)
        return;
    for (size_t i = len - 1; i > 0; i--) {
        size_t j = (size_t)(rand() % (int)(i + 1));
        size_t tmp = pages[i];
        pages[i] = pages[j];
        pages[j] = tmp;
    }
}

static void set_default_options(struct options *opt)
{
    memset(opt, 0, sizeof(*opt));
    opt->mode = MODE_SINGLE;
    opt->touch = TOUCH_TOUCHED;
    opt->runs = 30;
    opt->seed = (unsigned int)time(NULL);
    opt->shuffle = 1;
    opt->no_hugepage = 1;
    opt->cpu = -1;
    if (parse_pages_list("256,512,1024,2048,4096,8192", &opt->pages, &opt->pages_len) != 0) {
        fprintf(stderr, "failed to allocate default page list\n");
        exit(1);
    }
}

static int parse_args(int argc, char **argv, struct options *opt)
{
    set_default_options(opt);

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-h") || !strcmp(argv[i], "--help")) {
            usage(argv[0]);
            exit(0);
        } else if (!strcmp(argv[i], "--mode")) {
            if (++i >= argc)
                return -1;
            if (!strcmp(argv[i], "single"))
                opt->mode = MODE_SINGLE;
            else if (!strcmp(argv[i], "batched"))
                opt->mode = MODE_BATCHED;
            else
                return -1;
        } else if (!strcmp(argv[i], "--touch")) {
            if (++i >= argc)
                return -1;
            if (!strcmp(argv[i], "touched"))
                opt->touch = TOUCH_TOUCHED;
            else if (!strcmp(argv[i], "untouched"))
                opt->touch = TOUCH_UNTOUCHED;
            else
                return -1;
        } else if (!strcmp(argv[i], "--pages")) {
            size_t *pages = NULL;
            size_t len = 0;
            if (++i >= argc)
                return -1;
            if (parse_pages_list(argv[i], &pages, &len) != 0)
                return -1;
            free(opt->pages);
            opt->pages = pages;
            opt->pages_len = len;
        } else if (!strcmp(argv[i], "--runs")) {
            if (++i >= argc || parse_positive_int(argv[i], &opt->runs) != 0)
                return -1;
        } else if (!strcmp(argv[i], "--seed")) {
            if (++i >= argc || parse_uint(argv[i], &opt->seed) != 0)
                return -1;
        } else if (!strcmp(argv[i], "--cpu")) {
            if (++i >= argc || parse_nonnegative_int(argv[i], &opt->cpu) != 0)
                return -1;
        } else if (!strcmp(argv[i], "--no-shuffle")) {
            opt->shuffle = 0;
        } else if (!strcmp(argv[i], "--allow-hugepage")) {
            opt->no_hugepage = 0;
        } else {
            return -1;
        }
    }

    return 0;
}

static void pin_cpu_or_die(int cpu)
{
    cpu_set_t set;

    if (cpu < 0)
        return;
    CPU_ZERO(&set);
    CPU_SET(cpu, &set);
    if (sched_setaffinity(0, sizeof(set), &set) != 0) {
        perror("sched_setaffinity");
        exit(1);
    }
}

static const char *mode_name(enum run_mode mode)
{
    return mode == MODE_SINGLE ? "single" : "batched";
}

static const char *touch_name(enum touch_mode touch)
{
    return touch == TOUCH_TOUCHED ? "touched" : "untouched";
}

static void touch_pages(char *p, size_t pages, size_t page_size)
{
    volatile char *vp = (volatile char *)p;

    for (size_t i = 0; i < pages; i++)
        vp[i * page_size] = 1;
}

static uint64_t run_once(const struct options *opt, size_t pages, size_t page_size,
                         uint64_t *setup_elapsed, long *setup_minflt_delta,
                         long *timed_minflt_delta, int *cpu_before,
                         int *cpu_after, const char **status)
{
    size_t len = pages * page_size;
    char *p;
    uint64_t setup_t0, setup_t1, t0, t1;
    long setup_f0, setup_f1, f0, f1;
    int rc = 0;

    *status = "ok";
    setup_f0 = minor_faults();
    setup_t0 = now_ns();
    p = mmap(NULL, len, PROT_READ | PROT_WRITE,
             MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (p == MAP_FAILED) {
        perror("mmap");
        exit(1);
    }
    if (opt->no_hugepage)
        (void)madvise(p, len, MADV_NOHUGEPAGE);

    if (opt->touch == TOUCH_TOUCHED)
        touch_pages(p, pages, page_size);
    setup_t1 = now_ns();
    setup_f1 = minor_faults();
    *setup_elapsed = setup_t1 - setup_t0;
    *setup_minflt_delta = setup_f1 - setup_f0;

    f0 = minor_faults();
    *cpu_before = sched_getcpu();
    t0 = now_ns();
    if (opt->mode == MODE_SINGLE) {
        for (size_t i = 0; i < pages; i++) {
            rc = madvise(p + i * page_size, page_size, MADV_DONTNEED);
            if (rc != 0)
                break;
        }
    } else {
        rc = madvise(p, len, MADV_DONTNEED);
    }
    t1 = now_ns();
    *cpu_after = sched_getcpu();
    f1 = minor_faults();

    if (rc != 0)
        *status = "madvise_error";
    *timed_minflt_delta = f1 - f0;

    if (munmap(p, len) != 0) {
        perror("munmap");
        exit(1);
    }
    return t1 - t0;
}

int main(int argc, char **argv)
{
    struct options opt;
    long page_size_l = sysconf(_SC_PAGESIZE);
    size_t page_size;

    if (parse_args(argc, argv, &opt) != 0) {
        usage(argv[0]);
        return 2;
    }
    pin_cpu_or_die(opt.cpu);
    if (page_size_l <= 0) {
        fprintf(stderr, "sysconf(_SC_PAGESIZE) failed\n");
        return 1;
    }
    page_size = (size_t)page_size_l;
    srand(opt.seed);
    if (opt.shuffle)
        shuffle_pages(opt.pages, opt.pages_len);

    printf("schema_version,mode,touch,page_size,pages,run_index,op_count,setup_elapsed_ns,setup_minor_faults_delta,elapsed_ns,timed_minor_faults_delta,cpu_before,cpu_after,status\n");
    for (size_t pi = 0; pi < opt.pages_len; pi++) {
        size_t pages = opt.pages[pi];
        size_t op_count = opt.mode == MODE_SINGLE ? pages : 1;

        if (pages > ((size_t)-1) / page_size) {
            fprintf(stderr, "page count too large: %zu\n", pages);
            free(opt.pages);
            return 1;
        }
        for (int run = 0; run < opt.runs; run++) {
            uint64_t setup_elapsed = 0;
            long setup_minflt_delta = 0;
            long timed_minflt_delta = 0;
            int cpu_before = -1;
            int cpu_after = -1;
            const char *status = NULL;
            uint64_t elapsed = run_once(&opt, pages, page_size, &setup_elapsed,
                                        &setup_minflt_delta, &timed_minflt_delta,
                                        &cpu_before, &cpu_after, &status);

            printf("1,%s,%s,%zu,%zu,%d,%zu,%" PRIu64 ",%ld,%" PRIu64 ",%ld,%d,%d,%s\n",
                   mode_name(opt.mode), touch_name(opt.touch), page_size,
                   pages, run, op_count, setup_elapsed, setup_minflt_delta,
                   elapsed, timed_minflt_delta, cpu_before, cpu_after, status);
        }
    }

    free(opt.pages);
    return 0;
}
