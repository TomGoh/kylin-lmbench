#!/bin/sh
# Runs the three interconnect-frequency experiments one after another
# (G1 fixed frequencies, G2/G3 governors, G4 lmbench's own program).
# Root.  About 1.5 hours.  Each part restores the original governor when it
# exits; this wrapper checks once more at the end.
cd "$(dirname "$0")" || exit 1
DF=/sys/class/devfreq/nocfreq
ORIG=$(cat $DF/governor) || exit 1
trap 'echo "$ORIG" > $DF/governor; echo "# noc-all end $(date -Is) governor=$(cat $DF/governor) cur_freq=$(cat $DF/cur_freq)" >> meta.log' EXIT
trap 'exit 1' INT TERM HUP
echo "# noc-all start $(date -Is) orig_governor=$ORIG" >> meta.log
sh ./run4-noc-fixed.sh
sh ./run7-noc-governors.sh
sh ./run8-noc-lmbench.sh
