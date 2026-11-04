# Agent Overlay Specification (AOS)

**Draft edition 0.1.0-draft**

This is the normative entry point. The specification is in [`spec/v0/`](spec/v0/index.md); what the
reference implementation does today is in [Compatibility](docs/compatibility.md).

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHOULD**, **SHOULD NOT**, and **MAY** are to be
interpreted as described by [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) and
[RFC 8174](https://www.rfc-editor.org/rfc/rfc8174) when, and only when, they appear in all capitals.

AOS defines a package format and static declarations. It does not prescribe an installer, a target
configuration, a runtime, a programming language, or a transport for obtaining overlays.

## Normative sections

- [Terminology and conformance classes](spec/v0/terminology.md)
- [Package layout](spec/v0/package.md)
- [Manifest: reading `overlay.cfg`, the data model, the fields](spec/v0/manifest.md)
- [Composition](spec/v0/composition.md), [dependencies](spec/v0/dependencies.md),
  [resolution](spec/v0/resolution.md)
- [Environment](spec/v0/environment.md) and [runtime and setup](spec/v0/runtime.md)
- [Commands](spec/v0/commands.md), [skills](spec/v0/skills.md),
  [context and harnesses](spec/v0/harness.md), [MCP](spec/v0/mcp.md)
- [Sources and distribution](spec/v0/distribution.md) and [integrity](spec/v0/integrity.md)
- [Store metadata and catalogs](spec/v0/catalog.md)
- [Security](spec/v0/security.md)
- [Conformance](spec/v0/conformance.md)

Every feature carries a class, **Core**, **Optional Extension** or **Implementation-Specific**, and
a feature no implementation reads yet also carries **Proposed**.
