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

**Status:** adopted; Proposed until an implementation reads it.

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
