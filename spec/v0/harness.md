# Context and harnesses

**Optional Extension, Proposed.** An overlay can add text to an agent's initial context, and give
hints that apply to one harness (the agent program: an editor agent, a command-line agent, an
orchestrator).

## `context`

`context` lists files whose text a consumer adds to the agent's initial context, in order:

```toml
context = ["CONTEXT.md", "kb/glossary.md"]
```

Each entry is a [relative path](manifest.md#fields) to a UTF-8 text file that MUST exist. A consumer
adds the files overlay by overlay in [composition order](composition.md#deterministic-ordering),
after the base context it starts from. A leading front matter block is not context and is dropped:
after an optional byte-order mark, a first line that is `---`, up to the next line that is `---` or
`...` (line ends `LF` or `CRLF`). Without that closing line there is no front matter. A consumer MAY bound the total size by a setting, and refuses with that setting's
name when the bound is passed, rather than cutting text silently.

An operator chose to give the overlay to the agent, so the text is instruction, not fenced data; a
consumer still marks where each file came from.

> **Status:** dotagents adds the overlay root's `CONTEXT.md`, by file name, to the context it
> assembles, without its front matter, and expands `<NAME>_OVERLAY_ROOT` placeholders in output that
> is not written to a file. It does not read `context`.

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
weakening being reported. Hints are suggestions: they never override the user's or the operator's
choice, and a consumer that ignores one is still conforming.
