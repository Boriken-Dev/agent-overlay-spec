# Implementations

Any application can add AOS support in its existing language and architecture. Python, Rust, JavaScript, Go, and other languages are equally suitable.

## Reference implementation

[dotagents](https://github.com/jose-pr/dotagents) is the reference implementation. Its overlay resolver, composition manager, and MCP gateway behavior are useful compatibility evidence. AOS does not depend on it.

## Potential consumers

These are possible integration targets, not claims of existing AOS support:

- Claude Code integrations
- OpenAI Codex integrations
- GitHub Copilot integrations
- Gemini CLI integrations
- Agent orchestration platforms
- IDE extensions
- Standalone configuration managers

No listed application is claimed to support AOS unless that support has been independently verified and documented.

## Implementation levels

| Level | Minimum useful support |
|---|---|
| Read-only consumer | Enumerate an overlay directory and expose files safely; treat the manifest as optional. |
| Manifest parser | Parse TOML, retain unknown top-level keys, validate recognized types, and report errors. |
| Overlay resolver | Define source protocols, normalized identity, dependency behavior, deterministic order, and provenance. |
| Full manager | Define installation, recomposition, scope precedence, collisions, removal, extension support, and execution policy. |

See [Conformance](spec/v0/conformance.md) for the obligations associated with each claim.
