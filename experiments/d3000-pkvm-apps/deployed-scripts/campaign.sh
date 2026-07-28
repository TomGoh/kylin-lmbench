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

validate_manifest() {
    awk -F '\t' '
        NF != 5 || $1 != NR { bad = 1 }
        NR <= 2 && ($2 != "calibration" || $3 != "calibration") { bad = 1 }
        NR == 1 && $4 != "nvhe" { bad = 1 }
        NR == 2 && $4 != "protected" { bad = 1 }
        NR >= 3 {
            if ($2 != "formal" || $3 !~ /^[1-5]$/ || $4 !~ /^(nvhe|protected)$/) bad = 1
            seen[$3, $4]++
        }
        END {
            if (NR != 12) bad = 1
            for (pair = 1; pair <= 5; pair++) {
                if (seen[pair, "nvhe"] != 1 || seen[pair, "protected"] != 1) bad = 1
            }
            exit bad
        }
    ' < <(manifest) || die "campaign manifest failed structural validation"
}

verify_rabbitmq_fix_marker() {
    local marker="$STATE_DIR/rabbitmq-fixes-verified" expected_rabbit expected_config expected_bundle
    local actual_rabbit actual_config actual_bundle
    [[ -s "$marker" ]] || die "RabbitMQ Q3/Q5 fixes have not passed the required smoke verification"
    expected_rabbit=$(sed -n 's/^rabbitmq_sha256=//p' "$marker")
    expected_config=$(sed -n 's/^config_sha256=//p' "$marker")
    actual_rabbit=$(sha256sum "$SCRIPT_DIR/rabbitmq.sh" | awk '{print $1}')
    actual_config=$(sha256sum "$SCRIPT_DIR/config.env" | awk '{print $1}')
    [[ -n "$expected_rabbit" && "$actual_rabbit" == "$expected_rabbit" ]] ||
        die "rabbitmq.sh changed after verification; rerun verify-rabbitmq-fixes.sh"
    [[ -n "$expected_config" && "$actual_config" == "$expected_config" ]] ||
        die "config.env changed after verification; rerun verify-rabbitmq-fixes.sh"
    expected_bundle=$(sed -n 's/^runtime_bundle_sha256=//p' "$marker")
    actual_bundle=$(runtime_bundle_sha256 "$SCRIPT_DIR")
    [[ -n "$expected_bundle" && "$actual_bundle" == "$expected_bundle" ]] ||
        die "campaign runtime changed after verification; rerun verify-rabbitmq-fixes.sh"
}

preflight() {
    local profile=$1 project effective
    [[ -f "$STATE_DIR/bootstrap-complete" ]] || die "bootstrap is incomplete"
    [[ -f "$STATE_DIR/smoke-complete" ]] || die "smoke is incomplete"
    [[ ! -f "$STATE_DIR/campaign-enabled" ]] || die "campaign already enabled"
    validate_thp_profile "$profile"
    validate_manifest
    verify_rabbitmq_fix_marker
    for project in anchors redis rabbitmq geekbench; do
        effective=$(THP_PROFILE="$profile" thp_for_project "$project")
        [[ "$effective" == "$profile" ]] ||
            die "THP preflight mismatch: profile=$profile project=$project effective=$effective"
        printf 'thp_profile=%s project=%s effective=%s\n' "$profile" "$project" "$effective"
    done
    cmp "$SCRIPT_DIR/d3000-pkvm-campaign.service" /etc/systemd/system/d3000-pkvm-campaign.service ||
        die "installed campaign service differs from the verified runtime unit"
    cmp "$SCRIPT_DIR/d3000-thp-always-chain.service" /etc/systemd/system/d3000-thp-always-chain.service ||
        die "installed THP=always chain service differs from the verified runtime unit"
    "$SCRIPT_DIR/launch-pending-thp-always.sh" selftest
    systemctl is-active --quiet d3000-pkvm-campaign.service && die "campaign service is already active"
    printf 'manifest_legs=12\nformal_pairs=5\nprofile=%s\nruntime_bundle_sha256=%s\npreflight=pass\n' \
        "$profile" "$(runtime_bundle_sha256 "$SCRIPT_DIR")"
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
    preflight)
        profile=${2:-}
        [[ -n "$profile" ]] || die "usage: campaign.sh preflight never|always"
        preflight "$profile"
        ;;
    start)
        profile=${2:-}
        [[ -n "$profile" ]] || die "usage: campaign.sh start never|always"
        preflight "$profile"
        campaign_id="d3000-apps-${profile}-$(date +%Y%m%d-%H%M%S)"
        manifest >"$STATE_DIR/manifest.tsv"
        printf '%s\n' "$campaign_id" >"$STATE_DIR/campaign-id"
        printf '%s\n' "$profile" >"$STATE_DIR/campaign-profile"
        printf '1\n' >"$STATE_DIR/leg"
        rm -f "$STATE_DIR/completed-leg" "$STATE_DIR/leg.next" "$STATE_DIR/rabbit-rate-common" \
            "$STATE_DIR/redis-rate-common" "$STATE_DIR/redis-rate-70"
        mkdir -p "$RESULTS_DIR/$campaign_id"
        cp "$STATE_DIR/manifest.tsv" "$RESULTS_DIR/$campaign_id/manifest.tsv"
        printf 'campaign_id=%s\nthp_profile=%s\ncreated_at=%s\n' \
            "$campaign_id" "$profile" "$(timestamp)" >"$RESULTS_DIR/$campaign_id/campaign.env"
        if [[ "$profile" == never ]]; then
            printf '%s\n' "$campaign_id" >"$STATE_DIR/thp-always-pending"
            rm -f "$STATE_DIR/thp-never-pending"
        fi
        touch "$STATE_DIR/campaign-enabled"
        sudo systemctl enable d3000-pkvm-campaign.service
        if [[ "$profile" == never ]]; then
            sudo systemctl enable d3000-thp-always-chain.service
        fi
        "$SCRIPT_DIR/set-next-mode.sh" nvhe
        record_note campaign "initialized id=$campaign_id thp_profile=$profile"
        write_status "campaign=$campaign_id thp_profile=$profile initialized; rebooting into calibration nVHE"
        sync
        sudo systemctl reboot
        ;;
    stop)
        rm -f "$STATE_DIR/campaign-enabled" "$STATE_DIR/thp-always-pending" "$STATE_DIR/thp-never-pending"
        sudo systemctl stop d3000-pkvm-campaign.service || true
        sudo systemctl disable d3000-pkvm-campaign.service d3000-thp-always-chain.service \
            d3000-thp-never-chain.service || true
        sudo grub-editenv /boot/efi/boot/grub/grubenv unset next_entry || true
        sudo grub-editenv /boot/grub/grubenv unset next_entry || true
        "$SCRIPT_DIR/restore-host.sh"
        write_status "campaign stopped manually"
        ;;
    *) die "usage: campaign.sh status|smoke|preflight never|always|start never|always|stop" ;;
esac
