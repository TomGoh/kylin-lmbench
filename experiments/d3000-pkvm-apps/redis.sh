#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

REDIS_SERVER="$TOOLS_DIR/bin/redis-server"
REDIS_CLI="$TOOLS_DIR/bin/redis-cli"
MEMTIER="$TOOLS_DIR/bin/memtier_benchmark"
SEED_RDB="$WORK_ROOT/redis/seed-8g/dump.rdb"
SEED_META="$WORK_ROOT/redis/seed-8g/seed.env"
REDIS_PID=''

redis_config() {
    local dir=$1 policy=${2:-noeviction} maxmemory=${3:-0}
    cat >"$dir/redis.conf" <<EOF
bind 127.0.0.1
protected-mode no
port $REDIS_PORT
daemonize no
supervised no
dir $dir
dbfilename dump.rdb
save ""
appendonly no
rdbcompression no
rdbchecksum yes
maxmemory $maxmemory
maxmemory-policy $policy
latency-monitor-threshold 1
loglevel notice
EOF
}

start_redis() {
    local dir=$1 policy=${2:-noeviction} maxmemory=${3:-0} load_seed=${4:-yes}
    mkdir -p "$dir"
    if [[ "$load_seed" == yes ]]; then
        [[ -s "$SEED_RDB" ]] || die "Redis seed missing: $SEED_RDB"
        cp --reflink=auto --sparse=always "$SEED_RDB" "$dir/dump.rdb"
    fi
    redis_config "$dir" "$policy" "$maxmemory"
    taskset -c "$SERVER_CPUS" "$REDIS_SERVER" "$dir/redis.conf" >"$dir/server.log" 2>&1 &
    REDIS_PID=$!
    printf '%s\n' "$REDIS_PID" >"$dir/server.pid"
    local reply='' ready=no
    for _ in $(seq 1 300); do
        if ! kill -0 "$REDIS_PID" 2>/dev/null; then
            tail -n 100 "$dir/server.log" >&2
            die "Redis exited while loading its dataset"
        fi
        reply=$("$REDIS_CLI" -p "$REDIS_PORT" ping 2>/dev/null || true)
        if [[ "$reply" == PONG ]]; then ready=yes; break; fi
        sleep 1
    done
    if [[ "$ready" != yes ]]; then
        tail -n 100 "$dir/server.log" >&2
        kill "$REDIS_PID" 2>/dev/null || true
        die "Redis did not become ready within 300 seconds; last reply=${reply:-none}"
    fi
    if [[ "$load_seed" == yes ]]; then
        local keys expected
        keys=$("$REDIS_CLI" -p "$REDIS_PORT" dbsize)
        expected=$(sed -n 's/^keys=//p' "$SEED_META")
        [[ "$keys" == "$expected" ]] || die "seed key count mismatch: expected=$expected actual=$keys"
    fi
}

stop_redis() {
    "$REDIS_CLI" -p "$REDIS_PORT" shutdown nosave >/dev/null 2>&1 || true
    if [[ -n "$REDIS_PID" ]]; then
        wait "$REDIS_PID" 2>/dev/null || true
    fi
    REDIS_PID=''
}

redis_info() {
    local out=$1
    mkdir -p "$out"
    "$REDIS_CLI" -p "$REDIS_PORT" info all >"$out/info.txt"
    "$REDIS_CLI" -p "$REDIS_PORT" latency latest >"$out/latency-latest.txt"
    "$REDIS_CLI" -p "$REDIS_PORT" latency histogram >"$out/latency-histogram.txt"
}

