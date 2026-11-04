# Security considerations

An overlay is data, but its instructions steer an agent, and it can carry scripts, dependency lists,
setup steps, environment and server declarations. **Conformance does not establish trust or
safety.** A consumer treats an overlay from elsewhere as untrusted until its user or administrator
decides to trust it, and then pins what was trusted.

## Reading is safe by construction

Reading a manifest executes nothing, reads no other file, and consults no environment
([static reading](manifest.md#static-reading)). A consumer can therefore show a user everything an
overlay would do (its environment, path additions, setup, runtime, servers and weakenings) before
any of it happens, from the manifest and the overlay's list of files, which decides the
[defaults](package.md#defaults). YAML tags, anchors, aliases and merge keys are refused because
general YAML loaders construct objects or expand documents from them; JSON duplicate keys are
refused because two readers would disagree on which value wins.

A reader bounds the size and nesting of what it reads, by settings with defaults.

## Trust and sources

A consumer shows source and revision before it first activates an overlay, and the difference before
it updates one. A branch or a registry entry can change after review; a [pin](integrity.md#pins)
cannot. A mismatched pin is a refusal, never a warning.

## Weakenings

A **weakening** is a choice looser than the default, declared by an overlay or made by a consumer.
AOS does not forbid them: a user may need an overlay whose setup downloads a toolchain. It requires
that each is **reported, never applied silently**: in a log line, a status view or the user
interface, each time the overlay is activated, with an identifier, the overlay, and a subject (a
variable name or a path), never a value. A consumer MAY refuse any weakening by its own policy, and
then reports the refusal the same way.

| Id | When |
| --- | --- |
| `unpinned` | An overlay is activated without a [pin](integrity.md#pins). |
| `setup-network` | The selected [setup](runtime.md#setup) variant declares `network = true`, or a [default setup](runtime.md#default-scripts) is selected. |
| `network-not-enforced` | The selected setup variant declares no network, and the consumer cannot deny it one. |
| `no-timeout` | The selected setup variant or an [env script](environment.md#env-scripts) that runs has `timeout = 0`. |
| `env-script` | An env script runs, declared or by default. |
| `script-not-run` | A [default script](runtime.md#default-scripts) is present and none can run on this OS with the consumer's interpreters. The subject is each file. |
| `env-passthrough` | A granted value is read from the consumer's own environment: an env value with `provider = "env"`, an MCP `env_passthrough` or `headers_env` entry. The subject is the variable read. |
| `secret-read` | A granted [secret reference](environment.md#secret-references) is resolved for the overlay. The subject is the reference (`secret:<name>`, `file:<key>`, `<provider>:<key>`). |
| `env-sensitive` | An overlay sets a [sensitive variable](#sensitive-variables) through `env`, an env file or an env script, or adds to one other than `PATH` and `PYTHONPATH` through `paths`. The subject is the variable. |
| `unlocked-dependencies` | The selected Python variant has `requirements` and no `lock`. |
| `insecure-transport` | An MCP server is reached over plain `http` on a host other than loopback. The subject is the server. |

A consumer's own settings can weaken too (a disabled sandbox, a raised limit); a consumer reports
those the same way, under identifiers of its own.

### Sensitive variables

Variables that change how programs find and load code, which startup or configuration files run,
which certificates are trusted, where packages come from, or where network traffic and an agent's
own API calls go. Names compare without regard to ASCII case. A name is sensitive when it:

- is one of `PATH`, `PATHEXT`, `HOME`, `USERPROFILE`, `SHELL`, `COMSPEC`, `SYSTEMROOT`, `BASH_ENV`,
  `ENV`, `ZDOTDIR`, `PROMPT_COMMAND`, `IFS`, `EDITOR`, `VISUAL`, `PAGER`, `LESSOPEN`, `LESSCLOSE`,
  `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `APPDATA`, `LOCALAPPDATA`, `TMPDIR`, `TEMP`, `TMP`,
  `PSMODULEPATH`, `CLASSPATH`, `JAVA_TOOL_OPTIONS`, `_JAVA_OPTIONS`, `JDK_JAVA_OPTIONS`,
  `PERL5OPT`, `PERL5LIB`, `RUBYOPT`, `RUBYLIB`, `RUSTFLAGS`, `GOPROXY`, `GONOSUMDB`, `GONOSUMCHECK`,
  `GOPRIVATE`, `GOFLAGS`, `SSH_ASKPASS`, `SSLKEYLOGFILE`, `REQUESTS_CA_BUNDLE`, `CURL_CA_BUNDLE`;
- starts with `LD_`, `DYLD_`, `GIT_`, `PYTHON`, `NODE_`, `NPM_CONFIG_`, `PIP_`, `UV_`, `CARGO_`,
  `RUSTC_`, `DOTNET_`, `COR_`, `CORECLR_` or `SSL_`;
- ends with `_PROXY` or `_BASE_URL`.

A consumer MAY treat more names as sensitive; it MUST treat at least these.

## Execution and dependencies

Setup, env scripts, commands and dependency installation run only under an explicit policy of the
user or administrator: installing an overlay is a trust decision, fetching one is not. A consumer
runs setup outside the agent's sandbox, in its [phases](runtime.md#setup-phases) (`install` once,
`sync` once per new digest, `remove` on removal), bounded by a timeout, with the network denied
unless declared, and with the overlay root read-only where it can. Dependencies are installed
from a lock file in hash-checking mode where one is declared.

Starting an MCP server, running a command and running an env script are the same decision as
setup: code from the overlay runs. Overlays an overlay `requires` are shown and accepted like the
ones asked for, never installed silently.

`env.<ext>` and `setup.<ext>` [run by default](runtime.md#default-scripts), without a manifest.
That moves no decision: a default script runs only in an overlay the consumer has activated, never
in one it fetched or only read, with the same timeout, process group and state directory as a
declared one, and every run is reported. A default setup is taken to need the network and reported
as such, since nothing in it says otherwise. Nothing else runs by default: dependencies install only
from a declared [`runtime`](runtime.md#runtime), and a command is exposed only by a `scripts` entry.

An overlay's files under an [excluded name](package.md#layout) (`__pycache__`, `node_modules`,
`.venv`, `.git`, ...) are not part of the overlay and are not covered by its digest, yet Python,
Node.js and Git load code from them implicitly. So a consumer never installs them, counts any such
entry in an installed copy as a [mismatch](integrity.md#pins), and runs Python from an overlay with
`PYTHONPYCACHEPREFIX` pointing outside the root, so no bytecode is ever written or read there.

## Paths and filenames

A consumer refuses archive entries and declared paths that leave the root after normalization and
symbolic links, absolute paths, drive and device paths, and links inside the tree. Every member path
of a digest and every declared path is a [relative path](manifest.md#fields), which refuses the
names a platform would alias or alter (another case of an excluded name, a trailing dot or space, a
device name, a short name, `:`), and the [tree digest](integrity.md#tree-digest) refuses two paths
equal under ASCII case. A consumer SHOULD also refuse two paths equal after Unicode case folding and
normalization (NFC), which some filesystems hold as one file.

## Credentials and network

An overlay never holds a secret value: it holds [secret references](environment.md#secret-references),
and reads only what the consumer's configuration grants it. A consumer never logs, displays or
stores a resolved value, gives each overlay's processes only that overlay's environment, and SHOULD
start them from an environment it chose rather than everything it inherited.
[Substitution](environment.md#secrets-and-substitution) never reads a variable that holds a
resolved secret, so no part of one is copied into another variable, and a consumer shows a
substituted value as written, never its result. Substitution runs nothing and reads no file.
MCP servers can reach data and networks; a consumer shows each server, its transport and the
variables it reads before starting it.

## Collisions and updates

Overlay names, root variables, commands, skills, servers and tools can collide. A consumer detects
collisions before activation and reports which identity wins, or refuses. An update can change
instructions or code; a pin and a reviewable difference make it a decision rather than an accident.
