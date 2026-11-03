# Terminology

**Overlay**: a directory of agent configuration assets and, optionally, an `overlay.cfg` manifest.

**Overlay root**: the overlay's top directory. Relative paths are resolved from it.

**Identity**: the name a consumer installs an overlay under, compared normalized.

**Manifest**: the optional document `overlay.cfg` at the overlay root.

**Format line**: a first line starting `#!` that names the manifest's format.

**Data model**: the value a manifest reads as, the same whatever its format.

**Consumer**: software that reads or exposes overlay assets. A consumer can be read-only.

**Overlay manager**: a consumer that locates, installs, updates, removes or composes overlays.

**Harness**: the agent program an overlay is given to.

**Active overlays**: the overlays a consumer applies to one session or process, after dependencies.

**Composition order**: the deterministic order in which active overlays contribute.

**Env value**: what `env` gives a variable: a literal, a path under the root, or a secret reference.

**Secret reference**: a provider and its fields, or a secret's name, that say where a value comes
from; never the value.

**Tree digest**: the SHA-256 digest of an overlay's files, computed as [Integrity](integrity.md)
defines.

**Pin**: a tree digest a consumer requires an overlay to have.

**Weakening**: a choice, declared by an overlay or made by a consumer, that is looser than the
default and that a consumer reports.

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

A class includes another's obligations only when the implementation claims both.
