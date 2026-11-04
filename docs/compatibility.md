# Compatibility and open decisions

This page compares the specification with dotagents 0.8.3, the reference implementation, from its
source and tests. "Proposed" in the specification means no implementation reads the field yet; the
table below is the list an implementation works from.

## What dotagents does and what AOS declares

| Topic | dotagents 0.8.3 | AOS |
| --- | --- | --- |
| Manifest | `overlay.toml`, TOML only; a small hand reader when no TOML library imports | `overlay.cfg`: TOML by default, `#!json` / `#!yaml` on the first line; static; one data model |
| Ordinary fields | Tolerant: a wrong type becomes the default, with a warning | A validator refuses; a consumer applies nothing of an invalid manifest |
| `name`, `description`, `requires`, `routing`, `rules`, `priority` | As specified | Unchanged (Core) |
| Root variable | `<NAME>_OVERLAY_ROOT`, set only when unset | Always set to the root the consumer exposes |
| Defaults | By file name, always on | On unless `[defaults]` turns one off (`bin`, `lib`, `env`, `env_scripts`, `setup`, `context`, `skills`, `rules`); declared entries add to them, and one naming a default's file or directory replaces it |
| `PATH` | Every overlay's `bin/` prepended, whether it exists or not | `bin/` prepended by default, only when it holds a file; with the separator of the OS |
| `PYTHONPATH` | An existing `lib/` prepended | **Changed:** `lib/python/` prepended by default; a bare `lib/` means nothing |
| Rules | Only the files `rules` lists | `rules/<name>.md` by default, in path order |
| Environment values | `env.py` / `pre.env.py` executed, `env` / `pre.env` sourced by bash, by file name | `env`, `env_files` (`aos` documents or `dotenv`), secret references. By default the root `env` is read as `dotenv` and one `env.<ext>` runs, chosen by runtime; `pre.env*` means nothing |
| A plain `env` file | Sourced by bash: `$(...)`, `$NAME` and shell code run | **Changed:** read as `dotenv`, every value literal, nothing run or expanded |
| `local.env` | Read from the project's own store, never from an overlay | Not an overlay file: a consumer's own scope, outside the format |
| Secrets | MCP `env_passthrough` and `headers_env` read the host environment | Secret references by provider and key, or by name; `env` provider reads are reported |
| Setup | `setup.py` by file name, under dotagents' Python, cwd the installed copy, on every add and sync | `setup` variants per OS with an interpreter, a timeout (300 s default), a network need; by default one root `setup.<ext>`, chosen by runtime and taken to need the network; once per digest; output into `AOS_OVERLAY_STATE` |
| `setup_timeout` | Top-level integer | `timeout` in each `setup` variant |
| Dependencies | `requirements.txt` by file name into a shared Python environment | `runtime.python`: minimum version, `requirements` (reported unlocked) or `lock` with `lock_digest`; one environment per digest |
| Runtime probing | None | `runtime.os`, `runtime.commands`, interpreter and version probes before placement |
| Context | Root `CONTEXT.md` by file name | The same by default, then the `context` list and per-harness `context` |
| Skills | Every `skills/*/SKILL.md` published | The same by default, for skill names, plus the `skills` list |
| Scripts | `bin/*.py` and `[scripts]` strings, run under Python | `[scripts]` only: strings by extension, or `{ path, interpreter, os }`; `bin/` is on `PATH`, and a file in it is no command by default |
| MCP stdio | Working directory inherited from the gateway; `env` strings | Working directory the overlay root; `env` values may be references |
| Harness hints | None | `[harness.<id>]`: `context`, `skills`, `model`, `effort` |
| Source form | `<location>[@<ref>][#<path>]`, registries, URI schemes | The same form, specified, with vectors |
| Integrity | A SHA-256 per installed file in its install record; no tree digest, no pin | The tree digest, pins checked at install and at each activation, a mismatch refuses |
| Installed copy | Keeps `.dotagents-install.json` and setup output inside the overlay directory | The copy stays as verified; state goes to `AOS_OVERLAY_STATE` |
| Weakenings | Not reported | Eleven identifiers reported each time, never silently |
| Secret grants | `env_passthrough` and `headers_env` pass any named host variable | A reference resolves only when the consumer's configuration grants it to that overlay |
| Reserved variables | An overlay's `env.py` can set any variable, another overlay's root included | `AOS_*`, `*_OVERLAY_ROOT`, `*_OVERLAY_STATE` cannot be set by an overlay |
| Relative paths | `[scripts]` paths checked; rules paths checked for containment | One rule for every path and digest member: no excluded or device names in any case, no trailing dot or space, no `:` or control characters |
| Source safety | Refuses a location or ref starting with `-` | Also refuses `::`, a host starting with `-`, other schemes, and a `#path` that is not a relative path |
| Processes per overlay | One environment for every overlay's processes | Each overlay's setup, scripts and servers get only that overlay's declarations |

## dotagents conventions that are not defaults

- **`bin/` when absent.** dotagents puts every overlay's `bin/` on `PATH` even when it does not
  exist, so a directory created later is found without rebuilding the environment. A default
  applies only when `bin/` holds a file: an entry that names nothing is noise on every search, and
  a directory that appears after the digest was checked is not what was pinned.
- **`bin/*.py` launchers.** dotagents makes a command for every top-level `bin/<name>.py`. A
  consumer exposes commands only for `scripts` entries: two overlays exposing the same command
  name is an error, and a default must not turn two overlays that declare nothing into an error.
  The program is still on `PATH`.
- **`requirements.txt`.** dotagents installs it into a shared Python environment by name. An
  unlocked file installs whatever the index serves on the day, so the digest would not pin what
  runs; AOS installs dependencies only from `runtime.python`, where an unlocked file is reported.
- **`pre.env.py`, `pre.env`.** dotagents runs them in a tier before every overlay's `env`. AOS has
  one env-script step per overlay, in composition order; an earlier step is a lower `priority`.
- **`cmds/`.** dotagents' own command modules, Implementation-Specific.
- **Arguments.** dotagents passes `--level <level>` to `env.py`; a default script gets none.

## Ambiguities and interoperability risks

- Overlay identity is the directory name in dotagents, while the manifest `name` affects display and
  ordering. Different tools may pick different identities unless the two normalize alike.
- dotagents' scope walk (system, user, project) and its shadowing are manager policy.
- Some MCP clients and harnesses handle credentials, inherited environment and skills differently;
  a consumer reports what it could not apply.
- URI source schemes depend on optional dependencies in dotagents.

## Proposals for a future edition

1. A versioned identity and alias model that keeps manifest-free overlays valid.
2. Dependency version constraints.
3. Extension namespaces and a policy for unknown extension tables.
4. Portable skill metadata that does not require one vendor's front matter.
5. Installing Node.js dependencies, and a PEP 751 lock file for Python.

Each needs review before it becomes normative.
