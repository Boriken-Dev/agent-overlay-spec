# Contributing to AOS

AOS is a draft. Contributions distinguish behaviour an implementation has from new proposals.

## Changes to the specification

1. Open an issue describing the use case, affected implementations, and compatibility impact.
2. Say whether the change is editorial, clarifying, additive, or breaking. A new required field or
   new required processing is breaking unless a new edition introduces it.
3. Change the normative section, the schema, the examples, the fixtures and the vectors together,
   and record the change in `CHANGELOG.md`.
4. Run the checks:

   ```bash
   python -m pytest
   python -m black --check tests
   mkdocs build --strict
   ```

5. Do not mark a draft as final or claim implementation support without evidence. A field no
   implementation reads carries the **Proposed** label.

Use RFC 2119 terms only for normative interoperability requirements. Keep vendor-specific behaviour
in implementation notes.

## Proposal review

A proposal states its motivation, the exact format or processing change, the overlays it affects,
the migration path, its security impact, and the vectors or examples that show it. Decisions are
recorded in [`docs/design/decisions.md`](docs/design/decisions.md).

## Scope

The reference implementation is [dotagents](https://github.com/jose-pr/dotagents). Changes to
dotagents are outside this repository and do not change AOS by themselves.
