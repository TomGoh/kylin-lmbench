#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

order=${1:?usage: run-boot-block.sh geek,redis,rabbitmq}
expected=${EXPECTED_MODE:-$(mode_from_cmdline)}
assert_mode "$expected"
space_guard
capture_metadata "$RESULTS_DIR/${CAMPAIGN_ID:?}/pair-${PAIR_INDEX:?}/$expected/boot-metadata"

"$SCRIPT_DIR/run-anchors.sh" start
IFS=, read -r -a projects <<<"$order"
for project in "${projects[@]}"; do
    write_status "pair=$PAIR_INDEX mode=$expected project=$project"
    case "$project" in
        geek) "$SCRIPT_DIR/run-geekbench.sh" ;;
        redis)
            set_project_thp redis
            for scenario in r1-steady r2-pipeline r3-ttl-eviction r4-bgsave; do "$SCRIPT_DIR/redis.sh" run "$scenario"; done
            ;;
        rabbitmq)
            set_project_thp rabbitmq
            for scenario in q1-one-fast q2-reliable q3-rate50 q3-rate70 q3-rate85 q4-join-late q5-backlog; do
                "$SCRIPT_DIR/rabbitmq.sh" run "$scenario"
            done
            ;;
        *) die "unknown project in boot order: $project" ;;
    esac
done
"$SCRIPT_DIR/run-anchors.sh" end
touch "$RESULTS_DIR/$CAMPAIGN_ID/pair-$PAIR_INDEX/$expected/BOOT_BLOCK_VALID"
