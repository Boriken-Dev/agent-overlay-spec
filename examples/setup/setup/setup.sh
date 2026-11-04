#!/bin/sh
# Writes only into the state directory the consumer provides, never into the overlay root.
# $1 is the phase (install, sync or remove); the declared arguments follow it.
set -eu
phase="${1:-}"
[ "${2:-}" = "--quiet" ] && quiet=1 || quiet=
case "$phase" in
  install|sync)
    mkdir -p "$AOS_OVERLAY_STATE"
    printf 'prepared for %s\n' "$AOS_OVERLAY_NAME" > "$AOS_OVERLAY_STATE/prepared.txt"
    [ -n "$quiet" ] || echo "setup ($phase) for $AOS_OVERLAY_NAME done"
    ;;
  remove)
    [ -n "$quiet" ] || echo "nothing to undo for $AOS_OVERLAY_NAME"
    ;;
  *) ;;  # a phase this script does not know: nothing to do
esac
