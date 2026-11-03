# Contributing to AOS

AOS is a draft. Contributions should distinguish verified compatibility behavior from new proposals.

## Changes to the specification

1. Open an issue describing the use case, affected implementations, and compatibility impact.
2. Identify whether the change is editorial, clarifying, additive, or breaking. New required manifest fields and new required processing behavior are breaking unless introduced by a versioned specification.
3. Update the normative section, compatibility notes, examples, schema, and fixtures together as applicable.
4. Run `python -m pytest` and `mkdocs build --strict`.
5. Do not mark a draft as final or claim implementation support without evidence.

Use RFC 2119 terms only for normative interoperability requirements. Use **Proposed** for behavior that needs review. Keep vendor-specific behavior in implementation notes.

## Proposal review

Proposals should state: motivation; exact format or processing change; affected existing overlays; migration path; security impact; and tests or examples demonstrating the change. The maintainers record decisions in [`docs/design/decisions.md`](docs/design/decisions.md).

## Scope

The reference implementation is [dotagents](https://github.com/jose-pr/dotagents). Changes to dotagents are outside this repository and do not automatically change AOS.
