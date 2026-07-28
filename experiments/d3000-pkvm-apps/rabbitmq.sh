#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

PERFTEST_JAR="$TOOLS_DIR/perf-test-${PERFTEST_VERSION}.jar"
RABBIT_NAME=d3000-pkvm-rabbit
RABBIT_URI="amqp://${RABBITMQ_USER}:${RABBITMQ_PASSWORD}@127.0.0.1:${RABBITMQ_PORT}/%2f"
RABBIT_DATA=''
RABBIT_PID=''

image_ref() {
    local digest_file="$EXP_HOME/metadata/rabbitmq-image-digests.txt"
    [[ -s "$digest_file" ]] && head -n 1 "$digest_file" || printf '%s\n' "$RABBITMQ_IMAGE"
}

start_rabbit() {
    local label=$1 image pid
    RABBIT_DATA="$WORK_ROOT/rabbitmq/$label"
    sudo docker rm -f "$RABBIT_NAME" >/dev/null 2>&1 || true
    sudo rm -rf "$RABBIT_DATA"
    sudo mkdir -p "$RABBIT_DATA"
    sudo chown 999:999 "$RABBIT_DATA"
    printf '%s\n' 'D3000PKVMBENCHCOOKIE20260713' | sudo tee "$RABBIT_DATA/.erlang.cookie" >/dev/null
    sudo chown 999:999 "$RABBIT_DATA/.erlang.cookie"
    sudo chmod 0400 "$RABBIT_DATA/.erlang.cookie"
    image=$(image_ref)
    log "starting RabbitMQ image=$image data=$RABBIT_DATA"
    sudo docker run -d --pull=never --name "$RABBIT_NAME" --hostname d3000-rabbit \
        --network host --cpuset-cpus "$SERVER_CPUS" \
        -e RABBITMQ_DEFAULT_USER="$RABBITMQ_USER" \
        -e RABBITMQ_DEFAULT_PASS="$RABBITMQ_PASSWORD" \
        -e RABBITMQ_SERVER_ADDITIONAL_ERL_ARGS='+S 4:4' \
        -v "$RABBIT_DATA:/var/lib/rabbitmq" "$image" >/dev/null
    for _ in $(seq 1 120); do
        if sudo docker exec "$RABBIT_NAME" rabbitmq-diagnostics -q ping >/dev/null 2>&1; then break; fi
        sleep 1
    done
    sudo docker exec "$RABBIT_NAME" rabbitmq-diagnostics -q check_running
    wait_port 127.0.0.1 "$RABBITMQ_PORT" 60 || die "RabbitMQ AMQP port did not open"
    pid=$(sudo docker inspect --format '{{.State.Pid}}' "$RABBIT_NAME")
    RABBIT_PID=$pid
}

stop_rabbit() {
    local out=${1:-}
    if [[ -n "$out" ]]; then
        sudo docker logs "$RABBIT_NAME" >"$out/container.log" 2>&1 || true
        sudo docker inspect "$RABBIT_NAME" >"$out/container-inspect.json" 2>&1 || true
    fi
    sudo docker rm -f "$RABBIT_NAME" >/dev/null 2>&1 || true
    [[ -z "$RABBIT_DATA" ]] || sudo rm -rf "$RABBIT_DATA"
    RABBIT_DATA=''
    RABBIT_PID=''
}

rabbit_snapshot() {
    local out=$1
    mkdir -p "$out"
    sudo docker exec "$RABBIT_NAME" rabbitmq-diagnostics status --formatter json >"$out/status.json"
    sudo docker exec "$RABBIT_NAME" rabbitmq-diagnostics memory_breakdown --formatter json >"$out/memory.json"
    sudo docker exec "$RABBIT_NAME" rabbitmqctl list_queues name durable auto_delete messages_ready messages_unacknowledged memory \
        --formatter json >"$out/queues.json"
    sudo docker stats --no-stream --format '{{json .}}' "$RABBIT_NAME" >"$out/docker-stats.json"
}

