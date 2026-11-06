"""After an edit: reminds the agent of a file left with trailing white space.

The payload names the tool's input, never its output; the hook reads the file itself.
"""

import json
import os
import sys

payload = json.load(sys.stdin)
tool_input = payload.get("tool", {}).get("input")
path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
if payload.get("status") == "completed" and isinstance(path, str) and os.path.isfile(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        if any(line.rstrip("\n").endswith((" ", "\t")) for line in handle):
            print(json.dumps({"context": "%s has trailing white space." % path}))
