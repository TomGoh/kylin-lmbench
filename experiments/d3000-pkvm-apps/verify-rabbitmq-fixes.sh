#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

[[ ! -e "$STATE_DIR/campaign-enabled" ]] || die "cannot verify fixes while a campaign is enabled"
require_cmd awk grep jq sha256sum
[[ -s "$STATE_DIR/rabbit-rate-common" ]] || die "missing prior RabbitMQ capacity for targeted Q3 smoke"

verification_id="rabbit-fix-verification-$(date +%Y%m%d-%H%M%S)"
mode=$(mode_from_cmdline)
VERIFY_THP_PROFILE=${VERIFY_THP_PROFILE:-never}
validate_thp_profile "$VERIFY_THP_PROFILE"
export THP_PROFILE=$VERIFY_THP_PROFILE
root="$RESULTS_DIR/$verification_id"
negative_out="$root/invalid-option"
q3_out="$root/pair-verification/$mode/rabbitmq-q3-rate50/rep-01"
q5_out="$root/pair-verification/$mode/rabbitmq-q5-backlog/rep-01"

cleanup() {
    sudo docker rm -f d3000-pkvm-rabbit >/dev/null 2>&1 || true
    if [[ -e "$STATE_DIR/host-prepared" ]]; then
        "$SCRIPT_DIR/restore-host.sh" || true
    fi
}
trap cleanup EXIT

mkdir -p "$root"
record_note verification "starting RabbitMQ Q3/Q5 fix verification id=$verification_id mode=$mode"

if "$SCRIPT_DIR/rabbitmq.sh" invalid-option-selftest "$negative_out"; then
    die "negative self-test unexpectedly accepted an invalid PerfTest option"
fi
grep -Fq 'Parsing failed' "$negative_out/stderr.txt" || die "negative self-test did not exercise PerfTest parse failure"
[[ ! -e "$negative_out/PERFTEST_VALID" ]] || die "negative self-test incorrectly created PERFTEST_VALID"
touch "$negative_out/EXPECTED_FAILURE_VALIDATED"

"$SCRIPT_DIR/prepare-host.sh"
set_project_thp rabbitmq

CAMPAIGN_ID="$verification_id" PAIR_INDEX=verification THP_PROFILE="$VERIFY_THP_PROFILE" \
RABBIT_WARMUP_SECONDS=10 COOLDOWN_SECONDS=2 RABBIT_STEADY_SECONDS=45 \
RABBIT_Q3_RATE_DISCARD_SECONDS=5 RABBIT_Q3_RATE_MIN_SAMPLES=30 RABBIT_Q3_RATE_TOLERANCE_PCT=5 \
    "$SCRIPT_DIR/rabbitmq.sh" one q3-rate50 1
[[ -e "$q3_out/VALID" && -e "$q3_out/PERFTEST_VALID" && -s "$q3_out/rate-validation.env" ]] ||
    die "Q3 targeted smoke did not produce all validity markers"

CAMPAIGN_ID="$verification_id" PAIR_INDEX=verification THP_PROFILE="$VERIFY_THP_PROFILE" \
RABBIT_WARMUP_SECONDS=10 COOLDOWN_SECONDS=2 RABBIT_Q5_MESSAGES=100000 RABBIT_Q5_TIMEOUT_SECONDS=180 \
    "$SCRIPT_DIR/rabbitmq.sh" one q5-backlog 1
[[ -e "$q5_out/VALID" && -e "$q5_out/fill/PERFTEST_VALID" && -e "$q5_out/drain/PERFTEST_VALID" ]] ||
    die "Q5 targeted smoke did not produce all PerfTest validity markers"
[[ -e "$q5_out/after-fill/QUEUE_COUNTS_VALID" && -e "$q5_out/after-drain/QUEUE_COUNTS_VALID" ]] ||
    die "Q5 targeted smoke did not produce queue-count validity markers"
grep -Fxq 'messages_ready=100000' "$q5_out/after-fill/validation.env" || die "Q5 fill count is not 100000"
grep -Fxq 'messages_ready=0' "$q5_out/after-drain/validation.env" || die "Q5 drain did not empty the queue"
grep -Fxq 'messages_unacknowledged=0' "$q5_out/after-drain/validation.env" || die "Q5 drain left unacknowledged messages"

rabbitmq_sha256=$(sha256sum "$SCRIPT_DIR/rabbitmq.sh" | awk '{print $1}')
config_sha256=$(sha256sum "$SCRIPT_DIR/config.env" | awk '{print $1}')
runtime_hash=$(runtime_bundle_sha256 "$SCRIPT_DIR")
q3_target=$(sed -n 's/^target_msg_s=//p' "$q3_out/rate-validation.env")
q3_observed=$(sed -n 's/^observed_mean_published_msg_s=//p' "$q3_out/rate-validation.env")
marker="$STATE_DIR/rabbitmq-fixes-verified"
{
    printf 'verified_at=%s\n' "$(timestamp)"
    printf 'verification_id=%s\n' "$verification_id"
    printf 'mode=%s\n' "$mode"
    printf 'thp_profile=%s\n' "$VERIFY_THP_PROFILE"
    printf 'rabbitmq_sha256=%s\n' "$rabbitmq_sha256"
    printf 'config_sha256=%s\n' "$config_sha256"
    printf 'runtime_bundle_sha256=%s\n' "$runtime_hash"
    printf 'q3_target_msg_s=%s\n' "$q3_target"
    printf 'q3_observed_mean_msg_s=%s\n' "$q3_observed"
    printf 'q5_smoke_messages=%s\n' 100000
    printf 'q5_after_fill_ready=%s\n' 100000
    printf 'q5_after_drain_ready=%s\n' 0
    printf 'q5_after_drain_unacked=%s\n' 0
    printf 'negative_parse_failure_rejected=yes\n'
} >"$marker.next"
mv "$marker.next" "$marker"
cp "$marker" "$root/VERIFICATION_PASSED.env"
record_note verification "passed RabbitMQ Q3/Q5 fix verification id=$verification_id q3_target=$q3_target q3_observed=$q3_observed q5_fill=100000 q5_drain=0"
log "RabbitMQ fix verification passed: marker=$marker results=$root"
