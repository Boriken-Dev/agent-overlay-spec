# Security policy

AOS describes files and declarations; conformance is not a safety review. An overlay can contain
malicious instructions, executable code, dependency declarations, or endpoints controlled by an
untrusted party.

## Reporting a vulnerability

For a vulnerability in this specification, use
[GitHub's private vulnerability reporting](https://github.com/Boriken-Dev/agent-overlay-spec/security/advisories/new)
for this repository. For issues in dotagents, report through
[the dotagents repository](https://github.com/jose-pr/dotagents). Do not put credentials or exploit
details in a public issue.

## Security expectations

Implementations treat remote overlays as untrusted until the user or administrator establishes
trust, pin what they install by digest, and report every non-default setting they apply. Review code, setup,
dependencies, environment declarations, MCP declarations, and update sources before activation. See
[Security considerations](https://boriken-dev.github.io/agent-overlay-spec/spec/v0/security/).
