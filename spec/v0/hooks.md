# Hooks

**Optional Extension, Proposed.** A hook is a program an overlay runs at a named moment of a session:
before the environment is built, when a session starts or ends, when the user sends a prompt, before a
tool runs. It can add to the agent's context, block or deny, and set variables where the consumer can.
**A hook tightens and never grants**: nothing it outputs approves a tool, a prompt or a session that
would not have gone ahead without it.

```toml
[hooks]
session-start = "hooks/start.py"
pre-tool = { run = "hooks/guard.sh", match = ["execute"], timeout = 5, on_failure = "refuse" }
turn-end = false
```

> **Status:** no implementation fires hooks yet. dotagents 0.9.1 and Canoa read an overlay that has
> them as if it had none; see [Compatibility](../../compatibility.md#hooks).

A consumer that does not fire hooks MUST say so of an overlay that declares `hooks` or holds a
`hook.<ext>`, wherever it reports what it did not apply: applying the overlay without them would drop a
guard its author wrote, and nobody would know.

## Events

An event is one of these names. A consumer that claims this extension fires each **Core** event on every
harness it serves, through the harness's own hooks or by seeing the event itself, and an **Extended**
event where the harness allows it. An event it cannot fire on a harness, for an overlay that has a hook
for it, it reports as `hook-unsupported`, with the harness and the event, every time it activates the
overlay there. It never skips one silently.

| Event | Class | When | Payload, besides `event`, `harness` and `cwd` | Outputs | `on_failure = "refuse"` stops | `match` | Fires `hook.<ext>` by default |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `pre-env` | Core | Each time the consumer builds the environment of a session, before it starts the harness. The consumer fires it itself; no harness needs to | none | An [env script's output](environment.md#env-scripts) | The session: the harness is not started | none | Yes |
| `session-start` | Core | A session opens | `session`, `reason` | `context`; `env` where the consumer can | The session, where the consumer can refuse it | reasons | Yes |
| `session-end` | Core | A session ends. Best effort: never after the consumer or the harness was killed | `session` | none | none | none | Yes |
| `prompt` | Core | A prompt from the user, before it reaches the model | `session`, `prompt` | `context`, `decision = "block"`; `env` where the consumer can | The prompt | none | No: declared only |
| `turn-end` | Core | The agent ends its turn | `session` | none | none | none | Yes |
| `cd` | Extended | The agent's working directory changes | `session`, `previous` | `env` where the consumer can | none | none | Yes |
| `pre-compact` | Extended | Before the harness compacts the context | `session`, `trigger` | `context`, as instructions to the summary; `decision = "block"` | The compaction | none | Yes |
| `pre-tool` | Extended | Before a tool call runs | `session`, `tool` | `context`, `decision = "deny"` or `"ask"`; `env` for an `execute` call where the consumer can | The call, which is denied | tool kinds | No: declared only |
| `post-tool` | Extended | After a tool call ends | `session`, `tool`, `status` | `context` | none | tool kinds | No: declared only |

`session-start` gives a `reason`:

| `reason` | The session |
| --- | --- |
| `new` | Was started empty |
| `resume` | Continues an earlier session, in this process or another |
| `clear` | Was emptied by the user, in the same process |
| `compact` | Continues after its context was compacted |
| `fork` | Was copied from another session |

Harnesses tell these apart differently, and a consumer that sees the event itself knows only its own
operations. A consumer documents, per harness, each reason it never sends and each it sends in place of
another (`new` for a `fork` it cannot tell from one, say).

**Events that carry content fire only when declared.** `prompt` carries the user's words and `pre-tool`
and `post-tool` a tool's input, which can hold anything the user or the agent wrote, a credential
included. `hook.<ext>` receives them only for an event `hooks` names, so what it learns is in the
manifest and listed [before installing](catalog.md#before-installing).

## `hook.<ext>`

**The default.** One `hook.<ext>` at the overlay root, chosen by runtime as [`env.<ext>` and
`setup.<ext>` are](runtime.md#default-scripts), receives every event the table above marks as firing it
by default, unless `[defaults] hooks = false`. Another extension (`hook.cfg`) is never a hook, and a
present `hook.<ext>` that cannot run on this OS with the consumer's interpreters is reported as
`script-not-run`, as a default script is.

**What it is told.** The event is the hook's first argument and the variable `AOS_HOOK_EVENT`; the
payload is one JSON object on its standard input, which it may read or not. A hook MUST exit 0 with no
output for an event it does not know, so a later edition can add one:

```python
#!/usr/bin/env python3
import json
import sys

event = sys.argv[1] if len(sys.argv) > 1 else ""
payload = json.load(sys.stdin)
if event == "session-start" and payload["reason"] == "new":
    print(json.dumps({"context": "Run the test suite before you report a task done."}))
# Any other event, including one this script does not know: no output, exit 0.
```

`setup.<ext>` stays separate. Setup prepares an overlay when it is installed, synced or removed, outside
any session; a hook runs within a session. Neither runs the other, and a hook is told no phase.

## `hooks`

`hooks` maps an event to what runs for it:

| Value | Runs |
| --- | --- |
| a script path | That script, its interpreter following from its extension as a [`scripts`](commands.md#scripts) path's does |
| a table | `hook.<ext>`, chosen by runtime, or the script its `run` names, with the table's settings |
| `false` | Nothing for this event, `hook.<ext>` included |

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `run` | script path | `hook.<ext>`, chosen by runtime | The script. A [relative path](manifest.md#fields) in the characters a `scripts` path takes, ending in `.py`, `.js`, `.mjs`, `.cjs`, `.ps1`, `.bash` or `.sh` |
| `match` | array of strings | every one | For `session-start`, the [reasons](#events) it runs for; for `pre-tool` and `post-tool`, the [tool kinds](#tool-kinds). No other event takes it |
| `timeout` | integer seconds, 1 to 3600 | `30` | Stopped, and failed, after this, or sooner by the consumer's [setting](#limits) |
| `on_failure` | `"report"` or `"refuse"` | `"report"` | What a [failure](#failures) does. `"refuse"` only for an event the table says it stops |

Any other key, and any other event name, is an error, so a misspelt `pre_tool` or `on-failure` fails
instead of leaving a guard that never runs. One entry per event: an overlay that needs two programs at one
event runs the second from the first.

**Declarations take an event's place.** The default gives `hook.<ext>` one entry per event it fires by
default. An event `hooks` names replaces that event's entry, so nothing runs twice, and the other events
keep theirs; `[defaults] hooks = false` drops every default entry and keeps the declared ones. A table
with no `run` still runs `hook.<ext>`, which is how a content event is given to it:

```toml
# hook.py gets its default events, and the shell calls too, failing closed.
[hooks]
pre-tool = { match = ["execute"], on_failure = "refuse" }
```

The same in [`OVERLAY.md`](manifest.md#overlaymd), whose front matter holds the same fields:

```markdown
---
hooks:
  pre-tool:
    match: [execute]
    on_failure: refuse
---
```

A `run` that names a file not in the overlay is a validation error (`missing-file`), and one that names a
manifest is refused (`manifest-file`), as for any field.

### Tool kinds

A tool kind is one of the kinds the [Agent Client Protocol](https://agentclientprotocol.com/protocol/tool-calls)
gives a tool call: `read`, `edit`, `delete`, `move`, `search`, `execute`, `think`, `fetch`,
`switch_mode`, `other`. A consumer gives each of its harness's tools one kind as ACP does, and documents
how: a shell is `execute`, a file write `edit`, a web request `fetch`; a tool it cannot place is `other`.
`match = ["execute"]` therefore means every shell tool of every harness.

## The payload

The payload is a JSON object, the same for every hook of one event, and holds exactly the keys the
[event](#events) gives and no other:

| Key | Value |
| --- | --- |
| `event` | The event's name |
| `harness` | The [harness id](harness.md#harness-hints): a well-known one, or the consumer's own |
| `cwd` | The agent's working directory, absolute; for `cd`, the new one |
| `session` | The consumer's id for the session, the same for each of its events, and no secret |
| `reason` | For `session-start`, one of the reasons above |
| `prompt` | For `prompt`, the text the user sent, as it will reach the model; attachments are not included |
| `previous` | For `cd`, the directory before, absolute |
| `trigger` | For `pre-compact`, `"manual"` when the user asked, `"auto"` otherwise |
| `tool` | For `pre-tool` and `post-tool`, an object: `kind`, `name` (the harness's own name for the tool) and `input` (the call's arguments as the harness gives them, a JSON value) |
| `status` | For `post-tool`, `"completed"` or `"failed"` |

A payload never holds the environment, a variable, a resolved secret the consumer holds, another
overlay's data, or a tool's output. What a hook learns beyond that it learns from the files and
programs it can reach, as any code of the overlay can.

## Running a hook

A hook runs as a [step](runtime.md#what-a-step-receives) does, with `AOS_HOOK_EVENT` besides:

- with the overlay root as its working directory, and the environment of that overlay's own processes
  ([which environment](environment.md#order-of-application)): never the session's, so a value another
  overlay was granted never reaches it. A `pre-env` hook runs before any declaration is applied, with the
  base environment and the root and state variables;
- **outside the agent's sandbox**, in its own process group (a job object on Windows), every process it
  started ended when it ends or is stopped;
- the script found and its interpreter run as [Interpreters](runtime.md#interpreters) says: an absolute
  path and arguments as a list, never through a shell's parsing.

**A consumer answers the harness itself.** Where it wires a hook into a harness's own hooks, it runs the
hook through a program of its own, reads the output as this section defines, and gives the harness its
own answer. It never hands the harness the hook's output or exit status: a harness's own vocabulary
(Claude Code's `permissionDecision`, an exit status of 2) means nothing coming from a hook, so a hook
cannot speak to the harness past the consumer.

### Output

The hook's standard output is empty, or UTF-8 text that is one JSON object, read under the manifest's
[JSON rules](manifest.md#static-reading), possibly over several lines. A `pre-env` hook's output is
instead exactly an [env script's](environment.md#env-scripts), in either of its two shapes. An object
holds only these keys, and only those the event's Outputs column gives:

| Key | Value | Means |
| --- | --- | --- |
| `context` | string | Text added to the agent's context, marked as this overlay's hook; an empty string adds nothing |
| `decision` | `"block"` for `prompt` and `pre-compact`; `"deny"` or `"ask"` for `pre-tool` | The prompt or the compaction does not go ahead; the call is refused, or goes to the user for approval |
| `reason` | string | Why, shown to the user and, where the harness passes one, to the agent. Only with `decision` |
| `env` | mapping of variable name to string, or to `null` to unset it | Variables, with the checks of an env script's output: no [reserved](environment.md#the-root-variable) name, no zero byte, and `env-sensitive` reported for a [sensitive](security.md#sensitive-variables) one |

A `decision` with any other value, on any event, is refused as an attempt to grant (`grant`), whatever it
says: `allow`, `approve`, `continue`, an empty string. So is a `decision` on an event that takes none.
There is no output that approves.

The exit status says only whether the hook succeeded: 0 applies its output, any other is a failure. A
hook blocks or denies by its output, never by its exit status.

### Variables

An `env` output applies, where the consumer can apply it on the harness, to commands the agent starts
afterwards in that session (`session-start`, `prompt`, `cd`), or to the one `execute` call it was given
for (`pre-tool`). Each harness offers this differently or not at all, so it is a capability of a
consumer on a harness, never a promise of the event, and a consumer that cannot apply it reports
`hook-not-applied`.

For a shell tool the values reach the command through a **loader**: the call is rewritten to read them
from a file the consumer wrote, outside the root, before it runs the command as given. Values are never
written into the command's text, where they would be read as shell syntax. **A rewrite carries no
decision**: the consumer gives the harness the rewritten call with no approval of its own, so the
harness's rules and prompts judge it. A harness that rewrites a call only with an approval gets no
rewrite, and the variables are reported as not applied. A consumer rewrites on a harness only where it
has checked that the harness's deny and ask rules still match the rewritten call; a rewrite may make a
call ask that a narrow allow rule would have let through, which is tighter, and is documented.

### Limits

A consumer bounds every hook by settings with defaults, and names the setting when it stops one:

| Bound | RECOMMENDED default | Past it |
| --- | --- | --- |
| The time of one run: the entry's `timeout`, or the setting when that is shorter | 60 seconds | The run is stopped, and failed (`timeout`) |
| The standard output it reads | 64 KiB | Failed (`too-large`); nothing past the bound is read, and nothing of it applies |
| The standard error it keeps, for the user's log only | 64 KiB | The rest is dropped; standard error never reaches the agent |
| The payload | 1 MiB | The hook is not run, and that is a failure (`payload-too-large`) |

Context a hook adds counts toward the [context bound](harness.md#context) of the session.

### Failures

A run **fails** when, checked in this order, the first of these holds, which is its cause:

1. its interpreter cannot start it (`not-run`);
2. its payload is past the bound, so it is not run (`payload-too-large`);
3. its time runs out (`timeout`);
4. its output is past the bound (`too-large`);
5. it exits other than 0 (`exit`);
6. its output tries to grant (`grant`);
7. its output is not what this section defines (`output`: not UTF-8, not one object, another key, a
   wrong type, a reserved variable).

A failure is reported as `hook-failed`, with the overlay, the event and the cause, never quoting the
output, and **nothing of that run applies**. Then:

- with `on_failure = "report"`, the event goes on as if that hook had output nothing;
- with `on_failure = "refuse"`, the event is refused as a block or a deny would refuse it, the
  consumer giving the failure as the reason: a guard fails closed.

Where the consumer cannot refuse the event on that harness (most harnesses cannot stop a session from
its start), it reports `hook-not-applied` for the refusal, and goes on.

## One event, several hooks

Every active overlay's hook for an event runs, one at a time, in
[composition order](composition.md#deterministic-ordering), then the scope's own hooks
([below](#hooks-outside-overlays)), each given the same payload. Their results combine to the
tightest:

- **A block or a deny ends the event.** Later hooks do not run, its `reason` is given, and the event's
  context and variables do not apply, since the prompt, compaction or call does not happen.
- **`ask` stays `ask`** unless a later hook denies. The call goes to the harness's approval, with the
  reasons. On a harness that cannot ask, `ask` is applied as `deny`, which is tighter, and reported as
  `hook-ask-denied`.
- **Context** from each hook is added in run order, each part marked with the overlay it came from.
- **Variables** apply in run order; a later hook's value replaces an earlier one's.
- **An output the consumer cannot apply on the harness is reported, never dropped** silently:
  `hook-not-applied`, with the overlay, the event and the output (`context`, `env`, `block`). The rest
  of that hook's output still applies.

A `pre-env` hook's output applies in the [order of application](environment.md#order-of-application),
after the root variables and before any overlay's declarations, every overlay's in composition order, as
that overlay's: so every overlay's values can read it, and a process of another overlay does not receive
it.

## Off until allowed

**An overlay's hooks are off until the user allows them at its digest.** A hook is the overlay's code
running at every session, outside the sandbox, told what the user typed, so activating an overlay is not
enough:

- the consumer keeps, per identity, the [tree digest](integrity.md#tree-digest) at which its user allowed
  that overlay's hooks. They fire only while the overlay's digest is that one. An update to any file, the
  manifest or a script, turns them off until the user allows the new digest, and a changed digest is
  never allowed by itself;
- the user allows them after seeing them [listed](catalog.md#before-installing), or by the consumer's own
  configuration naming that digest. Nothing in an overlay, a catalog or a project's files allows them.
  An allowance is not a [pin](integrity.md#pins), and a pin is not an allowance;
- while they are off, the overlay is otherwise applied as it would be, and the consumer reports
  `hook-not-allowed` with the overlay, each time it activates it. A hook that is off does not fail, so
  `on_failure = "refuse"` does not apply to it;
- while they are on, each event with a hook is reported as the [weakening](security.md#weakenings)
  `hook`, with the event as its subject, each time the overlay is activated.

## Hooks outside overlays

A scope's own configuration, a user's or a project's, may declare hooks in the same shape, with the same
events, payloads, outputs, limits, failures and combination, and the same rule that a hook never grants.
A `run` is relative to the directory that holds that configuration, which the consumer documents. Such a
hook receives `AOS_HOOK_EVENT` and none of the `AOS_OVERLAY_*` variables.

- **The user's own configuration** needs no allowance: its author is the user.
- **Any other** (a project's, which arrives with a checkout anyone may have written) is allowed as an
  overlay's is, at a tree digest over the files that declare and run its hooks, and is off until then.

They run after every overlay's hook of the same event: the user's, then the project's, unless the
consumer documents another order.

## Harness hints are not a route

A [harness hint](harness.md#harness-hints) never adds a hook: a `hooks` key under `[harness.<id>]` is that
harness's own data, preserved and never applied, as any other key there. This section is the one route
by which an overlay's code runs at a session's events, and it is the visible one: declared statically,
listed before installing, off until allowed at a digest, bounded, reported, and unable to grant.
