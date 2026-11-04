# Resolution and errors

Resolution has three parts: selecting a source, identifying an overlay in it, and composing the
active overlays.

## Name identity

Identities normalize as [Package](package.md#names-and-paths) says. A [catalog](catalog.md#catalogs) may give an overlay
an alias; the alias does not rename the overlay. A resolver SHOULD detect two source entries that
resolve to the same identity.

## Ordering and overrides

[Composition](composition.md#deterministic-ordering) defines the order. Consumers MUST NOT infer
that a later file replaces an earlier one unless their own policy says so.

## Errors

A reader reports malformed documents and invalid fields. A read-only consumer MAY still expose an
overlay's files when its manifest is invalid, provided it says that it ignored the manifest. A
consumer MUST NOT apply any declaration of a manifest it could not read and validate: no setup, no
environment, no MCP server, no command. Problems under `about` alone do not count: it is
[informational only](catalog.md#informational-only).

> **Status:** dotagents ignores an unreadable `overlay.toml` as a whole for contributions, replaces
> malformed ordinary values with defaults and warns, and refuses invalid MCP declarations when the
> gateway loads.

## Recomposition

When an overlay is removed or updated, a manager regenerates derived configuration from the base and
the active overlays. It does not destroy user-owned text, and it keeps the provenance of what it
generated.

> **Status:** dotagents keeps text outside its managed block, and backs up locally edited installed
> files before replacing or removing them.
