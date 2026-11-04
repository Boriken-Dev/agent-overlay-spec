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
| Defaults | By file name, always on | On unless `[defaults]` turns one off (`bin`, `lib`, `env`, `env_scripts`, `setup`, `deps`, `context`, `skills`, `rules`); declared entries add to them, and one naming a default's file or directory replaces it |
| `PATH` | Every overlay's `bin/` prepended, whether it exists or not | `bin/` prepended by default, only when it holds a file; with the separator of the OS |
| `PYTHONPATH` | An existing `lib/` prepended | **Changed:** `lib/python/` prepended by default; a bare `lib/` means nothing |
| `NODE_PATH` | Not set | `lib/node/` prepended by default, then the overlay's installed Node.js packages |
| Rules | Only the files `rules` lists | `rules/<name>.md` by default, in path order |
| Environment values | `env.py` / `pre.env.py` executed, `env` / `pre.env` sourced by bash, by file name | `env`, `env_files` (`aos` documents or `dotenv`), secret references. By default the root `env` is read as `dotenv` and one `env.<ext>` runs, chosen by runtime; `pre.env*` means nothing |
| A plain `env` file | Sourced by bash: `$(...)`, `$NAME` and shell code run | **Changed:** read as `dotenv`; `${NAME}` and its operators substituted line by line, single-quoted values kept as written, nothing run |
| Substitution | None of its own: bash expands what it sources; `overlay.toml` strings are literal | Every env value written as text (in `env`, `aos` and `dotenv` files, MCP `env`) substituted when set, in the order of application, against the environment as it stands; an undefined name is an error; a variable holding a secret is never read; see [Substitution with tplx](#substitution-with-tplx) |
| `local.env` | Read from the project's own store, never from an overlay | Not an overlay file: a consumer's own scope, outside the format |
| Secrets | MCP `env_passthrough` and `headers_env` read the host environment | Secret references by provider and key, or by name; `env` provider reads are reported |
| Setup | `setup.py` by file name, under dotagents' Python, cwd the installed copy, on every add and sync | `setup` variants per OS with an interpreter, a timeout (300 s default), a network need; by default one root `setup.<ext>`, chosen by runtime and taken to need the network; output into `AOS_OVERLAY_STATE` |
| Setup phases | No argument; run on every add and every sync, never on remove | The same runs, with the phase first, before `args`, and in `AOS_SETUP_PHASE`: `install` on the first add, `sync` on every sync whether or not the digest changed, `remove` on removal (its failure reported, the removal done anyway); a consumer with no sync of its own runs `sync` when the digest differs from the record |
| `setup_timeout` | Top-level integer | `timeout` in each `setup` variant |
| Dependencies | A root `requirements.txt` by file name into one Python environment per store | **Changed:** `lib/python/requirements.txt` and `lib/node/package.json` by default, or a file `runtime.python` / `runtime.node` names; installed at `install` and every `sync`, before setup; pinned by hashes or `package-lock.json`, an unpinned file reported; into the scope's shared environment (as dotagents' per-store one), a named one, or the overlay's own; conflicting pins block the overlays involved |
| Runtime probing | None | `runtime.os`, `runtime.commands`, interpreter and version probes before placement |
| Context | Root `CONTEXT.md` by file name | The same by default, then the `context` list and per-harness `context` |
| Skills | Every `skills/*/SKILL.md` published | The same by default, for skill names, plus the `skills` list |
| Scripts | `bin/*.py` and `[scripts]` strings, run under Python | `[scripts]` only: strings by extension, or `{ path, interpreter, os }`; `bin/` is on `PATH`, and a file in it is no command by default |
| MCP stdio | Working directory inherited from the gateway; `env` strings | Working directory the overlay root; `env` values may be references |
| Harness hints | None | `[harness.<id>]`: `context`, `skills`, `model`, `effort` |
| Source form | `<location>[@<ref>][#<path>]`, registries, URI schemes | The same form, specified, with vectors |
| Integrity | A SHA-256 per installed file in its install record; no tree digest, no pin | The tree digest, pins checked at install and at each activation, a mismatch refuses |
| Installed copy | Keeps `.dotagents-install.json` and setup output inside the overlay directory | The copy stays as verified; state goes to `AOS_OVERLAY_STATE`, one directory per identity and OS kept across syncs |
| Weakenings | Not reported | Twelve identifiers reported each time, never silently |
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
- **`requirements.txt` at the root.** dotagents installs a root `requirements.txt` by name. AOS
  reads it from `lib/python/requirements.txt`, beside the modules that import it, and keeps
  `lib/<runtime>/` for each runtime's manifest. An unpinned file installs whatever the index
  serves that day, so it is reported as `unlocked-dependencies`.