perftest() {
    local out=$1 id=$2 duration=$3 rc
    shift 3
    mkdir -p "$out"
    local -a cmd=(java -jar "$PERFTEST_JAR" --uri "$RABBIT_URI" --id "$id" --size 1000
        --time "$duration" --interval 1 --metrics-format compact --output-file "$out/perftest.csv")
    cmd+=("$@")
    printf '%q ' taskset -c "$CLIENT_CPUS" "${cmd[@]}" >"$out/command.sh"
    printf '\n' >>"$out/command.sh"
    if /usr/bin/time -v -o "$out/time.txt" taskset -c "$CLIENT_CPUS" "${cmd[@]}" \
        >"$out/stdout.txt" 2>"$out/stderr.txt"; then
        rc=0
    else
        rc=$?
    fi
    (( rc == 0 )) || die "PerfTest failed id=$id rc=$rc; see $out/stderr.txt"
    if grep -Fq 'Parsing failed' "$out/stderr.txt"; then
        die "PerfTest rejected its command line for id=$id; see $out/stderr.txt"
    fi
    [[ -s "$out/perftest.csv" ]] || die "PerfTest produced no CSV for id=$id"
    [[ $(wc -l <"$out/perftest.csv") -ge 2 ]] || die "PerfTest CSV has no data rows for id=$id"
    head -n 1 "$out/perftest.csv" | grep -Fq 'published (msg/s)' ||
        die "PerfTest CSV has an unexpected header for id=$id"
    touch "$out/PERFTEST_VALID"
}

warmup() {
    local out=$1
    perftest "$out/warmup" warmup "$RABBIT_WARMUP_SECONDS" --producers 1 --consumers 1 --queue warmup \
        --auto-delete true --confirm 500 --qos 500
    cooldown
}

