#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

manifest() {
    cat <<'EOF'
1	calibration	calibration	nvhe	-
2	calibration	calibration	protected	-
3	formal	1	nvhe	geek,redis,rabbitmq
4	formal	1	protected	geek,redis,rabbitmq
5	formal	2	protected	redis,rabbitmq,geek
6	formal	2	nvhe	redis,rabbitmq,geek
7	formal	3	nvhe	rabbitmq,geek,redis
8	formal	3	protected	rabbitmq,geek,redis
9	formal	4	protected	geek,rabbitmq,redis
10	formal	4	nvhe	geek,rabbitmq,redis
11	formal	5	nvhe	redis,geek,rabbitmq
12	formal	5	protected	redis,geek,rabbitmq
EOF
}

verify_rabbitmq_fix_marker() {
    local marker="$STATE_DIR/rabbitmq-fixes-verified" expected_rabbit expected_config actual_rabbit actual_config
    [[ -s "$marker" ]] || die "RabbitMQ Q3/Q5 fixes have not passed the required smoke verification"
    expected_rabbit=$(sed -n 's/^rabbitmq_sha256=//p' "$marker")
    expected_config=$(sed -n 's/^config_sha256=//p' "$marker")
    actual_rabbit=$(sha256sum "$SCRIPT_DIR/rabbitmq.sh" | awk '{print $1}')
    actual_config=$(sha256sum "$SCRIPT_DIR/config.env" | awk '{print $1}')
    [[ -n "$expected_rabbit" && "$actual_rabbit" == "$expected_rabbit" ]] ||
        die "rabbitmq.sh changed after verification; rerun verify-rabbitmq-fixes.sh"
    [[ -n "$expected_config" && "$actual_config" == "$expected_config" ]] ||
        die "config.env changed after verification; rerun verify-rabbitmq-fixes.sh"
}

case "${1:-status}" in
    status)
        printf 'mode=%s\n' "$(mode_from_cmdline)"
        for f in campaign-id campaign-profile leg status completed-leg; do [[ -f "$STATE_DIR/$f" ]] && printf '%s=%s\n' "$f" "$(cat "$STATE_DIR/$f")"; done
        [[ -f "$STATE_DIR/campaign-enabled" ]] && echo campaign_enabled=yes || echo campaign_enabled=no
        sudo systemctl --no-pager --full status d3000-pkvm-campaign.service || true
        ;;
    smoke)
        [[ -f "$STATE_DIR/bootstrap-complete" ]] || die "bootstrap is incomplete"
        "$SCRIPT_DIR/prepare-host.sh"
        [[ -s "$WORK_ROOT/redis/seed-8g/dump.rdb" ]] || "$SCRIPT_DIR/redis.sh" seed
        export CAMPAIGN_ID=smoke PAIR_INDEX=vhe
        redis_valid="$RESULTS_DIR/smoke/pair-vhe/vhe/redis-calibration/rep-01/VALID"
        rabbit_valid="$RESULTS_DIR/smoke/pair-vhe/vhe/rabbitmq-calibration/rep-01/VALID"
        [[ -f "$redis_valid" ]] || REPETITIONS=1 COOLDOWN_SECONDS=2 REDIS_CALIBRATION_SECONDS=15 "$SCRIPT_DIR/redis.sh" one calibration 1
        [[ -f "$rabbit_valid" ]] || REPETITIONS=1 COOLDOWN_SECONDS=2 RABBIT_CALIBRATION_SECONDS=20 "$SCRIPT_DIR/rabbitmq.sh" one calibration 1
        mkdir -p "$RESULTS_DIR/smoke"
        "$TOOLS_DIR/geekbench-6.7.1/geekbench6" --sysinfo >"$RESULTS_DIR/smoke/geekbench-sysinfo.txt" 2>&1
        REPETITIONS=1 "$SCRIPT_DIR/run-anchors.sh" start
        touch "$STATE_DIR/smoke-complete"
        log "VHE smoke complete"
        ;;
    start)
        [[ -f "$STATE_DIR/bootstrap-complete" ]] || die "bootstrap is incomplete"
        [[ -f "$STATE_DIR/smoke-complete" ]] || die "smoke is incomplete"
        [[ ! -f "$STATE_DIR/campaign-enabled" ]] || die "campaign already enabled"
        verify_rabbitmq_fix_marker
        profile=${2:-app-default}
        [[ "$profile" == app-default || "$profile" == never ]] || die "THP profile must be app-default or never"
        campaign_id="d3000-apps-${profile}-$(date +%Y%m%d-%H%M%S)"
        manifest >"$STATE_DIR/manifest.tsv"
        printf '%s\n' "$campaign_id" >"$STATE_DIR/campaign-id"
        printf '%s\n' "$profile" >"$STATE_DIR/campaign-profile"
        printf '1\n' >"$STATE_DIR/leg"
        rm -f "$STATE_DIR/completed-leg" "$STATE_DIR/leg.next" "$STATE_DIR/rabbit-rate-common" \
            "$STATE_DIR/redis-rate-common" "$STATE_DIR/redis-rate-70"
        if [[ "$profile" == app-default ]]; then
            printf '%s\n' "$campaign_id" >"$STATE_DIR/thp-never-pending"
        fi
        touch "$STATE_DIR/campaign-enabled"
        sudo systemctl enable d3000-pkvm-campaign.service d3000-thp-never-chain.service
        "$SCRIPT_DIR/set-next-mode.sh" nvhe
        record_note campaign "initialized id=$campaign_id thp_profile=$profile"
        write_status "campaign=$campaign_id thp_profile=$profile initialized; rebooting into calibration nVHE"
        sync
        sudo systemctl reboot
        ;;
    stop)
        rm -f "$STATE_DIR/campaign-enabled"
        sudo systemctl stop d3000-pkvm-campaign.service || true
        sudo systemctl disable d3000-pkvm-campaign.service d3000-thp-never-chain.service || true
        sudo grub-editenv /boot/efi/boot/grub/grubenv unset next_entry || true
        sudo grub-editenv /boot/grub/grubenv unset next_entry || true
        "$SCRIPT_DIR/restore-host.sh"
        write_status "campaign stopped manually"
        ;;
    *) die "usage: campaign.sh status|smoke|start [app-default|never]|stop" ;;
esac
