# Hooks

**Optional Extension, Proposed.** A hook is a program an overlay runs at a named moment of a session:
before the environment is built, when a session starts or ends, when the user sends a prompt, before a
tool runs. It can add to the agent's context, block, deny, ask or allow, and set variables where the consumer
can. **A hook may do what a harness's own hook may, allowing a tool call included, even as rewritten**:
where the user would have been asked, an allow answers as approved. Hooks combine to the tightest, so a deny beats an ask and
an ask beats an allow, and an allow never lifts the user's own refusals: their deny rules, the list of
paths a consumer protects and a mode that refuses.

```toml
[hooks]
session-start = "hooks/start.py"
pre-tool = { run = "hooks/guard.sh", match = ["execute"], timeout = 5, on_failure = "refuse" }
turn-end = false
```

> **Status:** no implementation fires hooks yet. dotagents 0.9.1 and Canoa read an overlay that has
> them as if it had none, and neither says so yet; see [Compatibility](../../compatibility.md#hooks).

A consumer that does not fire hooks MUST say so of an overlay that declares `hooks` or holds a
`hook.<ext>`, wherever it reports what it did not apply: applying the overlay without them would drop a
guard its author wrote, and nobody would know.

## Events

An event is one of these names. A consumer that claims this extension fires each **Core** event on every
harness it serves, through the harness's own hooks or by seeing the event itself, and an **Extended**
event where the harness allows it. An event it cannot fire on a harness, for an overlay that has a hook
for it, it reports as `hook-unsupported`, with the harness and the event, every time it activates the
overlay there. An event it fires for only some occurrences (only the tool calls a harness asks it about,
say) it reports as `hook-partial` the same way, since a guard there does not see every call. It never
skips one silently.

| Event | Class | When | Payload, besides `event`, `harness` and `cwd` | Outputs | `on_failure = "refuse"` stops | `match` | Fires `hook.<ext>` by default |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `pre-env` | Core | Each time the consumer builds the environment of a session, before it starts the harness. The consumer fires it itself; no harness needs to | none | An [env script's output](environment.md#env-scripts) | The session: the harness is not started | none | Yes |
| `session-start` | Core | A session opens | `session`, `reason` | `context`; `env` where the consumer can | The session, where the consumer can refuse it | reasons | Yes |
| `session-end` | Core | A session ends. Best effort: never after the consumer or the harness was killed | `session` | none | none | none | Yes |
| `prompt` | Core | A prompt from the user, before it reaches the model | `session`, `prompt` | `context`, `decision = "block"`; `env` where the consumer can | The prompt | none | No: declared only |
| `turn-end` | Core | The agent ends its turn | `session` | none | none | none | Yes |
| `cd` | Extended | The agent's working directory changes | `session`, `previous` | `env` where the consumer can | none | none | Yes |
| `pre-compact` | Extended | Before the harness compacts the context | `session`, `trigger` | `context`, as instructions to the summary; `decision = "block"` | The compaction | none | Yes |
| `pre-tool` | Extended | Before a tool call runs | `session`, `tool` | `context`, `decision = "deny"`, `"ask"` or `"allow"`, `input` with an allow; `env` for an `execute` call where the consumer can | The call, which is denied | tool kinds | No: declared only |
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
included. `hook.<ext>` receives them only for an event `hooks` names, so what it is told is in the
manifest and listed [before installing](catalog.md#before-installing). That bounds the payload, not
what a hook can reach: a hook runs with the user's access, outside the sandbox and with the network, so
it can read whatever the harness keeps on disk, a session's transcript included. A consumer says so when
it lists the hooks, and the allowance below is the decision that covers it.

## `hook.<ext>`

**The default.** One `hook.<ext>` at the overlay root, chosen by runtime as [`env.<ext>` and
`setup.<ext>` are](runtime.md#default-scripts), receives every event the table above marks as firing it
by default, unless `[defaults] hooks = false`. Another extension (`hook.cfg`) is never a hook. When an
event would run `hook.<ext>` and none present can run on this OS with the consumer's interpreters, each
present is reported as `script-not-run`, as a default script is; a declared event then fails each time
it fires, so a guard on it refuses.

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
| `sets` | array of variable names | none | The variables its `env` output may set, for an event that takes one (`session-start`, `prompt`, `cd`, `pre-tool`); none [reserved](environment.md#the-root-variable). Listed before installing |
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
`match = ["execute"]` therefore means every shell tool of every harness. **A call of kind `other` runs
every hook of its event, whatever its `match`**, so a tool that runs commands under a name the consumer
does not know (an MCP server's, say) never slips past a guard by its kind. **Such a hook may only
tighten it unless it names `other`:** a hook whose `match` is given and does not name `other` still runs,
and its deny and ask count, but its allow and any `input` it carries do not, and are reported as
`hook-not-applied` (`allow`), so a hook scoped to `read` cannot approve an MCP tool or a call of a kind
the consumer cannot place. A hook with no `match`, or one that names `other`, may allow it.

## The payload

The payload is a JSON object, the same for every hook of one event, and holds exactly the keys the
[event](#events) gives and no other:

| Key | Value |
| --- | --- |
| `event` | The event's name |
| `harness` | The [harness id](harness.md#harness-hints): a well-known one, or the consumer's own |
| `cwd` | The agent's working directory, absolute; for `cd`, the new one |
| `session` | The consumer's own id for the session, the same for each of its events, and no secret: never the harness's session id or the name of its transcript |
| `reason` | For `session-start`, one of the reasons above |
| `prompt` | For `prompt`, the text the user sent, as it will reach the model; attachments are not included |
| `previous` | For `cd`, the directory before, absolute |
| `trigger` | For `pre-compact`, `"manual"` when the user asked, `"auto"` otherwise |
| `tool` | For `pre-tool` and `post-tool`, an object: `kind`, `name` (the harness's own name for the tool) and `input` (the call's arguments as the harness gives them, a JSON value; for a later `pre-tool` hook, as an earlier hook rewrote them) |
| `status` | For `post-tool`, `"completed"` or `"failed"` |

A payload never holds the environment, a variable, a resolved secret the consumer holds, another
overlay's data, or a tool's output. What a hook learns beyond that it learns from the files and
programs it can reach, as any code of the overlay can.

## Running a hook

A hook runs as the agent's own hooks do, and gets what a [step](runtime.md#what-a-step-receives) gets in
`AOS_OVERLAY_ROOT`, `AOS_OVERLAY_NAME`, `AOS_OVERLAY_STATE` and `AOS_HOOK_EVENT`, with the session's folder
and environment in place of the overlay's, since overlays can depend on each other and a hook may expect
what another one provides:

- in the session's working directory, the `cwd` of its payload; for `pre-env`, which runs before there is a
  session, the directory the session will start in;
- with the session's environment: the base environment, every overlay's root and state variable, every
  overlay's declarations as they stand after the
  [order of application](environment.md#order-of-application), what every overlay's `pre-env` hook set,
  and what earlier hooks of the event set, in run order, where the consumer applies it. A hook of one
  overlay therefore reads a variable another overlay declared. `AOS_OVERLAY_ROOT`, `AOS_OVERLAY_NAME`
  and `AOS_OVERLAY_STATE` name the hook's own overlay, as the root and state variables of each overlay
  do for it. A `pre-env` hook runs before any declaration is applied, so it sees the base environment, the
  root and state variables, and what the `pre-env` hooks before it in composition order set, and no
  declaration; the hook of a scope's own configuration has no `AOS_OVERLAY_*`;
- **outside the agent's sandbox**, as a child process of the consumer. At its timeout the consumer stops
  that process; what it started is its own business, as with a harness's own hooks, and the consumer
  needs no process group or job object;
- the script found and its interpreter run as [Interpreters](runtime.md#interpreters) says: an absolute
  path and arguments as a list, never through a shell's parsing. A `run` whose interpreter the consumer
  lacks is a requirement a [probe](runtime.md#runtime) checks, as any script's is, so such a target is
  passed over; `not-run` is for a start that fails anyway;
- given its payload without the consumer waiting on it: a hook that exits without reading its standard
  input has not failed for that.

**A consumer answers the harness itself.** Where it wires a hook into a harness's own hooks, it runs the
hook through a program of its own, reads the output as this section defines, and gives the harness its
own answer. It never hands the harness the hook's output or exit status: a harness's own vocabulary
(Claude Code's `permissionDecision`, an exit status of 2) means nothing coming from a hook, so a hook
cannot speak to the harness past the consumer. It sets the harness's own timeout for that program above
the [event's bound](#limits), and when the program itself fails (it crashes, cannot read its
configuration, is stopped) while a hook of the event has `on_failure = "refuse"`, its answer refuses
the event.

### Output

The hook's standard output is empty, or UTF-8 text that is one JSON object, read under the manifest's
[JSON rules](manifest.md#static-reading), possibly over several lines. A `pre-env` hook's output is
instead exactly an [env script's](environment.md#env-scripts), in either of its two shapes. An object
holds only these keys, and only those the event's Outputs column gives:

| Key | Value | Means |
| --- | --- | --- |
| `context` | string | Text added to the agent's context, marked as this overlay's hook; an empty string adds nothing |
| `decision` | `"block"` for `prompt` and `pre-compact`; `"deny"`, `"ask"` or `"allow"` for `pre-tool` | The prompt or the compaction does not go ahead; the call is refused, goes to the user for approval, or is approved |
| `reason` | string of at most 1024 code points | Why, shown to the user and, where the harness passes one, to the agent. Only with `decision` |
| `input` | object | For `pre-tool`, only with `decision = "allow"`: the call's arguments, in place of `tool.input`, as the call is approved |
| `env` | mapping of variable name to string, or to `null` to unset it | Variables, each one the entry's `sets` lists, no two equal without regard to ASCII case, with the checks of an env script's output: no [reserved](environment.md#the-root-variable) name, no zero byte, and `env-sensitive` reported for a [sensitive](security.md#sensitive-variables) one that is set |

`context` and `reason` are shown to a person or an agent beside other text, so they hold no control
character other than tab, line feed and carriage return (none of U+0000–U+0008, U+000B, U+000C,
U+000E–U+001F, U+007F–U+009F) and no bidirectional override or isolate (U+202A–U+202E,
U+2066–U+2069): a terminal escape or a reordering in a reason could make an approval read as something
else. A consumer marks where each part of the context came from in a way the text cannot imitate (its own
message, block or field, never a line of text the hook could also print).

A `decision` with any other value, on any event, is an `output` failure, whatever it says: `approve`,
`continue`, an empty string, `allow` on an event that does not take it. So is a `decision` on an event that
takes none.

**An allow may carry the call as rewritten.** A harness's own hook may return the call it wants run
(Claude Code's `updatedInput`), and so may this one: `input` is the whole object that replaces `tool.input`,
and the consumer approves the call as rewritten. `input` without `decision = "allow"`, a value that is not
an object, and a harness's own spelling of it are `output` failures. A later hook of the event is given the
rewritten input as its `tool.input` (so it can still deny it, and a payload past the bound is
`payload-too-large` as any), and may rewrite it again. Only a combined allow applies a rewrite: with a deny
nothing runs, and with an ask the user is asked about the call as the harness gave it, since what they are
shown must be what they approve, and the rewrite is reported as `hook-not-applied` (`input`). What `input`
holds is the hook's own text and is bounded as any output; it is not the loader's: a variable reaches a
shell only through the loader below, which holds values and never writes them into the command's text.

The exit status says only whether the hook succeeded: 0 applies its output, any other is a failure. A
hook blocks or denies by its output, never by its exit status.

### Variables

An `env` output applies, where the consumer can apply it on the harness, to commands the agent starts
afterwards in that session (`session-start`, `prompt`, `cd`), or to the one `execute` call it was given
for (`pre-tool`). Each harness offers this differently or not at all, so it is a capability of a
consumer on a harness, never a promise of the event, and a consumer that cannot apply it reports
`hook-not-applied`. A hook sets only the variables its entry's `sets` names, so what it can change is in
the manifest; on Windows a name set under another case keeps the spelling it already has.

For a shell tool the values reach the command through a **loader**: the call is rewritten to read them
from a data file the consumer wrote, outside the root, created anew in a directory only the user can
write, and holding values, never a script, before it runs the command as given. Values are never
written into the command's text, where they would be read as shell syntax. **The loader's rewrite carries no
decision of its own**: the consumer gives the harness the rewritten call (a hook's `input` first, then the
loader's) with the answer the hooks of the event combined to, an allow only where one hook allowed and none
asked or denied, and otherwise none, so the harness's rules and prompts judge it as they would the call
without the rewrite. A harness that
rewrites a call only with an approval gets no rewrite unless the hooks allowed the call, and the
variables are reported as not applied. A consumer rewrites on a harness only where it
has checked that the harness's deny and ask rules still match the rewritten call; a rewrite may make a
call ask that a narrow allow rule would have let through, which is tighter, and is documented.

### Limits

A consumer bounds every hook by settings with defaults, and names the setting when it stops one:

| Bound | RECOMMENDED default | Past it |
| --- | --- | --- |
| The time of one run: the entry's `timeout`, or the setting when that is shorter | 60 seconds | The run is stopped, and failed (`timeout`) |
| The time of one event, every hook of it together | 120 seconds | A hook that would start after it has passed is not run, and fails (`event-timeout`) |
| The standard output it reads | 64 KiB | Failed (`too-large`); nothing past the bound is read, and nothing of it applies |
| The standard error it keeps, for the user's log only | 64 KiB | The rest is dropped; standard error never reaches the agent |
| The payload | 1 MiB | The hook is not run, and that is a failure (`payload-too-large`) |

Context a hook adds counts toward the [context bound](harness.md#context) of the session, in the bytes of
its UTF-8 text, together with what the session already holds. Each part is checked in run order: one that
would take the total past the bound is not added, whole and never cut, and is reported as
`hook-not-applied`; a later, smaller part that fits is still added. A part that reaches the bound exactly
fits.

### Failures

A run **fails** when, checked in this order, the first of these holds, which is its cause:

1. the event's bound has passed before it starts, so it is not run (`event-timeout`);
2. its interpreter cannot start it (`not-run`);
3. its payload is past the bound, so it is not run (`payload-too-large`);
4. its time runs out (`timeout`);
5. its output is past the bound (`too-large`);
6. it exits other than 0 (`exit`);
7. its output is not what this section defines (`output`: not UTF-8, not one object, another key, a
   wrong type, a decision that is not the event's own, a reserved or undeclared variable, a control
   character).

A failure is reported as `hook-failed`, with the overlay, the event and the cause, never quoting the
output, and **nothing of that run applies**. Then:

- with `on_failure = "report"`, the event goes on as if that hook had output nothing;
- with `on_failure = "refuse"`, the event is refused as a block or a deny would refuse it, the
  consumer giving the failure as the reason: a guard fails closed.

Where the consumer cannot refuse the event on that harness (most harnesses cannot stop a session from
its start), it reports `hook-not-applied` for the refusal, and goes on.

A hook that denies is a guard, and a guard is written with `on_failure = "refuse"`: several causes are in
the agent's hands (a tool input past the payload bound, an input that is slow to check), and with
`"report"` each of them lets the call through.

## One event, several hooks

Every active overlay's hook for an event runs, one at a time, in
[composition order](composition.md#deterministic-ordering), then the scope's own hooks
([below](#hooks-outside-overlays)), each given the same payload. Their results combine to the
tightest: a block or a deny beats an ask, and an ask beats an allow.

- **A block or a deny ends the event.** Later hooks do not run, its `reason` is given, and the event's
  context and variables do not apply, since the prompt, compaction or call does not happen.
- **`ask` stays `ask`** unless a later hook denies, even after an allow. The call goes to the harness's
  approval, with the reason of the first hook that asked. On a harness that cannot ask, `ask` is applied
  as `deny`, which is tighter, and reported as `hook-ask-denied`.
- **`allow` lets the event go on**, so a later hook may still ask or deny, and the call is approved only
  if none did, with the reason of the first hook that allowed. The consumer answers the harness's
  approval as approved only where it has checked that the harness's deny rules and any mode that refuses
  still win over that answer, and its own protected paths still refuse; where it cannot, the allow is
  reported as `hook-not-applied` (`allow`) and the call goes as it would without it. Over ACP the answer
  is the option that allows this once, never one that remembers the choice. On a call of kind `other`,
  only a hook with no `match` or one that names `other` may allow ([tool kinds](#tool-kinds)); another's
  allow is reported and does not count.
- **A rewritten `input`** is given to every later hook as `tool.input`, and the call runs with the last
  one only if the event is combined to an allow; the first deny or ask beats a rewrite as it beats any
  allow.
- **Context** from each hook is added in run order, each part marked with the overlay it came from.
- **Variables** apply in run order; a later hook's value replaces an earlier one's.
- **An output the consumer cannot apply on the harness is reported, never dropped** silently:
  `hook-not-applied`, with the overlay, the event and the output (`context`, `env`, `block`). The rest
  of that hook's output still applies.

**No decision leaves the call to the user; an allow approves it.** Where the consumer's own answer to the
harness is itself an approval (over ACP, the answer to `session/request_permission`), hooks that decide
nothing leave the call to the user, as it would have gone without them, and the consumer never approves a
call because no hook objected. Only a hook's `allow` approves one, and only as above.

A `pre-env` hook's output applies in the [order of application](environment.md#order-of-application),
after the root variables and before any overlay's declarations, every overlay's in composition order, as
that overlay's. Every overlay's values can read it, as they read what an earlier overlay's env script
set, so a `pre-env` hook does not compute a secret into a variable: a secret is a
[reference](environment.md#secret-references), which only the overlay granted it reads.

## Off until allowed

**An overlay's hooks and [env scripts](environment.md#env-scripts) are off until the user allows them at
its digest.** A hook is the overlay's code running at every session, outside the sandbox, told what the
user typed, and an env script is its code running each time an environment is built, so activating an
overlay is not enough for either. One allowance covers both, by one rule:

- the consumer keeps, per identity, **one** [tree digest](integrity.md#tree-digest) at which its user
  allowed that overlay's hooks and env scripts: the digest of what the user was shown. They run only
  while the overlay's digest is that one, which the consumer checks each time it activates the overlay,
  as it checks a pin. An update to any file, the manifest or a script, turns them off until the user
  allows the new digest; a changed digest is never allowed by itself, and allowing one replaces the last,
  so going back to an earlier digest needs a new yes;
- the user allows them after seeing them [listed](catalog.md#before-installing), or by the consumer's own
  configuration naming that digest, which is the user's and never a file under a project's tree. Nothing
  in an overlay, a catalog or a project's files allows them. An allowance is not a
  [pin](integrity.md#pins), and a pin is not an allowance;
- while they are off, the overlay is otherwise applied as it would be: no hook fires and no env script
  runs, declared or default, and the consumer reports `hook-not-allowed` for an overlay that has a hook
  and `env-script-not-allowed` for one that has an env script, each with the overlay, each time it
  activates it. Something that is off does not fail, so `on_failure = "refuse"` does not apply to it.
  **An overlay with a hook that has `on_failure = "refuse"` is not activated while its allowance is
  missing**, since its guard would be missing without a word: the consumer keeps the digest it last
  activated with the allowance, if it keeps one active across an update, or activates none until the user
  allows;
- while they are on, each event with a hook is reported as the [non-default setting](security.md#non-default-settings)
  `hook`, with the event as its subject, and each env script that runs as `env-script`, each time the
  overlay is activated.

The allowance covers an overlay's hooks and env scripts and nothing else of it: its setup and servers
run under the decision to activate it, as [Security](security.md#execution-and-dependencies) says.

## Hooks outside overlays

A scope's own configuration, a user's or a project's, may declare hooks in the same shape, with the same
events, payloads, outputs, limits, failures and combination. A `run` is relative to the directory that
holds that configuration, which the consumer documents. Such a hook receives `AOS_HOOK_EVENT` and none of
the `AOS_OVERLAY_*` variables, and runs, as an overlay's does, in the session's folder with the session's
environment.

- **The user's own configuration** needs no allowance: its author is the user.
- **Any other** (a project's, which arrives with a checkout anyone may have written, and which the agent
  can write to) is allowed as an overlay's is, at the tree digest of **every file** in the directory that
  holds that configuration, not only the files its hooks name: a module beside a script is loaded by it.
  The consumer runs such a hook from its own copy of those files, made from the bytes it hashed, with
  Python's bytecode written and read outside the copy and the script's own directory kept off Python's
  import path, so nothing the agent writes into the project between two events runs. It is off until
  allowed.

They run after every overlay's hook of the same event: the user's, then the project's, unless the
consumer documents another order.

## Harness hints are not a route

A [harness hint](harness.md#harness-hints) never adds a hook: a `hooks` key under `[harness.<id>]` is that
harness's own data, preserved and never applied, as any other key there. This section is the one route
by which an overlay's code runs at a session's events, and it is the visible one: declared statically,
listed before installing, off until allowed at a digest, bounded, reported, and answering the harness only through the consumer.
