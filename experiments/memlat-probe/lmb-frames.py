#!/usr/bin/env python3
"""Record the physical layout of the buffer of every lat_mem_rd child.

lmbench's lat_mem_rd forks one child per size; the child malloc()s the whole
maximum length and writes the pointer chain over the first <size> bytes.  The
program itself reports nothing about the frames it got.  This watcher finds
every child of a running lat_mem_rd, reads the page map of its large
anonymous mapping a moment after it appeared and writes one line per child:

  t=<unix time> pid=<pid> pages=<present pages> size_mb=<pages x 4 KiB>
  contig_frac=<fraction of virtually adjacent present pages that are physically ascending neighbours>
  rcontig_frac=<the same for descending neighbours>
  mb2_regions=<distinct 2 MiB regions> gb_slots=<distinct 1 GiB slots>
  runs=<maximal runs of physically adjacent pages, either direction> longest_run=<pages>

The line is matched to lmbench's output line by its time and size.

usage: lmb-frames.py <output file> [command name, default lat_mem_rd] [dump file]
Runs until killed.  Needs root (frame numbers from /proc/<pid>/pagemap).
Pin it to a core other than the one the benchmark uses.
With a dump file, the frame numbers of every buffer are appended to it as
well, one line per child: "pid=<pid> t=<time> pfns=<hex>,<hex>,..." in
virtual order, so that one can see which frames consecutive children share.
"""
import os
import sys
import time

PAGE = 4096
MIN_MAP = 60 << 20      # the buffer is 64 MB plus two pages; anything this large is it


def comm(pid):
    try:
        with open(f"/proc/{pid}/comm") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def ppid(pid):
    try:
        with open(f"/proc/{pid}/stat") as fh:
            return int(fh.read().rsplit(")", 1)[1].split()[1])
    except (OSError, ValueError, IndexError):
        return -1


def big_mapping(pid):
    """(start, end) of the largest anonymous read-write private mapping, if it is large enough."""
    best = None
    try:
        with open(f"/proc/{pid}/maps") as fh:
            for line in fh:
                p = line.split()
                if len(p) != 5 or p[1] != "rw-p":
                    continue
                a, b = (int(x, 16) for x in p[0].split("-"))
                if b - a >= MIN_MAP and (best is None or b - a > best[1] - best[0]):
                    best = (a, b)
    except OSError:
        return None
    return best


def frames(pid, start, end):
    """Frame numbers, in virtual order, of the longest stretch of present pages of [start, end).

    The mapping can hold other malloc()ed blocks next to the buffer (lmbench's
    page permutation array, 33 pages); the buffer is the longest stretch.
    """
    try:
        with open(f"/proc/{pid}/pagemap", "rb") as fh:
            fh.seek(start // PAGE * 8)
            raw = fh.read((end - start) // PAGE * 8)
    except OSError:
        return None
    best, cur = [], []
    for i in range(0, len(raw) - 7, 8):
        e = int.from_bytes(raw[i:i + 8], "little")
        if e >> 63:
            cur.append(e & ((1 << 55) - 1))
        else:
            if len(cur) > len(best):
                best = cur
            cur = []
    return cur if len(cur) > len(best) else best


def describe(f):
    n = len(f)
    asc = sum(1 for a, b in zip(f, f[1:]) if b == a + 1)
    desc = sum(1 for a, b in zip(f, f[1:]) if b + 1 == a)
    runs, cur, longest = 1, 1, 1
    for a, b in zip(f, f[1:]):
        if b == a + 1 or b + 1 == a:
            cur += 1
        else:
            runs += 1
            cur = 1
        longest = max(longest, cur)
    return (f"pages={n} size_mb={n * PAGE / 1048576:.5f} contig_frac={asc / max(1, n - 1):.4f} "
            f"rcontig_frac={desc / max(1, n - 1):.4f} mb2_regions={len({x >> 9 for x in f})} "
            f"gb_slots={len({x >> 18 for x in f})} runs={runs} longest_run={longest}")


def main():
    out = open(sys.argv[1], "a", buffering=1)
    name = sys.argv[2] if len(sys.argv) > 2 else "lat_mem_rd"
    dump = open(sys.argv[3], "a", buffering=1) if len(sys.argv) > 3 else None
    seen = {}       # pid -> time first seen
    done = set()
    while True:
        now = time.time()
        for d in os.listdir("/proc"):
            if not d.isdigit():
                continue
            pid = int(d)
            if pid in done or comm(pid) != name:
                continue
            # the measuring process is a child of another process of the same name
            if comm(ppid(pid)) != name:
                continue
            first = seen.setdefault(pid, now)
            if now - first < 0.25:
                continue
            m = big_mapping(pid)
            if m is None:
                continue
            f = frames(pid, *m)
            if not f:
                continue
            # read again a little later: the count must have stopped growing
            time.sleep(0.05)
            g = frames(pid, *m)
            if g is None or len(g) != len(f):
                continue
            now2 = time.time()
            out.write(f"t={now2:.3f} pid={pid} {describe(g)}\n")
            if dump:
                dump.write(f"pid={pid} t={now2:.3f} pfns=" + ",".join(f"{x:x}" for x in g) + "\n")
            done.add(pid)
        for pid in [p for p in seen if not os.path.exists(f"/proc/{p}")]:
            del seen[pid]
        time.sleep(0.05)


if __name__ == "__main__":
    main()
