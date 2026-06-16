// SPDX-License-Identifier: GPL-2.0
/*
 * tlbi_ab.c — Experiment 2: isolate the cross-core (broadcast) TLBI cost from
 * the local invalidation cost, on a single fixed core, with IRQs off — so the
 * result does NOT depend on CPU hotplug removing cores from the DVM domain
 * (the one caveat of the core-scaling experiment).
 *
 * It issues a fixed batch of N per-page TLBIs over a real (vmalloc'd) kernel VA
 * range, then one barrier, timed two ways that differ in EXACTLY one dimension:
 *
 *   IS  (broadcast): reps * `tlbi vae1is, VA`  then  `dsb ish`
 *   NSH (local):     reps * `tlbi vae1,   VA`  then  `dsb nsh`
 *
 * `vae1`/`vae1is` and `dsb nsh`/`dsb ish` invalidate the identical entries; the
 * only difference is whether the op is broadcast to the Inner-Shareable domain
 * and waited on. So (IS - NSH) per slot IS the cross-core broadcast/sync cost.
 *
 * In protected mode the host VAs are combined stage-1xstage-2 VMID-tagged
 * entries; in nvhe they are stage-1 only. Run in both and compare:
 *   protected (IS-NSH)  should ~= core-scaling protected broadcast (~0.198 us/slot)
 *   nvhe      (IS-NSH)  should ~= core-scaling nvhe broadcast      (~0     us/slot)
 *
 * Usage (taskset to the bench core, e.g. cpu0):
 *   echo "<nslots> [reps] [iters]" > /proc/tlbi_ab   # nslots<=4096, default reps=2 iters=50
 *   cat /proc/tlbi_ab
 */
#include <linux/module.h>
#include <linux/proc_fs.h>
#include <linux/vmalloc.h>
#include <linux/uaccess.h>
#include <linux/preempt.h>
#include <linux/irqflags.h>
#include <linux/bitops.h>
#include <asm/sysreg.h>
#include <asm/barrier.h>

#define MAX_SLOTS 4096

static DEFINE_MUTEX(tlbi_lock);
static char result[640] = "no run yet; write \"<nslots> [reps] [iters] [dsb_per_slot] [memwork]\" to /proc/tlbi_ab\n";

/* pointer-chase buffer: DEPENDENT, RANDOM (LCG-permuted) loads over 128 MB so
 * each step misses the 2 MB L3 and the hw prefetcher can't hide the latency —
 * real memory traffic in flight with the TLBI broadcast (like munmap's
 * page-free), so the broadcast back-pressure has something to stall.
 * Seeded per-iteration so every timed batch walks fresh-cold lines. */
#define CHASE_N   (16UL << 20)		/* 16M u64 = 128 MB, >> 2 MB L3 */
#define CHASE_MASK (CHASE_N - 1)
#define LCG_A 1664525ULL		/* Hull-Dobell full-period over 2^24 */
#define LCG_C 1013904223ULL
static u64 *chase;
static volatile u64 chase_sink;

/* __TLBI_VADDR-style operand: VA>>12 in [43:0], ASID in [63:48].
 * asid=0 -> kernel-global VAs; asid=ASID(current->mm) -> user nG VAs (matches
 * what munmap invalidates: combined stage-1xstage-2 VMID-tagged entries). */
static inline u64 tlbi_op(unsigned long va, u64 asid)
{
	return ((va >> 12) & GENMASK_ULL(43, 0)) | (asid << 48);
}

/* One timed batch: N slots * reps TLBIs. Returns timer ticks.
 * shareable=1 -> vae1is + dsb ish (broadcast); 0 -> vae1 + dsb nsh (local).
 * dsb_per_slot=1 -> a dsb after EACH slot (exposes the per-slot completion wait,
 * like munmap interleaving TLBIs with other work); 0 -> one dsb amortized over
 * the whole batch (lets the broadcasts pipeline/parallelize). */
static u64 do_batch(unsigned long base, u64 asid, int nslots, int reps,
		    int shareable, int dsb_per_slot, int memwork, u64 seed)
{
	unsigned long flags;
	u64 t0, t1, idx = (seed * 2654435761ULL) & CHASE_MASK;
	int i, r, k;

	preempt_disable();
	local_irq_save(flags);

	isb();
	t0 = read_sysreg(cntvct_el0);
	for (i = 0; i < nslots; i++) {
		u64 op = tlbi_op(base + (unsigned long)i * PAGE_SIZE, asid);

		for (r = 0; r < reps; r++) {
			if (shareable)
				asm volatile("tlbi vae1is, %0" :: "r"(op) : "memory");
			else
				asm volatile("tlbi vae1, %0"   :: "r"(op) : "memory");
		}
		/* dependent cache-missing loads in flight with the broadcast */
		for (k = 0; k < memwork; k++)
			idx = chase[idx];
		if (dsb_per_slot) {
			if (shareable)
				asm volatile("dsb ish" ::: "memory");
			else
				asm volatile("dsb nsh" ::: "memory");
		}
	}
	chase_sink = idx;
	if (!dsb_per_slot) {
		if (shareable)
			asm volatile("dsb ish" ::: "memory");
		else
			asm volatile("dsb nsh" ::: "memory");
	}
	isb();
	t1 = read_sysreg(cntvct_el0);

	local_irq_restore(flags);
	preempt_enable();
	return t1 - t0;
}

