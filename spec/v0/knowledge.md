# Knowledge served through MCP

**Core, Proposed**, and **Optional Extension, Proposed** for search. Every consumer that runs an agent
session with overlays active serves those overlays' knowledge to the agent over
[MCP](https://modelcontextprotocol.io/specification/) by relative path: two tools every such consumer
offers, `kb_list` and `kb_read`, and a third, `kb_search`, that it MAY offer. A consumer with no session
(an installer, a store, a validator) has nothing to serve.

An overlay's knowledge is the text an agent should consult when it needs it: conventions, procedures,
definitions, references. Putting all of it in the context costs every turn, and an agent given a path can
read what it needs. The tools make the overlay's own layout the interface: a path an author wrote in a
routing line, a rule or another file is the path the agent reads.

> **Status:** no implementation serves knowledge yet. Canoa serves the three tools from an index of its own
> and is the model for the result shapes; the coqui-aos readers implement the handlers and the vectors.

AOS fixes what the tools take and return, what they refuse and how, and the order of every list. It does not
fix a transport, how a consumer starts its server, how a passage is ranked, or which model answers a search.

## What is served

The **knowledge** of an overlay is the set of its files that:

- lie under `kb/`, `flows/`, `references/`, `rules/` or `context/`, or are the root `CONTEXT.md`, or are named
  by the manifest's `rules` or `context` field (wherever they lie); and
- are [members of its tree](integrity.md#tree-digest): regular files, no excluded name, no `.pyc`; and
- are not a manifest (`OVERLAY.md`, `overlay.cfg`). The body of `OVERLAY.md` is context, and is not a file
  the tools serve; an overlay whose knowledge is to be served keeps it in `kb/`.

The set does not depend on [`defaults`](package.md#turning-a-default-off). Of these files, one is **served**
only if its name holds no character that [served text](#served-text) writes out, its size is at most
`max_file_bytes`, and its bytes are UTF-8; otherwise it is **skipped**, with the reason `name`, `too-large` or
`not-text`. A link, a directory and a special file are no files of the set.

Every other file of the overlay (programs, env files, hooks, setup, the manifest) is not knowledge, and
`kb_read` answers `not-found` for it, as for a file that is not there, so a call cannot learn what an overlay
holds beyond its knowledge.

## The tools

A consumer offers its tools to the agent as one MCP server, in the consumer's own way (standard input and
output, an in-process or a local HTTP connection); its name is the consumer's. The tools are named as below,
whatever prefix a gateway adds to them. Each tool's input is the JSON Schema the vectors give; a server
MAY add a `description` to a tool and to each property, and nothing else. It lists `kb_list`, `kb_read` and,
when it declares at least one [mode](#search), `kb_search`, in that order.

| Tool | Arguments | Answers |
| --- | --- | --- |
| `kb_list` | `overlay`? | Each active overlay's served files, in order, and what is skipped |
| `kb_read` | `path`, `from`?, `to`?, `overlay`?, `context`? | Lines of one file |
| `kb_search` | `query`, `top`?, `overlay`?, `mode`?, `path`? | The passages that best answer a query |

**Arguments.** The arguments are an object with only the keys the tool defines. A `null` is the argument absent.
`overlay` and `path` are text. `from`, `to` and `top` are integers (`true`, text and a number with a fraction,
such as `2.5`, are not), `from` and `to` from 1 to 9007199254740991. Whether `2.0` is an integer is the
consumer's: a JSON reader with one number type cannot tell it from `2`, and a consumer may accept it or refuse
it; no vector asks. A failure of any of this is `invalid-arguments`. An `overlay` names an active overlay as an
[identity](package.md#names-and-paths) is compared, normalized; one the session has not is `unknown-overlay`.
Every result names an overlay by the identity the consumer holds it under, **as it holds it and not
normalized**, whatever spelling the call used.

**Results.** A result is a JSON object with the keys this section names and no other, returned as the call's
`structuredContent` and, as the same JSON text, in one `text` block of `content`, with `isError` false. An
error is `{"error": {"class", "message"}}` returned the same way with `isError` true. The class is one of the
[classes below](#errors), and the message is text for a person, never parsed.

### `kb_list`

```json
{"overlays": [{"overlay": "team-docs", "served": true,
               "files": [{"path": "kb/intro.md", "lines": 6, "bytes": 32},
                         {"path": "kb/review.md", "template": "mustache", "rendered": true}],
               "skipped": [{"path": "kb/big.md", "reason": "too-large"}]}],
 "engines": ["envsubst", "mustache"], "search": {"modes": ["words", "meaning"]}}
```

- `overlays` holds each active overlay, or the one `overlay` names, in [composition order](composition.md#deterministic-ordering).
- `served` says whether the consumer has left this overlay's `rules` and `context` files out of the context
  [because they are served](#the-hint).
- `files` holds the served files in the order of their paths as UTF-8 bytes, compared as unsigned bytes (the
  order of the [digest](integrity.md#tree-digest): not UTF-16 order, not case folded). Each has `lines` and
  `bytes`: the [lines](#lines) and the size in bytes of [the served text](#formats-and-templates), which is not
  the stored file's when the file has `${…}` or an include (an include's lines are in its includer's count). A file
  whose first line names an engine other than markdown and raw also has `template`, the name, and `rendered`,
  whether this server renders that engine.
- `skipped` holds the skipped files in the same order, each with its `reason`: `name`, `too-large` or `not-text`
  as above, or `render` for a file whose served text cannot be made without a `context` (a cycle of includes, an
  option of the wrong type, a Mustache body refused: `kb_read` says which). A path in it is written out as
  [served text](#served-text) is.
- `engines` are the [template engines](#formats-and-templates) this server renders with, in the order `envsubst`, `mustache`
  and then any others of its own by their names' bytes; possibly none.
- `search` is present only when `kb_search` is offered, and `modes` are its declared modes in the order
  `words`, `meaning`, `llm`.

### `kb_read`

```json
{"overlay": "team-docs", "path": "kb/intro.md", "from_line": 3, "to_line": 5, "total_lines": 6,
 "truncated": false, "text": "Hello\n\n## Setup"}
```

`template`, the engine the file names, and `rendered`, whether this server rendered it, are also present when
the file [names an engine](#formats-and-templates) other than markdown and raw.

**Which file.** `path` is a [relative path](manifest.md#fields) under the overlay's root, compared exactly
(case and Unicode form included) and never normalized, and with none of the characters served text writes out.
Anything else (an empty path, an absolute one, a `..` or `.` component, a backslash, a drive, an empty
component, a trailing separator, a control character, an excluded name) is `invalid-path`. With no `overlay`,
every active overlay is asked; exactly one that has the file answers; more than one is `ambiguous`; with an
`overlay`, only that one is asked.

**What is refused.** A path none of whose files is served is answered, when an overlay says so, in this order of
priority: `link` when the path, or a directory on the way to it, is a symbolic link, a junction or another
reparse point, whatever it points at (it is never followed); `not-text` and `too-large` for a skipped file; and
otherwise `not-found`, which also answers a directory, a special file, a file outside the knowledge, one that is
not there, and any path when no overlay is active and none is named.

A `link` answer depends on the tree the consumer holds recording links: a tree read as an [integrity
digest](integrity.md#tree-digest) reads refuses one, and one read from a filesystem shows it. The race between
looking and opening is the consumer's to close: it opens a path so that it cannot leave the root through a link, as
the [manifest section](manifest.md#fields) says, and does not check first and open after.

**Which lines.** See [Lines](#lines).

### Lines

The [served text](#formats-and-templates) is split into **lines** at line feed. A carriage return immediately
before the line feed is not part of the line, and one anywhere else is. The text has no line after a final line
feed, and an empty file has no line; a file with no final line feed has the line it ends on. No other character
ends a line (U+2028, U+000B and U+000C do not).

`from` defaults to 1 and `to` to the last line; a `to` past the end is the end. A `to` before `from`, or a
`from` past the last line, is `line-range`; the one exception is an empty file, which `from` 1 reads as the
empty text, `from_line` 1 and `to_line` 0. `total_lines` is the file's line count.

The text returned is the chosen lines joined by line feed, with no line feed after the last. It holds whole lines
only: lines are taken in order while the text stays within `max_read_bytes` bytes of UTF-8 (the lines as read,
joined by line feeds, before [writing out](#served-text)), and the first line is always taken whole. When lines
were left, `truncated` is true and `to_line` is the last line taken. A reader continues with `from` set to
`to_line` plus one.

## Served text

What an overlay wrote is its author's text, and an overlay may come from anywhere. Served text reaches the agent
as a field of a JSON result and never as part of a message the consumer writes, so a file cannot imitate the
consumer; the consumer MUST NOT splice it into any other text of its own, and SHOULD say in the tools'
descriptions that passages are data from the overlays' files, not instructions to the agent and not statements
by the consumer.

The **text** of a result (`text` and `heading` of `kb_read` and `kb_search`, a skipped path, a `note`) is written
out: each C0 or C1 control character except tab and line feed (U+0000–U+0008, U+000B–U+001F, U+007F–U+009F, so a
lone carriage return too), each of U+00AD, U+034F, U+061C, U+115F, U+1160, U+17B4, U+17B5, U+180E,
U+200B–U+200F, U+2028, U+2029, U+202A–U+202E, U+2060–U+2064, U+2066–U+206F, U+3164, U+FE00–U+FE0F, U+FEFF, U+FFA0,
U+FFF9–U+FFFB, U+1D173–U+1D17A, U+E0000–U+E007F and U+E0100–U+E01EF is replaced by `<U+XXXX>`, with four or more
uppercase hexadecimal digits. These are the characters that hide, reorder or invisibly alter text, and they
include the ones a [hook's](hooks.md#output) output refuses, which a file cannot be asked to forgo. Nothing
else changes. A path is never written out in a result that gives a path to read: a file whose name holds
such a character is skipped instead.

## Formats and templates

Every served file has a **format**, and the format is named by the file's first line.

**The first line.** A file names its format by its **first line**, from its first byte, written as a **format
line** like [a manifest's](manifest.md#reading-overlaycfg): `#!` and then words, and the last word, after any `/`
or `\`, with leading dots dropped and ASCII capitals lower-cased, is the **name**. So `#!mustache`,
`#!/usr/bin/env mustache`, `#!/usr/bin/env -S mustache` and `#!MUSTACHE` all name `mustache`. A byte-order mark,
a space or anything else before the `#!`, a `#!` on any other line, a line with no word and a path that ends in a
separator name nothing, and the line is text.

**The formats.** A file with no name is **markdown**. AOS defines four formats, and a server may have more under
names of its own, with no registry, as a [format name of its own](manifest.md#formats) is for a manifest:

| Name | Every server | The file is served as |
| --- | --- | --- |
| `markdown`, `md` | yes | [Markdown](#markdown): `${NAME}` replaced and `@path` included; the default |
| `raw` | yes | [Raw](#raw): as it is |
| `envsubst` | no | [envsubst](#envsubst) over the whole text |
| `mustache` | no | [Mustache](#mustache) over the whole text |

A server says in `kb_list` which of the last two, and which of its own, it renders with. A first line that names
`markdown`, `md` or `raw` is understood by every server and is **not served**: it says how to read the file, and
carries no content, so the text a reader gets begins at the next line. A first line that names an engine this
server renders is not served either. One that names an engine it does not render is [kept](#an-engine-this-server-does-not-render).

**The text served.** What `kb_read` serves for a file, called with no `context`, is **the served text**. Its
lines are what `kb_read` counts and numbers, what `kb_list` reports as `lines` and `bytes`, and what `kb_search`
indexes and returns passages of, so an included file's text is found through the file that includes it and a
line number means the same everywhere. A `context` can only change what an [engine](#the-facts) reads from it.
A file whose served text cannot be made without a `context`, such as one whose includes form a cycle, is listed
as skipped with the reason `render` and is not searched, and `kb_read` says why.

### Markdown

The text after the first line (the whole file when it names nothing) is read from left to right, one line at a
time, and two things in it are replaced: **`${NAME}`** and **`@path`**. Nothing else is changed: the file's own
front matter, headings, links, `{{…}}` text and every other character stay, and a file with neither is served as
it is.

- **`${NAME}`** is replaced as [Templating](harness.md#templating) says, with [the names](#the-facts) of the
  facts: `${AOS_OVERLAY_NAME}`, an option's name, `${AOS_CALLER_ROLE}`, `${AOS_ENV_<NAME>}`, `${AOS_ARG_<key>}`
  and the rest. A name with no value, and one that is none of these, stays as written, and `$${` is the literal
  `${`; so `$${AOS_OVERLAY_NAME}` is the text `${AOS_OVERLAY_NAME}`, and `$$` and `$x` are themselves. This is
  done **everywhere, code included**: the names are a closed set, so a shell line's `${HOME}` is untouched, and
  an author who writes a path in a code span (`` `${AOS_OVERLAY_ROOT}/kb/a.md` ``) means it replaced. An option of
  the wrong type is `invalid-option`, but only where a `${…}` that would read it is met.
- **`@path`** includes a file of the same overlay, in the manner of the `@path` imports of Claude Code's
  `CLAUDE.md` and of `AGENTS.md` readers. The rules below decide what is an include; all else is text.

**What is an include.** An `@` is the start of one only if all of these hold:

1. it is **not in code**: not in a fenced block, and not in a code span (below);
2. it is the first character of its line, or follows a space, a tab, a carriage return, a vertical tab or a form
   feed, so `a@b.md`, `(@b.md)`, `@@b.md` and `\@b.md` are not includes, and an address is never one;
3. the **name** after it, up to the next white space, with any of `. , ; : ! ? ) ] } ' "` taken off its end, is
   not empty, does not start with `/` or `~`, holds no `\`, does not start with a drive letter and `:`, and has
   no empty component; so a handle such as `@john` is a candidate and is settled by the next rule;
4. it names a **served file of the same overlay**, found from the folder of the file that holds the `@`. A `.`
   component stays where it is, and a `..` goes up one folder and may rise only as far as the root: one that would
   leave it names nothing. A file that is another overlay's, a link, a file outside the knowledge, a program, one
   that is skipped, one for an engine this server does not render and one that is not there are no served file,
   and neither is a path through a link. Names are compared exactly, in case and in Unicode form.

What is not an include is **text, left as written, and no error**, because a word that names no file is prose: a
handle, an address, a path in a sentence. An include that is one is different: the author meant it, and it can fail
(below), which is an error.

**What is included.** The included file's **own format** applies, so an author's choice of format is the same
whether a file is read or included:

- a markdown file is read as this section says, on its own, with its first line (if it names markdown) not
  served, and **its front matter dropped** if it has one (a block that closes, the empty one too; front matter
  describes the file, not its text), and its own `@path` are resolved from **its** folder;
- a raw file is included as it is, after its first line, front matter and all;
- a file of `envsubst` or `mustache` is rendered with the same facts and the same `context`, and includes
  nothing further (neither engine has includes).

Why the file's own format and not markdown for all: a file that says it is a template is rendered when read
directly, and would otherwise reach the agent with its placeholders when included.

The included text replaces the `@` and the name; **one line end is dropped from its end** (CR LF, or LF), so a
line that holds only `@path` becomes the included lines, the includer's line end after them; the text after the
name, on the same line, follows. Text that is included is **never read again** for names or includes, by the file
that includes it or any other.

**Depth and cycles.** Includes nest at most `max_include_depth` hops (default 5, as Claude Code's); one more is
`include-error`, and with the depth 0 an include is an error. A file that includes a file that is being read (itself
or one above it in the chain) is `include-error`. The same file included twice, side by side or by two routes, is no
cycle. The text added is counted with the served text toward `max_rendered_bytes`.

**Code.** A **fenced block** opens at a line of up to three spaces and then three or more backticks or three or
more tildes, and closes at a line of up to three spaces, then as many of the same character or more, and nothing but
spaces and tabs; one not closed runs to the end of the file; its fence lines are in it. A **code span** is a run of
backticks and the text to the next run of exactly as many backticks, on the same line; a run with no such closing run
is literal backticks. An indented block is **not** code here. An `@` in code is never an include, so a decorator
(`@property`), a command (`@echo off`) and an example of an include are safe; `${NAME}` is replaced in code as
above. To write an `@path` that would include, put it in a code span or write `\@path`.

### Raw

A file whose first line names `raw` is served as the bytes after that line, with **nothing replaced**: no
`${…}`, no `@path`, no `{{…}}`, its front matter kept, a `$${` and a CR LF as they are. It is how an author turns
the markdown engine off. The `#!raw` line itself is not served, as a markdown line is not: the server understood
it, it carries no content, and keeping it would leave a line in every raw file that no reader asked for; the
author who needs the bytes of the file, first line included, keeps the line out of the knowledge by naming the
file as a program in `bin/`, where it is not knowledge. A raw file may be included by a markdown one, as it is.

### An engine this server renders

An `envsubst` or `mustache` file, or one of a server's own, that this server renders, is served as its **rendered
text**: the engine applied to all the text after the first line (its line end with it), the first line left out.
The file's own front matter, if it has any, is part of that text and is rendered with it. A template is rendered
when `kb_read` serves it, with the facts of that call, never when it is installed, so the
[tree digest](integrity.md#tree-digest) is unchanged. The text is at most `max_rendered_bytes` bytes, or `too-large`
refuses it. A server that has no engine for a name, whether AOS or the server has never heard of it, or it is not
installed there (a Python without the engine's package), is in the next case.

### An engine this server does not render

This is no error. The file is served as it is, **its first line kept**, and with a front matter that carries what
the renderer would have used, so that the agent reading it can do the substitution itself. The text served is, in
order: the first line as written, the block below, and the rest of the file exactly as it was; no `${…}` is
replaced and no `@path` included.

```text
#!jinja
---
aos_template_context: {"engine": "jinja", "overlay": {"name": "team-docs", …}, "caller": {"role": "reviewer"}, …}
---
Hello {{ name }}
```

The block is the lines `---`, `aos_template_context: ` and one flow mapping on the same line, and `---`, each
ended by a line feed, and the first line gets one when it has none. It is a front matter of its own, placed
before whatever front matter the file has, which stays as the author wrote it: the two never share a mapping, so
nothing the author wrote is overwritten or reordered, and a key of the same name in the author's front matter
is the author's. The mapping holds `engine` (the name) and then, each only when it holds something, `overlay`,
`project`, `caller`, `env`, `options` and `context`: the same data, with the same limits, that
[Mustache](#mustache) reads under those roots, so a sensitive option or variable is never in it. It is written as
JSON is, on one line with `, ` and `: ` between, the keys of every mapping below the first level in UTF-8 byte
order, integers in decimal, booleans as `true` and `false`, and a string in double quotes in which only `"`, `\`
and U+0000–U+001F are escaped, those last as `\u00xx` in lower case. The whole text is [written out](#served-text)
after, as any is. The text is at most `max_rendered_bytes` bytes. A configured option of the wrong type is
`invalid-option`, as when rendering. A markdown file that includes such a file leaves the `@path` as written.

### An engine of a server's own

A server that renders an engine of its own gives the template the facts and nothing else: it MUST NOT let the file
read a file, include or import another, run code or call a program, reach the network, read an environment variable
the user did not open or any object of the server, and it bounds time and output (`max_rendered_bytes`). What the
engine is allowed is this section's, and not the engine's: how the server keeps it so (a sandboxed environment, a
process with nothing, a subset) is its own. An engine that cannot be held to this (one whose includes or attribute
access reach the host) is not listed in `engines`, and its files are served as above. The reason is that a template's
text is a third party's and is rendered on the person's machine because an agent asked, so an engine that can read a
file or run code would let an overlay do that on request; it is the reason this edition defines no partial and no
lambda for Mustache, and no include in `envsubst`.

### The facts

What a file reads when it is served. Markdown reads the names of the first column, as `envsubst` does.

| `envsubst` name | `mustache` path | Value |
| --- | --- | --- |
| `AOS_OVERLAY_ROOT` | `overlay.root` | As in [Templating](harness.md#templating) |
| `AOS_OVERLAY_STATE` | `overlay.state` | |
| `AOS_OVERLAY_NAME` | `overlay.name` | |
| `AOS_OVERLAY_SCOPE` | `overlay.scope` | |
| `AOS_PROJECT_ROOT` | `project.root` | |
| an option's name | `options.<name>` | The overlay's [options](harness.md#options), a sensitive one never |
| `AOS_CALLER_ROLE` | `caller.role` | The role the consumer has the agent in, as its own label; no value when none |
| `AOS_CALLER_PROFILE` | `caller.profile` | The profile in use, likewise |
| `AOS_ENV_<NAME>` | `env.<NAME>` | The consumer's environment variable `NAME`, for the names the user allowed templates to read |
| `AOS_ARG_<key>` | `context.<key>` | What the call's `context` gave under `key` |

A fact with no value is absent. The names `AOS_CALLER_*`, `AOS_ENV_*` and `AOS_ARG_*` are names for text only,
as the five `AOS_` names already are: nothing sets a variable in any environment.

- **The environment is the user's to open.** A consumer reads no environment variable into a template unless
  the user named it, in the consumer's own configuration, as one templates may read; none by default. A
  [sensitive variable](security.md#sensitive-variables) is never given, though the user named it, and a
  consumer MAY refuse more. A variable's value is text; one that is not set is absent. The names compare
  exactly, in every OS.
- **The context is the caller's.** `context` is an object whose keys are names (`[A-Za-z_][A-Za-z0-9_]*`) at
  every depth and whose values are strings, integers (at most 9007199254740991 in absolute value; a number with a fraction is not one), booleans,
  lists and objects, nested at most `max_context_depth` levels (the object itself is one), with strings and
  keys together at most `max_context_bytes` bytes of UTF-8. Anything else, a `null` and a float included, is
  `invalid-arguments`. It is given by the agent, so it is as trusted as the agent is and no more: it can change
  only the text returned to the agent, and it sets nothing. A `context` for a raw or markdown file with nothing to read it is ignored.
- **Option values** are the user's, typed, as in [Options](harness.md#options): a configured value, or a default,
  of the wrong type is `invalid-option`, whichever engine reads it. A sensitive option is not read at all.

### `envsubst`

The text after the first line is read as [Templating](harness.md#templating) reads it, with the names above: `${NAME}` is replaced when
`NAME` has a value, `$${` is `${`, and anything else, an unknown name such as `${HOME}`, a name with no value,
another case, an operator, a bare `$NAME` and a Mustache tag, is left as written and is no error. A value is
inserted as it is and never read again. Of the context, only the keys whose value is a string, an integer or a
boolean are names (as text, `true` or `false` for a boolean).

### `mustache`

The text after the first line is read as a small subset of [Mustache](https://mustache.github.io/mustache.5.html), over the data of
the table's second column: the roots `overlay`, `project`, `caller`, `env`, `options` and `context`.

- **Tags.** `{{name}}`, `{{{name}}}` and `{{&name}}` insert a value; `{{#name}}…{{/name}}` is a section,
  `{{^name}}…{{/name}}` an inverted one, `{{! text }}` a comment. White space inside a tag, around its name, is
  ignored. A tag is on one line. A name is `.` or dotted identifiers (`[A-Za-z_][A-Za-z0-9_]*`); a section's name
  is not `.`.
- **Not defined, and refused** (`template-error`): partials (`{{> name}}`), a change of delimiters
  (`{{=…=}}`), inheritance and blocks, a lambda or any other tag or sigil, a name that is not a name, a tag not
  closed on its line, a section not closed or closed by another name, a section deeper than `max_template_depth`.
  Nothing a template says reads a file, runs code or calls a function: values are data, and a value that is a
  function does not exist. There is no way to write a literal `{{`; text that needs one is served from a markdown or raw file.
- **Values.** A name is looked up in the contexts of the sections around it, innermost first, the roots last: its
  first part, then each later part must be a key of what that found. A name that is not found is missing and
  renders as nothing. `.` is the innermost context.
- **Inserting.** A string is inserted as it is, an integer in decimal, a boolean as `true` or `false`; an object
  or a list inserts nothing. There is **no escaping**, in any of the three forms: the output is text for an agent,
  not markup.
- **Sections.** A section is skipped when its name is missing, `null`, `false` or an empty list. Otherwise a list
  renders its body once for each item, each as the innermost context; any other value renders it once with that
  value as the innermost context. An inverted section renders its body when a section on it would be skipped. An
  empty string and 0 are not false.
- **Standalone lines.** A line that holds only a section tag (opening, inverted or closing) or a comment, and
  white space (spaces and tabs) around it, is removed whole with its line end (`\n` or `\r\n`); a line with any
  other tag or text, or with two tags, is not changed.
- **Text.** Everything else is copied exactly, `${…}` and a single `{` included, and a value is never read as
  a template.

**Where this departs from [Mustache's own specification](https://github.com/mustache/spec)**, and why. A library
that follows the specification can meet each by a check before it renders or an option, but not by default.

- *No escaping.* The specification escapes `{{x}}`; the set of characters it escapes, past `& < > "`, differs
  between libraries (the apostrophe, `/`, the backtick, `=`), so two consumers would serve different bytes. The
  output is text for an agent, not markup.
- *Stringification and truthiness are fixed*, since a library's own is its language's: a boolean is `true` or
  `false` (not `True`), an empty string and 0 are not false (a list's emptiness, `false` and a missing name are), and an
  object or a list inserts nothing (libraries print their own text for it).
- *Refused, not supported:* partials, delimiter changes, inheritance and lambdas (they read files, or run code),
  a name outside `[A-Za-z_][A-Za-z0-9_]*` and dots, and sections nested past `max_template_depth`. The
  specification defines the first and the delimiters; lambdas and inheritance are its optional modules.
- *A tag, a comment included, is on one line*; the specification lets a comment span lines.
- *`{{& x}}`* takes white space after the `&`, as the specification does.

### Refusals

`invalid-option` for an option of the wrong type, configured or by default, in any engine,
`template-error` for a Mustache template the subset refuses, `too-large` for an output past `max_rendered_bytes`,
and `invalid-arguments` for a context that is not usable.

## Search

**Optional Extension, Proposed.** A server that can find passages offers `kb_search`. It **declares its modes**,
and a mode is how a query is matched:

| Mode | Matches |
| --- | --- |
| `words` | the words used, with no model |
| `meaning` | what is meant, with vectors from an embeddings provider |
| `llm` | what a language model the person chose picks or orders from candidates another mode found |

A server declares at least one mode and no other name: it offers the tool only if it does. It SHOULD declare
`words`, which needs nothing outside the consumer. How a mode ranks, indexes, chunks, caches or which model it
calls is the server's own, and AOS defines none; a server says in `kb_list` which modes it declares, and in each
answer which one answered.

**The call.** `query` is text of 1 to `max_query_characters` characters (code points) with something other than
space, tab, line feed, vertical tab, form feed and carriage return in it. `top` is the most passages per overlay,
from 1 to `max_top`, 5 when absent. `overlay` limits the overlays asked. `path` limits the passages to one file or
to the files under one folder (`kb` holds `kb/a.md` and not `kbx/a.md`): a [relative path](manifest.md#fields) as
`kb_read` takes it, otherwise `invalid-path`, and no file at it is no error, only no passage. `mode` is `auto`,
which is the default, or a declared mode; any other is `invalid-arguments`. A named mode is never answered by
another: where it is not available the entry says `mode-unavailable`. `auto` is answered by a declared mode the
server chooses, which it MAY change from call to call (a server whose embeddings are down answers by words, and
may say why in a `note`); it chooses `llm` only if the person has asked for that.

**The answer.**

```json
{"results": [{"overlay": "team-docs", "mode": "words", "note": "…",
              "passages": [{"path": "kb/intro.md", "heading": "Intro > Setup",
                            "from_line": 5, "to_line": 6, "score": 1.5, "text": "## Setup\nrun it"}]}]}
```

- `results` holds one entry for each overlay asked, in the order `kb_list` gives them. An entry is
  `{"overlay", "mode", "passages"}` with an optional `note` (text, written out), or `{"overlay", "error"}` where
  that overlay cannot answer now, which does not fail the call: its `error` has a `class`, `unavailable` (an
  index is still being made, or failed) or `mode-unavailable`, and a `message`.
- `mode` is the mode that answered, one the server declares, and for a named mode that one.
- A passage has `path` (a served file of the overlay), `heading`, `from_line` and `to_line` (inclusive, from
  1, not past the file's last line, the first not after the second), `score` and `text`. The `text` lies within the
  lines from `from_line` to `to_line` of [the served text](#formats-and-templates), as `kb_read` serves it with no
  `context`, written out the same way; it is those lines whole,
  except that a line longer than the server's passage size may be cut, so that a passage is part of a line.
  `heading` is the path of the Markdown headings above the passage, outermost first, joined by ` > `, empty where
  there is none; it is written out.
- `score` is a finite number, higher meaning a better match. It is comparable only within one entry, and means
  what the mode makes it mean; it has no scale, and a client does not compare it across modes, overlays or calls.
- **Order.** Within an entry, passages are ordered by `score`, highest first; then by `path`, as UTF-8 bytes; then
  by `from_line`; then by `to_line`, each ascending. Passages equal in all four keep the order they have in the
  file. At most `top` are given.

A passage names where to read more: `kb_read` with its `path`, and lines around `from_line` and `to_line`.

## The hint

An overlay can say that its knowledge is meant to be served rather than put in the agent's context:

```toml
[knowledge]
serve = true
```

`serve` is a boolean, `false` when absent, and the table holds no other key. It is a **hint**, like a
[harness hint](harness.md#harness-hints): the user's choice, in the consumer's own configuration, wins over it
either way, and a consumer that ignores it still conforms. When the overlay is **served** (the hint, or the user,
says so), a consumer MAY leave out of the context it assembles the files that overlay's `rules` and `context`
list, defaults included, which the tools serve instead; `routing` lines, which point the agent at them, and the
body of `OVERLAY.md`, which no tool serves, stay. `kb_list` says `served` for the overlay.

A consumer that cannot give the agent MCP tools (a harness that takes no server) says so, never serves, and
applies the context as if there were no hint: the hint never takes text away from an agent that cannot ask for
it. A hint never forces a consumer without MCP to do anything.

## Settings

Every limit is a setting of the consumer with a default, and no floor: a person may raise or lower any, or **lift** it so that it bounds nothing. A lifted `max_query_characters` leaves `maxLength` out of the schema of `query`, and a lifted `max_top` leaves `maximum` out of `top`'s; the least stays (a query of one character, a `top` of 1).

| Setting | Default | Bounds |
| --- | --- | --- |
| `max_file_bytes` | 1 MiB | the size of a served file |
| `max_read_bytes` | 64 KiB | the text of one `kb_read` |
| `max_rendered_bytes` | 1 MiB | a template as served, rendered or with its context |
| `max_query_characters` | 1000 | a query |
| `max_top` | 100 | `top` |
| `max_context_bytes` | 16 KiB | strings and keys of a `context` |
| `max_context_depth` | 8 | a `context`'s nesting |
| `max_template_depth` | 32 | Mustache sections one in another |
| `max_include_depth` | 5 | `@path` includes one in another |

## Errors

| Class | When |
| --- | --- |
| `invalid-arguments` | the arguments are not as the tool's schema and the rules above say, a context included |
| `invalid-path` | a `path` is not a relative path, or holds a character served text writes out |
| `unknown-overlay` | an `overlay` the session does not have |
| `ambiguous` | more than one overlay has the path, and none was named |
| `not-found` | no file of the knowledge is at the path, or no overlay is active |
| `link` | the path, or a directory on the way, is a link |
| `not-text` | the file's bytes are not UTF-8 |
| `too-large` | the file is past `max_file_bytes`, or a rendered text past `max_rendered_bytes` |
| `invalid-option` | a configured option, or a default, is not of its declared type |
| `template-error` | a Mustache body the subset refuses |
| `include-error` | an `@path` that names a served file and cannot be included: a cycle, or nesting past `max_include_depth` |
| `line-range` | `to` before `from`, or `from` past the last line |
| `unavailable`, `mode-unavailable` | in a search entry: no answer now, or not by that mode |

A `kb_read` that more than one overlay could answer with an error answers with the first class in the order
`link`, `not-text`, `too-large`, `not-found`.

## Security

Every file read is a file of an overlay the user chose, but not one the user read: its text may say anything,
so the served text is data and is written out as above. A path never leaves the root, and a link is refused
rather than followed, since a link in an overlay is a way to read a file the overlay does not hold. An `@path`
names a served file of the same overlay or nothing, resolved from the including file's folder and no higher than
the root, so a file cannot pull in another overlay's text, a file outside the knowledge or the person's own files;
nesting and cycles are bounded. A template
reaches the user's environment only through names the user opened, and never through a
[sensitive](security.md#sensitive-variables) one; it cannot read files or run code under either engine, which is
why this edition defines no partial and no lambda, and no engine of a server's own may either. The environment's values and the call's context go to the
agent that asked and to no one else. A consumer that gives an agent a role or profile tells it, in the
template's facts, nothing more than the label.
