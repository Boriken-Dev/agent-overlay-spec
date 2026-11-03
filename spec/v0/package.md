# Package format

**Core.** An overlay is a directory tree. It MAY contain `overlay.toml`; assets do not require a manifest. This preserves compatibility with manifest-free directories supported by dotagents.

## Layout

Common paths are conventions, not universal required directories:

| Path | Meaning |
|---|---|
| `overlay.toml` | Optional metadata and integration declarations |
| `AGENTS.md`, `instructions/`, `rules/` | Instructions or rules; target interpretation is manager-defined except where declared by supported fields |
| `skills/<name>/SKILL.md` | Optional skill package convention |
| `kb/`, `knowledge/`, `references/` | Knowledge and workflow material |
| `cmds/`, `bin/`, `lib/`, `scripts/` | Executable or importable assets; execution is optional and implementation-specific |
| `templates/`, `workflows/` | Reusable project or process assets |

An overlay MAY use other relative paths. Empty directories may not survive archive formats and carry no required meaning.

## Names and paths

For dotagents compatibility, a raw directory name starts with an ASCII letter, continues with letters, digits, `_`, `.` or `-`, and ends with a letter or digit. It is case-insensitive; `.` and `_` normalize to `-`. Leading dot, leading underscore, or leading digit names are rejected by dotagents. Dotagents also rejects reserved scope labels and Windows device names. These restrictions are **Compatibility Baseline**, not yet a universal namespace registry.

A manifest `name` is a display/metadata value in dotagents; the selected overlay directory and normalized directory identity determine installation location. To avoid ambiguity, authors SHOULD use a manifest name whose normalized form equals the directory name's normalized form.

Paths in fields that explicitly take overlay-relative paths MUST be relative to the overlay root and MUST NOT escape it. A consumer MUST validate the resolved path after symbolic links and normalization before reading or executing it. Generic content links and paths embedded in prose are uninterpreted strings.

Assets SHOULD use UTF-8 text for portable instructions and TOML. Binary assets MAY be included, but consumers are not required to understand their contents.

## Relative references

The overlay root is the base for manifest paths, scripts, rule files, skill folders, and other package-relative assets. A manager MAY expose a runtime root variable or another stable locator; variable spelling and expansion are implementation-specific. Dotagents exports `<NORMALIZED_NAME>_OVERLAY_ROOT` and expands selected placeholders in its context output.
