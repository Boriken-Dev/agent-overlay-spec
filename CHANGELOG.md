# Changelog

All notable changes to this specification are recorded here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and editions
follow [Semantic Versioning](https://semver.org/). AOS has not reached 1.0.

## [Unreleased]

The first edition, `0.1.0-draft`, a development draft open for review.

### Added

- `OVERLAY.md` (Proposed): the manifest as front matter, YAML by default or as a `#!<format>` first line
  inside the fence names, holding the same fields as `overlay.cfg`, `about` included; a body with anything
  but white space is the overlay's context, and `CONTEXT.md` beside it is ignored and reported. An overlay
  with both `OVERLAY.md` and `overlay.cfg` is refused; `overlay.cfg` stays readable, TOML by default. Digest
  rules are unchanged. A consumer that does not read `OVERLAY.md` says so, or refuses the overlay.
- The split of a document into metadata and body, a normative rule with vectors in
  `tests/vectors/front_matter.json`: no fence, unterminated, too large, empty, an unknown format, metadata
  that does not parse or is no mapping, as a viewer and a gate each treat them; the closing fence (`---` or
  `...`, blanks allowed after it); a byte-order mark and `\r`; the body's bytes never changed; positions;
  bounds as settings with no floor, and nothing read past one.
- `skills` entries may be a name for the consumer's catalogs to resolve, or a table of `name`, `source`,
  `ref` and `pin` (Proposed). Catalogs gain a `skills` table. Missing and ambiguous names are reported and
  never guessed, an entry with no pin is reported `unpinned`, "what it would do" lists them with their
  sources, and a consumer that does not fetch says so of each. A manifest names no local source and holds
  no credential; a fetched skill is checked against its pin first, needs a `SKILL.md`, and must not name
  another skill. Vectors in `tests/vectors/skills.json`.
- Hooks (Proposed): `hook.<ext>` at the root, chosen by runtime, and a `hooks` field mapping an event to
  a script, a table of `run`, `match`, `timeout` and `on_failure`, or `false`; a `hooks` key in
  `defaults`. Core events `pre-env`, `session-start` (with a `reason`), `session-end`, `prompt` and
  `turn-end`; Extended `cd`, `pre-compact`, `pre-tool` and `post-tool`, matched by ACP tool kind.
  `hook.<ext>` gets the events with no content by default; `prompt` and the tool events only when
  declared. A hook is told its event as its first argument and `AOS_HOOK_EVENT`, and a payload of that
  event's keys alone on standard input; its output adds context, blocks, denies or asks, and sets
  variables where the consumer can, through a loader with no decision for a shell. No output approves:
  any other decision is refused (`grant`). Time, output and payload bounded by settings; a failure is
  reported (`hook-failed`), and `on_failure = "refuse"` fails a guard closed. An overlay's hooks are off
  until the user allows them at its digest (`hook-not-allowed`), a running one is the weakening `hook`,
  and an event a consumer cannot fire is reported (`hook-unsupported`), as is an output it cannot apply
  (`hook-not-applied`). A scope's own configuration may declare hooks too, the user's with no allowance.
  `pre-env` output applies after the root variables and before every overlay's declarations. Vectors in
  `tests/vectors/hooks.json`, with `pre-env` cases in `compose.json` and the field's in `validation.json`.

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
  seconds), and a network need, run with `AOS_OVERLAY_ROOT`, `AOS_OVERLAY_NAME` and
  `AOS_OVERLAY_STATE`.
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
  `AOS_SETUP_PHASE`: `install` on the first add, `sync` on every sync (a fetch of the source
  whatever it finds, a change of source, ref or pin, or setup run again on request), `remove` on
  removal; a consumer with no sync of its own runs `sync` before activating a digest other than the
  recorded one. The record per identity and OS holds the digest and phase of the last preparation
  that succeeded. The state directory belongs to the identity and OS, kept across syncs and
  digests, made empty before `install`, deleted after `remove`, read-only in the sandbox. A failed
  `install` or `sync` keeps the record and blocks the digest it ran for, except the recorded one;
  a failed `remove` is reported and the overlay removed anyway; an overlay under a new identity is
  removed and added again. A script treats an unknown phase as nothing to do. Vectors for the
  phase, the steps, the record and activation of each operation, with failures.
- Dependencies (Proposed): `lib/python/requirements.txt` and `lib/node/package.json` install by
  default at `install` and every `sync`, before setup (`[defaults] deps`), unless a
  `runtime.python` file or a `runtime.node` `package` replaces them. A hash on every requirement,
  or a `package-lock.json` beside `package.json` (`npm ci`), pins a file; an unpinned one installs
  and is reported `unlocked-dependencies`; a partly hashed one is refused. Each install is reported
  `deps-network`, and needs its interpreter and package manager (`npm`). `lib/node/` is on
  `NODE_PATH`. `environment` (`"shared"` by default, a name, or `"isolated"`) chooses the
  environment: shared ones install every member's file in one run, in composition order, block
  overlays whose pins conflict, are rebuilt on every install, sync and removal, and live while an
  overlay uses them. Vectors for each default, overrides, pins, sharing, conflicts and removal.
  A consumer may isolate every overlay, per digest too, but never shares an overlay that chose a
  name or `isolated`.
