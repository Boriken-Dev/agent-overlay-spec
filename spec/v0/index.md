# AOS v0 draft

**Status: development draft.** This document captures the compatibility baseline and proposes a portable vocabulary. It is not AOS 1.0 and has not been reviewed across independent implementations.

The core package is a directory tree. A manifest is optional. A consumer may read the files without installing them or executing them. A manager may add installation and runtime capabilities, but it MUST identify unsupported declarations instead of silently presenting them as active.

## Requirements language

The uppercase terms MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY carry RFC 2119 / RFC 8174 meaning only in normative statements.

## Feature labels

- **Core** — package and parsed-manifest interoperability described by this draft.
- **Optional Extension** — portable declarations that implementations may support independently, including skills and MCP integration.
- **Implementation-Specific** — installation, target mapping, execution, and lifecycle behavior not made portable by the file format.
- **Proposed** — a candidate future requirement that is not part of the compatibility baseline.

See [terminology](terminology.md) and [conformance](conformance.md) for consumer levels.
