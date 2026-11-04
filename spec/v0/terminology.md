# Terminology

**Overlay**: a directory of agent configuration assets and, optionally, an `overlay.cfg` manifest.

**Overlay root**: the overlay's top directory. Relative paths are resolved from it.

**Identity**: the name a consumer installs an overlay under, compared normalized.

**Manifest**: the optional document `overlay.cfg` at the overlay root.

**Format line**: a first line starting `#!` that names the manifest's format.

**Data model**: the value a manifest reads as, the same whatever its format.

**Default**: what a file in a conventional place adds to a field without being declared, unless
the manifest's `defaults` turns it off; see [Package](package.md#defaults).

**Consumer**: software that reads or exposes overlay assets. A consumer can be read-only.

**Overlay manager**: a consumer that locates, installs, updates, removes or composes overlays.

**Harness**: the agent program an overlay is given to.

**Active overlays**: the overlays a consumer applies to one session or process, after dependencies.

**Composition order**: the deterministic order in which active overlays contribute.

**Env value**: what `env` gives a variable: text, a path under the root, or a secret reference.

**Placeholder**: `${NAME}` or one of its forms in an env value's text, substituted from the
environment being built when the variable is set; see [Substitution](environment.md#substitution).

**Setup phase**: what setup is told it is doing, `install`, `sync` or `remove`; see
[Setup phases](runtime.md#setup-phases).

**Sync**: an operation of a consumer that brings an installed overlay up to date: fetching its
source again, changing its source, ref or pin, or running its setup again on request. Every sync
runs the `sync` phase.

**State directory**: a directory outside the overlay root, per identity and OS, where setup
writes; kept across syncs and digests, deleted after removal.

**Scope**: a set of overlays a consumer installs and activates together, such as a user's or a
project's. A consumer documents its scopes; AOS defines none.

**Environment** (of dependencies): a directory outside every overlay root where a runtime's
packages are installed: shared in a scope, named, or isolated to one overlay; see
[Dependencies](runtime.md#environments).

**Secret reference**: a provider and its fields, or a secret's name, that say where a value comes
from; never the value.

**Tree digest**: the SHA-256 digest of an overlay's files, computed as [Integrity](integrity.md)
defines.

**Pin**: a tree digest a consumer requires an overlay to have.

**Weakening**: a choice, declared by an overlay or made by a consumer, that is looser than the
default and that a consumer reports.

**Informational field**: a field a store shows and nothing else reads: the `about` table and a
catalog's own fields; see [Store metadata and catalogs](catalog.md).

**Store**: a consumer, or the part of one, that lists overlays for a person to find and install.

**Catalog**: a document listing overlays by name with their sources, for a store; a registry is a
catalog in the minimal form.

**Label**: the name a consumer gives a catalog in its own configuration, which qualifies the names
two catalogs share.

**Reference implementation**: dotagents, the implementation behaviour is compared against. AOS does
not require it.

## Conformance classes

An implementation states which of these it claims; see [Conformance](conformance.md):

1. **Read-only consumer**: lists and reads overlay files without changing them.
2. **Manifest reader**: reads `overlay.cfg` into the data model and validates it.
3. **Environment**: builds an environment from `env`, `env_files`, `paths` and root variables.
4. **Runtime and setup**: probes runtimes and runs setup.
5. **Integrity**: computes tree digests and enforces pins.
6. **Resolver**: resolves sources and dependencies in a deterministic order.
7. **Manager**: installs, updates, removes and composes overlays.
8. **Store**: lists overlays from catalogs, with their informational fields and icons.

A class includes another's obligations only when the implementation claims both.
