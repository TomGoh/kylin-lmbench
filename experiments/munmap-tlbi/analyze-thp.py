#!/usr/bin/env python3
# Summarize one THP-leg mode dir (E1/E2/E3) into medians. Usage: analyze-thp.py <mode_dir>
import sys, os, re, statistics as st

d = sys.argv[1]
def med(xs): return round(st.median(xs), 1) if xs else None

def grab_mean(line):
    m = re.search(r'mean=([\d.]+)', line); return float(m.group(1)) if m else None
def grab_iter_us(line):
    m = re.search(r'per_iter_us=([\d.]+)', line); return float(m.group(1)) if m else None

# E1: point|mode -> [means]
e1 = {}
for fn in ('e1-anon-sweep.txt','e1-anon-dense.txt'):
    p = os.path.join(d, fn)
    if not os.path.exists(p): continue
    for ln in open(p):
        if not ln.startswith('point='): continue
        f = ln.split()
        point = f[0].split('=')[1]; mode = f[2]; v = grab_mean(ln)
        if v is not None: e1.setdefault((point,mode), []).append(v)

# E2: thp -> op_sweep means / lat per_iter_us
e2o, e2l = {}, {}
p = os.path.join(d, 'e2-file-thp.txt')
if os.path.exists(p):
    for ln in open(p):
        thp = re.search(r'thp=(\w+)', ln); thp = thp.group(1) if thp else '?'
        if 'op_sweep_sparse' in ln: e2o.setdefault(thp, []).append(grab_mean(ln))
        elif 'lat_mmap_precise' in ln: e2l.setdefault(thp, []).append(grab_iter_us(ln))

# E3: op_sweep means / lat per_iter_us
e3o, e3l = [], []
p = os.path.join(d, 'e3-tmpfs.txt')
if os.path.exists(p):
    for ln in open(p):
        if 'op_sweep_sparse' in ln: e3o.append(grab_mean(ln))
        elif 'lat_mmap_precise' in ln: e3l.append(grab_iter_us(ln))

print(f"### {os.path.basename(d.rstrip('/'))}  (us, median)")
print("E1 anon teardown (munmap mean):")
for (pt,mode) in sorted(e1):
    print(f"   {pt:14s} {mode:10s} {med(e1[(pt,mode)])}")
print("E2 ext4 file (THP-insensitivity):")
for thp in sorted(e2o): print(f"   op_sweep_sparse THP={thp:7s} {med([x for x in e2o[thp] if x])}")
for thp in sorted(e2l): print(f"   lat_mmap_precise THP={thp:7s} {med([x for x in e2l[thp] if x])}")
print("E3 tmpfs/shmem:")
print(f"   op_sweep_sparse  {med([x for x in e3o if x])}")
print(f"   lat_mmap_precise {med([x for x in e3l if x])}")
