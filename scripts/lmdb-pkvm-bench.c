/*
 * Small LMDB benchmark for comparing host kvm-arm modes.
 *
 * Build:
 *   cc -O2 -Wall -Wextra -o bin/lmdb-pkvm-bench scripts/lmdb-pkvm-bench.c -llmdb
 *
 * Modes:
 *   prepare   <dir> <records> <value_size> <map_mb> <batch> <nosync:0|1>
 *   read      <dir> <ops> <txn_batch> <seed>
 *   write     <dir> <records> <value_size> <map_mb> <batch> <nosync:0|1>
 *   openclose <dir> <iters> <map_mb>
 */

#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>

#define MDB_SUCCESS 0
#define MDB_NOTFOUND (-30798)
#define MDB_RDONLY 0x20000
#define MDB_CREATE 0x40000
#define MDB_NOSYNC 0x10000
#define MDB_NOMETASYNC 0x40000

typedef struct MDB_env MDB_env;
typedef struct MDB_txn MDB_txn;
typedef unsigned int MDB_dbi;
typedef struct MDB_val {
    size_t mv_size;
    void *mv_data;
} MDB_val;
typedef struct MDB_stat {
    unsigned int ms_psize;
    unsigned int ms_depth;
    size_t ms_branch_pages;
    size_t ms_leaf_pages;
    size_t ms_overflow_pages;
    size_t ms_entries;
} MDB_stat;

static int (*lmdb_env_create)(MDB_env **env);
static int (*lmdb_env_set_mapsize)(MDB_env *env, size_t size);
static int (*lmdb_env_set_maxdbs)(MDB_env *env, MDB_dbi dbs);
static int (*lmdb_env_open)(MDB_env *env, const char *path, unsigned int flags, unsigned int mode);
static void (*lmdb_env_close)(MDB_env *env);
static int (*lmdb_txn_begin)(MDB_env *env, MDB_txn *parent, unsigned int flags, MDB_txn **txn);
static int (*lmdb_txn_commit)(MDB_txn *txn);
static void (*lmdb_txn_abort)(MDB_txn *txn);
static int (*lmdb_dbi_open)(MDB_txn *txn, const char *name, unsigned int flags, MDB_dbi *dbi);
static int (*lmdb_put)(MDB_txn *txn, MDB_dbi dbi, MDB_val *key, MDB_val *data, unsigned int flags);
static int (*lmdb_get)(MDB_txn *txn, MDB_dbi dbi, MDB_val *key, MDB_val *data);
static int (*lmdb_stat)(MDB_txn *txn, MDB_dbi dbi, MDB_stat *stat);
static char *(*lmdb_strerror)(int err);

static void *must_sym(void *handle, const char *name)
{
    void *sym = dlsym(handle, name);
    if (!sym) {
        fprintf(stderr, "dlsym(%s): %s\n", name, dlerror());
        exit(1);
    }
    return sym;
}

static void load_lmdb(void)
{
    void *handle = dlopen("liblmdb.so.0", RTLD_NOW | RTLD_LOCAL);
    if (!handle)
        handle = dlopen("liblmdb.so", RTLD_NOW | RTLD_LOCAL);
    if (!handle) {
        fprintf(stderr, "dlopen liblmdb: %s\n", dlerror());
        exit(1);
    }

    lmdb_env_create = must_sym(handle, "mdb_env_create");
    lmdb_env_set_mapsize = must_sym(handle, "mdb_env_set_mapsize");
    lmdb_env_set_maxdbs = must_sym(handle, "mdb_env_set_maxdbs");
    lmdb_env_open = must_sym(handle, "mdb_env_open");
    lmdb_env_close = must_sym(handle, "mdb_env_close");
    lmdb_txn_begin = must_sym(handle, "mdb_txn_begin");
    lmdb_txn_commit = must_sym(handle, "mdb_txn_commit");
    lmdb_txn_abort = must_sym(handle, "mdb_txn_abort");
    lmdb_dbi_open = must_sym(handle, "mdb_dbi_open");
    lmdb_put = must_sym(handle, "mdb_put");
    lmdb_get = must_sym(handle, "mdb_get");
    lmdb_stat = must_sym(handle, "mdb_stat");
    lmdb_strerror = must_sym(handle, "mdb_strerror");
}

static void die_mdb(int rc, const char *what)
{
    if (rc != MDB_SUCCESS) {
        fprintf(stderr, "%s: %s\n", what, lmdb_strerror ? lmdb_strerror(rc) : "lmdb error");
        exit(1);
    }
}

static void die_errno(const char *what)
{
    perror(what);
    exit(1);
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

static double now_ns(void)
{
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0)
        die_errno("clock_gettime");
    return (double)ts.tv_sec * 1e9 + (double)ts.tv_nsec;
}

static void ensure_dir(const char *path)
{
    if (mkdir(path, 0775) != 0 && errno != EEXIST)
        die_errno("mkdir");
}

