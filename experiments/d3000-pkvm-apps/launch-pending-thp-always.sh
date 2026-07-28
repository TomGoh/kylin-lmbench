#!/usr/bin/env bash
set -euo pipefail

EXP_HOME=${EXP_HOME:-/home/jose/kylin-lmbench-exp}
ACTIVE_SCRIPTS=$EXP_HOME/scripts
STATE_DIR=$EXP_HOME/state
RESULTS_DIR=$EXP_HOME/results
PENDING=$STATE_DIR/thp-always-pending

# shellcheck source=lib.sh
source "$ACTIVE_SCRIPTS/lib.sh"

handoff_action() {
    local source_campaign=$1 current_campaign=$2 profile=$3 completed_leg=$4
    local source_complete=$5 current_complete=$6
    if [[ "$current_campaign" == "$source_campaign" && "$profile" == never && \
          "$completed_leg" == 12 && "$source_complete" == yes ]]; then
        printf 'launch-always\n'
    elif [[ "$current_campaign" != "$source_campaign" && "$profile" == always && \
            "$completed_leg" == 12 && "$source_complete" == yes && "$current_complete" == yes ]]; then
        printf 'cleanup\n'
    else
        printf 'inconsistent\n'
    fi
}

if [[ ${1:-} == selftest ]]; then
    [[ $(handoff_action never-id never-id never 12 yes no) == launch-always ]]
    [[ $(handoff_action never-id never-id never 11 yes no) == inconsistent ]]
    [[ $(handoff_action never-id always-id always 12 yes yes) == cleanup ]]
    [[ $(handoff_action never-id always-id always 12 yes no) == inconsistent ]]
    [[ $(handoff_action never-id never-id app-default 12 yes no) == inconsistent ]]
    printf 'thp_handoff_selftest=pass\n'
    exit 0
fi

[[ -f "$PENDING" ]] || exit 0
[[ ! -f "$STATE_DIR/campaign-enabled" ]] || exit 0

source_campaign=$(<"$PENDING")
current_campaign=$(cat "$STATE_DIR/campaign-id" 2>/dev/null || true)
profile=$(cat "$STATE_DIR/campaign-profile" 2>/dev/null || true)
completed_leg=$(cat "$STATE_DIR/completed-leg" 2>/dev/null || echo 0)
source_complete=no
current_complete=no
[[ -f "$RESULTS_DIR/$source_campaign/CAMPAIGN_COMPLETE" ]] && source_complete=yes
[[ -n "$current_campaign" && -f "$RESULTS_DIR/$current_campaign/CAMPAIGN_COMPLETE" ]] && current_complete=yes
action=$(handoff_action "$source_campaign" "$current_campaign" "$profile" "$completed_leg" \
    "$source_complete" "$current_complete")

if [[ "$action" == launch-always ]]; then
    assert_mode vhe
    record_note campaign "THP=never campaign complete; launching full THP=always campaign source=$source_campaign"
    exec "$ACTIVE_SCRIPTS/campaign.sh" start always
fi

if [[ "$action" == cleanup ]]; then
    assert_mode vhe
    rm -f "$PENDING"
    record_note campaign "THP=always follow-up complete id=$current_campaign source=$source_campaign"
    sudo systemctl disable d3000-pkvm-campaign.service d3000-thp-always-chain.service || true
    log "THP profile sequence complete; cleared pending marker and disabled campaign services"
    exit 0
fi

die "THP=always handoff state is inconsistent: source=$source_campaign current=$current_campaign profile=$profile completed_leg=$completed_leg source_complete=$source_complete current_complete=$current_complete"
