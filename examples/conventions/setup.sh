#!/bin/sh
# Told its phase: install on the first add, sync on every sync, remove before the state directory
# goes. The state directory is kept from one sync to the next, so sync updates it in place.
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
