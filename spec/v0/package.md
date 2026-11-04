# Package format

**Core.** An overlay is a directory tree. It MAY contain `overlay.cfg`; assets do not need a
manifest, and the conventional paths take effect without one.

## Layout

The conventional paths below take effect by [default](#defaults) when present; every other path
means something only when a field names it.

| Path | Meaning |
|---|---|
| `overlay.cfg` | Optional manifest: metadata and declarations |
| `bin/`, `lib/` | Programs and modules, on `PATH` and `PYTHONPATH` by default |
| `rules/<name>.md`, `CONTEXT.md` | Always-on rules and initial context, by default |
| `skills/<name>/SKILL.md` | A skill |
| `env`, `env.<ext>`, `setup.<ext>` | The env file, the env script and setup, by default |
| `kb/`, `flows/`, `references/` | Instructions and knowledge, named by `rules`, `routing` and `context` |
| `cmds/`, `scripts/` | Executable assets, exposed only by a [`scripts`](commands.md) entry |
| `setup/`, `env/`, `locks/` | Files named by `setup`, `env_files`, `env_scripts` and `runtime` |
| `templates/`, `workflows/` | Reusable project or process assets |

An overlay MAY use other relative paths. Empty directories carry no meaning, and archive formats may
drop them.

These path components are **not part of an overlay** wherever they appear: `.git`, `.hg`, `.svn`,
`__pycache__`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `.tox`, `.venv`, `node_modules`, and
any entry other than a directory whose name ends in `.pyc`. A consumer does not install, read or run them as overlay content,
and they do not count in the [tree digest](integrity.md#tree-digest).

## Defaults

**The basics need no manifest.** Seven fields take a default from the overlay's files. When the
manifest does not write the field, the field has its default. When it writes the field, what it
writes is the whole value: the default is not merged in, so a declared entry never repeats a default
one, and an empty list turns the default off.

| Field | Default, from the files present | Class |
| --- | --- | --- |
| [`paths`](environment.md#path-additions) | `bin/` prepended to `PATH`, then `lib/` prepended to `PYTHONPATH`, each when present | Optional Extension |
| [`rules`](composition.md#merging) | every `rules/<name>.md` directly in `rules/`, ordered by path bytes | Core, **Proposed** |
| [`context`](harness.md#context) | `CONTEXT.md` at the root | Optional Extension |
| [`skills`](skills.md#declaring-skills) | every `skills/<name>/SKILL.md` whose `<name>` is a skill name | Optional Extension |
| [`env_files`](environment.md#env-files) | the file `env` at the root, read as [`dotenv`](environment.md#env-files) | Optional Extension, **Proposed** |
| [`env_scripts`](environment.md#env-scripts) | one `env.<ext>` at the root, [chosen by runtime](runtime.md#default-scripts) | Optional Extension |
| [`setup`](runtime.md#setup) | one `setup.<ext>` at the root, chosen the same way, taken to need the network | Optional Extension |

A path is **present** when the overlay holds a file there that is a member of its
[tree digest](integrity.md#tree-digest): `bin/` is present when a file is under it at any depth,
`env` when it is a file. An empty directory, an excluded name and a `.pyc` file make nothing present.
Names match exactly, in case too: `Bin/`, `context.md` and `rules/A.MD` are not conventions.

A consumer computes a default when it applies the field, from the overlay's list of files. Reading
the manifest still reads no other file ([static reading](manifest.md#static-reading)), and a
validator that knows the files checks a default as it checks a written field.

```toml
# Turn defaults off: nothing on PATH or PYTHONPATH, no skills, env.py not run.
paths = []
skills = []
env_scripts = []
```

```toml
# Keep bin/ on PATH but append lib/ to PYTHONPATH: write paths in full.
[[paths]]
variable = "PATH"
path = "bin"

[[paths]]
variable = "PYTHONPATH"
path = "lib"
position = "append"
```

One rule covers every default, and it adds no key: a written field is exactly what it says, so a
reader never has to merge a declaration with a default or decide which of two entries wins, and an
empty list, which every field already accepts, is the one way to turn a default off.

**Defaults that run code.** `env_scripts` and `setup` default to scripts that run. Running by
default is never running silently: a consumer runs them only for an overlay it has activated, which
is the [trust decision](security.md#execution-and-dependencies), and reports each run as a
[weakening](security.md#weakenings): `env-script` for an env script, `setup-network` for a default
setup, and `script-not-run` for a default script present that cannot run.

No other name has a default. `requirements.txt`, `pre.env`, `cmds/` and any other file or directory
mean nothing by their name, and a program in `bin/` is on `PATH`, not a
[command](commands.md) a consumer exposes.

**`local.env` is not an overlay file.** A file named `local.env` in an overlay has no meaning in
AOS. A user's or a project's own local overrides belong to the consumer's scope, outside the format:
a consumer that reads such a file reads it from its own configuration, never from an overlay.

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
