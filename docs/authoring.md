# Authoring overlays

## Package layout

Keep each overlay in its own directory, and refer to its files with relative paths. Put files where
a consumer looks for them, and they work with no manifest:

| Put | And a consumer |
| --- | --- |
| programs in `bin/` | puts `bin/` first on `PATH` |
| Python modules in `lib/` | puts `lib/` first on `PYTHONPATH` |
| always-on rules in `rules/<name>.md` | adds them to the always-on rules |
| initial context in `CONTEXT.md` | adds it to the agent's first context |
| a skill in `skills/<name>/SKILL.md` | offers the skill |
| `NAME=value` lines in `env` | sets them, as literal values |
| a script in `env.py` (or `.js`, `.ps1`, `.sh`, ...) | runs it to compute environment values, and reports it |
| a script in `setup.py` (or `.ps1`, `.sh`, ...) | runs it once per version, with the network, and reports it |

Other common paths are `kb/`, `references/`, `workflows/`, `setup/`, `env/` and `locks/`; they mean
something when a field names them. A `local.env` is not part of an overlay: local overrides belong to
the user's or project's own configuration.

## Defaults and how to turn one off

A field you do not write takes its [default](spec/v0/package.md#defaults) from your files. A field
you write is exactly what you wrote: write `paths = []`, `skills = []`, `env_scripts = []` and so on
to turn a default off, and write the whole list to change one entry. To keep `bin/` on `PATH` and
append `lib/` instead of prepending it, list both:

```toml
[[paths]]
variable = "PATH"
path = "bin"

[[paths]]
variable = "PYTHONPATH"
path = "lib"
position = "append"
```

When you ship several env scripts or setup scripts, a consumer runs one: the first that can run, in
the order `.py`, `.js`, `.mjs`, `.cjs`, `.ps1` (Windows), `.bash`, `.sh` (the other systems). Ship
`env.ps1` beside `env.sh` to give each OS its own.

A default setup is taken to need the network. If yours does not, declare it, so the consumer can
deny it the network:

```toml
[[setup]]
interpreter = "sh"
path = "setup.sh"
network = false
```

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
- **Search paths**: `bin/` and `lib/` need nothing. `[[paths]]` adds other directories, or adds to
  another list variable, with the separator of each OS; it replaces the default, so list `bin/` and
  `lib/` in it too when you still want them.
- **Runtime**: the OSes, the commands that must exist, a minimum Python with a locked requirements
  file and its digest.
- **Setup**: a script per OS with its interpreter, a timeout, and whether it needs the network.
  Setup writes into `$AOS_OVERLAY_STATE`, never into the overlay.

Each of these is a weakening when it loosens a default (network for setup, reading the host's
environment, unlocked dependencies, no timeout), and consumers report it. Declare only what you need.

## Skills and commands

Put a skill in `skills/<skill-name>/SKILL.md`; list skills in `skills` only to offer some of them.
A `[scripts]` entry names a command and its script; give the interpreter when the extension does not
say it.

## Checks

Validate the parsed manifest against the [schema](schemas/overlay.schema.json) and check that every
file a field names exists. Review setup, scripts and dependency declarations as code, and the
`env.<ext>` and `setup.<ext>` files that run by default. In this
repository, `python -m pytest` runs every example and fixture.
