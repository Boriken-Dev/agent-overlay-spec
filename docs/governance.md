# Versioning and governance

AOS evolves independently from dotagents releases. The reference implementation can change without changing the normative document, and a specification revision does not imply a dotagents release.

## Versioned documents

Each normative edition is published under an immutable versioned path (`spec/v0/`, then a new directory for a later major edition). The edition identifier appears in its index and in the repository changelog. The current edition is `0.1.0-draft`; it is not a final 1.0 standard.

## Compatibility policy

The project intends to use Semantic Versioning for specification editions:

- While major version is `0`, a minor increment may introduce incompatible requirements or remove a draft requirement; a patch increment is for compatible clarification, corrections, and editorial fixes.
- At `1.0.0`, normative requirements are considered stable. Additions that preserve existing valid overlays and implementations increment the minor version; incompatible changes increment the major version.
- An erratum does not silently change a published normative edition. Publish a new patch edition and keep the previous version available.

This policy is an AOS governance rule, not a manifest field. It does not mean every parser has to inspect a version key.

## Deprecation

Before a stable field or requirement is removed, the maintainers SHOULD mark it deprecated in a minor edition, explain the replacement, and provide a migration path. Removal SHOULD wait until a major edition. A draft proposal may change more quickly, but compatibility effects MUST be recorded in `CHANGELOG.md` and `docs/compatibility.md`.

## Extensions

An extension SHOULD use a collision-resistant namespace controlled by its maintainer. This draft allows unknown top-level keys for compatibility but does not yet standardize namespaced extension tables. An implementation MUST NOT interpret another namespace's fields as its own without an explicit agreement.

## Proposals and conformance

Open an issue or pull request with the motivation, exact change, compatibility impact, security implications, affected consumers, and migration plan. Normative changes require maintainer review and updates to schema, examples, fixtures, and compatibility notes. A conformance claim identifies the edition and capabilities tested. Conformance does not imply vendor endorsement.
