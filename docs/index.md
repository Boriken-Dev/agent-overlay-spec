# Agent Overlay Specification

AOS is a draft format for packaging reusable instructions and capabilities for AI agents. It lets teams distribute focused overlays that can be combined with a user's existing setup.

An overlay is a directory of assets. `overlay.toml` is optional metadata. An overlay manager chooses how to install and compose packages for a particular agent product; the package does not require a particular runtime.

## Why overlays?

Complete agent configurations often repeat the same engineering guidance, skills, and workflows across projects. Overlays let teams keep those pieces separately reusable. A project can select the overlays it needs while leaving target-specific settings to the manager.

## Start here

- [Quick start](getting-started.md)
- [Author an overlay](authoring.md)
- [Format reference](spec/v0/index.md)
- [Implement AOS support](implementations.md)
- [Compatibility and open decisions](compatibility.md)
- [Security guidance](spec/v0/security.md)

The current specification is `0.1.0-draft`. It is not a final 1.0 standard. [dotagents](https://github.com/jose-pr/dotagents) is the reference implementation, not a required dependency.