static void make_key(uint64_t i, char key[16])
{
    static const char hex[] = "0123456789abcdef";
    for (int n = 15; n >= 0; --n) {
        key[n] = hex[i & 0xf];
        i >>= 4;
    }
}

static MDB_env *open_env(const char *dir, size_t map_size, unsigned int flags)
{
    MDB_env *env = NULL;
    die_mdb(lmdb_env_create(&env), "mdb_env_create");
    if (map_size > 0)
        die_mdb(lmdb_env_set_mapsize(env, map_size), "mdb_env_set_mapsize");
    die_mdb(lmdb_env_set_maxdbs(env, 1), "mdb_env_set_maxdbs");
    die_mdb(lmdb_env_open(env, dir, flags, 0664), "mdb_env_open");
    return env;
}

static MDB_dbi open_dbi(MDB_env *env, MDB_txn **txn_out, unsigned int txn_flags,
                        unsigned int dbi_flags)
{
    MDB_txn *txn = NULL;
    MDB_dbi dbi = 0;
    die_mdb(lmdb_txn_begin(env, NULL, txn_flags, &txn), "mdb_txn_begin");
    die_mdb(lmdb_dbi_open(txn, NULL, dbi_flags, &dbi), "mdb_dbi_open");
    *txn_out = txn;
    return dbi;
}

static uint64_t entry_count(MDB_env *env)
{
    MDB_txn *txn = NULL;
    MDB_dbi dbi = open_dbi(env, &txn, MDB_RDONLY, 0);
    MDB_stat st;
    die_mdb(lmdb_stat(txn, dbi, &st), "mdb_stat");
    lmdb_txn_abort(txn);
    return (uint64_t)st.ms_entries;
}

static void fill_value(char *buf, size_t len)
{
    for (size_t i = 0; i < len; ++i)
        buf[i] = (char)('a' + (i % 26));
}

static void put_range(MDB_env *env, uint64_t start, uint64_t records,
                      size_t value_size, uint64_t batch)
{
    char keybuf[16];
    char *valbuf = malloc(value_size ? value_size : 1);
    if (!valbuf)
        die_errno("malloc");
    fill_value(valbuf, value_size);

    uint64_t done = 0;
    while (done < records) {
        uint64_t todo = batch;
        if (todo == 0 || todo > records - done)
            todo = records - done;

        MDB_txn *txn = NULL;
        MDB_dbi dbi = open_dbi(env, &txn, 0, MDB_CREATE);

        for (uint64_t i = 0; i < todo; ++i) {
            make_key(start + done + i, keybuf);
            MDB_val key = { .mv_size = sizeof(keybuf), .mv_data = keybuf };
            MDB_val val = { .mv_size = value_size, .mv_data = valbuf };
            int rc = lmdb_put(txn, dbi, &key, &val, 0);
            if (rc != MDB_SUCCESS) {
                lmdb_txn_abort(txn);
                die_mdb(rc, "mdb_put");
            }
        }
        die_mdb(lmdb_txn_commit(txn), "mdb_txn_commit");
        done += todo;
    }
    free(valbuf);
}

static uint64_t lcg_next(uint64_t *state)
{
    *state = *state * UINT64_C(6364136223846793005) + UINT64_C(1442695040888963407);
    return *state;
}

static void mode_prepare(int argc, char **argv)
{
    if (argc != 8) {
        fprintf(stderr, "usage: %s prepare <dir> <records> <value_size> <map_mb> <batch> <nosync>\n", argv[0]);
        exit(2);
    }
    const char *dir = argv[2];
    uint64_t records = parse_u64(argv[3], "records");
    size_t value_size = (size_t)parse_u64(argv[4], "value_size");
    size_t map_size = (size_t)parse_u64(argv[5], "map_mb") << 20;
    uint64_t batch = parse_u64(argv[6], "batch");
    int nosync = (int)parse_u64(argv[7], "nosync");
    unsigned int flags = nosync ? (MDB_NOSYNC | MDB_NOMETASYNC) : 0;

    ensure_dir(dir);
    double t0 = now_ns();
    MDB_env *env = open_env(dir, map_size, flags);
    put_range(env, 0, records, value_size, batch);
    lmdb_env_close(env);
    double t1 = now_ns();

    double secs = (t1 - t0) / 1e9;
    printf("mode,records,value_size,map_mb,batch,nosync,total_s,ops_per_s,ns_per_op\n");
    printf("prepare,%" PRIu64 ",%zu,%s,%" PRIu64 ",%d,%.9f,%.3f,%.3f\n",
           records, value_size, argv[5], batch, nosync, secs,
           records / secs, (t1 - t0) / records);
}

