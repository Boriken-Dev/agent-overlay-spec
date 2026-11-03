"""Prints one JSON object per line: a string sets a variable, null unsets it."""

import json
import os

if not os.environ.get("COMPUTED_ENV_PREFIX"):
    print(json.dumps({"COMPUTED_ENV_PREFIX": "AGENTS_"}))
print(json.dumps({"COMPUTED_ENV_STATE": os.environ.get("AOS_OVERLAY_STATE", "")}))
