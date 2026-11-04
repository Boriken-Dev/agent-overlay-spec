"""Prints the variables the overlay's env file and env script set."""

import os

for name in ("TOOL_MODE", "TOOL_BANNER", "TOOL_PLATFORM"):
    print("%s=%s" % (name, os.environ.get(name, "")))
