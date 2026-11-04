# Authoring overlays

## Package layout

Keep each overlay in its own directory, and refer to its files with relative paths. Put files where
a consumer looks for them, and they work with no manifest:

| Put | And a consumer |
| --- | --- |
| programs in `bin/` | puts `bin/` first on `PATH` |
| Python modules in `lib/python/` | puts `lib/python/` first on `PYTHONPATH` |
| Node.js modules in `lib/node/` | puts `lib/node/` first on `NODE_PATH` |
| the packages they need in `lib/python/requirements.txt` or `lib/node/package.json` | installs them before setup, at every install and sync, and reports it |
| always-on rules in `rules/<name>.md` | adds them to the always-on rules |
| initial context in `CONTEXT.md` | adds it to the agent's first context |
| a skill in `skills/<name>/SKILL.md` | offers the skill |
| `NAME=value` lines in `env` | sets them in order, substituting `${NAME}` placeholders |
| a script in `env.py` (or `.js`, `.ps1`, `.sh`, ...) | runs it to compute environment values, and reports it |
| a script in `setup.py` (or `.ps1`, `.sh`, ...) | runs it with its phase (`install` on the first add, `sync` on every sync, `remove`), with the network, and reports it |

Other common paths are `kb/`, `references/`, `workflows/`, `setup/`, `env/` and `locks/`; they mean
something when a field names them. A `local.env` is not part of an overlay: local overrides belong to
the user's or project's own configuration.

## Defaults and how to turn one off

