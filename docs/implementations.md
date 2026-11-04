# Implementations

Any application can add AOS support in its own language and architecture. Every declaration is
static data, so a reader needs a TOML parser and nothing that executes; Python, Rust, Dart, Go and
JavaScript are equally suitable.

## Reference implementation

[dotagents](https://github.com/jose-pr/dotagents) is the reference implementation. Its resolver,
composition and MCP gateway are the behaviour this specification was written from. AOS does not
depend on it, and [Compatibility](compatibility.md) lists what it does not read yet.

## Potential consumers

These are possible integration targets, not claims of existing AOS support:

- Claude Code integrations
- OpenAI Codex integrations
- GitHub Copilot integrations
- Gemini CLI integrations
- Agent orchestration platforms
- IDE extensions
- Standalone configuration managers

No listed application is claimed to support AOS unless that support has been independently verified
and documented.

## Where to start

| Class | Minimum useful support |
|---|---|
| Read-only consumer | List an overlay's files and expose them; treat the manifest as optional. |
| Manifest reader | Read `overlay.cfg` (format line, TOML, the data model, static reading), keep unknown top-level keys, report errors. |
| Environment | Build an environment from the declarations, resolve secret references, report weakenings. |
| Integrity | Compute the tree digest; refuse a pin mismatch. |
| Resolver | Parse sources, normalize identities, resolve `requires`, order overlays. |
| Manager | Install, compose, remove; document scopes, collisions and execution policy. |
| Store | Read catalogs, list and search their entries by label, show `about` and icons; show what an overlay would do from its own manifest before installing it. |

Each class has [vectors](spec/v0/conformance.md#vectors) to test against. See
[Conformance](spec/v0/conformance.md) for the obligations of each claim.
