# Manifest

**Core.** An overlay MAY carry a manifest at its root, in one of two files:

- [`OVERLAY.md`](#overlaymd), the standard form: the manifest is its front matter, and its body is the
  overlay's context;
- `overlay.cfg`, the same fields as a document of their own, for overlays written by tools.

A consumer MUST accept an overlay with neither; it reads as the empty mapping. **An overlay with both
is refused, never merged** (`two-manifests`), whatever either holds: two places to write a field is
the duplication this rule exists to prevent. Telling which is present needs the overlay's list of
files and neither file's content.

> **Status:** dotagents 0.9.0, the reference implementation, reads `overlay.cfg`. `OVERLAY.md` is
> **Proposed** until an implementation reads it; see
> [Compatibility](../../compatibility.md#overlaymd-yaml-and-named-skills).

A consumer that does not read `OVERLAY.md` yet MUST say so of an overlay that holds one, or refuse it:
applying it as an overlay with no manifest would silently drop everything its front matter declares.

## Reading `overlay.cfg`

A reader turns the file's bytes into a value of the [data model](#data-model) in these steps. The
same steps apply to every other file AOS reads as a document, such as an
[env file](environment.md#env-files).

1. **Byte-order mark.** One leading UTF-8 byte-order mark (`EF BB BF`) is dropped. Only one.
2. **Format line.** If the remaining bytes start with `#!`, the first line names the format:
    - the line runs to the first line feed (`0x0A`), which is not part of it;
    - it is split on runs of space, tab, form feed and carriage return (so a carriage return
      before the line feed is whitespace), and the **last word** is taken;
    - of that word, the part after the last `/` or `\` is taken, leading `.` characters are
      dropped, and ASCII letters are lowercased;
    - the result is the format name: `#!json`, `#!/usr/bin/env yaml` and `#!.TOML` name `json`,
      `yaml` and `toml`.

    The line, with its line feed, is removed before the rest is parsed; a parse error's line number
    still counts it. A line that yields no name (`#!` alone, or only whitespace) is an error.
3. **Default.** Otherwise the format is `toml`, and the bytes are parsed whole.
4. **No guessing.** Nothing else selects a format: not the content (`{`, `---`, `%YAML`), not
   another marker, not the file's extension, not a retry with another parser. A document starting
   `{` without a format line is TOML, and fails as TOML.
5. **Parse** with the selected format's rules below, then check the result against the data model.

The text is UTF-8. Invalid UTF-8 is an error in every format. A byte-order mark where the parser's
text starts (a second one, or one after the format line) is an error, since parsers disagree on it.
A document whose remaining text is empty or only spaces, tabs and line breaks reads as the empty
mapping, in every format.

### Formats

| Name | Aliases | Class | Syntax |
| --- | --- | --- | --- |
| `toml` | | **Core**: every reader MUST read it | [TOML 1.0](https://toml.io/en/v1.0.0). A construct a later TOML adds (a newline or trailing comma in an inline table, the `\e` and `\xHH` escapes) is not portable: a reader either refuses it or gives it the meaning that TOML defines, and authors do not use it |
| `yaml` | `yml` | **Core**: every reader MUST read it | [Restricted YAML](#restricted-yaml): [YAML 1.2](https://yaml.org/spec/1.2.2/), one document, core schema |
| `json` | | **Optional Extension** | [RFC 8259](https://www.rfc-editor.org/rfc/rfc8259) |

Both TOML and YAML are required. Front matter defaults to YAML, so nobody can read `OVERLAY.md`
without it; `overlay.cfg` **keeps its own default of TOML**, and an `aos` env file and a catalog named
by no extension follow it, so nobody can read those without TOML. Requiring YAML changes what a reader
can read, never what an unmarked document is: an `overlay.cfg` holding YAML still needs its `#!yaml`.

A reader MAY support further formats under names of its own. A reader that meets a format name it
does not support MUST refuse the document with an error that names the format; it MUST NOT fall back
to another format. An error names the format only when the name is ASCII letters, digits, `-`, `_`
and `.`; otherwise it says that the line names no supported format.

### Static reading

Reading a manifest MUST NOT execute anything, read any other file, or consult the environment.
Whatever library a reader is built on, it reads the manifest this way:

- **No includes or imports.** No directive pulls in another file or URL (`include`, `import`,
  `$ref`, `extends`, `!include`). Such keys are ordinary data.
- **No interpolation or templating.** `$NAME`, `${NAME}`, `%(name)s`, `{{ name }}` and `<NAME>` in a
  string are those characters. A field that gives a string meaning (a path relative to the root,
  a routing line, an env value's [substitution](environment.md#substitution)) says so itself, and
  acts only when the declaration is applied.
- **YAML:** only the [restricted subset](#restricted-yaml).
- **JSON:** a reader MUST refuse a duplicate key in one object, and the non-standard `NaN`,
  `Infinity` and comments.
- Libraries that offer includes, relative imports, variable expansion or templating (some
  general configuration readers do) MUST have those features off for AOS documents.

### Restricted YAML

Wherever AOS reads YAML (front matter, a `#!yaml` document, a `.yaml` catalog) it reads this subset of
YAML 1.2, which a reader can build from a parser's events with nothing applied. Block and flow styles,
quoted and block scalars and comments are ordinary YAML, and stay.

| A reader MUST refuse | Class |
| --- | --- |
| An anchor (`&a`) or an alias (`*a`), defined or not | `yaml-anchor` |
| A tag: `!include`, `!!python/...`, `!!binary`, `!!str`, a verbatim `!<...>`, the bare `!`, on a scalar or a collection | `yaml-tag` |
| A mapping key `<<`, in any scalar style and however it is written (`"\x3c<"`) | `yaml-merge-key` |
| A directive: `%YAML`, `%TAG` | `yaml-directive` |
| More than one document, including content after a line `...` | `parse-error` |
| U+0085, U+2028 or U+2029 anywhere in the text, which YAML 1.1 and 1.2 parsers split differently. As an escape in a double-quoted string (`"\u2028"`) it is a character of the string | `parse-error` |
| A key that is not a string: a plain scalar resolving to another type (`1:`, `true:`), or a collection | `non-string-key` |
| Two keys equal once read, in whichever styles (`a` and `"a"`) | `duplicate-key` |

**Nothing is expanded before it is refused.** The size of a document with aliases is not the size of
its text, so a reader refuses an anchor or an alias where it stands. A library that applies aliases,
tags or merge keys and hands back the result cannot be checked afterwards, by which time it has done
so: a reader builds on that library's parser events, or on another parser.

**Typing is strict.** A quoted or block scalar is a string. A plain scalar resolves by the YAML 1.2
core schema, and by nothing else:

| A plain scalar | Is |
| --- | --- |
| empty, `~`, `null`, `Null`, `NULL` | a null, refused (`null-value`) |
| `true`, `True`, `TRUE`, `false`, `False`, `FALSE` | a boolean |
| `[-+]?[0-9]+`, `0o[0-7]+`, `0x[0-9a-fA-F]+` | an integer, in decimal when it has a leading zero; outside signed 64 bits, refused (`integer-range`) |
| `[-+]?(\.[0-9]+\|[0-9]+(\.[0-9]*)?)([eE][-+]?[0-9]+)?` | a float |
| `.inf`, `.nan` in the core schema's spellings, signed or not | refused (`non-finite-float`) |
| anything else, `yes`, `on`, `2026-11-04`, `1_000`, `0b11` and `1:20` included | a string |

The schema's types then hold as in every format: `priority: "5"` and `priority: 5.0` are not integers.

### Data model

The result of reading is a **mapping** whose keys are strings. Values are:

| Type | TOML | JSON | YAML |
| --- | --- | --- | --- |
| string | string | string | string scalar |
| integer, signed 64-bit | integer | number with no fraction and no exponent | core-schema int |
| float, finite | float | number with a fraction or an exponent | core-schema float |
| boolean | boolean | `true` / `false` | core-schema bool |
| array | array | array | sequence |
| mapping, string keys | table | object | mapping |

A reader MUST refuse:

- a null (`null`, `~`), anywhere, including in keys it does not recognise;
- a TOML date, time or date-time value;
- a non-finite float (`nan`, `inf`);
- an integer outside the signed 64-bit range;
- a mapping key that is not a string, and two keys equal in one mapping;
- a string that is not valid Unicode (a lone surrogate escape in JSON).

Two documents in different formats are the same manifest when their data model values are equal.
A number's type follows how it is written, never its size: a JSON integer outside the signed 64-bit
range is refused, not read as a float. Where a field takes an integer, a float of equal value is not
accepted (`30.0` is not `30`).
Mapping order carries no meaning anywhere in AOS.

A reader MUST bound what it reads: a size in bytes and a nesting depth. Both are settings with
defaults (1 MiB and 64 are RECOMMENDED); there is no floor. The depth counts arrays and mappings: the
top-level mapping is at depth 1, and an array or mapping inside one at depth `n` is at depth `n + 1`.

The depth bound holds while parsing, in every format: text nested past it is refused (`too-deep`), and
a parser that recurses on its input MUST NOT reach the end of its stack first. A document of a few
hundred kilobytes of `[` is within the size bound.

## `OVERLAY.md`

**Core, Proposed.** `OVERLAY.md` at the overlay root is the manifest and the context in one file, as
`SKILL.md` is for a skill. The name matches exactly: `overlay.md` and `kb/OVERLAY.md` are files like
any other.

```markdown
---
name: release-notes
description: Conventions for release notes and changelogs.
requires: [engineering]
priority: 450

about:
  summary: Release notes and changelogs, written the same way everywhere.
  license: MIT
---
# Release notes

Write a release note for the reader who is deciding whether to upgrade.
```

- **The same fields.** The front matter holds the [fields](#fields) of `overlay.cfg`, `about` included,
  as a value of the [data model](#data-model). The schema, [validation](#validation) and
  [static reading](#static-reading) apply as they do there.
- **YAML unless it says otherwise.** A first line inside the opening fence that starts `#!` is a
  [format line](#reading-overlaycfg), with its rules; without one the metadata is
  [restricted YAML](#restricted-yaml). To YAML the line is a comment, so tools that know front matter
  still see front matter; a `#!` before the fence would be a line of text, and there would be no front
  matter at all.

    ```markdown
    ---
    #!toml
    name = "release-notes"
    ---
    ```

- **No front matter.** A file with no opening fence has an empty manifest, and all of it is the body.
- **A body is the context.** A body holding anything but white space (space, tab, carriage return and
  line feed, and nothing else) is the overlay's [`context` default](package.md#defaults), instead of
  `CONTEXT.md`. While it is context, `CONTEXT.md` is **ignored and reported** (`context-ignored`)
  wherever it is named, in `context` or a [harness's](harness.md#harness-hints) `context`. A body of
  white space is no body, and `CONTEXT.md` stays. `[defaults] context = false` turns the body off as it
  would `CONTEXT.md`: nothing of the file is context, `CONTEXT.md` means only what `context` says of
  it, and a body that is not context is not read. Naming `OVERLAY.md` in `context` names its body and
  puts it there, as naming `CONTEXT.md` does. A body that is context is UTF-8 text, or the overlay is
  refused (`invalid-utf8`).
- **Digests do not change.** `OVERLAY.md` is a member of the [tree digest](integrity.md#tree-digest)
  like any file, by its bytes. Its front matter and body are not hashed apart, and nothing in them is
  normalized first, so a file differing in line ends or a byte-order mark has another digest, though it
  reads alike.

### The split

Splitting a document into metadata and body is one step, on bytes, before any parser and without
decoding. Reading the metadata is a second: a reader that wants only the body never parses. The same
split serves `OVERLAY.md`, a [context file](harness.md#context) and a [`SKILL.md`](skills.md).

1. **Byte-order mark.** One leading byte-order mark (`EF BB BF`) belongs to the file, and is in neither
   the metadata nor the body. A second one is text.
2. **Lines.** Only a line feed (`0A`) ends a line, and a carriage return directly before it is part of
   that line end. A carriage return elsewhere, a form feed, U+0085, U+2028 and U+2029 end no line, and
   `LF` and `CRLF` may mix within one file.
3. **Fences.** A fence is a line holding `---` or `...` from its first byte, followed only by spaces and
   tabs up to its line end. `--- # note`, ` ---`, `----` and `---` with a form feed are not fences, and
   a carriage return at the very end of a file, with no line feed, is not a line end.
4. **Opening.** The first line is the opening fence, and it is `---`. `...` closes and never opens.
5. **Closing.** The closing fence is the next line that is `---` or `...`, whichever comes first. It may
   be the file's last line, with no line end. The split knows no format: a line `---` in a TOML
   multi-line string closes the block there.
6. **Metadata and body.** The metadata is every byte from after the opening fence's line end up to the
   closing fence. The body is every byte after the closing fence's line end. **Neither is changed**: no
   line end is normalized, no blank line and no later byte-order mark is dropped, and the body is not
   checked as UTF-8 until it is used as context. Normalizing is the caller's choice, after the split.

A reader tells these cases apart. A **viewer** shows a document to a person; a **gate** applies or
validates it.

| Case | When | Manifest | A viewer | A gate |
| --- | --- | --- | --- | --- |
| `none` | The first line is no opening fence | empty | Shows the body | Accepts it |
| `unterminated` | There is an opening fence and no closing fence, so no block | | Shows the text, all of it | Refuses: `unterminated-front-matter` |
| `too-large` | The [bound](#bounds) ended before the split did | | Shows no metadata | Refuses: `too-large` |
| `empty` | The metadata is only white space, or a format line and white space | empty | Shows the body | Accepts it |
| `unknown-format` | A format line names a format the reader does not read, or none | | Shows the metadata as unreadable text | Refuses, by name: `unsupported-format`, `no-format-named` |
| `does-not-parse` | The parser refuses it, or [reading](#reading-overlaycfg) does | | Shows the metadata as unreadable text | Refuses, by the reading class |
| `not-a-mapping` | It parses to a sequence or a scalar | | Shows the metadata as text | Refuses: `not-a-mapping` |
| `mapping` | It reads as a mapping | the mapping | Shows its fields | Applies the [data model](#data-model) and the schema to it |

**Positions.** Offsets count bytes from the first byte of the file, a byte-order mark included. Lines
count from 1 at the file's first line, whose opening fence is line 1, so the metadata starts on line 2
and a format line counts as one. A refusal names the file and the line, as `OVERLAY.md:3`, and the
column where the parser gives one (`OVERLAY.md:3:5`; columns are not compared across parsers, which
count them in different units). With nothing finer, it names the metadata's first line.

#### Bounds

The **head** is every byte from after any byte-order mark through the closing fence's line end. A
reader bounds it by a setting, 1 MiB by default, with no floor; a head past the bound is `too-large`,
and a refusal names the setting. A split **reads nothing past its bound**, not even to see whether a
closing fence follows, so an unclosed block past the bound is `too-large` rather than `unterminated`,
and a first line still possibly an opening fence when the bound ends is `too-large` too. The body does
not count, however long it is: it is bounded where it is used, as [context](harness.md#context). The
[depth](#data-model) is a setting as it is for any document.

### Why a block closes by `---` or `...`

Both, in one rule for every document, because YAML itself ends a document with `...` and starts a new
one with `---`, because a [context file](harness.md#context) closed by `...` must not start showing an
agent its metadata, and because a narrower reader and a wider one would otherwise disagree about where
the same file's metadata ends. The vectors hold every reader to the same line.

## Validation

The JSON Schema at [`schemas/overlay.schema.json`](../../schemas/overlay.schema.json) describes the
data model a manifest must have, in any format. JSON Schema cannot express every rule (an integer
field refusing a float, cross references, files that must exist); a validator checks those
semantically, as each section states.

The schema is the strict authoring profile. dotagents is more tolerant of ordinary fields: it
replaces a value of the wrong type with the default, with a warning. A strict failure does not mean
dotagents would refuse the overlay.

**Unknown keys.** Unknown top-level keys are allowed and MUST be preserved by a parser that exposes
the document. A consumer MUST NOT act on an unknown key. Inside a table this specification defines,
unknown keys are errors unless the table says otherwise.

A problem under `about` is reported like any other, and never makes a manifest invalid for applying:
`about` is [informational only](catalog.md#informational-only).

There is no manifest version field. The edition is a property of the specification, not of a
manifest.

## Fields

| Field | Type | Class | Default | Section |
| --- | --- | --- | --- | --- |
| `name` | string | Core | the directory name | [Package](package.md#names-and-paths) |
| `description` | string | Core | `""` | |
| `requires` | array of overlay names | Core | `[]` | [Dependencies](dependencies.md) |
| `routing` | array of strings | Core | `[]` | [Composition](composition.md#merging) |
| `rules` | array of relative paths | Core | `[]`, after the [defaults](package.md#defaults) | [Composition](composition.md#merging) |
| `priority` | integer | Core | `500` | [Composition](composition.md#deterministic-ordering) |
| `defaults` | mapping of default to boolean | Core, **Proposed** | every default on | [Package](package.md#turning-a-default-off) |
| `context` | array of relative paths | Optional Extension, **Proposed** | `[]`, after the [defaults](package.md#defaults) | [Context and harnesses](harness.md) |
| `skills` | array of skill names and tables | Optional Extension, **Proposed** | `[]`, after the [defaults](package.md#defaults) | [Skills](skills.md) |
| `env` | mapping of variable to env value | Optional Extension, **Proposed** | `{}` | [Environment](environment.md#env) |
| `env_files` | array of env files | Optional Extension, **Proposed** | `[]`, after the [defaults](package.md#defaults) | [Environment](environment.md#env-files) |
| `paths` | array of path additions | Optional Extension, **Proposed** | `[]`, after the [defaults](package.md#defaults) | [Environment](environment.md#path-additions) |
| `env_scripts` | array of scripts | Optional Extension, **Proposed** | `[]`, after the [defaults](package.md#defaults) | [Environment](environment.md#env-scripts) |
| `runtime` | mapping | Optional Extension, **Proposed** | `{}` | [Runtime and setup](runtime.md#runtime) |
| `setup` | array of setup variants | Optional Extension, **Proposed** | `[]`, after the [defaults](package.md#defaults) | [Runtime and setup](runtime.md#setup) |
| `scripts` | mapping of command name to script | Optional Extension | `{}` | [Commands](commands.md) |
| `mcp` | mapping | Optional Extension | absent | [MCP](mcp.md) |
| `harness` | mapping of harness id to hints | Optional Extension, **Proposed** | `{}` | [Context and harnesses](harness.md#harness-hints) |
| `about` | mapping of informational fields | Optional Extension, **Proposed**, informational | absent | [Store metadata](catalog.md#informational-fields) |

Seven fields have [defaults](package.md#defaults) that come from the overlay's files. They apply
first, the field's declared entries follow, and a declared entry naming the same file or directory
as a default entry replaces it; `defaults` turns one off. A field's class is the class of its
declaration; the class of each default is in that section.

A **relative path** is `/`-separated and relative to the overlay root, and every component of it:

- is not empty and does not end in `.` or a space (so `.` and `..` are excluded, and so are names
  Windows silently shortens);
- holds none of `\ : * ? " < > |`, no control character (U+0000–U+001F, U+007F–U+009F), and no
  character that some filesystems ignore or that reorders text (U+200C–U+200F, U+202A–U+202E,
  U+2066–U+206F, U+FEFF);
- is not, in any ASCII case, an [excluded name](package.md#layout) or a Windows device name (`con`,
  `prn`, `aux`, `nul`, `conin$`, `conout$`, `com` or `lpt` followed by a digit or `¹²³`) with or
  without an extension, and does not end in `.pyc` in any case;
- holds no `~` followed by a digit, the shape of a Windows short name.

The schema's `relPath` expresses exactly this. A consumer resolves a relative path under the root
and opens it so that it cannot leave the root through a symbolic link, a junction or `..` (for
example `openat2` with `RESOLVE_BENEATH`, or a check of the opened handle's final path).

### Core fields in dotagents

| Field | dotagents 0.8.3 |
| --- | --- |
| `name` | The directory name when absent, empty, or not a string. A sort and display tiebreaker; the installed identity is the directory name. |
| `description` | `""` when absent or not a string. |
| `requires` | Non-strings and invalid names dropped with a warning; normalized and deduplicated in order. Used by add and remove. |
| `routing` | Non-strings and blanks dropped; surrounding newlines trimmed. Appended to the managed routing section. |
| `rules` | Each path's leading run of `- **` bullets, up to the next `## ` heading, appended to the always-on rules. No default: an absent `rules` contributes nothing. |
| `priority` | `500`; a boolean is not an integer. Sorted ascending by `(priority, name, directory)`. |

## Examples

As `OVERLAY.md`, the form above. As `overlay.cfg`, TOML, its default:

```toml
name = "python-quality"
description = "Python review conventions and reusable checks."
requires = ["engineering"]
routing = ["- Python changes → `$PYTHON_QUALITY_OVERLAY_ROOT/kb/PYTHON.md`"]
rules = ["kb/always-on.md"]
priority = 420

[[paths]]
variable = "PYTHONPATH"
path = "lib/python"
position = "append"
```

The same manifest in JSON. The format line is required, since TOML is the default:

```json
#!json
{
  "name": "python-quality",
  "description": "Python review conventions and reusable checks.",
  "requires": ["engineering"],
  "routing": ["- Python changes → `$PYTHON_QUALITY_OVERLAY_ROOT/kb/PYTHON.md`"],
  "rules": ["kb/always-on.md"],
  "priority": 420,
  "paths": [{ "variable": "PYTHONPATH", "path": "lib/python", "position": "append" }]
}
```

And in YAML:

```yaml
#!yaml
name: python-quality
description: Python review conventions and reusable checks.
requires: [engineering]
routing: ["- Python changes → `$PYTHON_QUALITY_OVERLAY_ROOT/kb/PYTHON.md`"]
rules: [kb/always-on.md]
priority: 420
paths:
  - variable: PYTHONPATH
    path: lib/python
    position: append
```
