#!/bin/sh
# Writes only into the state directory the consumer provides, never into the overlay root.
set -eu
mkdir -p "$AOS_OVERLAY_STATE"
printf 'prepared for %s\n' "$AOS_OVERLAY_NAME" > "$AOS_OVERLAY_STATE/prepared.txt"
[ "${1:-}" = "--quiet" ] || echo "setup for $AOS_OVERLAY_NAME done"
