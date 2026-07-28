#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

[[ -f "$STATE_DIR/campaign-enabled" ]] || exit 0
campaign_id=$(cat "$STATE_DIR/campaign-id")
[[ -s "$STATE_DIR/campaign-profile" ]] || die "campaign profile is missing"
THP_PROFILE=$(cat "$STATE_DIR/campaign-profile")
validate_thp_profile "$THP_PROFILE"
leg=$(cat "$STATE_DIR/leg")
line=$(awk -F '\t' -v n="$leg" '$1 == n {print; exit}' "$STATE_DIR/manifest.tsv")
[[ -n "$line" ]] || die "campaign manifest has no leg $leg"
IFS=$'\t' read -r leg_no stage pair expected order <<<"$line"
export CAMPAIGN_ID=$campaign_id PAIR_INDEX=$pair EXPECTED_MODE=$expected THP_PROFILE

write_status "leg=$leg stage=$stage pair=$pair expected=$expected starting"
assert_mode "$expected"
"$SCRIPT_DIR/prepare-host.sh"
capture_metadata "$RESULTS_DIR/$CAMPAIGN_ID/pair-$pair/$expected/leg-metadata"

case "$stage" in
    calibration)
        set_project_thp redis
        "$SCRIPT_DIR/redis.sh" run calibration
        set_project_thp rabbitmq
        "$SCRIPT_DIR/rabbitmq.sh" run calibration
        if [[ "$expected" == protected ]]; then
            "$SCRIPT_DIR/compute-capacity.py" "$RESULTS_DIR/$CAMPAIGN_ID" "$STATE_DIR" \
                "$RESULTS_DIR/$CAMPAIGN_ID/capacity.json"
        fi
        ;;
    formal) "$SCRIPT_DIR/run-boot-block.sh" "$order" ;;
    *) die "unknown campaign stage: $stage" ;;
esac

next=$((leg + 1))
next_line=$(awk -F '\t' -v n="$next" '$1 == n {print; exit}' "$STATE_DIR/manifest.tsv")
if [[ -n "$next_line" ]]; then
    printf '%s\n' "$next" >"$STATE_DIR/leg.next"
    mv "$STATE_DIR/leg.next" "$STATE_DIR/leg"
    next_mode=$(printf '%s\n' "$next_line" | cut -f4)
    "$SCRIPT_DIR/set-next-mode.sh" "$next_mode"
    write_status "leg=$leg complete; rebooting into $next_mode for leg=$next"
    sync
    sudo systemctl reboot
else
    rm -f "$STATE_DIR/campaign-enabled"
    printf '%s\n' "$leg" >"$STATE_DIR/completed-leg"
    touch "$RESULTS_DIR/$campaign_id/CAMPAIGN_COMPLETE"
    set_thp always
    sudo swapon -a || true
    sudo systemctl set-default graphical.target
    sudo grub-editenv /boot/efi/boot/grub/grubenv unset next_entry || true
    sudo grub-editenv /boot/grub/grubenv unset next_entry || true
    write_status "campaign complete; rebooting to default VHE"
    sync
    sudo systemctl reboot
fi
