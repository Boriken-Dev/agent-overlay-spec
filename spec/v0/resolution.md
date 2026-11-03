# Resolution and errors

Resolution has three distinct parts: selecting a package source, identifying an overlay within that source, and composing the selected packages.

## Name identity

The dotagents compatibility normalizer lowercases ASCII names and replaces `.` and `_` with `-`. Directory names are used as installation identity. Registries may use aliases, but an alias does not rewrite a manifest or package directory. A manager SHOULD detect multiple source entries that resolve to the same normalized identity.

## Ordering and overrides

Priority ordering is defined in [Composition](composition.md). AOS `priority` is an ordering hint for managers that merge ordered contributions; it is not a universal override instruction. Managers MUST NOT infer that a later file replaces an earlier file unless their own policy says so.

## Errors

A parser SHOULD report malformed TOML and invalid recognized fields. A read-only consumer MAY still expose package files if an optional manifest is malformed, provided it clearly reports that it ignored or could not parse the manifest. A manager MUST NOT silently execute an invalid setup or MCP declaration.

Dotagents ignores an invalid ordinary manifest as a whole for contributions, warns on many malformed ordinary values, and applies stricter errors to invalid MCP declarations when loading the gateway. This difference is intentional in the compatibility notes; AOS validators can be stricter without claiming that dotagents uses the same error policy.

## Recomposition

When an overlay is removed or updated, a manager SHOULD regenerate derived configuration from the base plus the currently selected overlays. It SHOULD avoid destructive edits to user-owned regions and SHOULD retain provenance for generated assets. Dotagents preserves edits outside its marker block and separately backs up locally edited installed files before replacement/removal during synchronization.
