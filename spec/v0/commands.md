# Commands and executable assets

**Optional Extension.** `cmds/`, `bin/`, `scripts/` and `lib/` are common conventions. Their presence
does not make a package executable, and does not put anything on a search path: an overlay declares
that with [path additions](environment.md#path-additions).

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
`[A-Za-z0-9][A-Za-z0-9._-]*` and does not end in `.exe`. A script path uses only `A`–`Z`, `a`–`z`,
`0`–`9`, `_`, `+`, `-` and `.`, so a launcher can embed it without quoting. Two active overlays that
expose the same command name are an error the consumer reports before exposing either.

An implementation that exposes commands documents how a name is resolved, the arguments, working
directory, environment, interpreter, permissions, timeout, output and collision policy. Python is
not required for AOS.

> **Status:** dotagents makes a launcher for every top-level `bin/<name>.py` and every `[scripts]`
> entry, always running it under its own Python; `false` drops a discovered launcher. It reads the
> string form only. It also discovers its own command modules under `cmds/`, an
> Implementation-Specific convention.

## Setup and dependencies

Setup is declared by [`setup`](runtime.md#setup) and dependencies by [`runtime`](runtime.md#runtime).
A file named `setup.py`, `setup.sh` or `requirements.txt` means nothing by its name alone.

Portable assets are the file bytes and their relative paths. Command launchers, dependency
installation and setup are what a consumer does with the declarations; a consumer that does none of
them still reads the overlay.
