"""Prints the tool settings the overlay's environment declares."""

import os

for name in ("TOOL_MODE", "TOOL_CONFIG", "TOOL_BANNER"):
    print("%s=%s" % (name, os.environ.get(name, "(unset)")))
