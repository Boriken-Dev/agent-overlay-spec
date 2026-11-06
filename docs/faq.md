# Frequently asked questions

## Is AOS a finalized standard?

No. `0.1.0-draft` is a development draft open for review, not a 1.0 promise.

## Do I need dotagents to use AOS?

No. AOS is a package format and a set of declarations; dotagents is the reference implementation.
Any language or manager can implement it.

## Is a manifest required?

No. A directory with no manifest is a valid overlay, and its conventional files (`bin/`,
`lib/python/`, `skills/`, `rules/`, `CONTEXT.md`, `env`, `env.<ext>`, `setup.<ext>`) take effect
by default.

## `OVERLAY.md` or `overlay.cfg`?

`OVERLAY.md` when a person writes it: the manifest as front matter and the context as the body, in one
file, as a skill's `SKILL.md` is. `overlay.cfg` when a tool writes it, or for a consumer that does not
read `OVERLAY.md` yet. The fields are the same; an overlay with both is refused.

## Which formats must a reader read?

TOML and YAML. Front matter is YAML unless its first line inside the fence names another format, and
`overlay.cfg` is TOML unless its first line does, so a reader needs both; JSON is optional. The data
model is the same in every format. YAML is a [restricted subset](spec/v0/manifest.md#restricted-yaml),
which refuses what expands a document or constructs objects.

## Does an overlay carry the skills it needs?

It can, or it can [name them](spec/v0/skills.md#declaring-skills) like `requirements.txt` does packages:
by a name the consumer's catalogs resolve, or with a source and a pin. A consumer shows them before it
fetches anything, and fetching runs nothing.

## Can a manifest include another file or use variables?

No. Reading a manifest never executes, includes or expands anything, so the smallest parser in any
language reads it. `$NAME` in a string is those characters.

## Does AOS run setup scripts or install dependencies?

The format declares them; a consumer decides. Running setup is a trust decision, happens outside
the agent's sandbox in three phases (`install` on the first add, `sync` on every sync, `remove`),
and is bounded by a timeout. Dependencies in `lib/python/requirements.txt` and
`lib/node/package.json` install before setup, into an environment shared in the scope unless the
overlay names one or asks for its own.

## Where do secrets go?

Nowhere in the overlay. An env value can be a reference (a provider and a key, or a secret's name),
which the consumer resolves from its own configuration.

## Does every consumer need to support MCP?

No. MCP is an optional extension. A consumer can read and expose the files without starting a server.

## Is an overlay safe if its manifest validates?

No. Validation checks structure and types. It does not assess instructions, code, dependencies,
remote services, or trustworthiness. Pin what you install by digest, and read the weakenings a
consumer reports.

## Will my existing dotagents overlay need migration?

Rename `overlay.toml` to `overlay.cfg`, or move its fields to `OVERLAY.md`'s front matter once your
consumers read it. `bin/`, `skills/`, `CONTEXT.md`, `env.py` and `setup.py`
keep working by default, and Python modules move from `lib/` to `lib/python/`. Three more things
change: a plain `env` file is read as `dotenv`, with `${NAME}` substituted,
rather than sourced by bash, `pre.env` files mean nothing by name (a `pre-env` hook takes their
place), a root `requirements.txt` moves
to `lib/python/requirements.txt`, and a `bin/*.py` becomes a command only through `[scripts]`. See
[Compatibility](compatibility.md).

## Does an overlay run code without a manifest?

Yes, when it ships `env.<ext>` or `setup.<ext>` and the consumer has activated it: those run by
default, and every run is reported. Set `env_scripts = false` or `setup = false` in `[defaults]`
to turn them off. A `hook.<ext>` also runs by default, at the events that carry no content, but only
once the user has allowed the overlay's hooks at its digest.

## Can a hook approve a tool call?

No. A hook adds context, blocks a prompt or a compaction, and denies a tool call or sends it to the user
to approve; there is no output that approves, and a hook that tries is a failure. A consumer reads the
hook's output itself and never hands the harness the hook's own words, so a harness's own approval
vocabulary means nothing from a hook. To make a guard fail closed, give it `on_failure = "refuse"`.

## What does a hook learn?

The event, and that event's payload: the harness, the working directory and a session id, plus a
reason, a directory, a prompt's text or a tool's input for the events that have them. Never the
environment, a secret or another overlay's data. The prompt and tool events reach a hook only when
its manifest names them, and a consumer lists every hook and what it is told before installing.

## Why is `pre.env` gone, and what replaces it?

An overlay's `pre.env` ran in a tier before every overlay's environment, by its name alone. A
`pre-env` [hook](spec/v0/hooks.md) does that now, declared and allowed like any hook: its output is an
env script's, and it applies after the root variables and before any overlay's declarations.
