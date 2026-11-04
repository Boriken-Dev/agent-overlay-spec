# Changelog

All notable changes to this specification are recorded here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and editions
follow [Semantic Versioning](https://semver.org/). AOS has not reached 1.0.

## [Unreleased]

The first edition, `0.1.0-draft`, a development draft open for review.

### Added

- The package format, manifest fields, composition, dependencies, sources, skills, commands, MCP
  declarations, security and conformance, grounded in the dotagents overlay format.
- A JSON Schema for the manifest, examples, and schema fixtures.
- The manifest is `overlay.cfg`: TOML unless its first line names another format (`#!json`,
  `#!yaml`, `#!/usr/bin/env yaml`), one leading byte-order mark ignored, nothing guessed from
  content. TOML is required of every reader; JSON and YAML are optional, and an unsupported format is
  refused by name. The schema describes the data model, the same in every format.
- Static reading: no include, import, interpolation, templating, YAML tag, anchor, alias or merge
  key; no null, date or non-finite value.
- Environment (Proposed): `env` with literals, paths under the root and secret references
  (`{ provider, key }` or `{ secret }`, with `if_unset` and `optional`); `env_files` in the
  manifest's own format or `dotenv`; `paths` additions to `PATH`, `PYTHONPATH` or any list variable,
  prepended or appended with the separator of the OS; the `<NAME>_OVERLAY_ROOT` variable defined;
  `env_scripts` with a named interpreter and a timeout, opt-in.
- Runtime and setup (Proposed): `runtime` with supported OSes, required commands and Python and
  Node.js variants (minimum version, `requirements` or `lock` with `lock_digest`); `setup` variants
  per OS with an interpreter (`python`, `bash`, `sh`, `powershell`, `node`), a timeout (default 300
  seconds), and a network need, run once per overlay digest with `AOS_OVERLAY_ROOT`,
  `AOS_OVERLAY_NAME` and `AOS_OVERLAY_STATE`.
- `skills` lists an overlay's skills; `context` lists initial-context files; `[harness.<id>]` gives
  per-harness context, skill delivery, model and effort hints (all Proposed).
- `[scripts]` entries may name an interpreter and OSes; a string path's interpreter follows from its
  extension. MCP server `env` values may be secret references, and stdio servers start in the
  overlay root (Proposed).

- Integrity (Proposed): the tree digest (`path NUL sha256:<hex> LF` per regular file, sorted by
  path bytes, SHA-256 of the lines; no normalization; `.git`, caches and `.pyc` excluded; links,
  special files, non-UTF-8 names and `\` refused; Git sources hashed from blob bytes), with 20 test
  vectors in `tests/vectors/digest.json`. Pins live in the consumer's configuration; a mismatch
  refuses the overlay.
- The source form `[git+]<location>[@<ref>][#<path>]`, specified with examples. A `#path` must be a
  relative path; a Git location holding `::`, a host or ref starting with `-`, or a scheme other than
  `https`, `http`, `ssh`, `git` and `file` is refused.
- Weakenings a consumer reports every time it applies one: `unpinned`, `setup-network`,
  `network-not-enforced`, `no-timeout`, `env-script`, `env-passthrough`, `secret-read`,
  `env-sensitive`, `unlocked-dependencies`, `insecure-transport`, with the list of sensitive
  variables (names, prefixes such as `GIT_` and `PIP_`, and the suffixes `_PROXY` and `_BASE_URL`).
- Secret references resolve only when the consumer's configuration grants them to that overlay;
  nothing is granted by default. Each overlay's own processes get only its own environment.
- `AOS_*`, `*_OVERLAY_ROOT` and `*_OVERLAY_STATE` are reserved: no overlay sets them.
- One rule for relative paths and digest members: no excluded or device name in any case, no
  trailing dot or space, no `\ : * ? " < > |`, control or invisible characters, no `~` and digit;
  a tree with two members equal under ASCII case has no digest.
- Reading refuses a byte-order mark after the format line, YAML directives and the characters
  U+0085, U+2028 and U+2029 in YAML. TOML constructs newer than TOML 1.0 are not portable: a reader
  refuses them or reads them with their TOML meaning.
- Harness hints act only on `context`, `skills`, `model` and `effort`; other keys are kept and not
  applied. MCP stdio commands with a separator are paths under the root; a batch file is never run
  as an interpreter or server on Windows.
- Lock and requirements files hold requirement lines only, and a lock installs binaries with hashes
  from an index the consumer names. Setup runs in its own process group, and the state directory is
  read-only inside the agent's sandbox.
- Defaults: files in conventional places take effect without a manifest. `bin/` is prepended to
  `PATH` and `lib/python/` to `PYTHONPATH`; `rules/*.md` are rules (Proposed), `CONTEXT.md` is
  context, `skills/*/SKILL.md` are skills; the root `env` is an env file read as `dotenv`
  (Proposed); one `env.<ext>` and one `setup.<ext>` run, the first in the order `.py`, `.js`,
  `.mjs`, `.cjs`, `.ps1` (Windows), `.bash`, `.sh` (other systems) that the consumer can run. Each
  stays on unless `[defaults]` turns it off (`bin`, `lib`, `env`, `env_scripts`, `setup`,
  `context`, `skills`, `rules`). Declared entries add to the defaults, and one naming the same
  file or directory as a default replaces it. A default setup is taken to need the network; the
  weakening `script-not-run` reports a default script that cannot run. `local.env` is not an
  overlay file. Examples `bin-only` and `conventions`, and vectors for each default on, off,
  declared and not runnable.
- An env script's output may also be one JSON object over several lines, as a pretty-printer
  writes it; reading vectors for that output.
- Substitution in env values (Proposed): `${NAME}`, `$$`, defaults `-` `:-` (`=` `:=` assign
  nothing), alternates `+` `:+`, nested words, `${#NAME}`, slices, glob replacements (`/`, `//`,
  `/#`, `/%`), trims (`#`, `##`, `%`, `%%`) and case changes (`^`, `^^`, `,`, `,,`), the `drone`
  envsubst dialect plus alternates; nothing runs, and `$NAME`, `$(...)` and backticks are
  characters. It applies to text in `env`, `aos` and `dotenv` files and MCP `env`, one value at a
  time in the order of application, so each value sees every earlier one, across lines, files and
  overlays, and its own earlier value; an overlay's own `AOS_OVERLAY_ROOT`, `AOS_OVERLAY_NAME` and
  `AOS_OVERLAY_STATE` are readable. An undefined name is an error; a variable holding a secret is
  never read; a single-quoted `dotenv` value is kept as written. Reading vectors for every operator,
  escapes, undefined names, quotes, nesting, chaining and secrets, and composition vectors for
  chains across overlays.
- Setup phases (Proposed): setup gets `install`, `sync` or `remove` as its first argument and in
  `AOS_SETUP_PHASE`, chosen from the digest of the last setup that succeeded; a failed `remove` is
  reported and the overlay removed anyway; a script treats an unknown phase as nothing to do.
  Vectors for the phase each change selects.

- Conformance vectors as JSON data in `tests/vectors/`: reading (format line, data model, static
  reading, limits, `dotenv`), validation of every field, names and root variables, source strings,
  the tree digest, resolution and composition, and one overlay's effective environment, setup,
  runtime, needs and weakenings. Conformance classes name the vectors each one passes.

### Changed

- `overlay.toml` is now `overlay.cfg`, with no second name.
- `setup_timeout` is replaced by `setup` variants; `setup.py` is one case of the default setup.
- Env scripts run by default in an activated overlay, each run reported, unless the consumer's
  policy turns them off; they are no longer a separate opt-in.
- A plain `env` file is read as `dotenv` instead of being sourced by a shell, and `pre.env` files
  mean nothing by name.
- Env values written as text are substituted instead of literal; `$$` writes a `$`.
- Setup runs `install` once, then `sync` once per new digest, instead of the same run once per
  digest, and `remove` on removal.
- `skills` adds to the skills found under `skills/` instead of replacing them; to offer only
  some, set `[defaults] skills = false` and list them.
- Composition order is `(priority, name, identity)` with code-point string comparison, for every
  contribution, not only rules and routing.
- Test, release and docs workflows; the docs site is published at
  `https://boriken-dev.github.io/agent-overlay-spec/`.

[Unreleased]: https://github.com/Boriken-Dev/agent-overlay-spec/commits/main
