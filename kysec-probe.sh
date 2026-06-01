#!/usr/bin/env bash
# kysec-probe.sh — normalized KYSEC (Kylin security stack) state fingerprint.
#
# Run on BOTH host and guest. Emits:
#   - a human-readable inventory to stderr
#   - one machine-readable fingerprint line to stdout, ending in `class=<...>`
#
# WHY THIS EXISTS
# A guest that benchmarks *faster* than its own host on syscall microbenchmarks
# is almost never a real virtualization win — a guest sits on top of one more
# layer (the hypervisor) and cannot get cheaper by adding it. The usual culprit
# on KylinOS is that the guest runs LESS of the KYSEC security stack than the
# host: the ksaf LSM hooks fire on both sides, but the host has the policy
# loaded + auditd consuming + BPF attached, so each syscall walks the full
# policy path, while a stock guest takes a short path (no policy to evaluate).
# That asymmetry shows up as a 14-26% "guest is faster" delta on lat_syscall.
#
# For a host-vs-guest comparison to be attributable to the hypervisor and not
# to KYSEC, BOTH sides must report the SAME class:
#
#   class=off      ksaf/kycp LSM not loaded at all (no lsm=ksaf / security=box
#                  on the cmdline) — the clean "pure hypervisor" baseline. This
#                  is the target state for the disable-KYSEC-both-sides method.
#   class=full     LSM loaded AND policy initialized AND /sys/fs/box present
#                  AND auditd active — the production host state.
#   class=partial  LSM module loaded but policy / audit / box NOT active — the
#                  state a stock guest boots into. THIS is the usual cause of
#                  "guest beats host"; it must be eliminated before trusting
#                  any host-vs-guest delta.
#
# Exit status is always 0 — read the `class=` token, do not branch on $?.
set -u

active() { systemctl is-active "$1" 2>/dev/null || echo unknown; }
read1()  { head -1 "$1" 2>/dev/null; }

LSM_STR="$(read1 /sys/kernel/security/lsm)"
CMDLINE="$(read1 /proc/cmdline)"

cl_lsm=$(printf '%s\n' "$CMDLINE" | grep -oE 'lsm=[^ ]+'      | head -1)
cl_sec=$(printf '%s\n' "$CMDLINE" | grep -oE 'security=[^ ]+' | head -1)
cl_aud=$(printf '%s\n' "$CMDLINE" | grep -oE 'audit=[^ ]+'    | head -1)

policy_init="$(active ksaf-policy-init.service)"
kbox="$(active kysec2-kbox-load.service)"
auditd="$(active auditd.service)"

if [ -e /sys/fs/box ]; then box_fs=present; else box_fs=absent; fi

audit_enabled="$(auditctl -s 2>/dev/null | awk '/^enabled/{print $2; f=1} END{if(!f) print "na"}')"
if auditctl -l 2>/dev/null | grep -qi '^no rules'; then
  audit_rules=0
else
  audit_rules="$(auditctl -l 2>/dev/null | grep -c '.')"
fi
bpf="$(bpftool prog show 2>/dev/null | grep -cE '^[0-9]+:')"

# --- classify ---------------------------------------------------------------
lsm_loaded=no
case "${LSM_STR}${cl_lsm}${cl_sec}" in
  *ksaf*|*kycp*|*box*) lsm_loaded=yes ;;
esac

if [ "$lsm_loaded" = no ]; then
  class=off
elif [ "$policy_init" = active ] && [ "$box_fs" = present ] && [ "$auditd" = active ]; then
  class=full
else
  class=partial
fi

# --- human inventory (stderr) -----------------------------------------------
{
  echo "[kysec-probe] node=$(uname -n) kernel=$(uname -r)"
  echo "  /sys/kernel/security/lsm = ${LSM_STR:-<absent>}"
  echo "  cmdline flags            = ${cl_lsm:-<no lsm=>} ${cl_sec:-<no security=>} ${cl_aud:-<no audit=>}"
  echo "  ksaf-policy-init.service = $policy_init"
  echo "  kysec2-kbox-load.service = $kbox"
  echo "  auditd.service           = $auditd"
  echo "  /sys/fs/box              = $box_fs"
  echo "  audit enabled / rules    = ${audit_enabled:-na} / $audit_rules"
  echo "  BPF programs loaded      = $bpf"
  echo "  ==> class=$class"
} >&2

# --- machine-readable fingerprint (stdout) ----------------------------------
echo "KYSEC_FP lsm=[${LSM_STR}] ${cl_lsm:-lsm=} ${cl_sec:-security=} ${cl_aud:-audit=} policy_init=$policy_init kbox=$kbox auditd=$auditd box=$box_fs audit_enabled=${audit_enabled:-na} audit_rules=$audit_rules bpf=$bpf class=$class"
