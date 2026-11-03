# Agent Overlay Specification (AOS)

**A draft, vendor-neutral format for portable agent configuration overlays.**

AOS describes a directory of reusable instructions, rules, skills, knowledge, workflow assets, commands, and optional integration declarations. An overlay manager decides how to install, combine, and expose those assets to a particular agent runtime.

The current format is grounded in the behavior of [dotagents](https://github.com/jose-pr/dotagents), which serves as a reference implementation. AOS does not require dotagents, Git, Python, or any particular agent product.

> **Status:** AOS `0.1.0-draft` is a development specification. It is open for review and is not a finalized 1.0 standard.

## Read the specification

- [Documentation and quick start](https://jose-pr.github.io/agent-overlay-spec/)
- [Normative specification](SPEC.md)
- [Compatibility baseline and open decisions](docs/compatibility.md)
- [JSON Schema](schemas/overlay.schema.json)
- [Examples](examples/)

## Design at a glance

An overlay is a portable directory. `overlay.toml` is optional; files inside it are assets and are interpreted by an implementation only when that implementation supports the relevant capability. AOS distinguishes format conformance from installation policy and runtime integrations.

```text
team-overlay/
├── overlay.toml       # optional metadata and declarations
├── rules/             # optional always-on instructions
├── skills/            # optional skills/<name>/SKILL.md packages
├── kb/                # optional knowledge and instructions
├── cmds/ bin/ lib/    # optional implementation-specific assets
└── workflows/         # optional workflow assets
```

The specification records verified `dotagents` behavior as a compatibility baseline, while flagging behavior that is only a manager policy or an AOS proposal.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the draft process and [SECURITY.md](SECURITY.md) for reporting security issues. Conformance does not imply endorsement by any agent vendor.

## License

The specification and documentation are available under the MIT License. Implementations may use the format freely.
