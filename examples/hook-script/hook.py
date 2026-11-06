"""The overlay's hook, run with no manifest: it receives the events hook.<ext> gets by default.

The event is the first argument and AOS_HOOK_EVENT; the payload is JSON on standard input. An
event this script does not know gets no output and exit status 0.
"""

import json
import sys

event = sys.argv[1] if len(sys.argv) > 1 else ""
payload = json.load(sys.stdin)

if event == "pre-env":
    # Exactly an env script's output: variables to set, or null to unset.
    print(json.dumps({"REVIEW_NOTES_STYLE": "short"}))
elif event == "session-start" and payload.get("reason") == "new":
    print(json.dumps({"context": "Keep review notes to one line per finding."}))
