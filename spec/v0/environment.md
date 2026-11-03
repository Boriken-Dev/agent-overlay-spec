# Environment

**Optional Extension, Proposed.** An overlay declares the environment variables the processes it
serves need: an agent session, a setup step, an MCP server, a command. Every declaration is static
data; a consumer applies it when it builds an environment, never when it reads the manifest.

A consumer that claims this extension applies `env`, `env_files` and `paths`, sets the
[root variable](#the-root-variable), and reports what it refuses. [Env scripts](#env-scripts)
execute, so they are a separate opt-in.

> **Status:** dotagents sets `<NAME>_OVERLAY_ROOT`, puts every overlay's `bin/` on `PATH` and an
> existing `lib/` on `PYTHONPATH`, and runs `pre.env.py`, `pre.env`, `env.py` and `env` at the
> overlay root, by file name. It reads none of the fields below yet.

## The root variable

For every active overlay a consumer sets `<NAME>_OVERLAY_ROOT` to the absolute path of the overlay
root it exposes. `NAME` is the overlay's normalized identity ([Package](package.md#names-and-paths))
in ASCII upper case, with every character other than `A`–`Z` and `0`–`9` replaced by `_`:

| Identity | Variable |
| --- | --- |
| `engineering` | `ENGINEERING_OVERLAY_ROOT` |
| `team-review` | `TEAM_REVIEW_OVERLAY_ROOT` |
| `Team_Review`, `team.review` | `TEAM_REVIEW_OVERLAY_ROOT` (they normalize to `team-review`) |

The identity is the name the consumer installed the overlay under (dotagents: its directory name),
not the manifest `name`. Two active overlays whose variables collide are an error the consumer
reports before applying either.

A consumer sets the variable to the root it exposes even when the base environment holds another
value. Routing lines and documents refer to files as `$<NAME>_OVERLAY_ROOT/<path>`; that text is not
expanded when the manifest is read.

> **Status:** dotagents sets the variable only when it is unset.

## `env`

A mapping from variable name to **env value**. A variable name matches `[A-Za-z_][A-Za-z0-9_]*`.
Two names in one overlay that differ only in ASCII case are an error, since Windows treats them as
one variable.

An env value is a string, or a mapping with exactly one **source key**:

| Form | Meaning |
| --- | --- |
| `"text"` or `{ value = "text" }` | The literal string. Nothing in it is expanded. |
| `{ path = "conf/tool.toml" }` | The absolute path of that [relative path](manifest.md#fields) under the root, with the platform's separator. The file need not exist. |
| `{ provider = "env", key = "HOST_VAR" }` | A [secret reference](#secret-references) |
| `{ secret = "name" }` | A secret the consumer's configuration names |

and these optional keys:

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `if_unset` | boolean | `false` | Set the variable only when it is unset in the environment being built. |
| `optional` | boolean | `false` | When a secret reference cannot be resolved, leave the variable unset instead of refusing. Only with `provider` or `secret`. |

```toml
[env]
TOOL_MODE = "read-only"
TOOL_CONFIG = { path = "conf/tool.toml" }
SYSHTTP_PREFIX = { value = "AGENTS_", if_unset = true }
DOCS_TOKEN = { provider = "env", key = "DOCS_TOKEN" }
SIGNING_KEY = { secret = "release-signing", optional = true }
```

An empty string is a value. An overlay cannot unset a variable.

## Secret references

A secret reference names where a value comes from; the value is never in the overlay. Its shape is
the same wherever AOS takes an env value:

- `{ provider = "<provider>", key = "<key>", ... }`: a provider and that provider's fields. `key` is
  required. A provider's further fields sit beside it, flat, with string, integer or boolean values;
  `value`, `path`, `provider`, `key`, `secret`, `if_unset` and `optional` are reserved and are never
  a provider's field.
- `{ secret = "<name>" }`: a secret defined in the consumer's own configuration under that name,
  with its own provider. The overlay knows only the name.

Two providers are defined:

| Provider | `key` | Value |
| --- | --- | --- |
| `env` | a variable name | That variable from the consumer's own environment (the host's, not the one being built). Reading it is a [weakening](security.md#weakenings), `env-passthrough`. |
| `file` | a relative path | The content of that file under a secrets directory the consumer's configuration names, with one trailing line feed (`LF` or `CRLF`) removed. Never a file in the overlay. A consumer with no secrets directory cannot resolve it. |

A consumer MAY support further providers (a vault, a system keychain, a password manager) under
names of its own. A reference to a provider the consumer does not have, to a secret name it does not
define, or to a value that is absent, **cannot be resolved**. Then the consumer MUST refuse to start
the process that needs it, naming the variable and the reference, unless the entry is `optional`, in
which case the variable stays unset. A consumer MUST NOT log, display or store a resolved value.

## Env files

`env_files` lists files of env values, applied in order before `env`. Each entry is a relative path,
or a mapping:

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `path` | relative path | required | The file |
| `format` | `"aos"` or `"dotenv"` | `"aos"` | How the file is read |
| `os` | array of [OS names](runtime.md#operating-systems) | every OS | Apply only on these |

A listed file that does not exist is an error. An env file cannot list further files.

**`aos`** files are read exactly as [`overlay.cfg`](manifest.md#reading-overlaycfg) is (format line,
TOML default, static), and the document is a mapping with the same rules as `env`: its values may be
secret references.

```toml
#!toml
TOOL_MODE = "read-only"
DOCS_TOKEN = { provider = "env", key = "DOCS_TOKEN", optional = true }
```

**`dotenv`** files are a line format for values that already exist in that form. Every value is a
literal; there are no references, quotes escapes or expansion:

- UTF-8; one leading byte-order mark is dropped; lines end at `LF`, and one `CR` before it is dropped.
- A line that is empty or only spaces and tabs, or whose first character other than a space or a
  tab is `#`, is skipped.
- Every other line is `[export ]NAME=VALUE`: optional leading whitespace, optionally the word
  `export` and whitespace, a variable name, optional whitespace, `=`, then the value.
- The value is the rest of the line with leading and trailing spaces and tabs removed. If it is at
  least two characters long and starts and ends with the same quote, `"` or `'`, those two
  characters are removed. Nothing else changes: `#`, `$` and `\` are literal.
- A line that is none of these, and a name given twice, are errors.

```text
# defaults for the documentation tools
TOOL_MODE=read-only
export TOOL_BANNER="Docs: read only"
```

## Path additions

`paths` adds directories inside the overlay to list variables such as `PATH` and `PYTHONPATH`. Each
entry is a mapping:

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `variable` | variable name | required | The list variable |
| `path` | relative path | required | The directory, under the root; it need not exist |
| `position` | `"prepend"` or `"append"` | `"prepend"` | Where it goes |
| `os` | array of [OS names](runtime.md#operating-systems) | every OS | Apply only on these |

```toml
[[paths]]
variable = "PATH"
path = "bin"

[[paths]]
variable = "PYTHONPATH"
path = "lib"
position = "append"
```

The separator is `;` on Windows and `:` on every other OS. For each variable a consumer:

1. splits the current value on the separator and drops empty components, which would mean the
   working directory;
2. removes every component equal to one of this overlay's entries for that variable (by exact
   string after resolving to an absolute path);
3. builds the result: this overlay's `prepend` entries in declaration order, then the remaining
   components, then its `append` entries in declaration order;
4. joins with the separator. An unset variable starts empty.

An overlay MUST NOT name a variable both in `paths` and in `env` or an `aos` env file; a validator
refuses it.

## Order of application

A consumer builds the environment from a base it chooses (its own, or a cleaned one) as follows, and
MUST give the same result for the same inputs:

1. Set the root variable of every active overlay.
2. For each overlay in [composition order](composition.md#deterministic-ordering):
    1. its `env_files` that apply to this OS, in order;
    2. its `env`;
    3. its `paths`;
    4. its env scripts, when they are enabled.

Within one mapping the entries are independent, since each names a different variable; `if_unset`
looks at the environment as it was before that mapping. A later overlay's value replaces an earlier
one's, and a later overlay's `prepend` entries come before an earlier one's. So the overlay with
the higher `priority` wins a conflict and is found first on a search path.

A consumer MAY refuse to let an overlay set a variable (its own policy), and MUST report each refusal
by variable name. Setting a process-control variable is a [weakening](security.md#weakenings).

## Env scripts

**Optional Extension, Proposed.** `env_scripts` runs programs that compute environment values. They
execute code each time an environment is built, so a consumer runs them only when its user or
administrator has enabled them, and reports `env-script` every time it does.

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `interpreter` | [interpreter name](runtime.md#interpreters) | required | How the script runs |
| `path` | relative path | required | The script |
| `args` | array of strings | `[]` | Arguments after the script |
| `timeout` | integer seconds, `0` for none | `60` | Stopped and failed after this |
| `os` | array of [OS names](runtime.md#operating-systems) | every OS | Run only on these |

```toml
[[env_scripts]]
interpreter = "python"
path = "env/compute.py"
timeout = 10
```

The script runs with the overlay root as its working directory and the environment built so far,
plus `AOS_OVERLAY_ROOT`, `AOS_OVERLAY_NAME` and `AOS_OVERLAY_STATE` ([Runtime](runtime.md#what-a-step-receives)).
Its standard output is JSON objects, one per line; each key is a variable name and each value a
string, to set it, or `null`, to unset it. The objects apply in order. Any other output, a non-zero
exit or a timeout fails the script; the consumer reports the failure and applies nothing from it.

> **Status:** dotagents runs `env.py` and `pre.env.py` with the same JSON protocol, and sources
> plain `env` and `pre.env` files with bash; it has no timeout for either.
