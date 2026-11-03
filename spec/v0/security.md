# Security considerations

An overlay is data, but its instructions influence an agent. It may also carry executable scripts, dependency manifests, setup hooks, or remote-service declarations. **Format conformance does not establish trust or safety.**

## Trust and sources

Implementations SHOULD display source and revision before activation, support review before updates, and preserve provenance. Remote content MUST NOT be described as safe solely because it conforms to AOS. A mutable branch or registry can change after review; pin immutable revisions and verify content digests where possible.

## Execution and dependencies

Setup hooks, scripts, and dependency installation MUST be opt-in or governed by an explicit user/administrator policy. Implementations SHOULD run with least privilege, controlled working directories, bounded resources, and clear logs. They SHOULD allow read-only inspection without executing anything.

## Paths and filenames

Managers MUST prevent archive path traversal and reject entries that escape the package root after normalization. They SHOULD reject unsafe names, absolute paths, device paths, duplicate normalized paths, and symlink escapes. Path validation must account for platform-specific separators and case folding.

## Credentials and network access

Manifests SHOULD contain references to credential variables, never secret values. Implementations MUST avoid logging credential values and SHOULD restrict inherited environment variables. MCP endpoints and commands can access sensitive data and network services; managers SHOULD expose the declared server, transport, permissions, and credential sources to the user.

## Collisions and updates

Namespaces for overlay names, scripts, skills, servers, and tools can collide. Managers SHOULD detect collisions before activation and report the winning identity. Updates may change instructions or code; a digest or revision pin and a reviewable diff reduce supply-chain risk.
