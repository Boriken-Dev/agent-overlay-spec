# Design decisions

## 1 — No required manifest version

**Decision:** the manifest stays optional, with no required `version` or `schema_version` key.

**Reason:** manifest-free overlays are valid, and a required field would refuse them. The edition is
versioned in the specification.

**Status:** adopted for `0.1.0-draft`; revisit before 1.0.

## 2 — Separate declarations from manager policy

**Decision:** source precedence, scopes, installation, execution and target rendering are manager
behaviour unless reading a declaration needs them.

**Reason:** runtimes expose instructions and tools through different targets and execution models.

**Status:** adopted.

## 3 — Unknown top-level keys are allowed

**Decision:** unknown top-level keys are allowed and preserved; tables this specification defines
refuse unknown keys.

**Reason:** a strict top level would refuse overlays that carry a manager's own metadata. Extension
namespaces remain a proposal.

**Status:** adopted.

## 4 — One manifest name, several syntaxes, TOML required

**Decision:** the manifest is `overlay.cfg`. A first line `#!<format>` names its format; anything
else means TOML; nothing is guessed from content; one leading byte-order mark is ignored. TOML is
required of every reader; JSON and YAML are optional; an unsupported format is refused by name.

**Reason:** teams generate manifests from tools that write JSON or YAML, and a single file name keeps
discovery trivial. Naming the format on the first line, instead of detecting it, means two readers
never disagree about what a file is. The rule is the `.cfg` rule of the anycfg libraries, stated
here so a reader without them can implement it. The draft is unreleased, so `overlay.toml` is not
kept as a second name.

**Status:** adopted.

## 5 — A data model independent of syntax, and static reading

**Decision:** a manifest reads as a mapping of strings, integers, finite floats, booleans, arrays
and mappings; no null, no dates. No include, import, interpolation, templating or YAML tag is
applied when it is read.

**Reason:** the same manifest must mean the same thing in every syntax and every language, and a
consumer with no interpreter (a Rust or Dart program) must be able to read every declaration.

**Status:** adopted.

## 6 — Environment and secrets as references

