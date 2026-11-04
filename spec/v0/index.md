# AOS v0 draft

**Status: development draft, edition `0.1.0-draft`.** It records the format dotagents implements
and adds what overlays need to be read, placed and pinned by any implementation. It is not AOS 1.0
and has not been reviewed across independent implementations.

The core package is a directory tree, and a manifest is optional: conventional files such as `bin/`,
`skills/<name>/SKILL.md` and `env` take effect by default. Every declaration is static data:
a consumer reads an overlay without installing it or running anything. A consumer that adds
installation and runtime behaviour MUST say which declarations it does not support instead of
presenting them as applied.

## Requirements language

The uppercase terms MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY carry their RFC 2119 and RFC 8174
meaning only in normative statements.

## Feature labels

Every feature carries one **class**:

- **Core**: the package and the manifest's reading and core fields. Every implementation of a
  class that reads manifests supports it.
- **Optional Extension**: a portable declaration an implementation may support on its own, such as
  environment, setup, skills, MCP or integrity.
- **Implementation-Specific**: installation, target mapping, execution and lifecycle behaviour that
  the format does not make portable.

A feature that no implementation reads yet also carries **Proposed**. Status notes say what dotagents,
the reference implementation, does today.

## Sections

- [Terminology](terminology.md) and [conformance](conformance.md)
- [Package](package.md), [manifest](manifest.md), [composition](composition.md),
  [dependencies](dependencies.md), [resolution](resolution.md)
- [Environment](environment.md), [runtime and setup](runtime.md), [commands](commands.md),
  [skills](skills.md), [context and harnesses](harness.md), [MCP](mcp.md)
- [Sources and distribution](distribution.md), [integrity](integrity.md), [security](security.md)