/* ticks -> nanoseconds using the architected timer frequency. */
static u64 ticks_to_ns(u64 ticks)
{
	u64 hz = read_sysreg(cntfrq_el0);
	u64 ns = ticks * 1000000000ULL;

	if (!hz)
		return 0;
	do_div(ns, hz);
	return ns;
}

static ssize_t tlbi_write(struct file *f, const char __user *ubuf,
			  size_t len, loff_t *off)
{
	char kbuf[96];
	int nslots = 0, reps = 2, iters = 50, dps = 0, mw = 0, it, cpu;
	unsigned long uva = 0, base;
	u64 asid = 0, is_min = ~0ULL, nsh_min = ~0ULL;
	char *buf = NULL;

	if (len >= sizeof(kbuf))
		return -EINVAL;
	if (copy_from_user(kbuf, ubuf, len))
		return -EFAULT;
	kbuf[len] = '\0';
	/* "<uva> <nslots> [reps] [iters] [dsb_per_slot] [memwork]"; uva=0 -> kernel mode */
	if (sscanf(kbuf, "%lu %d %d %d %d %d", &uva, &nslots, &reps, &iters, &dps, &mw) < 2)
		return -EINVAL;
	/* reps=0 -> no TLBI (memory-only baseline) */
	if (nslots < 1 || nslots > MAX_SLOTS || reps < 0 || iters < 1 || mw < 0)
		return -EINVAL;

	if (uva) {
		/* USER mode: invalidate the caller's user VAs with its ASID — exactly
		 * the nG combined entries munmap tears down. The pages must already be
		 * mapped+touched by the caller (and, for the broadcast to do remote
		 * work, by any other cores it was scheduled on). */
		base = uva & PAGE_MASK;
		asid = atomic64_read(&current->mm->context.id) & 0xffff;
	} else {
		/* KERNEL mode: vmalloc'd global VAs, ASID 0 (original behaviour). */
		buf = vmalloc(nslots * PAGE_SIZE);
		if (!buf)
			return -ENOMEM;
		memset(buf, 0, nslots * PAGE_SIZE);
		base = (unsigned long)buf;
		asid = 0;
	}

	mutex_lock(&tlbi_lock);
	cpu = smp_processor_id();
	for (it = 0; it < iters; it++) {
		/* distinct seeds per iter AND per arm -> every batch is fresh-cold */
		u64 a = do_batch(base, asid, nslots, reps, 1, dps, mw, 2*it);   /* IS  */
		u64 b = do_batch(base, asid, nslots, reps, 0, dps, mw, 2*it+1); /* NSH */

		if (a < is_min)  is_min  = a;
		if (b < nsh_min) nsh_min = b;
	}

	{
		u64 is_ns  = ticks_to_ns(is_min);
		u64 nsh_ns = ticks_to_ns(nsh_min);
		/* per-slot in picoseconds for sub-ns resolution */
		u64 is_ps  = ticks_to_ns(is_min)  * 1000ULL / nslots;
		u64 nsh_ps = ticks_to_ns(nsh_min) * 1000ULL / nslots;
		s64 bcast_ps = (s64)is_ps - (s64)nsh_ps;

		snprintf(result, sizeof(result),
			"cpu=%d mode=%s asid=%llu nslots=%d reps=%d iters=%d dsb_per_slot=%d memwork=%d (min over iters)\n"
			"IS  total=%llu ns  per_slot=%llu.%03llu ns\n"
			"NSH total=%llu ns  per_slot=%llu.%03llu ns\n"
			"broadcast (IS-NSH) per_slot=%lld.%03lld ns  (= %lld.%03lld us/slot)\n",
			cpu, uva ? "user" : "kernel", asid, nslots, reps, iters, dps, mw,
			is_ns,  is_ps/1000,  is_ps%1000,
			nsh_ns, nsh_ps/1000, nsh_ps%1000,
			bcast_ps/1000, (bcast_ps<0?-bcast_ps:bcast_ps)%1000,
			bcast_ps/1000000, (bcast_ps<0?-bcast_ps:bcast_ps)/1000%1000);
	}
	mutex_unlock(&tlbi_lock);
	vfree(buf);
	return len;
}

static ssize_t tlbi_read(struct file *f, char __user *ubuf, size_t len, loff_t *off)
{
	return simple_read_from_buffer(ubuf, len, off, result, strlen(result));
}

static const struct proc_ops tlbi_ops = {
	.proc_write = tlbi_write,
	.proc_read  = tlbi_read,
};

static struct proc_dir_entry *ent;

static int __init tlbi_ab_init(void)
{
	u64 i;

	chase = vmalloc(CHASE_N * sizeof(u64));
	if (!chase)
		return -ENOMEM;
	/* LCG permutation: chase[i] = next pseudo-random index (full period over
	 * 2^24), so `idx = chase[idx]` is a dependent random walk that misses L3. */
	for (i = 0; i < CHASE_N; i++)
		chase[i] = (i * LCG_A + LCG_C) & CHASE_MASK;

	ent = proc_create("tlbi_ab", 0666, NULL, &tlbi_ops);
	if (!ent) {
		vfree(chase);
		return -ENOMEM;
	}
	pr_info("tlbi_ab: loaded; echo \"<nslots> [reps] [iters] [dsb_per_slot] [memwork]\" > /proc/tlbi_ab\n");
	return 0;
}

static void __exit tlbi_ab_exit(void)
{
	proc_remove(ent);
	vfree(chase);
	pr_info("tlbi_ab: unloaded\n");
}

module_init(tlbi_ab_init);
module_exit(tlbi_ab_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("IS vs NSH TLBI broadcast-cost microbenchmark (pKVM munmap investigation)");
