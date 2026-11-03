# Design decisions

## D1 — No required manifest version in the initial draft

**Decision:** `overlay.toml` remains optional, with no required `version` or `schema_version` key.

**Reason:** existing packages are manifest-free or use the implemented fields without a schema version. Requiring a new field would reject those packages. Specification evolution is versioned in the normative document and repository instead.

**Status:** adopted for draft 0.1.0; revisit before 1.0 review.

## D2 — Separate package declarations from manager policy

**Decision:** source precedence, scope inheritance, installation, execution, and target-specific rendering are documented as manager behavior unless directly required for data interpretation.

**Reason:** different runtimes expose instructions and tools through different target files and execution models.

**Status:** adopted.

## D3 — Preserve permissive top-level extension space

**Decision:** the schema permits unknown top-level keys, while documenting recognized fields. The reference implementation ignores unknown ordinary fields but validates its `mcp` table strictly.

**Reason:** an early strict schema could reject overlays that carry manager-specific metadata. Extension namespaces remain a future proposal.

**Status:** adopted for draft 0.1.0.
