# Context and harnesses

**Optional Extension, Proposed.** An overlay can add text to an agent's initial context, and give
hints that apply to one harness (the agent program: an editor agent, a command-line agent, an
orchestrator).

## `context`

`context` lists files whose text a consumer adds to the agent's initial context, in order:

```toml
context = ["CONTEXT.md", "kb/glossary.md"]
```

The `context` [default](package.md#defaults) comes first: the [body](manifest.md#overlaymd) of
`OVERLAY.md` when it has one, otherwise `CONTEXT.md` at the overlay root when present. The listed files
follow, and listing the default's file, as the example above does, puts it at its listed place instead.
`[defaults] context = false` turns the default off.

Each entry is a [relative path](manifest.md#fields) to a UTF-8 text file that MUST exist. A consumer
adds the files overlay by overlay in [composition order](composition.md#deterministic-ordering),
after the base context it starts from. A leading front matter block, as [the split](manifest.md#the-split)
finds it, is not context and is dropped, unread: a block that would not parse or names an unknown format
is dropped the same, since no field of a context file is applied. Without a closing fence there is no
block, and all of the file is context. A head past the split's [bound](manifest.md#bounds) is refused
with that setting's name, never cut. A consumer MUST bound the total size of the context it adds, by
another setting with a default (1 MiB is RECOMMENDED), and likewise refuses past it with the setting's
name; the body of `OVERLAY.md` counts as its file does.

An operator chose to give the overlay to the agent, so the text is instruction, not fenced data; a
consumer still marks where each file came from. An overlay can ask that its `rules` and `context` files be
[served](knowledge.md#the-hint) instead.

> **Status:** dotagents adds the overlay root's `CONTEXT.md` to the context it assembles, without its
> front matter, and expands `<NAME>_OVERLAY_ROOT` placeholders in output that is not written to a file.
> It reads neither `context` nor the body of an `OVERLAY.md`.

## Templating

**Optional Extension, Proposed.** An overlay's text can name its own files and read its own settings.
The consumer replaces `${NAME}` in the text it hands the agent, as Claude Code does for a skill's body
and Gemini CLI and Codex do for a command's or a prompt's, once, when it loads it.

**When.** A consumer replaces when it assembles the [context](#context), when it serves a skill's body and when it serves a [template](knowledge.md#templates) of the knowledge tools,
each time, from the files as they are installed. It never changes an installed file: the
[tree digest](integrity.md#tree-digest), a pin, a sync and a move of the overlay's directory stay as
they were. It does not replace when it installs or reads a file for any other purpose, and it cannot
replace in a file the agent opens itself, since a consumer does not intercept every read.

**Where.** It replaces in:

- each context file, after its front matter is dropped, and the body of `OVERLAY.md`;
- the body of a [bundled skill](skills.md#declaring-skills)'s `SKILL.md`, which is the text after its
  front matter. The front matter reaches the harness exactly as written. A skill from elsewhere is
  delivered as it was fetched, since it is another overlay's text under a digest the user accepted;
- a knowledge file that marks itself a [template](knowledge.md#templates), when `kb_read` serves it: with the
  names below and the caller's and environment's [facts](knowledge.md#the-facts) added, or as Mustache.

and nowhere else: not in `routing`, `rules`, a manifest value or an env value (which have their own
[substitution](environment.md#substitution)), and not in any file the agent opens itself. Those files
refer to the overlay by `$<NAME>_OVERLAY_ROOT`, which the [environment](environment.md#the-root-variable)
resolves. The [bound](#context) on the context counts the text the agent receives, after replacing.

**Which names.** These, and the overlay's [options](#options), are replaced; each is read from the
overlay it is written in:

| Name | Value |
| --- | --- |
| `AOS_OVERLAY_ROOT` | The absolute root the consumer exposes, as the [root variable](environment.md#the-root-variable) |
| `AOS_OVERLAY_STATE` | The overlay's [state directory](runtime.md#what-a-step-receives); no value when it has none |
| `AOS_OVERLAY_NAME` | The overlay's normalized identity |
| `AOS_OVERLAY_SCOPE` | The label the consumer gives the scope the overlay is active in, such as `user` or `project`; AOS defines none, and a consumer with no labels gives no value |
| `AOS_PROJECT_ROOT` | The absolute root of the project the session works in; no value when it has none |

A path is written as the consumer holds it, with the platform's separators. `AOS_OVERLAY_SCOPE` and
`AOS_PROJECT_ROOT` are names for text only: this section sets no variable in any environment, and the
first three keep the meaning they have in what a [step receives](runtime.md#what-a-step-receives).

**How.** Text is read from left to right. At each place:

1. `$${` is `${`, and reading goes on after it, so `$${AOS_OVERLAY_ROOT}` is the text
   `${AOS_OVERLAY_ROOT}`;
2. `${NAME}` whose `NAME` is a name above or an option that has a value is replaced by that value;
3. anything else is itself.

A name is compared exactly, in every OS: it is text, not an environment. So an unknown name, such as
`${HOME}` or another overlay's `${ENGINEERING_OVERLAY_ROOT}`, a name with no value, a sensitive option,
a name with an operator (`${AOS_OVERLAY_ROOT:-x}`), a space, another case or no closing brace, a bare
`$NAME`, `$(...)` and a backtick are **left as written**, and are no error. A `$$` not followed by `{` is
itself. A value is inserted as it is and never read again: a `${` inside it is not a placeholder, and
nothing runs and no file is read.

This is the syntax of [env substitution](environment.md#syntax) made smaller: the same `${NAME}` and the
same escape, but no operator and no undefined-name error, and `$$` alone is itself. The text is prose
for an agent, which often holds shell lines and prices, and one name a consumer cannot give must not
refuse a whole context file. A consumer MAY report the placeholders it left.

### Options

An overlay declares the settings its text reads in `options`, a mapping from a name to a table:

```toml
[options.depth]
type = "string"
default = "normal"
description = "How thorough a review is."

[options.service_token]
type = "string"
sensitive = true
```

A name is a [variable name](environment.md#env) that is not [reserved](environment.md#the-root-variable),
so no option takes the place of `AOS_OVERLAY_ROOT`. A table has these keys and no other:

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `type` | `string`, `integer` or `boolean` | required | The type of the value |
| `default` | a value of that type | none | The value when the user configured none |
| `sensitive` | boolean | `false` | The value is a secret: it is never put in context |
| `description` | string | `""` | What the setting is for, which a consumer shows when it asks the user for a value |

An option's value is the user's. It is kept in the consumer's own configuration, under the overlay's
identity, never in the overlay, so a manifest stays static data, and how a consumer asks for it is its
own. A configured value that is not of the declared type is refused (`invalid-option`), never
converted; a boolean is no integer. A configured value for a name the overlay does not declare is
ignored. The value an option takes is the configured one, else its default, else none. It is written
as text: a string as it is, an integer in decimal, a boolean `true` or `false`.

**A sensitive option is never put in context.** Whatever its value, a sensitive option's placeholder is
left as written in context and in a skill body, since text that reaches the agent can be seen, kept and
sent on. A sensitive option has no `default`, for a manifest is public: a validator refuses one that has
it. This section gives such a value no other way to the agent; a secret a process needs is a
[secret reference](environment.md#secret-references). A value that is not sensitive reaches the agent, so
a consumer says so when it asks for it.

> **Status:** the coqui-aos readers (Rust, Python, Dart, TypeScript) implement templating and pass the
> templating vectors. dotagents templates overlay context files; it serves no skill bodies, so it has
> none to template.

## Harness hints

`harness` maps a **harness id** to hints that apply only to that harness:

```toml
[harness.claude-code]
context = ["kb/claude-notes.md"]
effort = "high"

[harness.codex]
skills = false
```

A harness id matches `[a-z0-9][a-z0-9-]*`. Well-known ids, for interchange:

| Id | Harness |
| --- | --- |
| `claude-code` | Claude Code |
| `codex` | OpenAI Codex CLI |
| `gemini-cli` | Gemini CLI |
| `copilot` | GitHub Copilot agents |
| `opencode` | OpenCode |

Recognised keys:

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `context` | array of relative paths | `[]` | Files added to the initial context, after the overlay's `context`, for this harness only |
| `skills` | boolean | `true` | Whether the overlay's skills are delivered natively to this harness; when `false` they are delivered by routing line |
| `model` | string | none | A suggested model, used only where nothing else chose one |
| `effort` | string | none | A suggested reasoning effort, likewise |

Other keys in a harness table are that harness's own data. A consumer preserves them for display and
MUST NOT apply them in this edition: a key that grants a permission, changes approval or sandboxing,
or adds hooks, servers, environment or commands would let an overlay loosen the harness without any
non-default setting being reported. Hints are suggestions: they never override the user's or the operator's
choice, and a consumer that ignores one is still conforming.

An overlay's code runs at a session's events by one route, [Hooks](hooks.md): the `hooks` field and
`hook.<ext>`, listed before installing, off until the user allows them at the overlay's digest, bounded,
reported, and answering the harness only through the consumer. A `hooks` key in a harness table is that harness's own data like any
other, and is never applied.
