#!/bin/sh
# Runs once per digest. It writes only into the state directory, never into the overlay.
set -eu
mkdir -p "$AOS_OVERLAY_STATE"
date -u +%Y-%m-%dT%H:%M:%SZ > "$AOS_OVERLAY_STATE/prepared-at"
