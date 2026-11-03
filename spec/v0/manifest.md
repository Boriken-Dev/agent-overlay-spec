# Manifest

**Core.** `overlay.toml` is optional UTF-8 TOML using TOML 1.0 syntax. A consumer MUST accept a package with no manifest. The parsed TOML document is an object/table. The JSON Schema at [`schemas/overlay.schema.json`](../../schemas/overlay.schema.json) describes field types and MCP shapes; JSON Schema cannot enforce all TOML syntax or filesystem constraints.

The manifest does not contain a required format version. AOS specification versioning is maintained separately. Introducing a required `version` or `schema_version` field would make existing manifest-free and legacy manifests fail strict validators; it is **Proposed**, not part of this draft.

The JSON Schema is a strict authoring profile for recognized field shapes, not a byte-for-byte model of dotagents' tolerant fallback behavior. For example, dotagents falls back when `name` is empty or has the wrong type; the schema accepts an empty string but rejects a non-string `name`. Unknown top-level keys are allowed. JSON Schema does not validate filesystem paths after symlink resolution, duplicate server/skill names, cross-reference existence, or all URL credential/fragment restrictions; consumers need semantic checks for those conditions.

## Fields

| Field | Type | Default and verified dotagents behavior |
|---|---|---|
| `name` | string | Directory name when absent, empty, or not a non-empty string. Used as a sort/display tiebreaker; the installed identity is directory-based. |
| `description` | string | Empty string when absent or wrong type. Informational. |
| `requires` | array of strings | Empty. Dotagents filters non-string/blank entries, validates names, normalizes them, and deduplicates in order. Used by add/remove operations, not a complete runtime dependency solver. |
| `routing` | array of strings | Empty. Non-string and blank entries are dropped; surrounding newlines are trimmed. Entries are appended to the managed routing section by dotagents. |
| `rules` | array of strings | Empty. Dotagents treats each string as an overlay-relative Markdown path, extracts leading bullet blocks up to the next `## ` heading, and appends those bullets to always-on rules. |
| `priority` | integer | `500`. Dotagents sorts ascending by `(priority, manifest name, directory name)`; higher numbers therefore appear later. Boolean is not accepted as an integer. |
| `setup_timeout` | integer ≥ 0 | Unset means 300 seconds; `0` means unlimited. Invalid values are ignored with a warning. A command-line override can take precedence. |
| `[scripts]` | table of string keys to relative path strings or `false` | Empty. Maps command names to script paths or disables an automatically discovered `bin/<name>.py` command. Invalid entries are ignored with a warning by dotagents. |
| `[mcp]` | table with `servers` and `skills` arrays | Absent means no MCP declarations. Dotagents rejects unknown keys inside this table. See [MCP](mcp.md). |

For ordinary fields, dotagents is deliberately tolerant: wrong types often become defaults or filtered values rather than a hard error. AOS validators SHOULD report invalid values clearly. A strict validation failure does not mean dotagents would reject the overlay.

## `scripts` names and paths

Dotagents accepts launcher names matching `[A-Za-z0-9][A-Za-z0-9._-]*`, except `.exe` endings and reserved command names. A path is slash-separated, relative, contains only the accepted filename characters, and excludes `.`/`..` path components, backslashes, empty components, absolute paths, and drive prefixes. These are compatibility constraints of its launcher generation.

Complete example:

```toml
name = "python-quality"
description = "Python review conventions and reusable checks."
requires = ["engineering"]
routing = ["- Python changes → `$PYTHON_QUALITY_OVERLAY_ROOT/kb/PYTHON.md`"]
rules = ["rules/always-on.md"]
priority = 420
setup_timeout = 60

[scripts]
check-python = "bin/check_python.py"
legacy-check = false
```

Complete MCP example:

```toml
[mcp]

[[mcp.servers]]
name = "docs"
transport = "stdio"
command = "node"
args = ["server.js"]
env = { DOCS_MODE = "read-only" }
env_passthrough = ["DOCS_TOKEN"]
timeout = 30

[[mcp.skills]]
name = "search-docs"
server = "docs"

[[mcp.servers]]
name = "remote-docs"
transport = "streamable-http"
url = "https://mcp.example.org/agent"
headers_env = { Authorization = "DOCS_AUTHORIZATION" }
timeout = 20
```
