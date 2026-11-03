# Security policy

AOS describes files and declarations; conformance is not a safety review. An overlay can contain malicious instructions, executable code, dependency declarations, or endpoints controlled by an untrusted party.

## Reporting a vulnerability

For a vulnerability in this specification repository, use GitHub's private vulnerability reporting for this repository when available. For issues in dotagents, report through [the dotagents repository](https://github.com/jose-pr/dotagents). Do not put credentials or exploit details in a public issue.

## Security expectations

Implementations should treat remote overlays as untrusted until the user or administrator establishes trust. Review code, setup hooks, dependencies, MCP declarations, and update sources before activation. See [Security considerations](spec/v0/security.md).