Each [default](spec/v0/package.md#defaults) stays on until you turn it off in `[defaults]`, one
key each: `bin`, `lib`, `env`, `env_scripts`, `setup`, `deps`, `context`, `skills`, `rules`.

```toml
[defaults]
setup = false
```

What you declare adds to the defaults: a `[[paths]]` entry for `man/` keeps `bin/` on `PATH`. An
entry that names the same file or directory as a default replaces that default, so it is never
applied twice. To append `lib/python/` instead of prepending it:

```toml
[[paths]]
variable = "PYTHONPATH"
path = "lib/python"
position = "append"
```

When you ship several env scripts or setup scripts, a consumer runs one: the first that can run, in
the order `.py`, `.js`, `.mjs`, `.cjs`, `.ps1` (Windows), `.bash`, `.sh` (the other systems). Ship
`env.ps1` beside `env.sh` to give each OS its own.

A default setup is taken to need the network. If yours does not, declare an entry naming it, so the
consumer can deny it the network:

```toml
[[setup]]
interpreter = "sh"
path = "setup.sh"
network = false
```

## Values that use other values

An env value can read other variables, as a shell would in `"${...}"`, but nothing runs:

```text
# env, read line by line: each line sees the lines before it
TOOL_HOME=${AOS_OVERLAY_ROOT}/tool
TOOL_CACHE=${TOOL_CACHE_DIR:-${TOOL_HOME}/cache}
PATH=${TOOL_HOME}/bin:${PATH}
TOOL_PROMPT='${USER}$ '
```

- `PATH=...${PATH}` reads `PATH` as it was before the line. An overlay with a `bin/` cannot also set
  `PATH`: there, `bin/` is already on it.
- `${AOS_OVERLAY_ROOT}` is your overlay's root, whatever name it was installed under;
  `${AOS_OVERLAY_STATE}` is its state directory. They are readable here, not set.
- **An unset name is an error.** Give a default where a variable may be missing: `${NAME:-default}`,
  or `${NAME-}` for empty. A refused value is better than `/bin` where you meant `$TOOL_HOME/bin`.
- Defaults (`-`, `:-`), alternates (`+`, `:+`), the length `${#NAME}`, slices `${NAME:1:3}`,
  replacements `${NAME//:/ }`, trims `${FILE%.*}` and case `${NAME^^}` work as in bash, on
  globs. `$NAME` without braces, `$(...)` and backticks are characters; `$$` is a `$`.
- Single quotes keep a `dotenv` value as written. In `overlay.cfg` and `aos` env files a string is
  substituted the same way; write `$${` for a literal `${`.
- Values chain in order: earlier lines and files, then `env`, and every overlay before yours. The
  entries of one mapping (`env`, one `aos` file) do not see each other, so put a value you reuse in
  an earlier file or line.
- A placeholder cannot read a variable set from a secret reference. Use the reference itself.

## The manifest

Start with the fields your consumers use:

```toml
name = "team-review"
description = "Review conventions for shared services."
requires = ["engineering"]
routing = ["- Service reviews → `$TEAM_REVIEW_OVERLAY_ROOT/kb/review.md`"]
priority = 450
```

Write it in TOML, or put `#!json` or `#!yaml` on the first line. Every reader reads TOML; JSON and
YAML are optional. Do not add a format version: the edition belongs to the specification. See the
[manifest reference](spec/v0/manifest.md) for every field.

## Declare what the overlay needs

- **Environment**: plain values, a path under the root, or a secret reference (`{ provider = "env",
  key = "TOKEN" }`, `{ secret = "name" }`), never a secret value. Env files hold the same.
- **Search paths**: `bin/` and `lib/python/` need nothing. `[[paths]]` adds other directories, or
  adds to another list variable, with the separator of each OS.
- **Runtime**: the OSes, the commands that must exist, a minimum Python with a locked requirements
  file and its digest.
- **Dependencies**: list packages in `lib/python/requirements.txt` and `lib/node/package.json`.
  Pin them: a `--hash` on every requirement (`pip-compile --generate-hashes` writes one), and a
  `package-lock.json` beside `package.json`; an unpinned file still installs, and is reported.
  They go into the scope's shared environment, where every overlay's packages are installed
  together, so two overlays pinning one package to two versions both fail to activate. To keep
  yours apart, choose a name several overlays share, or `isolated`:

  ```toml
  [[runtime.python]]
  environment = "isolated"
  ```

  An ES module reads a package from `NODE_PATH` through `createRequire(import.meta.url)`.
- **Setup**: a script per OS with its interpreter, a timeout, and whether it needs the network.
  Setup writes into `$AOS_OVERLAY_STATE`, never into the overlay; that directory is kept from one
  sync to the next. Its first argument (and `$AOS_SETUP_PHASE`) is the phase: `install` on the
  first add, `sync` on every sync (also when nothing changed, and when the user asks to run setup
  again), `remove` before the overlay and its state are deleted. Make `sync` cheap when there is
  nothing to do, and update the state in place so a failure leaves the old state usable. Do
  nothing, successfully, for a phase you do not know; a script that ignores the phase still
  works, and returns early on `remove` if its setup is slow:

  ```sh
  case "${1:-}" in
    install|sync) prepare ;;
    remove) cleanup ;;
    *) ;;
  esac
  ```

Each of these is a weakening when it loosens a default (network for setup or for installing
dependencies, reading the host's environment, unlocked dependencies, no timeout), and consumers
report it. Declare only what you need.

## Skills and commands

Put a skill in `skills/<skill-name>/SKILL.md`. To offer only some of them, set
`[defaults] skills = false` and list them in `skills`.
A `[scripts]` entry names a command and its script; give the interpreter when the extension does not
say it.

## Listing in a store

A store shows your overlay's `name` and `description`, and what you put in `[about]`. Every field
is optional and only shown: nothing in `[about]` changes what the overlay does, and a mistake in it
never stops the overlay from working.

```toml
[about]
summary = "Release notes and changelogs, written the same way in every repository."
icon = "icon.webp"
homepage = "https://example.org/overlays/release-notes"
repository = "https://github.com/example/overlays"
license = "MIT OR Apache-2.0"
authors = ["Example Docs Team <docs@example.org>"]
tags = ["documentation", "release", "changelog"]
```

- Keep `summary` to one short line; `description` holds the longer text.
- Ship the icon as a square PNG or WebP of 256 by 256 pixels or more, under 512 KiB and at most
  1024 pixels a side, the limits stores use by default. SVG is not accepted. Name it in `icon`: no
  file is an icon by its name.
- Links are `https`. `license` is an SPDX expression (`MIT`, `MIT OR Apache-2.0`).
- Tags are lowercase words joined by `-`; a store filters and searches by them.

To offer several overlays, publish a **catalog**: a TOML, JSON or YAML file, named by its format,
listing each overlay's source. A registry is already one; add tables where you want a store to show
more, and a `pin` where you reviewed a revision:

```toml
name = "Example overlays"

[overlays]
engineering = "../engineering"

[overlays.release-notes]
source = "https://github.com/example/overlays.git#release-notes"
ref = "v1.4.0"
pin = "sha256:8280aaf5de7c4f61342f648586d534e481ae095cef223dded70f5b1db5bd84a1"

[overlays.release-notes.about]
summary = "Release notes and changelogs, written the same way in every repository."
icon = "icons/release-notes.png"
```

Relative sources and icons resolve beside the catalog file. A store shows what a catalog says
until it fetches the overlay, then shows the overlay's own manifest, so keep the two in step. See
[`examples/registry/catalog.toml`](https://github.com/Boriken-Dev/agent-overlay-spec/blob/main/examples/registry/catalog.toml).

## Checks

Validate the parsed manifest against the [schema](schemas/overlay.schema.json) and check that every
file a field names exists. Review setup, scripts and dependency declarations as code, and the
`env.<ext>` and `setup.<ext>` files that run by default. In this
repository, `python -m pytest` runs every example and fixture.
Validate a catalog against the schema's `$defs/catalog`, and its icons as a store would.
