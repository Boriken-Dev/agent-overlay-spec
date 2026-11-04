#!/bin/sh
# Told its phase: install once, sync for each new digest, remove before the state directory goes.
# It writes only into the state directory, never into the overlay.
set -eu
case "${1:-}" in
  install|sync)
    mkdir -p "$AOS_OVERLAY_STATE"
    date -u +%Y-%m-%dT%H:%M:%SZ > "$AOS_OVERLAY_STATE/prepared-at"
    ;;
  remove) ;;  # nothing outside the state directory to undo
  *) ;;       # a phase this script does not know: nothing to do
esac
