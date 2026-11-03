# Sources and distribution

Distribution is outside the directory format. An overlay MAY be copied, archived, hosted over HTTP, served by a registry, included in a larger repository, or stored in a version-control system.

## Dotagents source compatibility

Dotagents accepts a standalone overlay directory, a directory containing multiple overlays, and JSON/TOML/YAML registry documents. A registry is either a mapping from overlay name or alias to source, or an object whose `overlays` key holds that mapping. Values are source strings.

Its source syntax is broadly `<location>[@<revision>][#<path>]`. Supported categories include local directories, Git repository locations and branch/tag/commit references, URL-based registry documents, and URI integrations such as `file:`, `http(s):`, `zip:`, `sftp:`, and `s3:` when the corresponding optional URI support is installed. `git+` can force Git handling for URL-shaped repository names. Relative registry entries resolve beside their registry. Exact URI support depends on optional dependencies and implementation version.

An explicit `--repo` list precedes configured source environment variables; keyed source variables and a default variable precede store registries. For a requested name, the first source offering it wins. This is dotagents policy, not a required AOS source order.

## Provenance and reproducibility

The manifest does not declare source provenance. Managers SHOULD record the selected source, immutable revision or content digest, retrieval time, and package digest in installation metadata. Branch names and mutable URLs are not reproducible pins. Registries SHOULD support immutable revisions and integrity metadata.

Consumers SHOULD verify archives and file digests before activation. AOS does not require GitHub, Git, or any single registry protocol.
