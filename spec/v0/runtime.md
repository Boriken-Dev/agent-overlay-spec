# Runtime and setup

**Optional Extension, Proposed.** An overlay declares what must exist where it runs (`runtime`) and
what to run once to prepare it (`setup`). A consumer reads both without running anything, so it can
decide where an overlay can go, and refuse with a reason, before it fetches or starts anything.

> **Status:** dotagents runs `setup.py` at the overlay root under its own Python, on every add and
> sync unless `--no-setup` is given, stopped after `setup_timeout` seconds (default 300, `0` for no
> limit): the `.py` case of the [default setup](#default-scripts), run more often than once per
> digest, with no [phase](#setup-phases) argument and never on remove. It installs
> `requirements.txt` into a Python environment by file name, which AOS does not do by default. It
> reads none of the fields below yet.

## Operating systems

Fields with an `os` key take an array of these names; an absent `os` means every OS.

| Name | Matches |
| --- | --- |
| `windows` | Windows |
| `macos` | macOS |
| `linux` | Linux, including Android and WSL |
| `freebsd`, `openbsd`, `netbsd` | that BSD |
| `unix` | every OS above except `windows` |

Other lowercase names (`[a-z][a-z0-9-]*`) are allowed for other systems; a name a consumer does not
know matches nothing. An array that would match nothing on any OS is not an error.

Where a field is an array of **variants** (`setup`, the entries of `runtime.python`), the first
variant whose `os` matches the current OS is the one that applies; the others are ignored. No
matching variant means the field does not apply on this OS.

## Interpreters

A script names its interpreter; nothing is inferred from its content or a `#!` line.

| Name | Runs | Invocation |
| --- | --- | --- |
| `python` | Python 3 | the [Python runtime](#runtime)'s interpreter, `<python> <script> <args>` |
| `bash` | GNU Bash | `bash <script> <args>` |
| `sh` | a POSIX shell | `sh <script> <args>` |
| `powershell` | PowerShell 7 or later | `pwsh -NoLogo -NoProfile -NonInteractive -File <script> <args>` |
| `node` | Node.js | `node <script> <args>` |

`<script>` is the absolute path of the script under the root, passed as one argument; arguments are
passed as a list, never through a shell's parsing, and none holds a zero byte. A consumer finds the
interpreter on the base environment's `PATH`, never through an overlay's
[path additions](environment.md#path-additions). On Windows it MUST NOT resolve an interpreter to a
batch file (`.cmd`, `.bat`): `cmd.exe` would parse the arguments again. A consumer MAY support
further interpreters under names of its own. A consumer that meets an interpreter it does not support MUST refuse the overlay
on that OS with an error naming the interpreter, before running anything of it.

An interpreter that a selected setup variant, env script or script names is a requirement, as if
`runtime` had declared it.

## Default scripts

**Optional Extension.** Unless `[defaults]` turns it off, a consumer runs at most one script by
[default](package.md#defaults) for `env_scripts` and one for `setup`: `env.<ext>`, or
`setup.<ext>`, at the overlay root. It tries the extensions in this order and takes the first whose
file is present, that applies on the current OS, and whose interpreter it can run (one it supports
and finds on the base environment's `PATH`):

| Order | Extension | Interpreter | Applies on |
| --- | --- | --- | --- |
| 1 | `.py` | `python` | every OS |
| 2 | `.js` | `node` | every OS |
| 3 | `.mjs` | `node` | every OS |
| 4 | `.cjs` | `node` | every OS |
| 5 | `.ps1` | `powershell` | `windows` |
| 6 | `.bash` | `bash` | `unix` |
| 7 | `.sh` | `sh` | `unix` |

These are the extensions of a [`scripts`](commands.md#scripts) path. The order is fixed so that two
consumers with the same interpreters run the same script:

- a script that runs the same on every OS comes before one written for some of them, so an overlay
  that ships `env.py` with shell fallbacks runs its Python wherever Python is found;
- a PowerShell script applies on Windows and a shell script on the other systems, so `env.ps1`
  beside `env.sh` gives each OS its own without a manifest. To run `env.sh` on Windows, or `env.ps1`
  elsewhere, configure it, below;
- `bash` comes before `sh`, the more specific before the more general.

The script runs as a declared one does, with its field's defaults: an env script with no arguments
and a timeout of 60 seconds; setup with the [phase](#setup-phases) as its only argument, a timeout
of 300 seconds, and `network = true`.
A default setup declares nothing, so it is taken to need the network, which is reported as
`setup-network`. The selected interpreter is a requirement like a declared one.

**Configuring a default script.** A declared `env_scripts` or `setup` entry whose `path` is a root
`env.<ext>` or `setup.<ext>` configures that file. The file keeps its place in the order above and
is chosen as before, but with the entry's `interpreter`, `args`, `timeout` and `os` (an absent
`os` is every OS), and for setup its `network`, which defaults to `false` as in any declared
variant: this is how a default setup is denied the network. A configured file runs only if it is
chosen, so it never runs beside the default.

```toml
# setup.sh, run by default, needs no network.
[[setup]]
interpreter = "sh"
path = "setup.sh"
network = false
```

Configuring a file does not move it up the order: with `setup.py` also present and Python found,
`setup.py` is still chosen. Every other declared env script runs after the default one, and every
other declared setup variant is tried before the default setup, which is the last variant.

When a file is present and none of them can run on this OS with the consumer's interpreters, no
script runs, the rest of the overlay still applies, and the consumer reports `script-not-run` for
each file present. A file with another extension (`env.cfg`, `setup.txt`) is never a default script.

## Runtime

`runtime` is a mapping:

| Key | Type | Meaning |
| --- | --- | --- |
| `os` | array of OS names | The OSes the overlay supports. On any other a consumer refuses it, naming the OS. |
| `commands` | array of command names, or `{ name, os }` | Programs that must be found on the base environment's `PATH`. A name has no path separator. |
| `python` | array of variants | A Python the overlay's code runs under, and its dependencies |
| `node` | array of variants | A Node.js the overlay's code runs under |

A `python` variant:

| Key | Type | Meaning |
| --- | --- | --- |
| `version` | string, one to three dotted numbers of at most nine digits (`"3.9"`, `"3.11.4"`) | The minimum version, compared numerically, missing parts as `0` |
| `requirements` | relative path | A requirements file, not locked. A [weakening](security.md#weakenings): `unlocked-dependencies`. |
| `lock` | relative path | A locked requirements file, installed in hash-checking mode |
| `lock_digest` | [digest](integrity.md#digest-form) | The SHA-256 of the lock file's bytes; a mismatch refuses the install |
| `os` | array of OS names | The OSes this variant applies on |

`requirements` and `lock` are exclusive. `lock_digest` needs `lock`. A `node` variant has `version`
and `os`; installing Node.js dependencies is not defined in this edition.

Both files hold only requirement lines and comments, never options: pip would otherwise follow
`-r` and `-c` to other files or URLs, change the index (`--index-url`, `--extra-index-url`,
`--find-links`, `--trusted-host`), or install editable and direct-URL packages. A line is
`name[extras]<specifier>[; marker]`, continued with `\` at the end of a line, and in a lock file
every requirement is pinned with `==` and carries at least one `--hash=sha256:<hex>`. A consumer
refuses a file with any other line, and installs a lock with
`--require-hashes --no-deps --only-binary=:all:` from an index its own configuration names, so no
source distribution is built and no build dependency is fetched unhashed.

```toml
[runtime]
os = ["linux", "macos", "windows"]
commands = ["git", { name = "gh", os = ["linux", "macos"] }]

[[runtime.python]]
os = ["windows"]
version = "3.11"
lock = "locks/windows.txt"
lock_digest = "sha256:…"

[[runtime.python]]
version = "3.9"
lock = "locks/posix.txt"
```

A consumer **probes** a target before it places an overlay there. On that target's OS the overlay
needs:

- an OS in `runtime.os`, when it is given;
- each command in `runtime.commands` that applies to the OS;
- each interpreter named by the selected setup variant, by an env script that will run, and by a
  `scripts` entry that applies to the OS (a string path's interpreter follows from its extension);
  a default script needs only the interpreter of the one selected on that target;
- `python` or `node`, at the selected variant's minimum version, when a variant applies.

A target that lacks one is passed over, with the reason naming what is missing. Dependencies are
installed outside the agent's sandbox, before the agent starts, into an environment that belongs to
the overlay's identity, [tree digest](integrity.md) and OS, so they change only when the digest does.
Inside the sandbox that environment is read-only.

## Setup

`setup` is an array of variants, each one program to run. After the declared variants comes the
`setup` [default](package.md#defaults), one `setup.<ext>` at the root chosen as
[Default scripts](#default-scripts) says, as the last variant; `[defaults] setup = false` turns it
off.

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `interpreter` | [interpreter name](#interpreters) | required | How it runs |
| `path` | relative path | required | The script |
| `args` | array of strings | `[]` | Arguments after the [phase](#setup-phases) |
| `timeout` | integer seconds, `0` for no limit, at most 2147483647 | `300` | Stopped, and failed, after this |
| `network` | boolean | `false` | Whether it needs the network |
| `os` | array of OS names | every OS | The OSes this variant applies on |

```toml
[[setup]]
os = ["windows"]
interpreter = "powershell"
path = "setup/setup.ps1"
timeout = 120

[[setup]]
os = ["unix"]
interpreter = "sh"
path = "setup/setup.sh"
network = true
```

Setup is code, and a [trust decision](security.md#execution-and-dependencies). A consumer that runs
it:

- runs the selected variant in a [phase](#setup-phases): `install` once, before the overlay is
  first activated on an OS, then `sync` once for each new digest, before that digest is activated,
  and `remove` when the overlay is removed; and in no other case, except when its user asks;
- runs it **outside the agent's sandbox**, as part of preparing the overlay, never from the agent's
  session;
- stops it after `timeout` and treats that as a failure; a consumer MAY lower or raise the timeout by
  its own setting, and `0` (no limit) is a [weakening](security.md#weakenings), `no-timeout`;
- runs it in its own process group (a job object on Windows) and, when it ends or is stopped, ends
  every process it started, so nothing it launched outlives it; it bounds the output it keeps;
- denies it the network when `network` is `false`, or reports `network-not-enforced` when it cannot;
  `network = true` is a weakening, `setup-network`;
- does not activate the overlay when `install` or `sync` fails, and reports the failure with the
  exit status.

Setup MUST be idempotent: running it twice leaves what running it once did.

### Setup phases

Setup receives the **phase** as its first argument, before the variant's `args`, and as the
variable `AOS_SETUP_PHASE`: `setup.sh install`, then `setup.sh sync`, then `setup.sh remove`. The
same variant runs in every phase, with the same interpreter, timeout, network rule, process group
and reporting; a phase changes only what the script is told.

The consumer keeps a **record** for each overlay identity and OS: the digest of the last setup that
succeeded there, or none. A phase is chosen from the change and that record:

| Change | Record | Phase |
| --- | --- | --- |
| The overlay is added, or a digest is prepared for activation | none | `install` |
| | another digest | `sync` |
| | this digest | none: setup does not run |
| Its user asks to run setup again | none | `install` |
| | any digest | `sync` |
| The overlay is removed | a digest | `remove` |
| | none | none: setup does not run |

A digest whose selected variant is absent runs nothing and leaves the record as it is. An `install`
or `sync` that succeeds records its digest; the overlay's removal deletes the record, whatever
`remove` did.

| Phase | When | A script may assume | When it fails or times out |
| --- | --- | --- | --- |
| `install` | Before the overlay is first activated on this OS | Its dependencies are installed; the state directory exists, empty; no earlier setup of this overlay succeeded here | The overlay is not activated; the failure is reported; nothing is recorded |
| `sync` | Before a new digest is activated, or on its user's request | Its dependencies are installed; the state directory of this digest exists, empty unless this digest's setup ran before; a setup of an earlier digest succeeded here | The new digest is not activated; the failure is reported. A consumer MAY keep the previous digest active, and says whether it does |
| `remove` | When the overlay is removed, after it stops being activated and before its state directory and dependencies are deleted | They still exist, as setup left them; an `install` or `sync` succeeded here | The overlay is removed anyway: the state directory, dependencies and record are deleted, and the failure is reported |

The timeout and the network rule apply in every phase as they do to setup: `remove` is stopped
after `timeout`, denied the network unless `network = true`, and reported as `setup-network`,
`network-not-enforced` or `no-timeout` like any other run.

**Writing for phases.** A script MUST treat a phase it does not know as success with nothing to
do (exit 0), so a later edition can add one. A script that ignores its arguments runs the same code
in every phase: `install` and `sync` do what setup always did, and `remove`, since setup is
idempotent and the state directory still holds its output, repeats a setup whose result is about to
be deleted. That is harmless; a script whose setup is slow or uses the network returns early on
`remove`:

```sh
#!/bin/sh
set -eu
case "${1:-}" in
  install|sync) mkdir -p "$AOS_OVERLAY_STATE" && date -u > "$AOS_OVERLAY_STATE/prepared-at" ;;
  remove) ;;    # nothing outside the state directory to undo
  *) ;;         # a phase this script does not know: nothing to do
esac
```

## What a step receives

A setup variant and an env script run with:

- the **working directory** set to the overlay root, which MAY be read-only;
- the environment of that overlay's own processes
  ([Environment](environment.md#order-of-application)), plus:
    - `AOS_OVERLAY_ROOT`: the absolute root, as the root variable;
    - `AOS_OVERLAY_NAME`: the normalized identity;
    - `AOS_OVERLAY_STATE`: an absolute, writable directory outside the root that belongs to this
      overlay's identity, digest and OS, and to no other overlay. Setup writes what it produces
      here, never into the root, since a write in the root changes the [tree digest](integrity.md);
    - for setup, `AOS_SETUP_PHASE`: `install`, `sync` or `remove`, as its first argument says.

A consumer sets `<NAME>_OVERLAY_STATE` to the same directory for every process the overlay serves,
so its tools find what setup produced. Inside the agent's sandbox the state directory is read-only:
what setup and env scripts read there, outside the sandbox, an agent must not be able to plant.

> **Status:** dotagents runs setup with the installed directory as working directory and keeps setup
> output in the installed directory, excluded from its copy by the overlay's root `.gitignore`. It
> sets `AGENTS_OVERLAY_DIR`, `AGENTS_HOME`, `AGENTS_SCOPE_ROOT` and `AGENTS_SCOPE`, not the `AOS_`
> variables.
