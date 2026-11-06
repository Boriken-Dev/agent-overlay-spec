# Implementations

Any application can add AOS support in its own language and architecture. Every declaration is
static data, so a reader needs a TOML parser, a YAML parser whose events it can read before anything is
applied, a few lines to split front matter, and nothing that executes; Python, Rust, Dart, Go and
JavaScript are equally suitable. A YAML loader that applies aliases first is not enough: Dart's
`package:yaml`, for one, hands back the expanded document, and a reader there needs a parser that
refuses first; that package's own parser also slows with the square of the nesting, so a reader built on
it scans for nesting past the depth bound before it parses.

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
| Manifest reader | Read `OVERLAY.md` (the split, front matter) and `overlay.cfg` (format line, TOML, restricted YAML, the data model, static reading), keep unknown top-level keys, report errors. |
| Environment | Build an environment from the declarations, resolve secret references, report weakenings. |
| Integrity | Compute the tree digest; refuse a pin mismatch. |
| Resolver | Parse sources, normalize identities, resolve `requires`, order overlays; resolve skill names through catalogs, reporting what is missing or ambiguous. |
| Manager | Install, compose, remove; document scopes, collisions and execution policy; fetch and check an overlay's skills after the user accepts them, or report each as not delivered. |
| Store | Read catalogs, list and search their entries by label, show `about` and icons; show what an overlay would do from its own manifest before installing it. |
| Hooks | Read `hooks` and `hook.<ext>`, list them before installing, keep them off until allowed at the digest; fire `pre-env` yourself and the session events from what you see or the harness's own hooks; read each output yourself, refuse any that grants, and report every event and output you cannot apply. |

Each class has [vectors](spec/v0/conformance.md#vectors) to test against. See
[Conformance](spec/v0/conformance.md) for the obligations of each claim.
