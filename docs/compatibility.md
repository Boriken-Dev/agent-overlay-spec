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
| `PATH` | Every overlay's `bin/` prepended, whether it exists or not | Only what `paths` declares, with the separator of the OS |
| `PYTHONPATH` | An existing `lib/` prepended | Only what `paths` declares |
| Environment values | `env.py` / `pre.env.py` executed, `env` / `pre.env` sourced by bash, by file name | `env`, `env_files` (`aos` documents or `dotenv`), secret references; env scripts opt-in, with a named interpreter and a timeout |
| Secrets | MCP `env_passthrough` and `headers_env` read the host environment | Secret references by provider and key, or by name; `env` provider reads are reported |
| Setup | `setup.py` by file name, under dotagents' Python, cwd the installed copy, on every add and sync | `setup` variants per OS with an interpreter, a timeout (300 s default), a network need; once per digest; output into `AOS_OVERLAY_STATE` |
| `setup_timeout` | Top-level integer | `timeout` in each `setup` variant |
| Dependencies | `requirements.txt` by file name into a shared Python environment | `runtime.python`: minimum version, `requirements` (reported unlocked) or `lock` with `lock_digest`; one environment per digest |
| Runtime probing | None | `runtime.os`, `runtime.commands`, interpreter and version probes before placement |
| Context | Root `CONTEXT.md` by file name | `context` list, plus per-harness `context` |
| Skills | Every `skills/*/SKILL.md` published | `skills` list when present, otherwise the same discovery |
| Scripts | `bin/*.py` and `[scripts]` strings, run under Python | Strings by extension, or `{ path, interpreter, os }` |
| MCP stdio | Working directory inherited from the gateway; `env` strings | Working directory the overlay root; `env` values may be references |
| Harness hints | None | `[harness.<id>]`: `context`, `skills`, `model`, `effort` |

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
