#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=config.env
source "$SCRIPT_DIR/config.env"

RUNTIME_HASH_FILES=(
    config.env
    lib.sh
    campaign.sh
    resume-campaign.sh
    run-boot-block.sh
    run-anchors.sh
    run-geekbench.sh
    redis.sh
    rabbitmq.sh
    prepare-host.sh
    restore-host.sh
    set-next-mode.sh
    compute-capacity.py
    verify-rabbitmq-fixes.sh
    launch-pending-thp-always.sh
    d3000-pkvm-campaign.service
    d3000-thp-always-chain.service
)

timestamp() { date --iso-8601=seconds; }
log() {
    local line
    line="[$(timestamp)] $*"
    printf '%s\n' "$line"
    if [[ -n ${LOG_DIR:-} && -d ${LOG_DIR:-/nonexistent} ]]; then
        printf '%s\n' "$line" >>"$LOG_DIR/events.log"
    fi
}
die() { log "ERROR: $*" >&2; exit 1; }

record_note() {
    local category=$1
    shift
    mkdir -p "$EXP_HOME/notes"
    printf -- '- %s | mode=%s | %s | %s\n' "$(timestamp)" "$(mode_from_cmdline)" "$category" "$*" \
        >>"$EXP_HOME/notes/WORKLOG.md"
}

require_cmd() {
    local cmd
    for cmd in "$@"; do
        command -v "$cmd" >/dev/null 2>&1 || die "missing command: $cmd"
    done
}

runtime_bundle_sha256() {
    local root=${1:-$SCRIPT_DIR} name sum manifest=''
    for name in "${RUNTIME_HASH_FILES[@]}"; do
        [[ -f "$root/$name" ]] || die "runtime hash input is missing: $root/$name"
        sum=$(sha256sum "$root/$name")
        sum=${sum%% *}
        manifest+="$sum  $name"$'\n'
    done
    printf '%s' "$manifest" | sha256sum | cut -d' ' -f1
}

validate_thp_profile() {
    case "$1" in
        never|always) ;;
        *) die "THP profile must be never or always, got: $1" ;;
    esac
}

mode_from_cmdline() {
    local arg
    arg=$(tr ' ' '\n' </proc/cmdline | sed -n 's/^kvm-arm\.mode=//p' | tail -n 1)
    case "$arg" in
        protected|nvhe|vhe|none) printf '%s\n' "$arg" ;;
        '') printf 'vhe\n' ;;
        *) printf '%s\n' "$arg" ;;
    esac
}

assert_mode() {
    local expected=$1 actual dmesg_text
    actual=$(mode_from_cmdline)
    [[ "$actual" == "$expected" ]] || die "boot mode mismatch: expected=$expected actual=$actual cmdline=$(</proc/cmdline)"
    dmesg_text=$(sudo dmesg)
    case "$expected" in
        protected)
            grep -Fq 'CPU features: detected: Protected KVM' <<<"$dmesg_text" ||
                die "cmdline says protected, but Protected KVM CPU feature was not detected"
            grep -Fq 'Kylin X Core initialized successfully' <<<"$dmesg_text" ||
                die "cmdline says protected, but Kylin X Core initialization marker is missing"
            if grep -Fq 'Protected KVM not available with VHE' <<<"$dmesg_text"; then
                die "protected KVM was rejected because the kernel remained in VHE"
            fi
            ;;
        nvhe)
            grep -Fq 'Hyp mode initialized successfully' <<<"$dmesg_text" ||
                die "cmdline says nvhe, but Hyp mode initialization marker is missing"
            if grep -Fq 'CPU features: detected: Protected KVM' <<<"$dmesg_text"; then
                die "cmdline says nvhe, but Protected KVM was detected"
            fi
            ;;
        vhe)
            grep -Fq 'VHE mode initialized successfully' <<<"$dmesg_text" ||
                die "VHE initialization marker not found"
            ;;
    esac
}

ensure_layout() {
    sudo mkdir -p "$WORK_ROOT"/{redis,rabbitmq,traces,tmp}
    sudo chown -R "$(id -u):$(id -g)" "$WORK_ROOT"
    mkdir -p "$EXP_HOME"/{scripts,configs,utils,tools,src,build,results,state,logs,metadata}
    ln -sfn "$WORK_ROOT" "$EXP_HOME/work"
}

