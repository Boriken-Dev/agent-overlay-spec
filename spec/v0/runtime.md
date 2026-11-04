# Runtime and setup

**Optional Extension, Proposed.** An overlay declares what must exist where it runs (`runtime`),
the packages it needs ([dependencies](#dependencies)) and what to run to prepare it (`setup`). A
consumer reads them without running anything, so it can decide where an overlay can go, and refuse
with a reason, before it fetches or starts anything.

> **Status:** dotagents runs `setup.py` at the overlay root under its own Python, on every add and
> sync unless `--no-setup` is given, stopped after `setup_timeout` seconds (default 300, `0` for no
> limit): the `.py` case of the [default setup](#default-scripts), run when AOS runs `install` and
> `sync`, but with no [phase](#setup-phases) argument and never on remove. It installs a root
> `requirements.txt` into its one Python environment per store, where AOS reads
> `lib/python/requirements.txt` into the scope's shared environment. It reads none of the fields
> below yet.

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
| `environment` | `"shared"`, `"isolated"` or a name | The [environment](#environments) its packages go into; default `"shared"` |
| `os` | array of OS names | The OSes this variant applies on |

`requirements` and `lock` are exclusive. `lock_digest` needs `lock`. Either one replaces the
default `lib/python/requirements.txt` on the OSes the variant applies to.

A `node` variant:

| Key | Type | Meaning |
| --- | --- | --- |
| `version` | string, as for Python | The minimum version |
| `package` | relative path ending in `package.json` | A `package.json` that replaces the default `lib/node/package.json`; the `package-lock.json` beside it, when present, is its lock |
| `environment` | `"shared"`, `"isolated"` or a name | The [environment](#environments) its packages go into; default `"shared"` |
| `os` | array of OS names | The OSes this variant applies on |

Both files hold only requirement lines and comments, never options: pip would otherwise follow
`-r` and `-c` to other files or URLs, change the index (`--index-url`, `--extra-index-url`,
`--find-links`, `--trusted-host`), or install editable and direct-URL packages. A line is
`name[extras]<specifier>[; marker]`, continued with `\` at the end of a line, and in a lock file
every requirement is pinned with `==` and carries at least one `--hash=sha256:<hex>`. A consumer
refuses a file with any other line, and installs a lock with
`--require-hashes --no-deps --only-binary=:all:` from an index its own configuration names, so no
source distribution is built and no build dependency is fetched unhashed.

The default `lib/python/requirements.txt` is the same kind of file. It is a lock when every
requirement in it carries a `--hash`, and then meets the rules of a lock; one where only some do is
refused (`partial-lock`), since pip checks hashes for all or none. PEP 751's `pylock.toml` is the
standard Python lock format, but pip installs it only as an experiment, so this edition pins with
hashes in the requirements file, and `lib/python/pylock.toml` means nothing yet.

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
- `python` or `node`, at the selected variant's minimum version, when a variant applies;
- for each [dependency file](#dependencies) that applies, its interpreter and package manager:
  `python` for a requirements file (pip and `venv` run from it), `node` and the command `npm` for a
  `package.json`.

A target that lacks one is passed over, with the reason naming what is missing; where there is no
other target, the overlay is not activated, and the same reason is reported.

## Dependencies

**Optional Extension, Proposed.** An overlay's packages are installed from one file per runtime.
By [default](package.md#defaults) the file is in the runtime's library directory:

| Runtime | Default file | Pinned by | Installed with | Added to |
| --- | --- | --- | --- | --- |
| Python | `lib/python/requirements.txt` | a `--hash` on every requirement | pip, in hash-checking mode when pinned | `PYTHONPATH`, after `lib/python/` |
| Node.js | `lib/node/package.json` | `package-lock.json` beside it | `npm ci` when pinned, `npm install` otherwise | `NODE_PATH`, after `lib/node/` |

`[defaults] deps = false` turns both off. A selected `runtime.python` variant that names
`requirements` or `lock`, or a `runtime.node` variant that names `package`, replaces that runtime's
default file. `lib/<runtime>/` holding that ecosystem's standard manifest is kept for other
runtimes, which a later edition may define.

A file that is not pinned still installs, and is reported as the weakening `unlocked-dependencies`,
since what it installs depends on what the index serves that day. Installing needs the network,
pinned or not, and every installed file is reported as `deps-network`. Installing runs code: pip
builds a source distribution it is given (a lock refuses them), and npm runs packages' install
scripts, which a consumer MAY turn off by its own policy (`--ignore-scripts`).

### Environments

Packages are installed into an **environment**: a directory outside every overlay root, per OS,
that the consumer chooses. The selected variant's `environment` key says which one; a variant that
names no file still chooses the environment of the default file.

| `environment` | The environment | Used by |
| --- | --- | --- |
| `"shared"` (default) | The consumer's one environment for that runtime in the [scope](terminology.md) | Every overlay of the scope that does not choose another |
| a name | The environment of that name and runtime in the scope | Every overlay of the scope that chooses the name, compared normalized as an [identity](package.md#names-and-paths) is |
| `"isolated"` | The overlay's own, per identity | That overlay alone |

```toml
# This overlay's packages never meet another overlay's.
[[runtime.python]]
environment = "isolated"
```

The key is `environment`, not `env`, since `env` is the field of environment variables.

- **Python.** The environment is a virtual environment the consumer makes with the selected
  interpreter (`python -m venv`) and installs into with its own pip. Its packages directory is
  added to `PYTHONPATH`, after `lib/python/`, for every process an overlay in it serves, which
  runs under that interpreter.
- **Node.js.** The environment is a directory whose `node_modules` npm fills, run with that
  directory as its prefix, from copies of the `package.json` and `package-lock.json` alone, so no
  `.npmrc` or other file of an overlay configures npm. Its `node_modules` is added to `NODE_PATH`,
  after `lib/node/`. `require()` reads `NODE_PATH`; an ES module's `import` of a bare name does not,
  so an ES module loads a package with `createRequire(import.meta.url)`.

**Installing together.** The overlays of one shared or named environment are installed into it as
one: from every member's file, in [composition order](composition.md#deterministic-ordering), in
one run of the package manager, so a package two overlays need is fetched once.

- Python: pip is given every file, in hash-checking mode only when every member's file is pinned.
- Node.js: npm is given one `package.json` whose dependencies are every member's. With one member
  that has a lock, it runs `npm ci` with that lock; otherwise `npm install`, since npm reads one
  lock and several cannot be combined. A Node.js overlay that must stay pinned chooses `isolated`
  or a name of its own.

An environment is pinned only when it is installed in hash-checking mode or with `npm ci`. One that
is not is reported to each of its members as `unlocked-dependencies`, with the environment
(`python:shared`, `node:<name>`) as the subject, even to a member whose own file is pinned.

**Conflicts.** Members of one environment conflict when two of them ask for one package at different
versions: two Python files pin it with `==` to different versions (package names compared
normalized, as PEP 503 does), two `package.json` files give it different version ranges (one
`node_modules` holds one version of each package at its top level), or the package manager cannot
satisfy them together. The consumer reports the package and the overlays, as the package manager
names them, or every member when it does not; it activates none of those overlays, and installs the
environment from the others. It never picks a version for them. The fix is to give one of them a
name of its own, or `isolated`.

**Updating.** Each `install`, `sync` and removal that touches an environment **rebuilds** it from the
files of the overlays that remain in it: the consumer installs into a new directory and replaces the
old one only when that succeeds, so a failed install leaves the environment as it was. A rebuild
takes out what no remaining file asks for, where removing packages one by one would not (pip and npm
remove a package, not the packages only it needed), and needs no record of which overlay installed
what; the package managers' caches keep it from fetching again. A sync of one member rebuilds the
whole environment, so an unpinned member's packages may change then; pinned ones do not.

**Lifetime.** A shared or named environment is kept while any overlay of the scope uses it, and
deleted when the last one is removed. Removing an overlay rebuilds every shared or named environment
it was in without it; when that rebuild fails, the removal still completes, the environment is kept
as it was, the failure is reported, and the next install or sync rebuilds it. An isolated
environment is deleted with its overlay, after `remove`.

**Pins.** A [pin](integrity.md#pins) covers one overlay's files: its dependency file, its lock and
the hashes in them. A pinned overlay with a pinned file installs exactly what its hashes name. A pin
does not cover what other overlays put in a shared environment, and no environment is part of any
tree digest, since none is under an overlay root.

Dependencies are installed outside the agent's sandbox, before the agent starts. Inside the sandbox
every environment is read-only.

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

- runs the selected variant in a [phase](#setup-phases), after the overlay's
  [dependencies](#dependencies) are installed: `install` on the first add, `sync` on every
  [sync](#setup-phases) and before a digest other than the recorded one is activated, and `remove`
  when the overlay is removed; and in no other case;
- runs it **outside the agent's sandbox**, as part of preparing the overlay, never from the agent's
  session;
- stops it after `timeout` and treats that as a failure; a consumer MAY lower or raise the timeout by
  its own setting, and `0` (no limit) is a [weakening](security.md#weakenings), `no-timeout`;
- runs it in its own process group (a job object on Windows) and, when it ends or is stopped, ends
  every process it started, so nothing it launched outlives it; it bounds the output it keeps;
- denies it the network when `network` is `false`, or reports `network-not-enforced` when it cannot;
  `network = true` is a weakening, `setup-network`;
- does not activate the digest an `install` or `sync` failed for, as [Setup phases](#setup-phases)
  says, and reports the failure with the exit status.

Setup MUST be idempotent: running it twice leaves what running it once did. It runs on every sync,
mostly with nothing to do.

### Setup phases

Setup receives the **phase** as its first argument, before the variant's `args`, and as the
variable `AOS_SETUP_PHASE`: `setup.sh install`, then `setup.sh sync`, then `setup.sh remove`. The
same variant runs in every phase, with the same interpreter, timeout, network rule, process group
and reporting; a phase changes only what the script is told.

Phases follow what the consumer does to the overlay, not only changes of its digest:

- **Add.** Adding an overlay runs `install`; adding one already prepared under that identity is a
  sync.
- **Sync.** A sync is any operation of the consumer that brings an installed overlay up to date,
  asked by its user or run on the consumer's own schedule: fetching its source again, whatever the
  fetch finds; changing its source, ref or pin; or running its setup again on request. Each overlay
  one such operation covers is synced once. Every sync runs `sync`, whether the digest changed or
  not. Starting a session, reading, listing, probing and activating an overlay are not syncs.
- **Activate.** A consumer with no sync operation of its own (one that reads overlays something else
  installed, or re-reads pinned overlays) runs `sync` before it activates a digest other than the
  recorded one. Any consumer does the same when it finds such a digest outside a sync.
- **Remove.** Removing an overlay runs `remove`.

The consumer keeps a **record** for each overlay identity and OS: the digest and the phase of the
last preparation that succeeded there, or none. The phase is chosen from what the consumer does and
that record:

| The consumer | Record | Phase |
| --- | --- | --- |
| adds or syncs the overlay | none | `install` |
| | any digest, this one or another | `sync` |
| activates a digest outside a sync | none | `install` |
| | another digest | `sync` |
| | this digest | none: nothing runs |
| removes the overlay | a digest | `remove` |
| | none | none: setup does not run; the overlay is still deleted |

**Preparing.** At `install` and `sync` the consumer installs the overlay's
[dependencies](#dependencies), then runs the selected setup variant, then records the digest and
phase. An overlay with no dependency file and no setup variant on this OS has nothing to prepare:
no phase applies and the record stays as it is. A preparation stops at the first step that fails.

| Phase | Steps, in order | A script may assume | When a step fails or times out |
| --- | --- | --- | --- |
| `install` | The state directory is made empty; the dependencies are installed; setup runs; the record is written | Its dependencies are installed; the state directory exists, empty; nothing of this identity was prepared here | Nothing is recorded; the overlay is not activated; the failure is reported, and the next add, sync or activation runs `install` again |
| `sync` | The dependencies are installed; setup runs; the record is written | Its dependencies are installed; the state directory holds what earlier phases left there, for this digest or an earlier one; an `install` or `sync` succeeded here | The record still names the previous digest, and the state directory is as the script left it; the failure is reported. A new digest is not activated, and a consumer MAY keep the previous one active, and says whether it does. A sync of the recorded digest itself leaves that digest active |
| `remove` | Setup runs; the state directory, the record and an isolated environment are deleted, and every shared or named environment is rebuilt without the overlay | The state directory and the dependencies still exist, as earlier phases left them; an `install` or `sync` succeeded here | The overlay is removed anyway, and the failure is reported |

A failed `install` or `sync` still blocks the digest it ran for: only the record says that a digest
is prepared, and until a preparation of that digest succeeds, nothing says its dependencies and
state are what it expects. The recorded digest is the one exception, since the record already says
so, and the failure of a sync run again on it is reported without deactivating it.

The timeout and the network rule apply in every phase as they do to setup: `remove` is stopped
after `timeout`, denied the network unless `network = true`, and reported as `setup-network`,
`network-not-enforced` or `no-timeout` like any other run.

**The state directory** belongs to the overlay's identity and OS, and is kept across syncs and
digests, so `sync` updates in place what earlier phases left. It is made empty before `install`,
which removes what a failed earlier `install` left, and deleted after `remove`, whether `remove`
succeeded or not. It is outside the overlay root, so never part of the
[tree digest](integrity.md#tree-digest).

**A new identity.** The state directory, the record and an isolated environment belong to one
identity. An overlay installed under another identity (renamed, or added again under a new name) is
a new overlay: the consumer removes the old identity as any removal does, its `remove` included,
then adds the new one, which runs `install` into an empty state directory. Nothing is carried from
one identity to the other.

**Writing for phases.** A script MUST treat a phase it does not know as success with nothing to
do (exit 0), so a later edition can add one. `sync` runs on every sync, mostly with nothing to do,
on a state directory earlier phases filled: it updates in place, skips what is done, and when it
fails partway leaves the state usable by the recorded digest (it writes a new file beside the old
one and renames it), since that digest may stay active. Running sessions of the overlay see the
state directory change. A script that ignores its arguments runs the same code in every phase:
`install` and `sync` do what setup always did, and `remove`, since setup is idempotent and the
state directory still holds its output, repeats a setup whose result is about to be deleted. That
is harmless; a script whose setup is slow or uses the network returns early on `remove`:

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
      overlay's identity and OS, and to no other overlay, kept across syncs and digests as
      [Setup phases](#setup-phases) says. Setup writes what it produces here, never into the root,
      since a write in the root changes the [tree digest](integrity.md);
    - for setup, `AOS_SETUP_PHASE`: `install`, `sync` or `remove`, as its first argument says.

A consumer sets `<NAME>_OVERLAY_STATE` to the same directory for every process the overlay serves,
so its tools find what setup produced. Inside the agent's sandbox the state directory is read-only:
what setup and env scripts read there, outside the sandbox, an agent must not be able to plant, and
since the directory outlives a digest, what it planted would reach every later sync.

> **Status:** dotagents runs setup with the installed directory as working directory and keeps setup
> output in the installed directory, excluded from its copy by the overlay's root `.gitignore`. It
> sets `AGENTS_OVERLAY_DIR`, `AGENTS_HOME`, `AGENTS_SCOPE_ROOT` and `AGENTS_SCOPE`, not the `AOS_`
> variables.
