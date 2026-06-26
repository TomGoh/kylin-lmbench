// op_sweep.c — generalize the munmap TLBI-threshold sweep to OTHER teardown ops.
//
// Hypothesis under test: the pKVM sub-2MB per-page TLBI penalty is NOT specific to
// munmap. munmap, madvise(MADV_DONTNEED) and mprotect all funnel through arm64's
// __flush_tlb_range() and the SAME MAX_DVM_OPS=512 (2MB) gate (tlbflush.h:422-424).
// If so, dontneed/mprotect should show the same protected-vs-nvhe gap: ∝ range below
// 2MB, collapsing to ~0 at/above 2MB.
//
// Method mirrors munmap_only.c: re-map each iteration, dense-touch the first N MB so
// the op's flush range ≈ N MB, time ONLY the op, report mean + min (mean is the honest
// metric — see the core-scaling follow-up §9 on the `min` trap).
//
// Usage: op_sweep <op> <mode> <mb> <iters> [path] [touch_mb] [stride_kb]
//   op       : munmap | dontneed | mprotect
//   mode     : file | anon
//   mb       : mapping size in MB
//   iters    : timed iterations
//   path     : backing file for mode=file (default /tmp/mb.bin)
//   touch_mb : touch (and apply the op to) the first touch_mb MB (default = mb)
//   stride_kb: touch stride in KB (4 = dense, sharp threshold; 16 = sparse, lat_mmap-like)
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <time.h>
#include <sys/mman.h>

enum op { OP_MUNMAP, OP_DONTNEED, OP_MPROTECT };

static double now_ns(void)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (double)t.tv_sec * 1e9 + (double)t.tv_nsec;
}

static enum op parse_op(const char *s)
{
    if (!strcmp(s, "munmap"))   return OP_MUNMAP;
    if (!strcmp(s, "dontneed")) return OP_DONTNEED;
    if (!strcmp(s, "mprotect")) return OP_MPROTECT;
    fprintf(stderr, "unknown op '%s' (want munmap|dontneed|mprotect)\n", s);
    exit(2);
}

// ─────────────────────────────────────────────────────────────────────────────
// do_op(): perform the ONE teardown operation that is being timed, on the first
// `op_len` bytes of the mapping `p` (full mapping is `full_sz` bytes).
//
// This is the heart of the experiment: each op must actually issue the per-page
// TLBI sequence we are studying, otherwise the sweep measures nothing.
//
//   - OP_MUNMAP   : worked example below (matches munmap_only.c — unmaps the whole
//                   mapping; the untouched tail has no PTEs so the flush range ≈ op_len).
//   - OP_DONTNEED : YOU implement. madvise(...MADV_DONTNEED) zaps the PTEs in the range
//                   → zap_page_range → mmu_gather → __flush_tlb_range (same gate).
//   - OP_MPROTECT : YOU implement. The DIRECTION matters for correctness:
//                     * RW→RO is more restrictive → a stale permissive entry is unsafe
//                       → the kernel MUST flush (pte_needs_flush() true) → TLBIs fire.
//                     * RO→RW is more permissive → the kernel may skip the flush
//                       (a stale restrictive entry just refaults) → NO TLBIs → the
//                       experiment would measure ~nothing. Pick the direction that
//                       guarantees a flush.
//
// Return 0 on success, -1 on failure (caller will perror+exit). For OP_MUNMAP the
// mapping is consumed here; for the others the caller munmaps the rest untimed.
// ─────────────────────────────────────────────────────────────────────────────
static int do_op(enum op op, char *p, size_t op_len, size_t full_sz)
{
    switch (op) {
    case OP_MUNMAP:
        return munmap(p, full_sz);   // worked example: flush range ≈ touched extent

    case OP_DONTNEED:
        // MADV_DONTNEED zaps the PTEs now → __flush_tlb_range fires this instant
        // (MADV_FREE would be lazy → no immediate flush → null result).
        return madvise(p, op_len, MADV_DONTNEED);

    case OP_MPROTECT:
        // RW→RO is more restrictive → stale permissive entry is unsafe → kernel MUST
        // flush (RO→RW could be skipped → null result).
        return mprotect(p, op_len, PROT_READ);
    }
    return -1;
}

int main(int argc, char **argv)
{
    if (argc < 5) {
        fprintf(stderr,
            "usage: %s <munmap|dontneed|mprotect> <file|anon> <mb> <iters> "
            "[path] [touch_mb] [stride_kb]\n", argv[0]);
        return 2;
    }
    enum op op   = parse_op(argv[1]);
    const char *mode = argv[2];
    size_t mb    = (size_t)atoi(argv[3]);
    int iters    = atoi(argv[4]);
    const char *path = argc > 5 ? argv[5] : "/tmp/mb.bin";
    double touch_mb  = argc > 6 ? atof(argv[6]) : (double)mb;
    size_t stride    = (argc > 7 ? (size_t)atoi(argv[7]) : 4) * 1024;

    size_t pagesz = (size_t)sysconf(_SC_PAGESIZE);
    size_t sz = mb << 20;
    size_t tb = (size_t)(touch_mb * 1024.0 * 1024.0);
    if (tb > sz) tb = sz;
    size_t op_len = (tb / pagesz) * pagesz;          // page-align the op range
    if (op_len == 0) op_len = pagesz;

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
                madvise(p, sz, MADV_NOHUGEPAGE);
        }
        if (p == MAP_FAILED) { perror("mmap"); return 1; }

        for (size_t i = 0; i < tb; i += stride)      // dense/sparse write touch
            ((volatile char *)p)[i] = 1;

        double t0 = now_ns();
        int rc = do_op(op, p, op_len, sz);           // ← the only timed operation
        double d = now_ns() - t0;
        if (rc != 0) { perror("do_op"); return 1; }

        if (op != OP_MUNMAP)                          // untimed cleanup for next iter
            munmap(p, sz);

        mtot += d;
        if (d < mmin) mmin = d;
    }

    printf("%-8s %-4s mb=%zu touch=%.3fMB stride=%zuK : mean=%.1f us  min=%.1f us\n",
           argv[1], mode, mb, touch_mb, stride / 1024,
           mtot / iters / 1e3, mmin / 1e3);
    if (fd >= 0) close(fd);
    return 0;
}
