#!/usr/bin/env python3
"""Where in physical memory does a running VM's guest memory sit?

  sudo python3 vm-frames.py <pid of the VMM process, e.g. crosvm> [file for the list of 2 MiB regions]

With a second argument, the 2 MiB region numbers (PFN >> 9, hexadecimal, one per
line) that hold at least one page of the VM are written to that file; frames2
reads it to tell pool pages that share a region with the VM from those that do not.

Read-only: parses /proc/<pid>/maps, reads /proc/<pid>/pagemap for every
mapping of at least 64 MB, and prints, per 1 GiB physical slot, how many
present pages the mapping has there and in how many distinct 2 MiB regions.

Why it matters here: pages given to a protected VM are removed from the host's
stage-2 map one 4 KiB page at a time, which splits the 1 GiB or 2 MiB block
that contained them.  Host pages that share a 2 MiB region with guest pages
are then mapped with 4 KiB stage-2 leaves.
"""
import collections
import struct
import sys

PAGE = 4096


def main():
    pid = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    allreg = set()
    maps = []
    with open(f"/proc/{pid}/maps") as fh:
        for line in fh:
            f = line.split(None, 5)
            lo, hi = (int(x, 16) for x in f[0].split("-"))
            name = f[5].strip() if len(f) > 5 else ""
            if hi - lo >= 64 << 20:
                maps.append((lo, hi, f[1], name))
    with open(f"/proc/{pid}/pagemap", "rb") as pm:
        for lo, hi, perm, name in maps:
            n = (hi - lo) // PAGE
            pm.seek((lo // PAGE) * 8)
            raw = pm.read(n * 8)
            ents = struct.unpack(f"<{len(raw) // 8}Q", raw)
            slots = collections.Counter()
            regions = collections.defaultdict(set)
            present = 0
            for e in ents:
                if e >> 63:
                    pfn = e & ((1 << 55) - 1)
                    if pfn:
                        present += 1
                        slots[pfn >> 18] += 1
                        regions[pfn >> 18].add(pfn >> 9)
                        allreg.add(pfn >> 9)
            print(f"mapping {lo:x}-{hi:x} {perm} size_mb={(hi - lo) >> 20} name={name!r} present_pages={present} "
                  f"({present * PAGE >> 20} MB)")
            for s in sorted(slots):
                print(f"  slot=0x{s:x} phys=0x{s << 30:x} pages={slots[s]} ({slots[s] * PAGE >> 20} MB) "
                      f"distinct_2mb_regions={len(regions[s])} of 512")
    if out:
        with open(out, "w") as fh:
            for r in sorted(allreg):
                fh.write(f"{r:x}\n")
        print(f"wrote {len(allreg)} region numbers to {out}")


if __name__ == "__main__":
    main()
