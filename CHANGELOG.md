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

### Changed

- `overlay.toml` is now `overlay.cfg`, with no second name.
- `setup_timeout` and the `setup.py` file convention are replaced by `setup` variants.
- Composition order is `(priority, name, identity)` with code-point string comparison, for every
  contribution, not only rules and routing.
- Test, release and docs workflows; the docs site is published at
  `https://boriken-dev.github.io/agent-overlay-spec/`.

[Unreleased]: https://github.com/Boriken-Dev/agent-overlay-spec/commits/main
