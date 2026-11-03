# Compatibility and open decisions

This page separates verified behavior from proposals. Evidence was checked against dotagents `main` source and tests, plus the public `repo` branch containing example overlays. Local overlay manifests were also reviewed for field usage; their content is not reproduced here.

## Verified behavior in dotagents

- Overlays are directories; `overlay.toml` is optional.
- The public example overlays use `name`, `description`, `requires`, and `routing`; the engineering example also uses `rules`.
- Manifest parsing uses TOML when available. Ordinary fields are permissive: defaults or filtered entries are used for many type errors. Invalid TOML suppresses ordinary manifest contributions with a warning.
- Name normalization lowercases and maps `.` and `_` to `-`; directory identity is distinct from manifest display name.
- `requires` is normalized and deduplicated. Add installs requirements first; remove protects required overlays unless forced. There is no dependency version syntax in the manifest.
- `priority` defaults to 500; deterministic composition sorts by priority, manifest name, then directory name.
- `setup_timeout` defaults to 300 seconds; zero means unlimited. Root `setup.py` or `setup.sh` can be run by the manager.
- `[scripts]` maps launcher names to relative paths or `false`; top-level `bin/*.py` can be discovered automatically.
- `[mcp]` supports arrays of stdio and streamable HTTP servers plus links from skill names to a server. The gateway has additional runtime behavior.
- Sources include local directories, directory collections, JSON/TOML/YAML registries, Git repositories and revisions, and optional URI-backed sources. GitHub is not required by the source parser.
- Scope walking and project/user/system shadowing are dotagents-specific manager behavior.

## Documentation and implementation differences

The `dotagents` overlay guide and authoring guide document most common behavior. The source and tests establish stricter details and occasional differences: for example, ordinary manifest values are often filtered/defaulted instead of rejected, whereas MCP declarations reject unknown keys and invalid structures. Therefore this spec gives the schema as an authoring/validation contract and separately describes the tolerant reference parser.

The guide calls the manifest `name` canonical, while the implementation derives installation identity from the selected directory name; the manifest name is used as metadata and as a composition tiebreaker. This draft documents both roles and recommends that they normalize to the same value.

The user request mentions MCP structures, scripts, and setup timeout that are implemented but not exercised by the `repo` branch's current example manifests. Their support is verified in source and tests, not inferred from the example branch.

## Ambiguities and interoperability risks

- AOS has no manifest version field; parser behavior for unknown keys differs between ordinary manifest fields and the MCP table.
- Dependency cycles, partially installed dependency graphs, and conflict handling for manually assembled installations are not a stable portable contract.
- Overlay identity is directory-based in dotagents, while manifest `name` affects display and ordering. Different tools may choose a different identity model unless constrained.
- Skill publication and command collisions depend on manager and runtime behavior.
- URI scheme support depends on optional dependencies and environment configuration.
- MCP credential lookup, inherited environment, server permissions, and skill presentation are runtime-specific.

## Proposals for a future version

1. Define a versioned identity and alias model without invalidating manifest-free legacy packages.
2. Define dependency cycle errors and optional version constraints.
3. Define a portable provenance and integrity sidecar or registry metadata format.
4. Define extension namespaces and a policy for unknown extension tables.
5. Clarify portable skill metadata without requiring one vendor's front matter.

Each proposal requires review before becoming normative. Existing overlays require no migration for this draft.
