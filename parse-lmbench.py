#!/usr/bin/env python3
"""Parse lmbench scripts/lmbench stderr output into a long-format CSV.

Input: one or more lmbench report files (the stderr captured from `scripts/lmbench`).
Output: CSV on stdout with columns:
    env, core, iter, bench, variant, value, unit

Each input file is one (env, core, iter) triple — these are derived from the
filename pattern <env>-cpu<N>-iter<I>.txt unless overridden via --env/--core/--iter.

The parser is a small state machine: most metrics emit on a single line; ctx,
lat_mem_rd, and par_mem produce multi-line tables that need a "current section"
flag set by a header line.
"""

import argparse
import csv
import re
import sys
from pathlib import Path

# --- single-line patterns: (regex, bench, variant, unit) ---
# `_M` captures the numeric value.
SINGLE_LINE = [
    # syscalls
    (r'^Simple syscall:\s+([\d.]+) microseconds$',      'lat_syscall', 'null',  'us'),
    (r'^Simple read:\s+([\d.]+) microseconds$',         'lat_syscall', 'read',  'us'),
    (r'^Simple write:\s+([\d.]+) microseconds$',        'lat_syscall', 'write', 'us'),
    (r'^Simple stat:\s+([\d.]+) microseconds$',         'lat_syscall', 'stat',  'us'),
    (r'^Simple fstat:\s+([\d.]+) microseconds$',        'lat_syscall', 'fstat', 'us'),
    (r'^Simple open/close:\s+([\d.]+) microseconds$',   'lat_syscall', 'open',  'us'),
    # signals
    (r'^Signal handler installation:\s+([\d.]+) microseconds$', 'lat_sig', 'install', 'us'),
    (r'^Signal handler overhead:\s+([\d.]+) microseconds$',     'lat_sig', 'catch',   'us'),
    (r'^Protection fault:\s+([\d.]+) microseconds$',            'lat_sig', 'prot',    'us'),
    # IPC latency
    (r'^Pipe latency:\s+([\d.]+) microseconds$',        'lat_pipe', 'rt',  'us'),
    (r'^AF_UNIX sock stream latency:\s+([\d.]+) microseconds$', 'lat_unix', 'rt', 'us'),
    # IPC bandwidth
    (r'^Pipe bandwidth:\s+([\d.]+) MB/sec',             'bw_pipe', 'bw', 'MB/s'),
    (r'^AF_UNIX sock stream bandwidth:\s+([\d.]+) MB/sec', 'bw_unix', 'bw', 'MB/s'),
    # process
    (r'^Simple procedure call:\s+([\d.]+) microseconds$',  'lat_proc', 'procedure', 'us'),
    (r'^Process fork\+exit:\s+([\d.]+) microseconds$',     'lat_proc', 'fork',  'us'),
    (r'^Process fork\+execve:\s+([\d.]+) microseconds$',   'lat_proc', 'exec',  'us'),
    (r'^Process fork\+/bin/sh -c:\s+([\d.]+) microseconds$', 'lat_proc', 'shell', 'us'),
    # pagefault, mmap (single mmap line: "<size_MB> <us>")
    (r'^Pagefaults on \S+:\s+([\d.]+) microseconds$',   'lat_pagefault', 'minor', 'us'),
    # network localhost
    (r'^UDP latency using localhost:\s+([\d.]+) microseconds$',  'lat_udp',     'lhost', 'us'),
    (r'^TCP latency using localhost:\s+([\d.]+) microseconds$',  'lat_tcp',     'lhost', 'us'),
    (r'^TCP/IP connection cost to localhost:\s+([\d.]+) microseconds$', 'lat_connect', 'lhost', 'us'),
    (r'^RPC/udp latency using localhost:\s+([\d.]+) microseconds$', 'lat_rpc', 'udp_lhost', 'us'),
    (r'^RPC/tcp latency using localhost:\s+([\d.]+) microseconds$', 'lat_rpc', 'tcp_lhost', 'us'),
    # tlb (uses pages, not microseconds)
    (r'^tlb:\s+(\d+)\s+pages$',                         'tlb', 'effective', 'pages'),
]

# STREAM: "STREAM <op> latency: <ns> nanoseconds" / "STREAM <op> bandwidth: <MB/s> MB/sec"
STREAM_LAT = re.compile(r'^(STREAM2?) (\w+) latency:\s+([\d.]+) nanoseconds$')
STREAM_BW  = re.compile(r'^(STREAM2?) (\w+) bandwidth:\s+([\d.]+) MB/sec$')

