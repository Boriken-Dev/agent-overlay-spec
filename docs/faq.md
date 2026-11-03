# Frequently asked questions

## Is AOS a finalized standard?

No. `0.1.0-draft` is a development draft open for review, not a 1.0 promise.

## Do I need dotagents to use AOS?

No. AOS is a package format and a set of declarations; dotagents is the reference implementation.
Any language or manager can implement it.

## Is `overlay.cfg` required?

No. A directory with no manifest is a valid overlay.

## Why `overlay.cfg` and not `overlay.toml`?

One file name, several syntaxes: a manifest is TOML unless its first line names another format
(`#!json`, `#!yaml`). Every reader must read TOML; the others are optional. The data model is the
same in every format. dotagents reads `overlay.toml` today.

## Can a manifest include another file or use variables?

No. Reading a manifest never executes, includes or expands anything, so the smallest parser in any
language reads it. `$NAME` in a string is those characters.

## Does AOS run setup scripts or install dependencies?

The format declares them; a consumer decides. Running setup is a trust decision, happens once per
overlay digest outside the agent's sandbox, and is bounded by a timeout.

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

Rename `overlay.toml` to `overlay.cfg`, and declare what dotagents infers from file names today:
`bin/` on `PATH`, `lib/` on `PYTHONPATH`, `setup.py`, `requirements.txt`, `CONTEXT.md`. See
[Compatibility](compatibility.md).
