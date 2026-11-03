# Conformance

An implementation claims conformance only for named capabilities. It MUST identify unsupported optional extensions and MUST NOT imply that package parsing means scripts were executed or runtime behavior was integrated.

## Read-only consumer

A read-only consumer can list package files, read content, and report an absent or invalid optional manifest. It does not need installation, dependency resolution, or code execution.

## Manifest parser

A parser MUST parse valid UTF-8 TOML manifests, preserve unknown top-level fields for forward compatibility, expose the recognized fields and their types, and report parse errors. It SHOULD validate recognized fields against the published schema. A parser MUST treat absence of `overlay.toml` as a valid manifest-free package.

## Overlay resolver

A resolver MUST document its source protocols, identity normalization, dependency behavior, duplicate policy, and deterministic order. It SHOULD preserve provenance and immutable source identifiers.

## Full manager

A full manager MUST document install/update/remove behavior, scope precedence, merge targets, collision handling, and executable integration policy. It MUST protect user-owned data and MUST NOT run setup or other code merely because a package is fetched.

## Validation

The repository tests positive and negative JSON Schema fixtures and parses all TOML examples. These checks validate declarations only; they do not prove that an overlay is secure or that a particular agent runtime behaves as expected.