memtier_base() {
    local out=$1 duration=$2 ratio=$3 pipeline=$4
    local keys
    keys=$(sed -n 's/^keys=//p' "$SEED_META")
    printf '%s\0' \
        "$MEMTIER" --server=127.0.0.1 --port="$REDIS_PORT" --protocol=redis \
        --threads=4 --clients=25 --ratio="$ratio" --pipeline="$pipeline" \
        --key-pattern=R:R --distinct-client-seed --key-minimum=1 --key-maximum="$keys" \
        --key-prefix=k: --test-time="$duration" --run-count=1 \
        --print-percentiles=50,95,99,99.9 \
        --json-out-file="$out/memtier.json" --hdr-file-prefix="$out/memtier-hdr" \
        --out-file="$out/memtier.txt"
}

run_memtier() {
    local out=$1 duration=$2 ratio=$3 pipeline=$4 rate_total=${5:-0}
    shift 5 || true
    local -a cmd=()
    while IFS= read -r -d '' arg; do cmd+=("$arg"); done < <(memtier_base "$out" "$duration" "$ratio" "$pipeline")
    if (( rate_total > 0 )); then
        # memtier rate limiting is per connection: 4 threads * 25 clients = 100.
        local per_connection=$(( (rate_total + 99) / 100 ))
        cmd+=("--rate-limiting=$per_connection")
        printf 'requested_total=%s\nper_connection=%s\nactual_target=%s\n' \
            "$rate_total" "$per_connection" "$((per_connection * 100))" >"$out/rate.env"
    fi
    cmd+=("$@")
    printf '%q ' taskset -c "$CLIENT_CPUS" "${cmd[@]}" >"$out/command.sh"
    printf '\n' >>"$out/command.sh"
    taskset -c "$CLIENT_CPUS" "${cmd[@]}"
}

prepare_seed() {
    ensure_layout
    set_thp never
    local seed_dir="$WORK_ROOT/redis/seed-build" batch=1000000 next=1 target=$((8 * 1024 * 1024 * 1024))
    rm -rf "$seed_dir"
    mkdir -p "$seed_dir" "$(dirname "$SEED_RDB")"
    start_redis "$seed_dir" noeviction 0 no
    trap stop_redis EXIT
    while :; do
        log "Redis seed: adding keys $next..$((next + batch - 1))"
        "$TOOLS_DIR/bin/redis-seed-generator" "$next" "$batch" 1024 |
            "$REDIS_CLI" -p "$REDIS_PORT" --pipe | tee -a "$seed_dir/pipe.log"
        next=$((next + batch))
        used=$("$REDIS_CLI" -p "$REDIS_PORT" info memory | sed -n 's/^used_memory:\([0-9]*\).*/\1/p')
        keys=$("$REDIS_CLI" -p "$REDIS_PORT" dbsize)
        log "Redis seed: keys=$keys used_memory=$used"
        (( used >= target )) && break
    done
    "$REDIS_CLI" -p "$REDIS_PORT" save
    redis_info "$seed_dir"
    stop_redis
    trap - EXIT
    mv "$seed_dir/dump.rdb" "$SEED_RDB"
    used=$(sed -n 's/^used_memory:\([0-9]*\).*/\1/p' "$seed_dir/info.txt")
    keys=$(sed -n 's/^db0:keys=\([0-9]*\).*/\1/p' "$seed_dir/info.txt")
    {
        printf 'created_at=%s\n' "$(timestamp)"
        printf 'keys=%s\n' "$keys"
        printf 'used_memory=%s\n' "$used"
        printf 'rdb_sha256=%s\n' "$(sha256sum "$SEED_RDB" | cut -d' ' -f1)"
    } >"$SEED_META"
    cp "$SEED_META" "$EXP_HOME/metadata/redis-seed.env"
    log "Redis seed complete: keys=$keys used_memory=$used"
}

