#!/bin/sh
# Illustrative command: checks that each named shell script parses.
status=0
for script in "$@"; do
    sh -n "$script" || status=1
done
exit "$status"