- **`pre.env.py`, `pre.env`.** dotagents runs them in a tier before every overlay's `env`. AOS has
  one env-script step per overlay, in composition order; an earlier step is a lower `priority`.
- **`cmds/`.** dotagents' own command modules, Implementation-Specific.
- **Arguments.** dotagents passes `--level <level>` to `env.py`; a default env script gets none, and
  a default setup only its phase.

## Substitution with tplx

[tplx](https://pypi.org/project/tplx/) has the substitution AOS defines, so a Python consumer such as
dotagents can use it instead of its own parser. Its `EnvsubstTemplate` with the `drone` dialect and
`alternate` added to its `FEATURES` reads the same syntax: braced placeholders only (`PATTERN` is
`braced`), and the features `escape`, `default`, `assign`, `alternate`, `nested`, `slice`,
`replace`, `trim`, `case` and `length`, without `unquote`:

```python
from tplx.engines import EnvsubstTemplate

class AOSEnvsubst(EnvsubstTemplate):
    DIALECT = "drone"
    FEATURES = EnvsubstTemplate.DIALECTS["drone"][1] | {"alternate"}
```

**Chaining.** `ShellTemplate.expand(text, variables)` substitutes one string against a mapping. A
consumer calls it once per value, in the order of application, with the environment as it stands,
and sets the result before the next value: `PATH=${MYTOOL_HOME}/bin:${PATH}` after
`MYTOOL_HOME=...` gives the new directory before the old `PATH`, as the
[vectors](https://github.com/Boriken-Dev/agent-overlay-spec/tree/main/tests/vectors) check. This was
checked against tplx 0.2.1, with these conditions:

- `expand` is a method of a template, so the consumer builds one from the text,
  `AOSEnvsubst(text).expand(text, variables)`; it is not in the API that tplx's `AGENTS.md`
  documents, so a consumer pins the version.
- A template built without a loader is strict: an undefined name raises `UndefinedError`, as AOS
  requires. A template from a loader takes the loader's mode, which must be `strict`.
- tplx looks a name up as `name.upper()`, so the mapping's keys are upper case and every name
  matches without regard to case. Off Windows, where AOS matches names exactly, build the mapping
  from `template.references()`: each name the text reads, upper-cased, to the value AOS's own lookup
  gives for it. The result then differs only for a value that reads two names equal under ASCII case.
- The mapping also holds the overlay's own `AOS_OVERLAY_ROOT`, `AOS_OVERLAY_NAME` and
  `AOS_OVERLAY_STATE`.
- tplx cannot know which variables hold a secret. It reads a variable through the mapping's `get`,
  and only when the expression needs it, so a mapping whose `get` raises for those names enforces
  [the rule](spec/v0/environment.md#secrets-and-substitution) at the same moment AOS does.

Two further departures, each in text no author needs: tplx accepts a slice written with non-ASCII
digits or white space (`${A: ١}`), which AOS leaves as text, and reads brackets that hold only a
negation as part of a later bracket expression (`${A/[!]x[y]/z}`) where AOS refuses the pattern.
The [reading vectors](https://github.com/Boriken-Dev/agent-overlay-spec/tree/main/tests/vectors)
cover both.

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
5. A PEP 751 `pylock.toml` for Python, once pip installs it without calling it experimental, and
   dependency files for runtimes other than Python and Node.js.

Each needs review before it becomes normative.
