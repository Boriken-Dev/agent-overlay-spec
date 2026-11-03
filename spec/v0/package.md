# Package format

**Core.** An overlay is a directory tree. It MAY contain `overlay.cfg`; assets do not need a
manifest.

## Layout

Common paths are conventions. Only `overlay.cfg` and `skills/<name>/SKILL.md` have a meaning of
their own; every other path means something only when a field names it.

| Path | Meaning |
|---|---|
| `overlay.cfg` | Optional manifest: metadata and declarations |
| `rules/`, `kb/`, `flows/`, `references/` | Instructions and knowledge, named by `rules`, `routing` and `context` |
| `skills/<name>/SKILL.md` | A skill |
| `bin/`, `lib/`, `cmds/`, `scripts/` | Executable or importable assets, placed on search paths by `paths` |
| `setup/`, `env/`, `locks/` | Files named by `setup`, `env_files`, `env_scripts` and `runtime` |
| `templates/`, `workflows/` | Reusable project or process assets |

An overlay MAY use other relative paths. Empty directories carry no meaning, and archive formats may
drop them.

These path components are **not part of an overlay** wherever they appear: `.git`, `.hg`, `.svn`,
`__pycache__`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `.tox`, `.venv`, `node_modules`, and
files whose name ends in `.pyc`. A consumer does not install, read or run them as overlay content,
and they do not count in the [tree digest](integrity.md#tree-digest).

## Names and paths

An overlay's **identity** is the name a consumer installs it under. A valid name starts with an
ASCII letter, continues with ASCII letters, digits, `_`, `.` or `-`, and ends with a letter or a
digit. It is compared **normalized**: ASCII lowercase, with `_` and `.` replaced by `-`, so
`Team_Review`, `team.review` and `team-review` are one overlay. These names are refused:

- `default`, `overlay`, `system`, `user`, `project`, `project-root` (dotagents' scope labels);
- a Windows device name (`con`, `prn`, `aux`, `nul`, `com1`–`com9`, `lpt1`–`lpt9`) as the whole name
  or before its first `.`.

The manifest `name` is display metadata and a sort tiebreaker. Authors SHOULD use a manifest name
whose normalized form equals the identity's.

Fields that take an overlay-relative path take a [relative path](manifest.md#fields). A consumer
resolves it under the root and MUST refuse one that leaves the root after normalization and symbolic
links. Paths inside prose (routing lines, Markdown) are uninterpreted text.

Instructions and manifests SHOULD be UTF-8 text. Binary assets MAY be included.

## Relative references

The overlay root is the base for manifest paths, scripts, rule files and skill folders. A consumer
that exposes the overlay to processes sets its [root variable](environment.md#the-root-variable),
`<NAME>_OVERLAY_ROOT`, and documents refer to files as `$<NAME>_OVERLAY_ROOT/<path>`.