static void mode_write(int argc, char **argv)
{
    if (argc != 8) {
        fprintf(stderr, "usage: %s write <dir> <records> <value_size> <map_mb> <batch> <nosync>\n", argv[0]);
        exit(2);
    }
    const char *dir = argv[2];
    uint64_t records = parse_u64(argv[3], "records");
    size_t value_size = (size_t)parse_u64(argv[4], "value_size");
    size_t map_size = (size_t)parse_u64(argv[5], "map_mb") << 20;
    uint64_t batch = parse_u64(argv[6], "batch");
    int nosync = (int)parse_u64(argv[7], "nosync");
    unsigned int flags = nosync ? (MDB_NOSYNC | MDB_NOMETASYNC) : 0;

    MDB_env *env = open_env(dir, map_size, flags);
    uint64_t start = entry_count(env);
    double t0 = now_ns();
    put_range(env, start, records, value_size, batch);
    double t1 = now_ns();
    lmdb_env_close(env);

    double secs = (t1 - t0) / 1e9;
    printf("mode,start,records,value_size,map_mb,batch,nosync,total_s,ops_per_s,ns_per_op\n");
    printf("write,%" PRIu64 ",%" PRIu64 ",%zu,%s,%" PRIu64 ",%d,%.9f,%.3f,%.3f\n",
           start, records, value_size, argv[5], batch, nosync, secs,
           records / secs, (t1 - t0) / records);
}

static void mode_read(int argc, char **argv)
{
    if (argc != 6) {
        fprintf(stderr, "usage: %s read <dir> <ops> <txn_batch> <seed>\n", argv[0]);
        exit(2);
    }
    const char *dir = argv[2];
    uint64_t ops = parse_u64(argv[3], "ops");
    uint64_t txn_batch = parse_u64(argv[4], "txn_batch");
    uint64_t seed = parse_u64(argv[5], "seed");
    if (txn_batch == 0)
        txn_batch = ops;

    MDB_env *env = open_env(dir, 0, 0);
    uint64_t records = entry_count(env);
    if (records == 0) {
        fprintf(stderr, "database is empty\n");
        exit(1);
    }

    char keybuf[16];
    uint64_t found = 0;
    double t0 = now_ns();
    for (uint64_t done = 0; done < ops;) {
        uint64_t todo = txn_batch;
        if (todo > ops - done)
            todo = ops - done;

        MDB_txn *txn = NULL;
        MDB_dbi dbi = open_dbi(env, &txn, MDB_RDONLY, 0);
        for (uint64_t i = 0; i < todo; ++i) {
            uint64_t k = lcg_next(&seed) % records;
            make_key(k, keybuf);
            MDB_val key = { .mv_size = sizeof(keybuf), .mv_data = keybuf };
            MDB_val val;
            int rc = lmdb_get(txn, dbi, &key, &val);
            if (rc == MDB_SUCCESS) {
                found++;
            } else if (rc != MDB_NOTFOUND) {
                lmdb_txn_abort(txn);
                die_mdb(rc, "mdb_get");
            }
        }
        lmdb_txn_abort(txn);
        done += todo;
    }
    double t1 = now_ns();
    lmdb_env_close(env);

    double secs = (t1 - t0) / 1e9;
    printf("mode,records,ops,txn_batch,found,total_s,ops_per_s,ns_per_op\n");
    printf("read,%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%.9f,%.3f,%.3f\n",
           records, ops, txn_batch, found, secs, ops / secs, (t1 - t0) / ops);
}

static void mode_openclose(int argc, char **argv)
{
    if (argc != 5) {
        fprintf(stderr, "usage: %s openclose <dir> <iters> <map_mb>\n", argv[0]);
        exit(2);
    }
    const char *dir = argv[2];
    uint64_t iters = parse_u64(argv[3], "iters");
    size_t map_size = (size_t)parse_u64(argv[4], "map_mb") << 20;

    double t0 = now_ns();
    for (uint64_t i = 0; i < iters; ++i) {
        MDB_env *env = open_env(dir, map_size, 0);
        MDB_txn *txn = NULL;
        (void)open_dbi(env, &txn, MDB_RDONLY, 0);
        lmdb_txn_abort(txn);
        lmdb_env_close(env);
    }
    double t1 = now_ns();

    double secs = (t1 - t0) / 1e9;
    printf("mode,iters,map_mb,total_s,ops_per_s,us_per_openclose\n");
    printf("openclose,%" PRIu64 ",%s,%.9f,%.3f,%.3f\n",
           iters, argv[4], secs, iters / secs, (t1 - t0) / iters / 1000.0);
}

int main(int argc, char **argv)
{
    load_lmdb();

    if (argc < 2) {
        fprintf(stderr, "usage: %s <prepare|read|write|openclose> ...\n", argv[0]);
        return 2;
    }
    if (strcmp(argv[1], "prepare") == 0)
        mode_prepare(argc, argv);
    else if (strcmp(argv[1], "read") == 0)
        mode_read(argc, argv);
    else if (strcmp(argv[1], "write") == 0)
        mode_write(argc, argv);
    else if (strcmp(argv[1], "openclose") == 0)
        mode_openclose(argc, argv);
    else {
        fprintf(stderr, "unknown mode: %s\n", argv[1]);
        return 2;
    }
    return 0;
}