q3_values() {
    local scenario=$1 pct common producers requested_total per_producer effective_total
    [[ "$scenario" =~ ^q3-rate(50|70|85)$ ]] || die "not a Q3 scenario: $scenario"
    pct=${scenario#q3-rate}
    common=$(<"$STATE_DIR/rabbit-rate-common")
    producers=$RABBIT_Q3_PRODUCERS
    [[ "$common" =~ ^[0-9]+$ && "$producers" =~ ^[1-9][0-9]*$ ]] ||
        die "invalid Q3 inputs: common=$common producers=$producers"
    requested_total=$((common * pct / 100))
    per_producer=$(((requested_total + producers - 1) / producers))
    effective_total=$((per_producer * producers))
    printf '%s %s %s %s %s %s\n' "$pct" "$common" "$producers" "$requested_total" "$per_producer" "$effective_total"
}

write_q3_target() {
    local out=$1 scenario=$2 pct common producers requested_total per_producer effective_total
    read -r pct common producers requested_total per_producer effective_total < <(q3_values "$scenario")
    {
        printf 'scenario=%s\n' "$scenario"
        printf 'capacity_common_msg_s=%s\n' "$common"
        printf 'percentage=%s\n' "$pct"
        printf 'producer_count=%s\n' "$producers"
        printf 'requested_total_msg_s=%s\n' "$requested_total"
        printf 'per_producer_rate_arg=%s\n' "$per_producer"
        printf 'effective_total_target_msg_s=%s\n' "$effective_total"
    } >"$out/rate-target.env"
}

validate_q3_rate() {
    local out=$1 target samples observed error_pct
    target=$(sed -n 's/^effective_total_target_msg_s=//p' "$out/rate-target.env")
    if ! read -r samples observed < <(
        awk -F, -v cutoff="$RABBIT_Q3_RATE_DISCARD_SECONDS" '
            NR == 1 {
                for (i = 1; i <= NF; i++) {
                    if ($i == "time (s)") time_col = i
                    if ($i == "published (msg/s)") published_col = i
                }
                next
            }
            time_col && published_col && ($time_col + 0) >= cutoff && $published_col != "" {
                sum += $published_col
                count++
            }
            END {
                if (!count) exit 1
                printf "%d %.6f\n", count, sum / count
            }
        ' "$out/perftest.csv"
    ); then
        die "cannot calculate Q3 observed rate from $out/perftest.csv"
    fi
    (( samples >= RABBIT_Q3_RATE_MIN_SAMPLES )) ||
        die "Q3 rate validation has only $samples samples; need $RABBIT_Q3_RATE_MIN_SAMPLES"
    error_pct=$(awk -v observed="$observed" -v target="$target" 'BEGIN { printf "%.4f", (observed / target - 1) * 100 }')
    {
        printf 'samples=%s\n' "$samples"
        printf 'observed_mean_published_msg_s=%s\n' "$observed"
        printf 'target_msg_s=%s\n' "$target"
        printf 'error_pct=%s\n' "$error_pct"
        printf 'tolerance_pct=%s\n' "$RABBIT_Q3_RATE_TOLERANCE_PCT"
    } >"$out/rate-validation.env"
    awk -v error="$error_pct" -v tolerance="$RABBIT_Q3_RATE_TOLERANCE_PCT" \
        'BEGIN { if (error < 0) error = -error; exit !(error <= tolerance) }' ||
        die "Q3 published rate missed target by ${error_pct}% (allowed +/-${RABBIT_Q3_RATE_TOLERANCE_PCT}%)"
}

q5_snapshot_and_assert() {
    local out=$1 expected_ready=$2 expected_unacked=$3 counts ready unacked
    mkdir -p "$out"
    sudo docker exec "$RABBIT_NAME" rabbitmqctl list_queues name messages_ready messages_unacknowledged \
        --formatter json >"$out/queues.json"
    if ! counts=$(jq -er --arg queue q5-backlog '
        [.[] | select(.name == $queue)] |
        if length == 1 then "\(.[0].messages_ready) \(.[0].messages_unacknowledged)"
        else error("expected exactly one q5-backlog queue") end
    ' "$out/queues.json"); then
        die "cannot read q5-backlog counts from $out/queues.json"
    fi
    read -r ready unacked <<<"$counts"
    {
        printf 'messages_ready=%s\n' "$ready"
        printf 'messages_unacknowledged=%s\n' "$unacked"
        printf 'expected_ready=%s\n' "$expected_ready"
        printf 'expected_unacknowledged=%s\n' "$expected_unacked"
    } >"$out/validation.env"
    [[ "$ready" == "$expected_ready" && "$unacked" == "$expected_unacked" ]] ||
        die "Q5 queue count mismatch: ready=$ready/$expected_ready unacked=$unacked/$expected_unacked"
    touch "$out/QUEUE_COUNTS_VALID"
}

scenario_args() {
    local scenario=$1
    case "$scenario" in
        calibration|q2-reliable)
            printf '%s\0' --producers 8 --consumers 8 --queue-pattern "${scenario}-%d" \
                --queue-pattern-from 1 --queue-pattern-to 8 --confirm 500 --qos 500 \
                --multi-ack-every 100 --flag persistent --auto-delete false
            ;;
        q1-one-fast)
            printf '%s\0' --producers 1 --consumers 1 --queue q1-one-fast \
                --auto-delete true --qos 500
            ;;
        q3-rate50|q3-rate70|q3-rate85)
            read -r _ _ producers _ rate _ < <(q3_values "$scenario")
            printf '%s\0' --producers "$producers" --consumers "$producers" --queue-pattern "${scenario}-%d" \
                --queue-pattern-from 1 --queue-pattern-to "$producers" --confirm 500 --qos 500 \
                --multi-ack-every 100 --flag persistent --auto-delete false --rate "$rate"
            ;;
        q4-join-late)
            printf '%s\0' --producers 1 --consumers 10 --queue q4-join-late \
                --confirm 100 --qos 300 --flag persistent --auto-delete false \
                --rate 10000 --consumer-start-delay 120
            ;;
        *) die "unknown RabbitMQ scenario: $scenario" ;;
    esac
}

