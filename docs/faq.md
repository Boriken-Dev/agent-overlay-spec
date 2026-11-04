# Frequently asked questions

## Is AOS a finalized standard?

No. `0.1.0-draft` is a development draft open for review, not a 1.0 promise.

## Do I need dotagents to use AOS?

No. AOS is a package format and a set of declarations; dotagents is the reference implementation.
Any language or manager can implement it.

## Is `overlay.cfg` required?

No. A directory with no manifest is a valid overlay, and its conventional files (`bin/`,
`lib/python/`, `skills/`, `rules/`, `CONTEXT.md`, `env`, `env.<ext>`, `setup.<ext>`) take effect
by default.

## Why `overlay.cfg` and not `overlay.toml`?

One file name, several syntaxes: a manifest is TOML unless its first line names another format
(`#!json`, `#!yaml`). Every reader must read TOML; the others are optional. The data model is the
same in every format. dotagents reads `overlay.toml` today.

## Can a manifest include another file or use variables?

No. Reading a manifest never executes, includes or expands anything, so the smallest parser in any
language reads it. `$NAME` in a string is those characters.

## Does AOS run setup scripts or install dependencies?

The format declares them; a consumer decides. Running setup is a trust decision, happens outside
the agent's sandbox in three phases (`install` once, `sync` per new digest, `remove`), and is
bounded by a timeout.

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

Rename `overlay.toml` to `overlay.cfg`. `bin/`, `skills/`, `CONTEXT.md`, `env.py` and `setup.py`
keep working by default, and Python modules move from `lib/` to `lib/python/`. Three more things
change: a plain `env` file is read as `dotenv`, with `${NAME}` substituted,
rather than sourced by bash, `pre.env` files and `requirements.txt` mean nothing by name (declare
dependencies in `runtime`), and a `bin/*.py` becomes a command only through `[scripts]`. See
[Compatibility](compatibility.md).

## Does an overlay run code without a manifest?

Yes, when it ships `env.<ext>` or `setup.<ext>` and the consumer has activated it: those run by
default, and every run is reported. Set `env_scripts = false` or `setup = false` in `[defaults]`
to turn them off.
