# Package format

**Core.** An overlay is a directory tree. It MAY contain a [manifest](manifest.md), `OVERLAY.md` or
`overlay.cfg` and never both; assets do not need one, and the conventional paths take effect without
one.

## Layout

The conventional paths below take effect by [default](#defaults) when present; every other path
means something only when a field names it.

| Path | Meaning |
|---|---|
| `OVERLAY.md` | Optional manifest as front matter, and the overlay's context as its body |
| `overlay.cfg` | Optional manifest as a document of its own, refused beside `OVERLAY.md` |
| `bin/`, `lib/python/`, `lib/node/` | Programs, Python modules and Node.js modules, on `PATH`, `PYTHONPATH` and `NODE_PATH` by default |
| `lib/python/requirements.txt`, `lib/node/package.json` | The overlay's [dependencies](runtime.md#dependencies), installed by default |
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

**The basics need no manifest.** Files in conventional places take effect by default. Each default
stays on unless the manifest's [`defaults`](#turning-a-default-off) table turns it off, and what the
manifest declares adds to the defaults.

| `defaults` key | Default, from the files present | Adds to | Class |
| --- | --- | --- | --- |
| `bin` | `bin/` prepended to `PATH` | [`paths`](environment.md#path-additions) | Optional Extension |
| `lib` | `lib/python/` prepended to `PYTHONPATH`, `lib/node/` to `NODE_PATH` | [`paths`](environment.md#path-additions) | Optional Extension |
| `env` | the file `env` at the root, read as [`dotenv`](environment.md#env-files) | [`env_files`](environment.md#env-files) | Optional Extension, **Proposed** |
| `env_scripts` | one `env.<ext>` at the root, [chosen by runtime](runtime.md#default-scripts) | [`env_scripts`](environment.md#env-scripts) | Optional Extension |
| `setup` | one `setup.<ext>` at the root, chosen the same way, taken to need the network | [`setup`](runtime.md#setup) | Optional Extension |
| `deps` | `lib/python/requirements.txt` and `lib/node/package.json` installed at `install` and `sync`, before setup | [`runtime`](runtime.md#dependencies) | Optional Extension, **Proposed** |
| `context` | the [body](manifest.md#overlaymd) of `OVERLAY.md` when it has one, otherwise `CONTEXT.md` at the root | [`context`](harness.md#context) | Optional Extension |
| `skills` | every `skills/<name>/SKILL.md` whose `<name>` is a skill name | [`skills`](skills.md#declaring-skills) | Optional Extension |
| `rules` | every `rules/<name>.md` directly in `rules/`, ordered by path bytes | [`rules`](composition.md#merging) | Core, **Proposed** |

A path is **present** when the overlay holds a file there that is a member of its
[tree digest](integrity.md#tree-digest): `bin/` is present when a file is under it at any depth,
`env` when it is a file. An empty directory, an excluded name and a `.pyc` file make nothing present.
Names match exactly, in case too: `Bin/`, `context.md` and `rules/A.MD` are not conventions.

Python modules go in `lib/python/` and Node.js modules in `lib/node/`; a bare `lib/` means
nothing. `lib/<runtime>/` is kept for the libraries of other runtimes, and the standard manifest of
that ecosystem in it for their dependencies, which a later edition may define. The `lib` key turns
off every library directory, and the `deps` key every dependency file.

A consumer computes the defaults when it applies the fields, from the overlay's list of files.
Reading the manifest still reads no other file ([static reading](manifest.md#static-reading)), and
a validator that knows the files checks a default entry as it checks a declared one.

### Turning a default off

`defaults` is a table of the keys above. Each value is a boolean, `true` when absent; `false` turns
that one default off, and nothing else does: an empty list declares nothing and turns nothing off.
Any other key is an error, so a misspelt key fails instead of leaving a default on.

```toml
[defaults]
lib = false      # lib/python/ stays off PYTHONPATH
setup = false    # setup.sh does not run
```

### Declarations add to the defaults

A field's default entries come first, then the entries the manifest declares. A declared entry that
names the same file or directory as a default entry **replaces** it, so nothing applies twice: the
declared entry applies at its own place and with its own settings, and where its `os` does not
match, that file or directory does not apply at all.

- `paths`: an entry whose `path` is `bin`, `lib/python` or `lib/node` replaces that default
  addition, whatever its variable. Other entries are added after the defaults, so declaring another directory keeps
  `bin/` on `PATH`.
- `rules`, `context`, `env_files`: an entry naming the same file replaces that default entry. Naming
  `OVERLAY.md` in `context` names its body.
- `skills`: the listed skills, [bundled, named or sourced](skills.md#declaring-skills), are added to the
  ones found. With `skills = false` in `defaults`, the list is exactly the skills the overlay offers.
- `env_scripts`, `setup`: an entry naming a root `env.<ext>` or `setup.<ext>` configures that file in
  the [default choice](runtime.md#default-scripts). The file keeps its place in the order, takes the
  entry's interpreter, arguments, timeout, `os` and (for setup) `network`, and runs only if it is
  chosen. Other declared env scripts run after the default one; other declared setup variants are
  tried before the default setup, which is the last variant.
- `runtime.python`, `runtime.node`: a selected variant that names a dependency file (`requirements`,
  `lock`, `package`) replaces that runtime's default file; one that names none keeps it, in the
  variant's `environment`.

```toml
# bin/ stays first on PATH; lib/python/ is appended instead of prepended; man/ is added.
[[paths]]
variable = "PYTHONPATH"
path = "lib/python"
position = "append"

[[paths]]
variable = "MANPATH"
path = "man"
position = "append"
```

A default is on until it is switched off, by its own key. Declaring adds, so an author who adds a
directory keeps `bin/`, and an entry naming a default's file changes that default's settings without
turning it off and without applying it twice. Each key is named for what it turns off: the directory
or file of a default that is one entry of a shared field (`bin`, `lib`, `env`), the field itself
where the default is all of it (`env_scripts`, `setup`, `context`, `skills`, `rules`), and `deps`
for the dependency files of every runtime, so an overlay that turned them off stays that way when
an edition adds a runtime, as with `lib`.

**Defaults that run code.** The `env_scripts` and `setup` defaults run scripts, and the `deps`
default runs a package manager. Running by default is never running silently: a consumer runs them only for an overlay it has activated, which is the
[trust decision](security.md#execution-and-dependencies), and reports each run as a
[weakening](security.md#weakenings): `env-script` for an env script, `setup-network` for a default
setup, `deps-network` for each dependency file installed, and `script-not-run` for a default
script present that cannot run.

No other name has a default. A `requirements.txt` or `package.json` outside `lib/<runtime>/`,
`pre.env`, `cmds/`, a bare `lib/` and any other file or directory mean nothing by their name, and a program in `bin/` is on `PATH`, not a
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