- Store metadata (Proposed): an informational `[about]` table with `summary`, `icon`, `homepage`,
  `repository`, `license` (an SPDX expression), `authors` and `tags`. Only a store and a validator
  read it; nothing in it changes what an overlay does, and a problem in it never stops the manifest
  from applying. Icons are PNG or WebP, never SVG, checked against size and dimension limits (512
  KiB and 1024 pixels a side by default) before decoding, with a store's own placeholder when one
  is missing or refused.
- Catalogs: the registry, extended. A string entry is the minimal form dotagents reads; a table
  entry (`source`, `ref`, `pin`, `description`, `about`) and catalog-level `name`, `description`
  and `homepage` make the full form (Proposed). The file extension selects the format; relative
  sources resolve beside the catalog; a catalog from a repository or a URL cannot name a local
  source; a bad entry is refused alone. Several catalogs are labelled by the consumer, a name they
  share is shown qualified and never picked silently. Catalog metadata is advertising: the fetched
  overlay is authoritative, a catalog pin is checked, and what an overlay would do is shown from
  its own manifest before it is installed. A Store conformance class, `catalog.json` vectors
  (catalogs, collisions, icons), `catalog` reading cases and `about` validation cases; examples
  `about` and `registry/catalog.toml`.

- Conformance vectors as JSON data in `tests/vectors/`: reading (format line, data model, static
  reading, limits, `dotenv`), validation of every field, names and root variables, source strings,
  the tree digest, resolution and composition, and one overlay's effective environment, setup,
  runtime, needs and weakenings. Conformance classes name the vectors each one passes.

### Changed

- **YAML is required of every reader**, as a [restricted subset](spec/v0/manifest.md#restricted-yaml) of YAML
  1.2; TOML stays required and `overlay.cfg` keeps its default of TOML. JSON stays optional. The depth bound
  holds while parsing, in every format, and a mapping key `<<` is refused in any scalar style.
- A validator no longer refuses a listed skill with no directory: it flags it (`skill-from-catalog`), and
  refuses a table whose name is also bundled and a name differing from a bundled one only in case. A skill
  name is also a single path component.
- Sources: an `@` in a URL's authority is user information, never a ref; a source holds no control or
  reordering character and an authority no backslash; a user, port or scp-like path starting with `-`,
  percent-decoded, is refused. A catalog from elsewhere names no host that is this machine, no location
  that is neither Git nor the web, and no credential (`source-credentials`).
- A skill from elsewhere never takes a name another overlay's skill holds by default; a fetched skill has
  YAML front matter naming it, and its other keys are reported (`skill-keys`); a bundled `SKILL.md` naming
  another skill is not delivered. A source over `http` or `git://` is reported `insecure-transport`, one at a
  private address `private-source`.
- A document that looks like front matter and is not is refused at a gate (`malformed-fence`); U+FEFF is
  refused in YAML; an integer past 64 bits is refused before it is converted; reading is linear in the text;
  no field names a manifest (`manifest-file`); a consumer bounds the context it adds.
- A front matter block in a context file follows the split: blanks after a fence are allowed, and only a line
  feed ends a line. A catalog may hold `overlays`, `skills` or both, and one from elsewhere cannot name a
  `file:` URL of any kind.
- The order of application gains a step: every overlay's allowed `pre-env` hook output, after the root
  variables and before any overlay's declarations. A harness hint still adds no hook; `hooks` is the one
  route, and is listed before installing.

- `overlay.toml` is now `overlay.cfg`, with no second name.
- `setup_timeout` is replaced by `setup` variants; `setup.py` is one case of the default setup.
- Env scripts run by default in an activated overlay, each run reported, unless the consumer's
  policy turns them off; they are no longer a separate opt-in.
- A plain `env` file is read as `dotenv` instead of being sourced by a shell, and `pre.env` files
  mean nothing by name.
- Env values written as text are substituted instead of literal; `$$` writes a `$`.
- Setup runs `install` on the first add, then `sync` on every sync, whether or not the digest
  changed, instead of the same run once per digest, and `remove` on removal. The state directory
  belongs to the overlay's identity and OS instead of its digest.
- `lib/python/requirements.txt` installs by default instead of meaning nothing, into the scope's
  shared environment instead of one per digest, and `runtime.node` can name a `package.json`.
- `NODE_PATH` joins `PATH` and `PYTHONPATH` as a variable `paths` adds to without `env-sensitive`.
- `skills` adds to the skills found under `skills/` instead of replacing them; to offer only
  some, set `[defaults] skills = false` and list them.
- Composition order is `(priority, name, identity)` with code-point string comparison, for every
  contribution, not only rules and routing.
- Test, release and docs workflows; the docs site is published at
  `https://boriken-dev.github.io/agent-overlay-spec/`.

[Unreleased]: https://github.com/Boriken-Dev/agent-overlay-spec/commits/main