one_regular_run() {
    local scenario=$1 rep=$2 duration out host_pid monitor
    out=$(run_dir rabbitmq "$scenario" "$rep")
    record_note rabbitmq "start scenario=$scenario rep=$rep output=$out"
    rm -rf "$out"; mkdir -p "$out"
    case "$scenario" in
        calibration) duration=$RABBIT_CALIBRATION_SECONDS ;;
        *) duration=$RABBIT_STEADY_SECONDS ;;
    esac
    start_rabbit "run-${CAMPAIGN_ID:-manual}-${PAIR_INDEX:-0}-$(mode_from_cmdline)-$scenario-$rep"
    trap 'stop_rabbit "$out"' EXIT
    warmup "$out"
    rabbit_snapshot "$out/before"
    host_pid=$RABBIT_PID
    pidstat -h -r -u -p "$host_pid" 1 >"$out/pidstat.txt" 2>&1 & monitor=$!
    args=(); while IFS= read -r -d '' arg; do args+=("$arg"); done < <(scenario_args "$scenario")
    if [[ "$scenario" =~ ^q3-rate(50|70|85)$ ]]; then
        write_q3_target "$out" "$scenario"
    fi
    perftest "$out" "$scenario" "$duration" "${args[@]}"
    if [[ "$scenario" =~ ^q3-rate(50|70|85)$ ]]; then
        validate_q3_rate "$out"
    fi
    kill "$monitor" 2>/dev/null || true; wait "$monitor" 2>/dev/null || true
    rabbit_snapshot "$out/after"
    stop_rabbit "$out"
    trap - EXIT
    touch "$out/VALID"
    record_note rabbitmq "valid scenario=$scenario rep=$rep output=$out"
}

one_backlog_run() {
    local rep=$1 out host_pid monitor
    out=$(run_dir rabbitmq q5-backlog "$rep")
    record_note rabbitmq "start scenario=q5-backlog rep=$rep output=$out"
    rm -rf "$out"; mkdir -p "$out"
    start_rabbit "run-${CAMPAIGN_ID:-manual}-${PAIR_INDEX:-0}-$(mode_from_cmdline)-q5-backlog-$rep"
    trap 'stop_rabbit "$out"' EXIT
    warmup "$out"
    rabbit_snapshot "$out/before"
    host_pid=$RABBIT_PID
    pidstat -h -r -u -p "$host_pid" 1 >"$out/pidstat.txt" 2>&1 & monitor=$!
    perftest "$out/fill" q5-fill "$RABBIT_Q5_TIMEOUT_SECONDS" --producers 1 --consumers 0 --queue q5-backlog \
        --pmessages "$RABBIT_Q5_MESSAGES" --confirm 500 --flag persistent --auto-delete false
    q5_snapshot_and_assert "$out/after-fill" "$RABBIT_Q5_MESSAGES" 0
    perftest "$out/drain" q5-drain "$RABBIT_Q5_TIMEOUT_SECONDS" --predeclared --producers 0 --consumers 4 --queue q5-backlog \
        --cmessages "$RABBIT_Q5_MESSAGES" --qos 500 --multi-ack-every 100 --exit-when empty
    q5_snapshot_and_assert "$out/after-drain" 0 0
    kill "$monitor" 2>/dev/null || true; wait "$monitor" 2>/dev/null || true
    rabbit_snapshot "$out/after"
    stop_rabbit "$out"
    trap - EXIT
    touch "$out/VALID"
    record_note rabbitmq "valid scenario=q5-backlog rep=$rep output=$out"
}

run_group() {
    local scenario=$1 rep
    for rep in $(seq 1 "$REPETITIONS"); do
        space_guard
        if [[ "$scenario" == q5-backlog ]]; then one_backlog_run "$rep"; else one_regular_run "$scenario" "$rep"; fi
        cooldown
    done
}

case "${1:-}" in
    run) run_group "${2:?scenario required}" ;;
    one)
        if [[ ${2:-} == q5-backlog ]]; then one_backlog_run "${3:?rep required}"; else one_regular_run "${2:?scenario required}" "${3:?rep required}"; fi
        ;;
    q3-values) q3_values "${2:?Q3 scenario required}" ;;
    invalid-option-selftest)
        out=${2:?output directory required}
        rm -rf "$out"
        perftest "$out" invalid-option-selftest 1 --definitely-not-a-perftest-option
        die "invalid option unexpectedly passed PerfTest validation"
        ;;
    *) die "usage: rabbitmq.sh run SCENARIO|one SCENARIO REP|q3-values SCENARIO|invalid-option-selftest OUT" ;;
esac