**Decision:** an env value is a literal, a path under the root, or a secret reference (a provider
and its key, or a secret's name). Env files hold the same values; `dotenv` files hold literals only.
Env scripts are an opt-in, run with a named interpreter, and are reported.

**Reason:** an overlay is shared and often public, so a secret value never belongs in it; a reference
lets each consumer resolve it from where its user keeps secrets.

**Status:** adopted; Proposed until an implementation reads it. "`dotenv` files hold literals only" is
superseded by [decision 13](#13-env-values-are-substituted-in-the-order-of-application): text values
are substituted, in every format.

## 7 — Per-OS variants as ordered arrays

**Decision:** `setup` and `runtime.python` are arrays; the first entry whose `os` matches applies.

**Reason:** one rule for every per-OS field, with no table-or-array ambiguity for parsers in
statically typed languages.

**Status:** adopted.

## 8 — A tree digest over bytes as published

**Decision:** the tree digest hashes one line per regular file, `path NUL sha256:<hex> LF`, sorted by
path bytes, with SHA-256. Nothing is normalized: not line endings, encodings or names. Version-control
and cache directories and `.pyc` files are excluded by a fixed list; links, special files,
non-UTF-8 names and names with `\` are refused. Git sources are hashed from blob bytes.

**Reason:** two implementations must agree byte for byte, in any language. Deciding which files are
text, to normalize their line endings, has no portable answer, so the digest covers the bytes and the
author keeps them LF. The line format is the per-file manifest some consumers already pin skills
with, so one digest serves both. The exclusions are what managers already refuse to copy, so a
digest of the source and of an installed copy agree.

**Status:** adopted; Proposed until an implementation computes it.

## 9 — Weakenings are reported, not forbidden

**Decision:** AOS names a fixed set of weakenings (`unpinned`, `setup-network`,
`network-not-enforced`, `no-timeout`, `env-script`, `env-passthrough`, `secret-read`,
`env-sensitive`, `unlocked-dependencies`, `insecure-transport`). A consumer reports each one it applies, every time, by identifier,
overlay and subject, never a value; it may refuse any by its own policy.

**Reason:** a user sometimes needs a setup that downloads, or an overlay that reads a token from the
environment. Taking the choice away pushes people to work around the consumer; reporting keeps the
default strict and every loosening visible.

**Status:** adopted.

## 10 — An overlay asks for secrets; the consumer grants them

**Decision:** a secret reference, an `env` provider read, and an MCP `env_passthrough` or
`headers_env` name resolve only when the consumer's configuration grants that overlay that reference.
Nothing is granted by default. Each overlay's own processes get only that overlay's environment.

**Reason:** an overlay from elsewhere chooses its own references, so without grants it could name
any secret the consumer can reach and send it out through a server or a setup step. A grant keeps the
choice with the user, and per-overlay environments keep one overlay's secret from another's code.

**Status:** adopted; Proposed until an implementation reads it.

## 11 — One rule for paths, shared by declarations and the digest

**Decision:** a relative path refuses names a platform aliases or alters (an excluded name in any
case, a trailing dot or space, a device name, a short name, `:`, control and invisible characters),
and every member of a tree digest must be one; two members equal under ASCII case are refused.

**Reason:** a digest is only worth what it covers. A name that Windows or macOS opens as `.git`,
`node_modules` or a bytecode file would let a pinned overlay change behaviour without changing its
digest, and two names one filesystem holds as one file would make the installed bytes differ from
the reviewed ones.

**Status:** adopted.

## 12 — Conventional files take effect by default, until `[defaults]` turns one off

**Decision:** files in conventional places take effect without a manifest: `bin/` prepended to
`PATH`, `lib/python/` prepended to `PYTHONPATH`, the root `env` read as a `dotenv` file, one
`env.<ext>` and one `setup.<ext>` chosen by a fixed extension order, the OS and the interpreters at
hand, `CONTEXT.md`, `skills/*/SKILL.md` and `rules/*.md`. Each stays on unless the manifest's
`[defaults]` table sets its key to `false`: `bin`, `lib`, `env`, `env_scripts`, `setup`, `context`,
`skills`, `rules`. Declared entries add to the defaults, after them; a declared entry naming the same
file or directory as a default entry replaces it, and one naming a root `env.<ext>` or `setup.<ext>`
configures that file in the default choice. A default script that runs is reported, a default setup
is taken to need the network, one that cannot run is reported as `script-not-run`, and `local.env` is
not an overlay file.

**Reason:** the owner ruled that the basics need no manifest, that `bin/` is on `PATH` unless
disabled, and that `env.*` and `setup.*` run by default, picked by runtime. One boolean per default is
the single way to turn it off, and the keys read as a list of what an overlay opts out of. Declaring
adds, so an author who adds a directory does not lose `bin/`; replacing a same-named entry lets an
author change a default's settings without turning it off and without applying it twice. Unknown
keys are errors, so a misspelt key fails rather than leaving a default on. Python modules go in
`lib/python/`, the owner's choice, which leaves `lib/<runtime>/` for other runtimes; the `lib` key
covers every one of them, so an overlay that turned libraries off stays that way when an edition adds
one. `lib/python/` is prepended, as dotagents prepends its `lib/` and as `bin/` is: on every search
path the overlay with the higher `priority` is then found first, where appending would invert that
for libraries alone. Running by default moves no trust decision: it happens only in an activated
overlay, and every run is reported.

**Status:** adopted. The `rules` and `env` defaults and the `[defaults]` table are Proposed; dotagents
applies the others, with the differences [Compatibility](../compatibility.md) lists.

## 13 — Env values are substituted in the order of application

**Decision:** an env value written as text, in `env`, in an `aos` or `dotenv` env file, or in an MCP
server's `env`, is substituted when its variable is set. The syntax is braced placeholders only,
`${NAME}`, with `$$` for a `$`, the defaults `-` and `:-` (and `=`, `:=`, which assign nothing), the
alternates `+` and `:+`, nested words, `${#NAME}`, slices, glob replacements and trims, and case
changes: the `drone` envsubst dialect plus alternates, as tplx implements it. Nothing runs and no file
is read; `$NAME`, `$(...)` and backticks are characters; an unknown expression is text. Values are
substituted one at a time in the order of application, each seeing the environment after every
earlier entry (earlier overlays, path additions and env-script output, earlier files and lines), and
an overlay's own `AOS_OVERLAY_ROOT`, `AOS_OVERLAY_NAME` and `AOS_OVERLAY_STATE`. The entries of one
mapping see the environment before it. An undefined name is an error; a placeholder never reads a
variable whose value came from a secret reference; a single-quoted `dotenv` value is not
substituted; a consumer shows a value as written, never its result.

**Reason:** the owner asked for the `.env` file to work as tplx's shell templates do, with the result
of one entry usable by the next. Braced-only, with a fixed set of string operations, keeps it static
and implementable in Rust or Dart with no shell, while existing envsubst text keeps its meaning; the
`drone` set was closest to what was asked, `alternate` was added, and `unquote` left out, since a
`dotenv` value has already lost its quotes. One rule for every text value means a line moved
between `env`, an `aos` file and a `dotenv` file keeps its meaning; only `${` and `$$` are special, so
plain text is unaffected, and reading a manifest stays static. Chaining in one fixed order makes
self-reference (`PATH=${MYTOOL_HOME}/bin:${PATH}`) work and cycles impossible, since nothing is
substituted twice. Mapping entries cannot chain, because mapping order carries no meaning in the data
model (decision 5). An undefined name is an error, not a consumer setting: a setting would let one
overlay build two environments under two consumers, and the author already chooses per placeholder
with `${NAME-}` or a default (no hidden choice). Refusing to read a secret keeps every secret value
whole in exactly the variable its reference names, so redaction stays complete and no slice, length
or copy of a secret can be reported. Single quotes stay literal because dotenv tools treat them so.

**Status:** adopted; Proposed until an implementation reads it.

## 14 — Setup is told its phase: install, sync, remove

**Decision:** setup receives its phase as its first argument, before `args`, and as
`AOS_SETUP_PHASE`. The consumer records, per identity and OS, the digest of the last setup that
succeeded: with no record, setup runs `install`; with another digest, `sync`; with this digest,
nothing, unless the user asks (`sync`); on removal, `remove` when a record exists, after the overlay
stops being activated and before its state directory and dependencies are deleted. A failed
`install` or `sync` blocks that digest's activation; a failed `remove` is reported and the overlay is
removed anyway. The timeout and network rules apply in every phase. A script treats a phase it does
not know as success with nothing to do; one that ignores its arguments keeps working.

**Reason:** the owner asked for setup to take an argument for install, sync and remove. One script
and one variant for every phase is the least an author writes, and needs no new manifest key: a
`case` on the first argument, or nothing at all. Choosing the phase from a recorded digest makes the
choice the same in every consumer and testable as data. "Once per digest" becomes `install` once,
then `sync` per new digest, the same number of runs as before. The state directory stays per digest,
so `sync` starts empty, as `install` does, and a running session keeps the previous digest's
directory; removal must not depend on cleanup succeeding, or one failing script would make an overlay
impossible to remove.

**Status:** adopted; Proposed until an implementation reads it.