free_gib() { df -BG --output=avail "$1" | tail -n 1 | tr -dc '0-9'; }

space_guard() {
    local root_free home_free
    root_free=$(free_gib /)
    home_free=$(free_gib /home)
    (( root_free >= MIN_ROOT_FREE_GIB )) || die "root free space ${root_free}GiB < ${MIN_ROOT_FREE_GIB}GiB"
    (( home_free >= MIN_HOME_FREE_GIB )) || die "/home free space ${home_free}GiB < ${MIN_HOME_FREE_GIB}GiB"
}

set_thp() {
    local value=$1 current
    validate_thp_profile "$value"
    [[ -e /sys/kernel/mm/transparent_hugepage/enabled ]] || return 0
    printf '%s\n' "$value" | sudo tee /sys/kernel/mm/transparent_hugepage/enabled >/dev/null
    current=$(cat /sys/kernel/mm/transparent_hugepage/enabled)
    [[ "$current" == *"[$value]"* ]] ||
        die "THP write did not take effect: requested=$value current=$current"
}

thp_for_project() {
    local project=$1 profile=${THP_PROFILE:-never}
    case "$project" in
        anchors|redis|rabbitmq|geekbench) ;;
        *) die "unknown project for THP policy: $project" ;;
    esac
    validate_thp_profile "$profile"
    printf '%s\n' "$profile"
}

set_project_thp() {
    local project=$1 value
    value=$(thp_for_project "$project")
    set_thp "$value"
    log "THP profile=${THP_PROFILE:-never} project=$project effective=$value"
}

cooldown() {
    log "cooldown ${COOLDOWN_SECONDS}s"
    sleep "$COOLDOWN_SECONDS"
}

wait_port() {
    local host=$1 port=$2 timeout=${3:-60} i
    for ((i=0; i<timeout; i++)); do
        if timeout 1 bash -c "exec 3<>/dev/tcp/$host/$port" 2>/dev/null; then return 0; fi
        sleep 1
    done
    return 1
}

run_dir() {
    local phase=$1 scenario=$2 rep=$3 mode pair
    mode=$(mode_from_cmdline)
    pair=${PAIR_INDEX:-screen}
    printf '%s/%s/pair-%s/%s/%s/rep-%02d\n' "$RESULTS_DIR" "${CAMPAIGN_ID:-manual}" "$pair" "$mode" "$phase-$scenario" "$rep"
}

capture_metadata() {
    local out=$1
    mkdir -p "$out"
    {
        printf 'captured_at=%s\n' "$(timestamp)"
        printf 'mode=%s\n' "$(mode_from_cmdline)"
        printf 'hostname=%s\n' "$(hostname)"
        printf 'kernel=%s\n' "$(uname -a)"
        printf 'cmdline=%s\n' "$(</proc/cmdline)"
        printf 'git_revision=%s\n' "$(cat "$EXP_HOME/SOURCE_REVISION" 2>/dev/null || echo unknown)"
        printf 'thp=%s\n' "$(cat /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null || echo unavailable)"
        printf 'thp_profile=%s\n' "${THP_PROFILE:-never}"
        printf 'aslr=%s\n' "$(cat /proc/sys/kernel/randomize_va_space)"
        printf 'swap=%s\n' "$(swapon --show --noheadings 2>/dev/null | tr '\n' ';')"
        printf 'root_free_gib=%s\n' "$(free_gib /)"
        printf 'home_free_gib=%s\n' "$(free_gib /home)"
    } >"$out/metadata.env"
    lscpu --extended >"$out/lscpu.txt"
    free -h >"$out/free.txt"
    sudo dmesg >"$out/dmesg.txt"
    cp /proc/cmdline "$out/cmdline.txt"
    for cpu in /sys/devices/system/cpu/cpu[0-9]*; do
        [[ -f "$cpu/cpufreq/scaling_cur_freq" ]] || continue
        printf '%s %s %s\n' "${cpu##*/}" "$(cat "$cpu/cpufreq/scaling_governor")" "$(cat "$cpu/cpufreq/scaling_cur_freq")"
    done >"$out/cpufreq.txt"
}

write_status() {
    local text=$1
    printf '%s %s\n' "$(timestamp)" "$text" >"$STATE_DIR/status"
    log "$text"
}
