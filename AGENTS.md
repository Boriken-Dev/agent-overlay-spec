# AOS — repository orientation

The Agent Overlay Specification: a normative text, a JSON Schema of the manifest's data model,
examples, and conformance vectors. Nothing here is packaged or installed.

## Layout

| Path | Responsibility |
| --- | --- |
| `SPEC.md` | Normative entry point; lists the sections |
| `spec/v0/` | The normative sections of the current edition |
| `schemas/overlay.schema.json` | The manifest's data model, and a catalog's at `$defs/catalog`; `docs/schemas/` holds an identical copy for the site |
| `examples/` | One overlay per feature, each valid against the schema |
| `tests/fixtures/` | Valid and invalid manifests for the schema tests, with `invalid/expect.json` |
| `tests/aos_reference.py` | The small Python reader and validator the tests use; the specification wins over it |
| `tests/vectors/` | Conformance vectors as JSON data, for implementations in any language |
| `docs/` | The site: hand-written pages, and `docs/spec/v0/*.md` snippet includes of `spec/v0/` |

## Rules

- Every feature carries a class label (Core, Optional Extension, Implementation-Specific); a feature
  no implementation reads yet also carries **Proposed**.
- A change to a field changes, together: the section, the schema (both copies), an example, the
  fixtures, the vectors, and `CHANGELOG.md`.
- Manifests stay static data: no field may require executing, including or interpolating anything
  to read it.
- Public text names dotagents as the reference implementation and nothing private.

## Commands

```sh
python -m pytest                 # schema, examples, fixtures and vectors
python -m black --check tests
mkdocs build --strict
```

## CI and release

`test.yml` runs on dispatch, on a `ci-*` tag or branch, and from `release.yml`. `docs.yml` publishes
Pages on a push to `main` touching the docs sources, and on dispatch. A `v*` tag runs the tests and a
strict docs build, then creates a GitHub release from the changelog; nothing is published to a
registry. Pushing a `v*` tag needs the owner's consent for that edition.
