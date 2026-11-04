# Manifest

**Core.** An overlay MAY carry a manifest named `overlay.cfg` at its root. A consumer MUST accept an
overlay with no manifest; it reads as the empty mapping.

> **Status:** dotagents, the reference implementation, reads `overlay.toml` (TOML only) today. The
> name `overlay.cfg` and the format line are **Proposed** until an implementation reads them.

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
| `json` | | **Optional Extension** | [RFC 8259](https://www.rfc-editor.org/rfc/rfc8259) |
| `yaml` | `yml` | **Optional Extension** | [YAML 1.2](https://yaml.org/spec/1.2.2/), one document, core schema |

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
- **YAML:** only the core schema. A reader MUST refuse an explicit tag (`!include`, `!!python/...`,
  `!!binary`, any `!...`), an anchor, an alias, a mapping key `<<`, a directive (`%YAML`, `%TAG`),
  and the characters U+0085, U+2028 and U+2029 anywhere in the document, which YAML 1.1 and 1.2
  parsers split differently. Plain scalars resolve by the YAML 1.2 core schema, so `yes`, `on` and
  `2026-11-04` are strings.
- **JSON:** a reader MUST refuse a duplicate key in one object, and the non-standard `NaN`,
  `Infinity` and comments.
- Libraries that offer includes, relative imports, variable expansion or templating (some
  general configuration readers do) MUST have those features off for AOS documents.

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
| `skills` | array of skill names | Optional Extension, **Proposed** | `[]`, after the [defaults](package.md#defaults) | [Skills](skills.md) |
| `env` | mapping of variable to env value | Optional Extension, **Proposed** | `{}` | [Environment](environment.md#env) |
| `env_files` | array of env files | Optional Extension, **Proposed** | `[]`, after the [defaults](package.md#defaults) | [Environment](environment.md#env-files) |
| `paths` | array of path additions | Optional Extension, **Proposed** | `[]`, after the [defaults](package.md#defaults) | [Environment](environment.md#path-additions) |
| `env_scripts` | array of scripts | Optional Extension, **Proposed** | `[]`, after the [defaults](package.md#defaults) | [Environment](environment.md#env-scripts) |
| `runtime` | mapping | Optional Extension, **Proposed** | `{}` | [Runtime and setup](runtime.md#runtime) |
| `setup` | array of setup variants | Optional Extension, **Proposed** | `[]`, after the [defaults](package.md#defaults) | [Runtime and setup](runtime.md#setup) |
| `scripts` | mapping of command name to script | Optional Extension | `{}` | [Commands](commands.md) |
| `mcp` | mapping | Optional Extension | absent | [MCP](mcp.md) |
| `harness` | mapping of harness id to hints | Optional Extension, **Proposed** | `{}` | [Context and harnesses](harness.md#harness-hints) |

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

TOML, the default:

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
