# Terminology

**Overlay**: a directory package containing agent configuration assets and, optionally, an `overlay.toml` manifest.

**Overlay root**: the directory containing the overlay's manifest, if any. Relative asset references are resolved from this root.

**Manifest**: optional UTF-8 TOML document named `overlay.toml` at the overlay root.

**Overlay manager**: software that locates, installs, removes, updates, or composes overlays.

**Consumer**: software that reads or exposes overlay assets. A consumer can be read-only and need not manage installation.

**Reference implementation**: dotagents. The phrase means an implementation used to compare behavior; it does not imply that AOS requires it.

**Name normalization**: the dotagents compatibility mapping that lowercases names and maps `_` and `.` to `-`.

## Conformance levels

An implementation SHOULD state which capabilities it supports:

1. **Read-only consumer** — lists and reads package assets without changing them.
2. **Manifest parser** — parses TOML and exposes recognized fields with type information.
3. **Overlay resolver** — resolves sources and dependencies and defines deterministic ordering.
4. **Overlay manager** — installs, updates, removes, composes, and applies runtime integrations.

Higher levels include the lower level's obligations only when the implementation claims those capabilities. A consumer can conform without executing assets.
