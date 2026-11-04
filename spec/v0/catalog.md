# Store metadata and catalogs

**Optional Extension, Proposed.** A **store** is a consumer, or the part of one, that lists overlays
for a person to find and install, by name, summary, icon and tags, from one or more catalogs. This
section defines what an overlay says about itself for a store (`about`), the catalog a store lists
from, and what a store may believe of either.

**All of it is informational.** A consumer that shows no store ignores this section and loses
nothing: no field here changes what an overlay does.

> **Status:** dotagents reads the minimal form of a catalog as its registry (see
> [Sources and distribution](distribution.md#source-form)). It reads no `about` table, shows no
> store and reads no icon.

## Informational fields

`about` is a table of `overlay.cfg`:

```toml
name = "release-notes"
description = "Conventions for release notes and changelogs."

[about]
summary = "Release notes and changelogs, written the same way in every repository."
icon = "icon.webp"
homepage = "https://example.org/overlays/release-notes"
repository = "https://github.com/example/overlays"
license = "MIT OR Apache-2.0"
authors = ["Example Docs Team <docs@example.org>"]
tags = ["documentation", "release", "changelog"]
```

| Field | Type | Meaning |
| --- | --- | --- |
| `summary` | line | What the overlay is for, in one line, shown under its name in a listing |
| `icon` | relative path | A PNG or WebP image in the overlay; see [Icons](#icons) |
| `homepage` | https URL | A page about the overlay |
| `repository` | https URL | A page where its files can be browsed. It is not a [source](distribution.md#source-form): nothing is fetched from it |
| `license` | license expression | The overlay's license |
| `authors` | array of lines | Who wrote it, as display text, conventionally `Name <address>` |
| `tags` | array of tags | Words a store filters and searches by |

- A **line** is a non-empty string with no control character (U+0000–U+001F, U+007F–U+009F), no
  U+2028 or U+2029, and no bidirectional embedding, override or isolate (U+202A–U+202E,
  U+2066–U+2069), which would let displayed text read differently from its characters.
- An **https URL** starts `https://`, names a host, and holds no user information, white space or
  control character.
- A **license expression** is an [SPDX license expression](https://spdx.github.io/spdx-spec/v2.3/SPDX-license-expressions/):
  license identifiers (ASCII letters, digits, `.` and `-`, optionally followed by `+`) and
  `LicenseRef-` references, a `WITH` exception, joined by `AND` and `OR` with parentheses, `AND`
  binding tighter than `OR`. The operators are upper case. Whether an identifier is on the SPDX
  License List is not checked; a store MAY check it for display.
- A **tag** is lowercase ASCII letters and digits in runs joined by single `-`, at most 32
  characters; `tags` holds each tag once.

The Core fields stay where they are: a store shows `name` as the overlay's title and `description`
as its long text, as plain text.

### Informational only

- Only a store and a validator read `about`; any other consumer MUST NOT. Reading the manifest
  still checks the [data model](manifest.md#data-model) everywhere, so a null inside `about` makes
  the manifest unreadable, as a null in an unknown key does.
- Nothing in `about` changes composition, its order, activation, the environment, setup,
  dependencies, permissions, trust or the result of any other section. A consumer MUST NOT act on
  it, and MUST NOT give it to an agent as instructions.
- **A problem in `about` never stops an overlay from applying.** A validator reports it, at a
  pointer under `/about`, like any other problem; a consumer that applies the overlay treats a
  manifest whose only problems are under `/about` as valid, and a store leaves out each invalid
  field.

`about` is a table this specification defines, so a key it does not define is an error to a
validator, and a store leaves that key out.

## Icons

`icon` names a file of the overlay by a [relative path](manifest.md#fields) ending in `.png` or
`.webp`, in any ASCII case. The file is a member of the [tree digest](integrity.md#tree-digest)
like any other, and a validator that knows the overlay's files checks that it is there. No file is
an icon by its name; only `about.icon` names one.

- **Formats.** PNG ([PNG, third edition](https://www.w3.org/TR/png-3/)) and WebP
  ([RFC 9649](https://www.rfc-editor.org/rfc/rfc9649)). The content MUST be the format its
  extension names, told by its signature: `89 50 4E 47 0D 0A 1A 0A` for PNG; `RIFF`, a size and
  `WEBP` for WebP, whose first chunk is `VP8 `, `VP8L` or `VP8X`.
- **No SVG.** SVG is not an icon format, and a `.svg` path is invalid. An SVG file is an XML
  document that can hold scripts, links, external references, fonts, styles and entity
  declarations; showing one safely means an XML parser that refuses entities and an allow-list of
  elements and attributes that every store would have to implement alike, for an icon that a
  256-pixel raster already serves.
- **Limits.** A store bounds an icon by settings with defaults: a size in bytes (512 KiB is
  RECOMMENDED) and a width and a height in pixels (1024 each are RECOMMENDED); there is no floor. It
  reads the dimensions from the header (PNG's `IHDR`; WebP's `VP8 ` frame header, `VP8L` header or
  `VP8X` canvas size) and refuses an icon past a limit **before decoding it**.
- **Still and bare.** A store shows an icon as a still image, the first frame of an animated one.
  It shows and follows nothing an image carries besides its pixels (text chunks, Exif, XMP), and
  MAY ignore an embedded colour profile.
- **Shape.** Authors ship a square icon, 256 by 256 pixels or larger within the default limits;
  transparency is allowed. A store scales an icon to fit the space it gives it, keeping its aspect
  ratio, and never crops it.

A store refuses an icon, checking in this order:

| Check | Class |
| --- | --- |
| The path's extension is neither `.png` nor `.webp` | `icon-format` |
| The file is larger than the size limit | `icon-too-large` |
| The content has neither signature | `icon-format` |
| The content is the other format | `icon-mismatch` |
| The header cannot be read, or gives a width or height of zero | `icon-unreadable` |
| The width or the height is past its limit | `icon-dimensions` |
| The image fails to decode | `icon-unreadable` |

**Missing or refused.** When `icon` is absent or invalid, names no file of the overlay, or the file
is refused, a store shows a placeholder of its own: an image it ships, or one it draws from the
overlay's name. It never shows an image fetched from elsewhere or another overlay's icon in its
place. It reports a refused icon where it reports other display problems, never as a problem of
the overlay, which installs and activates as if it had no icon.

## Catalogs

**Optional Extension.** A **catalog** is a document listing overlays by name with the source of
each, so a store can list and search them without fetching any. It is the registry that dotagents
reads, extended: a registry is a catalog in the [minimal form](#entries-and-forms). A catalog can be
a file in any directory or repository, or at a URL, and a consumer can be given
[several](#several-catalogs).

### Reading a catalog

A catalog's **file name** (for a URL, the last segment of its path) selects its format, since
existing registries are named by format:

- `.toml`, `.json`, `.yaml` and `.yml`, in any ASCII case, name TOML, JSON and YAML. One leading
  byte-order mark is dropped and the rest is parsed whole: a first line `#!...` is not a format line
  (TOML reads it as a comment, JSON as an error).
- Any other name (`catalog.cfg`, or none) is read as [`overlay.cfg` is](manifest.md#reading-overlaycfg):
  a format line, else TOML.

Everything else of [reading](manifest.md#reading-overlaycfg) holds: UTF-8, the data model, static
reading, and limits on size and depth, as settings with defaults (4 MiB and 64 are RECOMMENDED,
since a catalog lists many overlays).

### Entries and forms

```toml
name = "Example overlays"
description = "The overlays a team installs."
homepage = "https://example.org/overlays"

[overlays]
engineering = "../engineering"

[overlays.release-notes]
source = "https://github.com/example/overlays.git#release-notes"
ref = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
pin = "sha256:8280aaf5de7c4f61342f648586d534e481ae095cef223dded70f5b1db5bd84a1"
description = "Conventions for release notes and changelogs."

[overlays.release-notes.about]
summary = "Release notes and changelogs, written the same way in every repository."
icon = "icons/release-notes.png"
tags = ["documentation", "release", "changelog"]
```

A catalog is a mapping with an `overlays` mapping:

| Key | Type | Meaning |
| --- | --- | --- |
| `overlays` | mapping of name to entry | Required. The overlays the catalog lists |
| `name` | line | The catalog's title, informational |
| `description` | string | What the catalog holds, informational |
| `homepage` | https URL | A page about the catalog, informational |

Other top-level keys are allowed, kept and not acted on, as in a manifest. A document without an
`overlays` mapping, including one that is itself a mapping of names to sources, is not a catalog
(`not-a-catalog`).

Each key of `overlays` is an overlay **name**, valid and compared normalized as
[identities](package.md#names-and-paths) are. Its value, the **entry**, is either:

- a **string**, the overlay's [source](distribution.md#source-form): a **minimal entry**; or
- a **table**, a **full entry**:

| Key | Type | Meaning |
| --- | --- | --- |
| `source` | string | Required. The overlay's source |
| `ref` | string | The Git ref, for a Git source written without `@ref`: a branch, tag or commit with no `/`, `:`, `\`, `@`, `#`, white space or control character, not starting with `-` |
| `pin` | digest | A [tree digest](integrity.md#digest-form) the catalog's author reviewed |
| `description` | string | Informational, as the manifest's |
| `about` | table | The [informational fields](#informational-fields); its `icon` is a file beside the catalog |

A full entry has no other key: an unknown key refuses the entry, since a misspelt `pin` must not
install an overlay unpinned.

**The forms are told apart statically**, by the type of each entry in the data model, never by
content, file name or another key: a string entry is minimal, a table full, and one catalog may mix
them. A catalog whose entries are all strings is in the **minimal form**, which is what readers of
today's registries read; one with any table entry is in the **full form**. The top-level `name`,
`description` and `homepage` do not change the form.

### Sources in a catalog

A consumer resolves an entry's source against the catalog's own location, the source it read the
catalog file from.

- A **relative** source is a directory location that does not start with `/`, `\` or a drive
  letter and `:`. Nothing in it is expanded (`~` is a name). It resolves:
    - for a catalog on this machine, against the catalog file's directory, with `.` and `..`
      removed;
    - for a catalog in a Git repository (a Git source whose `#path` names the catalog file), to the
      same repository at the same ref, whose `#path` is the catalog file's directory joined with
      the relative location and its own `#path`, with `.` and `..` removed. A path that leaves the
      repository refuses the entry (`leaves-repository`);
    - for a catalog at a URL, to that location [resolved as a URL reference](https://www.rfc-editor.org/rfc/rfc3986#section-5)
      against the catalog's URL, keeping its own `#path`.
- Any other source stays as written. A Git location written as a relative path (`../other.git`) is
  not defined by this edition: a catalog writes Git locations in full.
- **A catalog from elsewhere names nothing on this machine.** In a catalog read from a Git
  repository or a URL, an absolute directory, or a Git location that is a local path or a `file:`
  URL, refuses the entry (`local-source`): a catalog chooses its own sources, and one naming a
  local path would install whatever the consumer's machine holds there.
- `ref` belongs to a Git source that has no ref of its own. A `ref` beside an `@ref`, on a relative
  source (whose ref is the catalog's), or on a source that is not Git refuses the entry
  (`ref-not-allowed`).

An entry's `icon` is a relative path resolved the same way, beside the catalog file; being a
relative path, it cannot leave the catalog's directory.

### What a store lists

A store refuses an entry, **alone**, and reports it:

| The entry | Class |
| --- | --- |
| Its name is not a valid overlay name | `invalid-name` |
| Its name normalizes as another's in the same catalog: both are refused | `duplicate-name` |
| It is neither a string nor a table; a table has no string `source`, an unknown key, or a `ref` of the wrong form | `invalid-entry` |
| Its source is not one ([source form](distribution.md#source-form)) | `invalid-source` |
| Its `pin` is not a digest | `invalid-pin` |
| Its `ref` is not allowed | `ref-not-allowed` |
| Its relative source leaves the catalog's repository | `leaves-repository` |
| A catalog from elsewhere names a local source | `local-source` |

An informational field that is invalid or unknown (the catalog's `name`, `description` or
`homepage`; an entry's `description`; each field of an entry's `about`, or an `about` that is not a
table) is left out and reported, and its entry is still listed. The whole catalog is refused only
when it cannot be read or has no `overlays` mapping.

### Several catalogs

A consumer may be given several catalogs. It gives each a **label** from its own configuration: a
valid overlay name, unique among its catalogs when normalized, never taken from the catalog, since
two catalogs can share a `name`.

- An identity that more than one catalog offers is listed once **per catalog**, each shown
  qualified by its label as `<label>/<name>`. An identity that one catalog alone offers is shown by
  its name. A refused entry offers nothing.
- Entries are **never merged**: not their sources, refs, pins or informational fields, even where
  they agree.
- A user names an entry `<label>/<name>`, or by a name that one catalog alone offers. A name that
  more than one catalog offers is **ambiguous**: a consumer MUST NOT pick one by itself. It asks
  the user, or follows an order of catalogs the user configured for this, and reports which catalog
  it took.

## Trust

**A catalog is advertising.** Its author writes its informational fields, and nothing makes them
true: an entry can take another overlay's name, summary or icon, and a `pin` says only what that
author reviewed.

- A store MUST show each entry's source, without user information or query
  ([as distribution says](distribution.md#source-form)), beside its name and its catalog's label:
  the source, not the name, says where an overlay comes from.
- Before fetching, a store MAY show the catalog's informational fields, as the catalog's. **After
  fetching, the overlay's own manifest and tree are authoritative**: what a store shows of a
  fetched overlay (name, description, informational fields, icon) comes from the overlay, and where
  the catalog said otherwise the catalog is wrong.
- A `pin` in an entry is a [pin](integrity.md#pins). A consumer installing from that entry computes
  the tree digest of what it fetched before it installs, sets up or exposes anything of it, and
  refuses the overlay on a mismatch; when the user's configuration pins it too, both MUST match.
  The consumer records the pin it checked in its own configuration. An entry without one installs
  unpinned unless the user pins it, and is reported `unpinned`.
- A catalog makes no overlay trusted. Fetching from a catalog is not installing; installing is the
  user's [trust decision](security.md#execution-and-dependencies), as for any source.

### Before installing

Before a consumer installs an overlay a store offers, it MUST show the user what the overlay would
do, **computed from the fetched overlay's manifest and list of files, after fetching and before
activating, never from catalog claims**:

- the [defaults](package.md#defaults) present and on: `bin/` and `lib/` additions, the `env` file,
  and the `env.<ext>` and `setup.<ext>` that would run;
- its env scripts; its setup, the variant that would run on this OS and its network need; its
  dependency files, their environments and whether each is pinned;
- the overlays it `requires`, each shown and accepted the same way;
- the variables it sets or adds to, the secrets and host variables it asks for, its MCP servers and
  its commands;
- every [weakening](security.md#weakenings) activating it would report, `unpinned` included.

Nothing of the overlay runs to compute this: [reading is static](security.md#reading-is-safe-by-construction).
A catalog field that seems to say any of it (a tag `offline`, a summary saying it runs nothing) is
not evidence of it, and a store MUST NOT present it as such.
