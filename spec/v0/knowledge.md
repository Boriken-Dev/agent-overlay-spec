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
`not-text`. A file whose front matter names a template engine no edition defines is skipped with the reason
`template`. A link, a directory and a special file are no files of the set.

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
`overlay` and `path` are text. `from`, `to` and `top` are integers (`2.0` and `true` are not), `from` and `to`
from 1 to 9007199254740991. A failure of any of this is `invalid-arguments`. An `overlay` names an active
overlay as an [identity](package.md#names-and-paths) is compared, normalized; one the session has not is
`unknown-overlay`. A server answers an overlay by the identity the consumer holds it under.

**Results.** A result is a JSON object with the keys this section names and no other, returned as the call's
`structuredContent` and, as the same JSON text, in one `text` block of `content`, with `isError` false. An
error is `{"error": {"class", "message"}}` returned the same way with `isError` true. The class is one of the
[classes below](#errors), and the message is text for a person, never parsed.

### `kb_list`

```json
{"overlays": [{"overlay": "team-docs", "served": true,
               "files": [{"path": "kb/intro.md", "lines": 6, "bytes": 32},
                         {"path": "kb/review.md", "template": "mustache"}],
               "skipped": [{"path": "kb/big.md", "reason": "too-large"}]}],
 "search": {"modes": ["words", "meaning"]}}
```

- `overlays` holds each active overlay, or the one `overlay` names, in [composition order](composition.md#deterministic-ordering).
- `served` says whether the consumer has left this overlay's `rules` and `context` files out of the context
  [because they are served](#the-hint).
- `files` holds the served files in the order of their paths as UTF-8 bytes, compared as unsigned bytes (the
  order of the [digest](integrity.md#tree-digest): not UTF-16 order, not case folded). A plain file has `lines`
  and `bytes`, its [lines](#lines) and its size as stored. A [template](#templates) has `template`, its engine,
  and neither, since what it serves depends on the call.
- `skipped` holds the skipped files in the same order, each with its `reason`; a path in it is written out as
  [served text](#served-text) is.
- `search` is present only when `kb_search` is offered, and `modes` are its declared modes in the order
  `words`, `meaning`, `llm`.

### `kb_read`

```json
{"overlay": "team-docs", "path": "kb/intro.md", "from_line": 3, "to_line": 5, "total_lines": 6,
 "truncated": false, "text": "Hello\n\n## Setup"}
```

`template` is also present, holding the engine, when the file was rendered.

**Which file.** `path` is a [relative path](manifest.md#fields) under the overlay's root, compared exactly
(case and Unicode form included) and never normalized, and with none of the characters served text writes out.
Anything else (an empty path, an absolute one, a `..` or `.` component, a backslash, a drive, an empty
component, a trailing separator, a control character, an excluded name) is `invalid-path`. With no `overlay`,
every active overlay is asked; exactly one that has the file answers; more than one is `ambiguous`; with an
`overlay`, only that one is asked.

**What is refused.** A path none of whose files is served is answered, when an overlay says so, in this order of
priority: `link` when the path, or a directory on the way to it, is a symbolic link, a junction or another
reparse point, whatever it points at (it is never followed); `not-text`, `too-large` and `unknown-template`
for a skipped file; and otherwise `not-found`, which also answers a directory, a special file, a file outside
the knowledge and one that is not there. A consumer opens a path so that it cannot leave the root through a
link, as the [manifest section](manifest.md#fields) says, and does not check first and open after.

**Which lines.** See [Lines](#lines).

### Lines

A file's text, or a rendered template's, is split into **lines** at line feed. A carriage return immediately
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

## Templates

A file is served as it is, byte for byte, unless its front matter marks it as a template. The front matter is
read as [the split](manifest.md#the-split) and the [front matter reading](manifest.md#overlaymd) say, with their
bounds. A file is a **template** only when the block closes, reads as a mapping, and that mapping has the key
`template`; a file with no front matter, a block that does not close, parse or map, a head past the bound or a
mapping with no `template` key is a plain file, whatever its text, and keeps its front matter in what is served.

The value of `template` names the engine, exactly and in this case: `envsubst` or `mustache`. Any other value
(another name, another case, an empty string, a boolean, a list) makes the file skipped with the reason
`template`, and a read of it is `unknown-template`; it is never guessed, and never served as plain text, since
its placeholders would reach the agent as written.

A template is served as its **rendered body**: the text after its front matter, with the engine applied. Its
lines are counted in the rendered text. The rendered text is at most `max_rendered_bytes` bytes, or `too-large`
refuses it. A template is rendered when `kb_read` serves it, with the facts of that call, never when it is
installed, so the [tree digest](integrity.md#tree-digest) is unchanged. `kb_search` never returns a passage of a
template, and a consumer MAY leave it out of any index, since what it serves changes with the call.

### The facts

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
  every depth and whose values are strings, integers (at most 9007199254740991 in absolute value), booleans,
  lists and objects, nested at most `max_context_depth` levels (the object itself is one), with strings and
  keys together at most `max_context_bytes` bytes of UTF-8. Anything else, a `null` and a float included, is
  `invalid-arguments`. It is given by the agent, so it is as trusted as the agent is and no more: it can change
  only the text returned to the agent, and it sets nothing. A `context` for a plain file is ignored.
- **Option values** are the user's, typed, as in [Options](harness.md#options): a configured value of the wrong
  type is `invalid-option`.

### `envsubst`

The body is read as [Templating](harness.md#templating) reads it, with the names above: `${NAME}` is replaced when
`NAME` has a value, `$${` is `${`, and anything else, an unknown name such as `${HOME}`, a name with no value,
another case, an operator, a bare `$NAME` and a Mustache tag, is left as written and is no error. A value is
inserted as it is and never read again. Of the context, only the keys whose value is a string, an integer or a
boolean are names (as text, `true` or `false` for a boolean).

### `mustache`

The body is read as a small subset of [Mustache](https://mustache.github.io/mustache.5.html), over the data of
the table's second column: the roots `overlay`, `project`, `caller`, `env`, `options` and `context`.

- **Tags.** `{{name}}`, `{{{name}}}` and `{{&name}}` insert a value; `{{#name}}…{{/name}}` is a section,
  `{{^name}}…{{/name}}` an inverted one, `{{! text }}` a comment. White space inside a tag, around its name, is
  ignored. A tag is on one line. A name is `.` or dotted identifiers (`[A-Za-z_][A-Za-z0-9_]*`); a section's name
  is not `.`.
- **Not defined, and refused** (`template-error`): partials (`{{> name}}`), a change of delimiters
  (`{{=…=}}`), inheritance and blocks, a lambda or any other tag or sigil, a name that is not a name, a tag not
  closed on its line, a section not closed or closed by another name, a section deeper than `max_template_depth`.
  Nothing a template says reads a file, runs code or calls a function: values are data, and a value that is a
  function does not exist. There is no way to write a literal `{{`; text that needs one is served from a plain file.
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

### Refusals

`unknown-template` for an engine that is not defined, `invalid-option` for a configured option of the wrong type,
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
- A passage has `path` (a served, plain file of the overlay), `heading`, `from_line` and `to_line` (inclusive, from
  1, not past the file's last line, the first not after the second), `score` and `text`. The `text` lies within the
  lines from `from_line` to `to_line` as `kb_read` serves them, written out the same way; it is those lines whole,
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

Every limit is a setting of the consumer with a default, and no floor: a person may raise or lower any.

| Setting | Default | Bounds |
| --- | --- | --- |
| `max_file_bytes` | 1 MiB | the size of a served file |
| `max_read_bytes` | 64 KiB | the text of one `kb_read` |
| `max_rendered_bytes` | 1 MiB | a rendered template |
| `max_query_characters` | 1000 | a query |
| `max_top` | 100 | `top` |
| `max_context_bytes` | 16 KiB | strings and keys of a `context` |
| `max_context_depth` | 8 | a `context`'s nesting |
| `max_template_depth` | 32 | Mustache sections one in another |

Reading a file's front matter is bounded as [the split's](manifest.md#bounds) bytes are.

## Errors

| Class | When |
| --- | --- |
| `invalid-arguments` | the arguments are not as the tool's schema and the rules above say, a context included |
| `invalid-path` | a `path` is not a relative path, or holds a character served text writes out |
| `unknown-overlay` | an `overlay` the session does not have |
| `ambiguous` | more than one overlay has the path, and none was named |
| `not-found` | no file of the knowledge is at the path |
| `link` | the path, or a directory on the way, is a link |
| `not-text` | the file's bytes are not UTF-8 |
| `too-large` | the file is past `max_file_bytes`, or a rendered text past `max_rendered_bytes` |
| `unknown-template` | the front matter names an engine no edition defines |
| `invalid-option` | a configured option is not of its declared type |
| `template-error` | a Mustache body the subset refuses |
| `line-range` | `to` before `from`, or `from` past the last line |
| `unavailable`, `mode-unavailable` | in a search entry: no answer now, or not by that mode |

A `kb_read` that more than one overlay could answer with an error answers with the first class in the order
`link`, `not-text`, `too-large`, `unknown-template`, `not-found`.

## Security

Every file read is a file of an overlay the user chose, but not one the user read: its text may say anything,
so the served text is data and is written out as above. A path never leaves the root, and a link is refused
rather than followed, since a link in an overlay is a way to read a file the overlay does not hold. A template
reaches the user's environment only through names the user opened, and never through a
[sensitive](security.md#sensitive-variables) one; it cannot read files or run code under either engine, which is
why this edition defines no partial and no lambda. The environment's values and the call's context go to the
agent that asked and to no one else. A consumer that gives an agent a role or profile tells it, in the
template's facts, nothing more than the label.
