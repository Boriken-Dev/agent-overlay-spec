# Security considerations

An overlay is data, but its instructions steer an agent, and it can carry scripts, dependency lists,
setup steps, environment and server declarations. **Conformance does not establish trust or
safety.** A consumer treats an overlay from elsewhere as untrusted until its user or administrator
decides to trust it, and then pins what was trusted.

## Reading is safe by construction

Reading a manifest executes nothing, reads no other file, and consults no environment
([static reading](manifest.md#static-reading)). A consumer can therefore show a user everything an
overlay would do (its environment, path additions, setup, runtime, servers and weakenings) before
any of it happens. YAML tags, anchors, aliases and merge keys are refused because general YAML
loaders construct objects or expand documents from them; JSON duplicate keys are refused because two
readers would disagree on which value wins.

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
| `setup-network` | The selected [setup](runtime.md#setup) variant declares `network = true`. |
| `network-not-enforced` | The selected setup variant declares no network, and the consumer cannot deny it one. |
| `no-timeout` | The selected setup variant or an [env script](environment.md#env-scripts) that runs has `timeout = 0`. |
| `env-script` | An env script runs. |
| `env-passthrough` | A value is read from the consumer's own environment: an env value with `provider = "env"`, an MCP `env_passthrough` or `headers_env` entry. The subject is the variable read. |
| `env-sensitive` | An overlay's `env` or `env_files` sets a [sensitive variable](#sensitive-variables). The subject is the variable set. |
| `unlocked-dependencies` | The selected Python variant has `requirements` and no `lock`. |

A consumer's own settings can weaken too (a disabled sandbox, a raised limit); a consumer reports
those the same way, under identifiers of its own.

### Sensitive variables

Variables that change how programs find and load code, which shell startup files run, which
certificates are trusted, or where network traffic goes. Setting one through `env` or `env_files`
is the `env-sensitive` weakening; [path additions](environment.md#path-additions) to `PATH` and
`PYTHONPATH` are declared for that purpose and are not. Names compare without regard to ASCII case:

- `PATH`, `PATHEXT`, `HOME`, `USERPROFILE`, `SHELL`, `COMSPEC`, `BASH_ENV`, `ENV`, `ZDOTDIR`,
  `PROMPT_COMMAND`, `IFS`;
- `PYTHONPATH`, `PYTHONHOME`, `PYTHONSTARTUP`, `NODE_OPTIONS`, `NODE_PATH`, `PERL5OPT`, `PERL5LIB`,
  `RUBYOPT`, `RUBYLIB`, `CLASSPATH`, `JAVA_TOOL_OPTIONS`, `_JAVA_OPTIONS`;
- `GIT_SSH_COMMAND`, `GIT_EXEC_PATH`, `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_SYSTEM`;
- `SSL_CERT_FILE`, `SSL_CERT_DIR`, `REQUESTS_CA_BUNDLE`, `CURL_CA_BUNDLE`, `NODE_EXTRA_CA_CERTS`;
- `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`;
- every name starting `LD_` or `DYLD_`.

## Execution and dependencies

Setup, env scripts, commands and dependency installation run only under an explicit policy of the
user or administrator: installing an overlay is a trust decision, fetching one is not. A consumer
runs setup outside the agent's sandbox, once per digest, bounded by a timeout, with the network
denied unless declared, and with the overlay root read-only where it can. Dependencies are installed
from a lock file in hash-checking mode where one is declared.

An overlay's files under an [excluded name](package.md#layout) (`__pycache__`, `node_modules`,
`.venv`, ...) are not part of the overlay and are not covered by its digest, so a consumer never
installs or runs them from an overlay. A consumer that runs Python from an overlay keeps bytecode
out of the root (`PYTHONDONTWRITEBYTECODE`, or `PYTHONPYCACHEPREFIX` pointing elsewhere), since a
planted `.pyc` there would run without changing the digest.

## Paths and filenames

A consumer refuses archive entries and declared paths that leave the root after normalization and
symbolic links, absolute paths, drive and device paths, and links inside the tree. It SHOULD refuse
an overlay holding two paths that differ only by case or Unicode normalization, or a name a platform
alters (a trailing dot or space on Windows, a reserved device name), since a checkout on another
platform would hold other files than the digest describes.

## Credentials and network

An overlay never holds a secret value: it holds [secret references](environment.md#secret-references).
A consumer never logs, displays or stores a resolved value, and SHOULD start an overlay's processes
from an environment it chose rather than everything it inherited.
MCP servers can reach data and networks; a consumer shows each server, its transport and the
variables it reads before starting it.

## Collisions and updates

Overlay names, root variables, commands, skills, servers and tools can collide. A consumer detects
collisions before activation and reports which identity wins, or refuses. An update can change
instructions or code; a pin and a reviewable difference make it a decision rather than an accident.
