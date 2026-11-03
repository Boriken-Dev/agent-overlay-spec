# Authoring overlays

## Package layout

Keep each overlay in its own directory, and refer to its files with relative paths. Common paths are
`rules/`, `skills/`, `kb/`, `references/`, `workflows/`, `bin/`, `lib/`, `setup/`, `env/` and
`locks/`; only `overlay.cfg` and `skills/<name>/SKILL.md` mean something by their name. Everything
else means something when a field names it.

## The manifest

Start with the fields your consumers use:

```toml
name = "team-review"
description = "Review conventions for shared services."
requires = ["engineering"]
routing = ["- Service reviews → `$TEAM_REVIEW_OVERLAY_ROOT/kb/review.md`"]
rules = ["rules/review.md"]
priority = 450
```

Write it in TOML, or put `#!json` or `#!yaml` on the first line. Every reader reads TOML; JSON and
YAML are optional. Do not add a format version: the edition belongs to the specification. See the
[manifest reference](spec/v0/manifest.md) for every field.

## Declare what the overlay needs

- **Environment**: plain values, a path under the root, or a secret reference (`{ provider = "env",
  key = "TOKEN" }`, `{ secret = "name" }`), never a secret value. Env files hold the same.
- **Search paths**: `[[paths]]` puts `bin/` on `PATH` or `lib/` on `PYTHONPATH`, with the separator
  of each OS.
- **Runtime**: the OSes, the commands that must exist, a minimum Python with a locked requirements
  file and its digest.
- **Setup**: a script per OS with its interpreter, a timeout, and whether it needs the network.
  Setup writes into `$AOS_OVERLAY_STATE`, never into the overlay.

Each of these is a weakening when it loosens a default (network for setup, reading the host's
environment, unlocked dependencies, no timeout), and consumers report it. Declare only what you need.

## Skills and commands

Put a skill in `skills/<skill-name>/SKILL.md` and list it in `skills`. A `[scripts]` entry names a
command and its script; give the interpreter when the extension does not say it.

## Checks

Validate the parsed manifest against the [schema](schemas/overlay.schema.json) and check that every
file a field names exists. Review setup, scripts and dependency declarations as code. In this
repository, `python -m pytest` runs every example and fixture.
