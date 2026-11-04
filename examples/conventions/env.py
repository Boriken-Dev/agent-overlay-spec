"""The overlay's env script: one JSON object per line, from variable name to value."""

import json
import platform

print(json.dumps({"TOOL_PLATFORM": platform.system().lower()}))
