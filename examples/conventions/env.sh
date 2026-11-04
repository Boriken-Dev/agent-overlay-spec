#!/bin/sh
# Runs only where env.py cannot: a Unix-like host without Python.
printf '{"TOOL_PLATFORM": "%s"}\n' "$(uname -s | tr 'A-Z' 'a-z')"