one_run() {
    local scenario=$1 rep=$2 duration ratio pipeline rate policy=noeviction maxmemory=0
    local out
    out=$(run_dir redis "$scenario" "$rep")
    record_note redis "start scenario=$scenario rep=$rep output=$out"
    rm -rf "$out"
    mkdir -p "$out"
    case "$scenario" in
        calibration) duration=$REDIS_CALIBRATION_SECONDS; ratio=1:10; pipeline=1; rate=0 ;;
        r1-steady) duration=$REDIS_STEADY_SECONDS; ratio=1:10; pipeline=1; rate=$(cat "$STATE_DIR/redis-rate-70") ;;
        r2-pipeline) duration=$REDIS_THROUGHPUT_SECONDS; ratio=1:1; pipeline=16; rate=0 ;;
        r3-ttl-eviction) duration=$REDIS_STEADY_SECONDS; ratio=1:1; pipeline=1; rate=$(cat "$STATE_DIR/redis-rate-70"); policy=allkeys-lru; maxmemory=10gb ;;
        r4-bgsave) duration=$REDIS_BGSAVE_SECONDS; ratio=1:1; pipeline=1; rate=$(cat "$STATE_DIR/redis-rate-70") ;;
        *) die "unknown Redis scenario: $scenario" ;;
    esac

    local data_dir="$WORK_ROOT/redis/run-${CAMPAIGN_ID:-manual}-${PAIR_INDEX:-0}-$(mode_from_cmdline)-$scenario-$rep"
    rm -rf "$data_dir"
    start_redis "$data_dir" "$policy" "$maxmemory" yes
    trap stop_redis EXIT
    redis_info "$out/before"
    pidstat -h -r -u -p "$REDIS_PID" 1 >"$out/pidstat.txt" 2>&1 & monitor=$!

    extra=()
    if [[ "$scenario" == r3-ttl-eviction ]]; then
        extra+=(--data-size-range=64-4096 --data-size-pattern=R --expiry-range=60-300)
    else
        extra+=(--data-size=1024)
    fi

    if [[ "$scenario" == r4-bgsave ]]; then
        run_memtier "$out" "$duration" "$ratio" "$pipeline" "$rate" "${extra[@]}" & client=$!
        sleep 120
        printf '%s first_start\n' "$(timestamp)" >>"$out/bgsave-events.txt"
        "$REDIS_CLI" -p "$REDIS_PORT" bgsave >>"$out/bgsave-events.txt"
        while [[ $("$REDIS_CLI" -p "$REDIS_PORT" info persistence | sed -n 's/^rdb_bgsave_in_progress:\([01]\).*/\1/p') == 1 ]]; do sleep 1; done
        printf '%s first_done\n' "$(timestamp)" >>"$out/bgsave-events.txt"
        now=$(date +%s); target=$(( $(stat -c %Y "$out/command.sh") + 240 )); (( target > now )) && sleep $((target-now))
        printf '%s second_start\n' "$(timestamp)" >>"$out/bgsave-events.txt"
        "$REDIS_CLI" -p "$REDIS_PORT" bgsave >>"$out/bgsave-events.txt"
        wait "$client"
        while [[ $("$REDIS_CLI" -p "$REDIS_PORT" info persistence | sed -n 's/^rdb_bgsave_in_progress:\([01]\).*/\1/p') == 1 ]]; do sleep 1; done
        printf '%s second_done\n' "$(timestamp)" >>"$out/bgsave-events.txt"
    else
        run_memtier "$out" "$duration" "$ratio" "$pipeline" "$rate" "${extra[@]}"
    fi
    kill "$monitor" 2>/dev/null || true
    wait "$monitor" 2>/dev/null || true
    redis_info "$out/after"
    stop_redis
    trap - EXIT
    rm -rf "$data_dir"
    touch "$out/VALID"
    record_note redis "valid scenario=$scenario rep=$rep output=$out"
}

run_group() {
    local scenario=$1 rep
    for rep in $(seq 1 "$REPETITIONS"); do
        space_guard
        one_run "$scenario" "$rep"
        cooldown
    done
}

case "${1:-}" in
    seed) prepare_seed ;;
    run) run_group "${2:?scenario required}" ;;
    one) one_run "${2:?scenario required}" "${3:?rep required}" ;;
    *) die "usage: redis.sh seed|run SCENARIO|one SCENARIO REP" ;;
esac
