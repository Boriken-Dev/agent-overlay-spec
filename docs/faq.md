# Frequently asked questions

## Is AOS a finalized standard?

No. The current `0.1.0-draft` is a development document open for review. Do not treat it as a stable 1.0 promise.

## Do I need dotagents to use AOS?

No. AOS is a package format and set of declarations. dotagents is the reference implementation. Any language or manager can implement the format.

## Is `overlay.toml` required?

No. A manifest-free directory is a valid package.

## Does AOS run setup scripts or install dependencies?

No. Those behaviors are optional manager extensions. Review executable content and explicitly decide whether it should run.

## Does every AOS consumer need to support MCP?

No. MCP is an optional extension. A consumer can read and expose the files without starting a server.

## Is an AOS overlay safe if its manifest validates?

No. Validation checks structure and types. It does not assess instructions, code, dependencies, remote services, or trustworthiness.

## Will my existing dotagents overlay need migration?

The draft is based on the existing format and introduces no required manifest version. See [Compatibility](compatibility.md) for behavior and unresolved decisions. A future breaking specification version will need an explicit migration policy.
