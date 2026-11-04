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
applies the others, with the differences [Compatibility](../compatibility.md) lists. The `deps`
default and `lib/node/` were added by
[decision 16](#16-dependencies-by-default-in-shared-named-or-isolated-environments).

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

**Status:** adopted; Proposed until an implementation reads it. The phase chosen by digest alone, and
the state directory per digest, are superseded by
[decision 15](#15-phases-follow-the-consumers-operations-state-belongs-to-the-identity): `sync` runs
on every sync, and the state directory belongs to the identity.

## 15 — Phases follow the consumer's operations; state belongs to the identity

**Decision:** setup runs `install` on the first add, `sync` on every sync the consumer performs, and
`remove` on removal. A sync is any operation that brings an installed overlay up to date (fetching
its source again whatever it finds, changing its source, ref or pin, running setup again on
request), so a sync runs `sync` whether or not the digest changed; adding an overlay already
prepared is a sync. A consumer with no sync operation of its own runs `sync` before it activates a
digest other than the recorded one. The record, per identity and OS, holds the digest and phase of
the last preparation that succeeded. The state directory belongs to the identity and OS, not the
digest: kept across syncs and digests, made empty before `install`, deleted after `remove` whether
`remove` succeeds or not, outside the root and the tree digest, read-only in the sandbox. A failed
`install` or `sync` leaves the record and the state as the script left them, is reported, and blocks
the digest it ran for, except the recorded digest itself, which stays active. An overlay under a new
identity is a new overlay: the old identity is removed through its own `remove`, and the new one
runs `install`.

**Reason:** the owner asked whether setup, which ran once per digest, should also run on sync, and
ruled that it should: a user who syncs expects the overlay brought up to date, and what setup
prepares (a toolchain, a model, a cache) can go stale without the overlay changing. Tying phases to
operations makes the rule one any consumer can apply, with or without a sync command. A state
directory per digest made `sync` start empty, so a heavy setup fetched everything again on each
update; one per identity lets `sync` update in place, which replaces the separate cache directory
considered for that. Emptying it before `install` keeps the promise that `install` starts empty,
since after a failed `install` the directory may hold its leftovers. Blocking a digest whose
preparation failed still fits: only the record says a digest is prepared. The recorded digest is
the exception because the record already vouches for it, and deactivating it on a failed re-run
would let a network outage disable an overlay that was working. The state directory stays read-only
in the sandbox, with more reason, since what an agent planted there would now reach every later
sync; it stays outside the root, or a write would change the digest it is checked against.

**Status:** adopted; Proposed until an implementation reads it. Supersedes the choice of phase by
digest alone and the per-digest state directory of
[decision 14](#14-setup-is-told-its-phase-install-sync-remove).

## 16 — Dependencies by default, in shared, named or isolated environments

**Decision:** `lib/python/requirements.txt` and `lib/node/package.json` are installed by default, at
`install` and every `sync`, before setup; `[defaults] deps = false` turns both off, and a
`runtime.python` variant naming `requirements` or `lock`, or a `runtime.node` variant naming
`package`, replaces the default file. A requirements file with a `--hash` on every requirement is
pinned, and one with some is refused; a `package.json` is pinned by the `package-lock.json` beside
it (`npm ci`), otherwise installed with `npm install`. An unpinned file installs and is reported as
`unlocked-dependencies`; every install is reported as `deps-network`. `lib/node/` is the Node.js
library directory, on `NODE_PATH`, as `lib/python/` is on `PYTHONPATH`, each followed by the
installed packages. Each runtime variant's `environment` chooses where packages go: `"shared"` (the
default), the consumer's one environment for that runtime in the scope; a name, shared by the
overlays choosing it; or `"isolated"`, the overlay's own. A shared or named environment is
installed from every member's file in one run, in composition order; members pinning one package to
different versions conflict, are reported with the package, and are not activated; the consumer
never picks a version. Each install, sync and removal rebuilds the environment from the remaining
members' files; a shared or named environment lives while an overlay uses it, an isolated one goes
with its overlay. `lib/<runtime>/` with that ecosystem's manifest is kept for other runtimes.

**Reason:** the owner ruled that `requirements.txt` in `lib/python/`, and each package manager's
usual file, belong to the install, and that an unlocked file installs and is reported rather than
being ignored, which overrides the earlier choice in [decision 12](#12-conventional-files-take-effect-by-default-until-defaults-turns-one-off)
to install only from `runtime`. The owner then ruled that one environment per overlay downloads
the same packages too often, so the default is the scope's shared environment, as dotagents keeps
one per store, with a name or `isolated` to keep an overlay apart. Installing a shared environment
in one run is what makes it fetch a package once and lets the package manager see every requirement
together; a conflict blocks the overlays rather than picking a version, since either version would
silently break one of them. Rebuilding, rather than uninstalling one overlay's packages, is the only
way to take out exactly what no remaining file asks for: pip and npm uninstall a package but not the
packages only it needed, and nothing records which overlay installed which. `pylock.toml` (PEP 751)
is the standard Python lock format, but pip installs it only as an experiment, so hashes in the
requirements file pin for now. npm reads one lock per install, so a shared Node.js environment of
several overlays is unpinned and says so. The key is `environment`, not `env`, which already names
environment variables; one `deps` key for every runtime, like `lib`, keeps an overlay that turned
dependencies off that way when an edition adds a runtime.

**Status:** adopted; Proposed until an implementation reads it.

## 17 — Store metadata is one informational table

**Decision:** what an overlay says about itself for a store is the `[about]` table of
`overlay.cfg`: `summary`, `icon`, `homepage`, `repository`, `license` (an SPDX expression),
`authors` and `tags`, beside the Core `name` and `description`, which keep their place. It is
informational: only a store and a validator read it, nothing in it changes composition, activation
or the environment, and a problem in it is reported without stopping the manifest from applying.
There is no `keywords` field and no `version` field.

**Reason:** one table lets a consumer skip all of it by one key, and draws the line a validator
needs between a problem that blocks an overlay and one that only spoils its listing: everything
under `/about`. Top-level fields would have spread that line over seven names, and taken names such
as `license` and `tags` from the unknown top-level keys other tools already write. The same table
serves a catalog entry, so the fields are defined once. `keywords` beside `tags` would be two lists
of search words with no rule telling them apart; a store searches `name`, `summary`, `description`
and `tags`. A version would compete with what already says which overlay this is: the source's
ref and the tree digest.

**Status:** adopted; Proposed until an implementation reads it.

## 18 — Icons are PNG or WebP, never SVG, within limits the consumer sets

**Decision:** `about.icon` is a relative path to a `.png` or `.webp` file, whose content must be the
format its extension names. A store bounds its size and dimensions by settings with defaults
(512 KiB, 1024 by 1024 pixels), reads the dimensions from the header and refuses before decoding,
shows a still image and nothing it carries besides its pixels, and shows its own placeholder when
an icon is missing or refused. SVG is not an icon format.

**Reason:** a store shows icons from overlays nobody has reviewed, so the format must be one a
store can bound before it spends memory on it. PNG and WebP carry their dimensions in a fixed
header and are decoded by maintained libraries in every language. SVG is a document format with
scripts, links, external references, fonts and entities; a safe subset would need an allow-list
every store implements alike, and no vector could show that two stores render it alike, for an
image a raster serves at icon sizes. Limits are settings, not constants, so a consumer on a small device can
lower them and none needs a waiver to raise them.

**Status:** adopted; Proposed until an implementation reads it.

## 19 — Catalogs extend the registry; the fetched overlay is authoritative

**Decision:** a catalog is the registry dotagents reads, with an `overlays` mapping whose entries
are a source string (minimal) or a table of `source`, `ref`, `pin`, `description` and `about`
(full), told apart by the entry's type; catalog-level `name`, `description` and `homepage` are
optional. A catalog's file extension selects its format; other names follow the manifest's rule.
Relative sources resolve beside the catalog; a catalog from a repository or a URL cannot name a
local source. A consumer labels each catalog it is given, shows a name two catalogs share qualified
as `<label>/<name>`, never merges entries, and never picks one for an unqualified name by itself.
Catalog metadata is advertising: after fetching, the overlay's manifest and tree are what a store
shows, a catalog pin is checked like any pin, and what an overlay would do is shown from its own
manifest before it is installed.

**Reason:** existing registries must keep working unchanged, and one file format is easier to
publish and read than a registry and a catalog side by side; telling the forms apart by type keeps
that decision static and lets one catalog mix them. Registries are named by format today, so the
extension decides, as it already does in dotagents. An unknown key refuses an entry, not the
catalog, because a misspelt `pin` must not install an overlay unpinned, and one bad entry should not
hide the rest. A catalog is written by someone other than the overlay's author and changes
independently of it, so nothing in it can stand in for reading the overlay itself; pins are the one
claim a consumer can check, and it does.

**Status:** adopted; the minimal form is what dotagents reads, the full form is Proposed.
