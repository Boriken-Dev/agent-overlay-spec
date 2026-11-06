"""The guard: told of new and resumed sessions, and of every shell call before it runs.

A pre-tool hook can deny or ask, never allow. With on_failure = "refuse", a crash or a timeout here
denies the call instead of letting it through.
"""

import json
import re
import sys

FORCE_PUSH = re.compile(r"\bgit\s+push\b.*\s(?:-f|--force)(?:\s|$)")

event = sys.argv[1] if len(sys.argv) > 1 else ""
payload = json.load(sys.stdin)

if event == "session-start":
    print(json.dumps({"context": "Force pushes are refused in this session."}))
elif event == "pre-tool":
    tool_input = payload["tool"].get("input")
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    if isinstance(command, str) and FORCE_PUSH.search(command):
        print(json.dumps({"decision": "deny", "reason": "Force pushes are refused."}))