# Select: "Select on <N> fd's: <us>"   (file variant)
#         "Select on <N> tcp fd's: <us>" (tcp variant)
SELECT = re.compile(r"^Select on (\d+)(?: (\w+))? fd'?s?:\s+([\d.]+) microseconds$")

# Section headers (set parser state)
CTX_HEADER = re.compile(r'^"size=(\w+) ovr=([\d.]+)$')                       # lat_ctx
STRIDE_HEADER = re.compile(r'^"stride=(\d+)$')                                # lat_mem_rd
SIZE_LAT_ROW = re.compile(r'^([\d.]+)\s+([\d.]+)$')                          # generic "size value"
# Three-field bandwidth row: "<size_MB> <bw_MBps> MB/sec" (used by bw_tcp via
# lib_timing mb() helper). The trailing "MB/sec" disambiguates from the two-
# field form used by bw_mem and bw_file_rd.
SIZE_BW_MBSEC = re.compile(r'^([\d.]+)\s+([\d.]+)\s+MB/sec$')
# lat_fs row format: "<sizeK>\t<n>\t<rate1>\t<rate2>[\t<rate3>]" (tab-separated;
# rates may be "-1" when measurement failed). Captures size and first rate.
LAT_FS_ROW = re.compile(r'^(\d+)k\t(\S+)(?:\t(\S+))?(?:\t(\S+))?(?:\t(\S+))?$')
# lmdd "label=File <path> write bandwidth: " produces:
#   "File <path> write bandwidth: <X> KB/sec"
LMDD_WRITE = re.compile(r'^File \S+ write bandwidth:\s+([\d.]+) KB/sec$')
# lat_http summary line:
#   "Avg xfer: 3.2KB, 41.8KB in 0.2660 millisecs, 157.03 MB/sec"
LAT_HTTP = re.compile(r'^Avg xfer:.*?,\s+([\d.]+) MB/sec$')

# Mode flags set by these literal section banners (next "stride=" / table belongs to them)
MODE_BANNERS = {
    # memory / mmap
    'Memory load latency':       'lat_mem_rd_load',
    'Random load latency':       'lat_mem_rd_rand',
    'Memory load parallelism':   'par_mem',
    '"mappings':                 'lat_mmap',
    '"Mmap read bandwidth':      'bw_mmap_rd',
    '"Mmap read open2close bandwidth': 'bw_mmap_rd_o2c',
    # file I/O
    '"read bandwidth':           'bw_file_rd',
    '"read open2close bandwidth':'bw_file_rd_o2c',
    # network bandwidth
    'Socket bandwidth using localhost': 'bw_tcp_lhost',
    # bw_mem flavors (each emits "<size_MB> <bw_MBps>" rows after this banner)
    '"libc bcopy unaligned':            'bw_mem_bcopy_unaligned',
    '"libc bcopy aligned':              'bw_mem_bcopy_aligned',
    'Memory bzero bandwidth':           'bw_mem_bzero',
    '"unrolled bcopy unaligned':        'bw_mem_fcp',
    '"unrolled partial bcopy unaligned':'bw_mem_cp',
    'Memory read bandwidth':            'bw_mem_frd',
    'Memory partial read bandwidth':    'bw_mem_rd',
    'Memory write bandwidth':           'bw_mem_fwr',
    'Memory partial write bandwidth':   'bw_mem_wr',
    'Memory partial read/write bandwidth': 'bw_mem_rdwr',
    # lat_fs (set before fs create/delete table)
    '"File system latency':                'lat_fs',
}

# Generic "<label>: <X.YY> <unit>" pattern used by lib_timing.c helpers
# (nano/micro/milli). lat_ops emits ~20 lines through nano(), e.g.
# "integer add: 1.23 nanoseconds". par_ops emits "integer add parallelism: 4.50"
# (no unit). We catch these AFTER specific patterns so the named ones win.
GENERIC_TIMED = re.compile(r'^([A-Za-z][A-Za-z0-9_+/ ]+?):\s+([\d.]+)\s+(nanoseconds|microseconds|milliseconds|MB/sec)$')
PAR_OPS = re.compile(r'^([a-zA-Z][a-zA-Z0-9 ]+?) parallelism:\s+([\d.]+)$')

