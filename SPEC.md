# Agent Overlay Specification (AOS)

**Draft version 0.1.0 — 2026-11-04**

This is the normative entry point. The complete specification is in [`spec/v0/`](spec/v0/index.md). The published draft status and compatibility baseline are described in [Compatibility](docs/compatibility.md).

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHOULD**, **SHOULD NOT**, and **MAY** are to be interpreted as described by [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) and [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174) when, and only when, they appear in all capitals.

AOS defines a package format and declarations. It does not prescribe a particular installer, target configuration, runtime, programming language, or transport for obtaining packages.

## Normative sections

- [Terminology and conformance classes](spec/v0/terminology.md)
- [Package layout](spec/v0/package.md)
- [Manifest fields and semantics](spec/v0/manifest.md)
- [Composition](spec/v0/composition.md)
- [Dependencies](spec/v0/dependencies.md)
- [Resolution and conflict behavior](spec/v0/resolution.md)
- [Sources and distribution](spec/v0/distribution.md)
- [Skills](spec/v0/skills.md) and [commands](spec/v0/commands.md)
- [MCP declarations](spec/v0/mcp.md)
- [Security](spec/v0/security.md)
- [Conformance](spec/v0/conformance.md)

Every feature is labeled **Core**, **Optional Extension**, **Implementation-Specific**, or **Proposed**. The labels separate portable file declarations from manager behavior.
