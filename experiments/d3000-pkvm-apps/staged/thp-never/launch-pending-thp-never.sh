#!/usr/bin/env bash
set -euo pipefail

EXP_HOME=${EXP_HOME:-/home/jose/kylin-lmbench-exp}
ACTIVE_SCRIPTS=$EXP_HOME/scripts
STAGED_SCRIPTS=${STAGED_SCRIPTS:-$EXP_HOME/staged/thp-never/scripts}
STATE_DIR=$EXP_HOME/state
PENDING=$STATE_DIR/thp-never-pending

# Use the active campaign's logging and exact VHE validation before replacing anything.
# shellcheck source=lib.sh
source "$ACTIVE_SCRIPTS/lib.sh"

[[ -f "$PENDING" ]] || exit 0
[[ ! -f "$STATE_DIR/campaign-enabled" ]] || exit 0

source_campaign=$(<"$PENDING")
current_campaign=$(cat "$STATE_DIR/campaign-id" 2>/dev/null || true)
profile=$(cat "$STATE_DIR/campaign-profile" 2>/dev/null || echo app-default)
completed_leg=$(cat "$STATE_DIR/completed-leg" 2>/dev/null || echo 0)

if [[ "$current_campaign" != "$source_campaign" ]]; then
    if [[ "$profile" == never && "$completed_leg" == 12 ]]; then
        rm -f "$PENDING"
        record_note campaign "THP=never follow-up completed id=$current_campaign"
        log "THP=never follow-up completed; cleared pending marker"
    else
        log "THP=never launcher deferred: current campaign id=$current_campaign source=$source_campaign profile=$profile completed_leg=$completed_leg"
    fi
    exit 0
fi

if [[ "$completed_leg" != 12 ]]; then
    log "THP=never launcher deferred: source campaign did not complete leg 12"
    exit 0
fi

assert_mode vhe
for name in config.env lib.sh campaign.sh resume-campaign.sh run-boot-block.sh run-anchors.sh run-geekbench.sh rabbitmq.sh; do
    [[ -f "$STAGED_SCRIPTS/$name" ]] || die "missing staged THP=never script: $name"
done
install -m 0644 "$STAGED_SCRIPTS/config.env" "$ACTIVE_SCRIPTS/config.env"
install -m 0644 "$STAGED_SCRIPTS/lib.sh" "$ACTIVE_SCRIPTS/lib.sh"
for name in campaign.sh resume-campaign.sh run-boot-block.sh run-anchors.sh run-geekbench.sh rabbitmq.sh; do
    install -m 0755 "$STAGED_SCRIPTS/$name" "$ACTIVE_SCRIPTS/$name"
done

record_note campaign "source campaign complete; installed complete staged THP profile support and launching full THP=never campaign"
log "launching full THP=never campaign after completed source=$source_campaign"
exec "$ACTIVE_SCRIPTS/campaign.sh" start never