# Lines we explicitly skip (RPC errors when rpcbind isn't running, etc.)
SKIP_PATTERNS = [
    re.compile(r'^Cannot register service'),
    re.compile(r'^unable to register'),
    re.compile(r'^\(null\): RPC:'),
    re.compile(r': RPC: '),
    re.compile(r'^x: No such'),
    re.compile(r'^\['),                  # metadata blocks
    re.compile(r'^\s*$'),                # blank lines (state-machine resets handled separately)
    re.compile(r'.+: \d+: .+ not found'),# script-internal "msleep not found" etc.
    re.compile(r'^[�\?\s]+$'),      # lone Unicode replacement char(s) from non-UTF8 metadata
]


def parse_file(path, env, core, iter_id, writer):
    mode = None                 # current section: ctx | lat_mem_rd_* | par_mem | lat_mmap | bw_tcp_lhost ...
    ctx_size = None             # set when ctx header seen, applies to subsequent "<n> <us>" rows
    stride = None               # set when "stride=<N>" header seen

    # lmbench reports embed system metadata (mount tables, ifconfig output)
    # that may contain non-UTF-8 bytes on Chinese-locale hosts. We don't care
    # about those bytes — replace undecodable bytes rather than crash.
    with open(path, encoding='utf-8', errors='replace') as f:
        for raw in f:
            line = raw.rstrip('\n')

            # State resets
            if not line.strip():
                # Blank line resets *sub-state* (stride, ctx_size) but NOT mode.
                # Critical for lat_mem_rd multi-stride output: lmbench emits
                #   "stride=16\n<rows>\n\n"stride=32\n<rows>\n\n...
                # under one "Memory load latency" banner. Resetting mode on the
                # blank line between strides would orphan all but the first
                # block. mode is overridden only by the next explicit banner.
                ctx_size = None
                stride = None
                continue

            # Section banner?
            if line in MODE_BANNERS:
                mode = MODE_BANNERS[line]
                stride = None
                continue

            # Ctx header sets sub-state
            m = CTX_HEADER.match(line)
            if m:
                mode = 'lat_ctx'
                ctx_size = m.group(1)        # "0k", "4k", ...
                continue

            # Stride header (only meaningful with a preceding mode)
            m = STRIDE_HEADER.match(line)
            if m:
                stride = m.group(1)
                continue

            # Now process by state
            if mode == 'lat_ctx':
                m = SIZE_LAT_ROW.match(line)
                if m:
                    nproc, us = m.group(1), m.group(2)
                    variant = f'sz{ctx_size}_p{nproc}'
                    writer.writerow([env, core, iter_id, 'lat_ctx', variant, us, 'us'])
                    continue

            if mode and mode.startswith('lat_mem_rd_'):
                m = SIZE_LAT_ROW.match(line)
                if m:
                    sz_mb, ns = m.group(1), m.group(2)
                    bench = mode             # lat_mem_rd_load or lat_mem_rd_rand
                    variant = f'stride{stride}_sz{sz_mb}MB'
                    writer.writerow([env, core, iter_id, bench, variant, ns, 'ns'])
                    continue

            if mode == 'par_mem':
                m = SIZE_LAT_ROW.match(line)
                if m:
                    sz_mb, par = m.group(1), m.group(2)
                    writer.writerow([env, core, iter_id, 'par_mem', f'sz{sz_mb}MB', par, 'parallel'])
                    continue

            if mode == 'lat_mmap':
                m = SIZE_LAT_ROW.match(line)
                if m:
                    sz_mb, us = m.group(1), m.group(2)
                    writer.writerow([env, core, iter_id, 'lat_mmap', f'sz{sz_mb}MB', us, 'us'])
                    continue

            if mode and mode.startswith('bw_tcp_lhost'):
                # bw_tcp rows are "<msg_size_MB> <bw> MB/sec" — 3 fields with unit.
                m = SIZE_BW_MBSEC.match(line)
                if m:
                    msz, bw = m.group(1), m.group(2)
                    writer.writerow([env, core, iter_id, 'bw_tcp', f'msg{msz}MB', bw, 'MB/s'])
                    continue

            if mode == 'lat_fs':
                m = LAT_FS_ROW.match(line)
                if m:
                    sz, *rates = m.groups()
                    # column meanings (from lmbench docs): n_iters, create_rate,
                    # unlink_rate, possibly directory_rate. Emit each non-null rate.
                    col_names = ['niters', 'create', 'unlink', 'dir']
                    for name, v in zip(col_names, rates):
                        if v is not None and v != '-1':
                            writer.writerow([env, core, iter_id, 'lat_fs',
                                             f'sz{sz}K_{name}', v, 'ops/s' if name != 'niters' else 'count'])
                    continue

            if mode and (mode.startswith('bw_file_rd') or mode.startswith('bw_mmap_rd')
                         or mode.startswith('bw_mem_')):
                m = SIZE_LAT_ROW.match(line)
                if m:
                    sz, bw = m.group(1), m.group(2)
                    writer.writerow([env, core, iter_id, mode, f'sz{sz}', bw, 'MB/s'])
                    continue

            # Single-line patterns (run AFTER state-machine to give state priority)
            matched = False
            for pat, bench, variant, unit in SINGLE_LINE:
                m = re.match(pat, line)
                if m:
                    writer.writerow([env, core, iter_id, bench, variant, m.group(1), unit])
                    matched = True
                    break
            if matched:
                continue

            m = STREAM_LAT.match(line)
            if m:
                fam, op, v = m.groups()
                writer.writerow([env, core, iter_id, fam.lower(), f'{op}_lat', v, 'ns'])
                continue
            m = STREAM_BW.match(line)
            if m:
                fam, op, v = m.groups()
                writer.writerow([env, core, iter_id, fam.lower(), f'{op}_bw', v, 'MB/s'])
                continue

            m = SELECT.match(line)
            if m:
                n, kind, us = m.groups()
                kind = kind or 'file'   # absent group means file variant
                writer.writerow([env, core, iter_id, 'lat_select', f'{kind}_n{n}', us, 'us'])
                continue

            m = LMDD_WRITE.match(line)
            if m:
                writer.writerow([env, core, iter_id, 'lmdd', 'file_write_bw', m.group(1), 'KB/s'])
                continue

            m = LAT_HTTP.match(line)
            if m:
                writer.writerow([env, core, iter_id, 'lat_http', 'bw_lhost', m.group(1), 'MB/s'])
                continue

            # par_ops: "<op> parallelism: <value>" (no unit)
            m = PAR_OPS.match(line)
            if m:
                op, par = m.group(1), m.group(2)
                writer.writerow([env, core, iter_id, 'par_ops',
                                 op.replace(' ', '_'), par, 'parallel'])
                continue

            # Generic "<label>: <value> <unit>" fallback — catches lat_ops
            # (`integer add: 1.23 nanoseconds`), and anything else routed
            # through lib_timing.c's nano/micro/milli helpers. Runs LAST so
            # specific patterns above (lat_syscall, lat_proc, etc.) win.
            m = GENERIC_TIMED.match(line)
            if m:
                label, value, unit = m.groups()
                unit_short = {'nanoseconds': 'ns', 'microseconds': 'us',
                              'milliseconds': 'ms', 'MB/sec': 'MB/s'}[unit]
                writer.writerow([env, core, iter_id, 'lat_ops',
                                 label.replace(' ', '_').replace('/', '_'),
                                 value, unit_short])
                continue

            # Skip known-noisy lines
            if any(p.search(line) for p in SKIP_PATTERNS):
                continue

            # Anything else: report on stderr so we can iterate the parser
            print(f'UNPARSED [{path.name}]: {line!r}', file=sys.stderr)


FNAME_RE = re.compile(r'^(?P<env>[^/]+)-cpu(?P<core>\d+)-iter(?P<iter>\d+)\.txt$')


def derive_meta(path, override):
    if override.get('env') and override.get('core') and override.get('iter') is not None:
        return override['env'], override['core'], override['iter']
    m = FNAME_RE.match(path.name)
    if not m:
        print(f'cannot derive env/core/iter from {path.name}; use --env/--core/--iter', file=sys.stderr)
        sys.exit(2)
    return m.group('env'), m.group('core'), m.group('iter')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='+', type=Path)
    ap.add_argument('--env')
    ap.add_argument('--core')
    ap.add_argument('--iter', type=int)
    args = ap.parse_args()

    writer = csv.writer(sys.stdout)
    writer.writerow(['env', 'core', 'iter', 'bench', 'variant', 'value', 'unit'])
    override = {'env': args.env, 'core': args.core, 'iter': args.iter}
    for p in args.files:
        env, core, it = derive_meta(p, override)
        parse_file(p, env, core, it, writer)


if __name__ == '__main__':
    main()
