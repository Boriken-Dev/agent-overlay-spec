# Commands and executable assets

**Optional Extension.** `bin/` and `lib/python/` go on `PATH` and `PYTHONPATH` by
[default](package.md#defaults), which makes their programs findable and runs nothing. A consumer
exposes a command only for a `scripts` entry: no directory makes one, and `cmds/` and `scripts/`
mean nothing by their name.

## `scripts`

`scripts` maps a command name to the script a consumer exposes under that name, or to `false`:

```toml
[scripts]
check-format = "bin/check_format.py"
lint-shell = { path = "tools/lint.sh", interpreter = "bash", os = ["unix"] }
old-check = false
```

| Value | Meaning |
| --- | --- |
| a relative path | The script; its interpreter follows from its extension, below |
| `{ path, interpreter, os }` | **Proposed.** The script, a named [interpreter](runtime.md#interpreters), and optionally the OSes it applies on |
| `false` | No command under this name, even one a consumer would discover by itself |

| Extension | Interpreter |
| --- | --- |
| `.py` | `python` |
| `.sh` | `sh` |
| `.bash` | `bash` |
| `.ps1` | `powershell` |
| `.js`, `.mjs`, `.cjs` | `node` |

A path with another extension needs the mapping form. A command name matches
`[A-Za-z0-9][A-Za-z0-9._-]*` and does not end in `.exe` in any case. A script path is a
[relative path](manifest.md#fields) that uses only `A`–`Z`, `a`–`z`, `0`–`9`, `_`, `+`, `-` and
`.`, so a launcher can embed it without quoting. Two active overlays that expose command names equal
without regard to ASCII case are an error the consumer reports before exposing either.

An implementation that exposes commands documents how a name is resolved, the arguments, working
directory, environment, interpreter, permissions, timeout, output and collision policy. Python is
not required for AOS.

> **Status:** dotagents makes a launcher for every top-level `bin/<name>.py` and every `[scripts]`
> entry, always running it under its own Python; `false` drops a discovered launcher. It reads the
> string form only. It also discovers its own command modules under `cmds/`, an
> Implementation-Specific convention.

## Setup and dependencies

Setup is declared by [`setup`](runtime.md#setup), or is a root `setup.<ext>` by
[default](runtime.md#default-scripts); dependencies are `lib/python/requirements.txt` and
`lib/node/package.json` by [default](runtime.md#dependencies), or declared by
[`runtime`](runtime.md#runtime). A `requirements.txt` anywhere else means nothing by its name.

Portable assets are the file bytes and their relative paths. Command launchers, dependency
installation and setup are what a consumer does with the declarations; a consumer that does none of
them still reads the overlay.
