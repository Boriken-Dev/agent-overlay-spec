# Conformance

An implementation claims conformance only for named classes, and names the edition. It MUST say which
optional extensions it does not support, and MUST NOT present reading a declaration as having applied
it. A class that applies a field applies its [defaults](package.md#defaults) too, unless the manifest
turns them off.

## Classes

| Class | Obligations | Vectors |
| --- | --- | --- |
| **Read-only consumer** | Lists and reads overlay files; treats an absent manifest as valid; says when it ignored an unreadable one. Shows an `OVERLAY.md` as a [viewer](manifest.md#the-split) does, and lists skills from elsewhere as named, not as present. | The split's cases of `front_matter.json` |
| **Manifest reader** | Reads `OVERLAY.md` and `overlay.cfg` as [Manifest](manifest.md) says: the split, the format line, TOML and restricted YAML, the data model, static reading, limits. States which optional formats it reads. Preserves unknown top-level keys. | `reading.json`, `front_matter.json` |
| **Validator** | Validates the data model against the schema and the semantic rules, including that named files exist, that an overlay has one manifest and, given the files, that `env` sets no variable the default `paths` adds to; flags each skill name neither bundled nor sourced; reports problems under `about` without stopping the manifest from applying. | `validation.json` |
| **Environment** | Builds the environment from root variables, `env`, `env_files` and `paths` in the [order of application](environment.md#order-of-application), [substituting](environment.md#substitution) each text value as it is set; resolves secret references or refuses; reads env-script output; reports weakenings. | `effective.json`, `compose.json`, the `dotenv` (substitution included) and `env-script` cases of `reading.json` |
| **Runtime and setup** | Selects variants per OS and [default scripts](runtime.md#default-scripts), probes what an overlay needs, runs setup in its [phases](runtime.md#setup-phases) as [Runtime and setup](runtime.md#setup) says, reports weakenings. | `effective.json` |
| **Integrity** | Computes the [tree digest](integrity.md#tree-digest) and enforces pins. | `digest.json` |
| **Resolver** | Parses [sources](distribution.md#source-form), validates and normalizes [identities](package.md#names-and-paths), resolves `requires`, orders the active overlays; [resolves skill names](skills.md#resolving-a-name) through catalogs, reporting each missing and ambiguous one. | `source.json`, `names.json`, `compose.json`, `skills.json` |
| **Manager** | Installs, updates and removes overlays; documents scopes, merge targets, collisions and execution policy; protects user-owned data; never runs code because an overlay was fetched; [fetches and checks](skills.md#fetching) an overlay's skills from elsewhere only after the user accepts them, or [reports each as not delivered](skills.md#a-consumer-that-does-not-fetch). | `skills.json` |
| **Store** | Reads [catalogs](catalog.md#catalogs) in both forms, their overlays and skills, resolves their sources, refuses entries alone and leaves out invalid informational fields; lists several catalogs by label, qualifying names they share; shows `about` and [icons](catalog.md#icons) as that section says; treats a catalog as advertising and shows what an overlay would do from its fetched manifest [before installing](catalog.md#before-installing). | `catalog.json`, the `catalog` cases of `reading.json`, the `about` cases of `validation.json` |

## Vectors

The vectors are JSON files in
[`tests/vectors/`](https://github.com/Boriken-Dev/agent-overlay-spec/tree/main/tests/vectors), data
rather than code, so an implementation in any language reads them with its own JSON library and
compares its results. Each file has a `description`, the `spec` section it tests, and `cases`, each
with an `id`, its input and an `expect`.

- **Types are part of a value.** `30` and `30.0` differ, and so do `1` and `true`.
- **Mapping order carries no meaning**; array order does.
- **Errors are classes**, such as `parse-error` or `symlink`. An implementation maps its own errors
  to them; where two classes are right, `expect.error` lists both, and where reading and refusing
  are both right, `expect` has both `data` and `error`.
- A file names every input it needs: file contents, an OS, an environment, secrets. No vector reads
  the filesystem or the network, except that `digest.json` trees can also be built on a filesystem
  that can hold them.

| File | Input | Expect |
| --- | --- | --- |
| `reading.json` | Document bytes (`text` or `base64`), `format` (`aos`, `dotenv`, `env-script` for an env script's output, or `catalog` with the file `name`), optional `limits`; for `dotenv`, optional `env`, `os` and `secret_variables` to substitute against | `data`, or `error` |
| `front_matter.json` | Document bytes (`text`, `base64`, or `parts` to concatenate, for what is too large to write out) with optional `limits`; a `context_file`; or an overlay's `files` | The split's and the reading's `case`, the `metadata` and `body` with their offsets and lines, the `format`, the `data` or the `error` and `line`; the context's text; or the manifest and the file it came from, the context in order, what was ignored, the problems and the digest |
| `skills.json` | `overlays`, `requested`, optional `files`, `catalogs`, `order` and `fetches`; or a `fetched` skill's files, its `name` and an optional `pin` | Each skill with its origin and source, the missing, ambiguous, unpinned and not-fetched names, what is delivered and the collisions; or the fetched tree's digest, or the refusal |
| `validation.json` | A data model `document`, optional `files` | `valid`, and for a valid one the pointers of any names `flags` picks out; for an invalid one the pointer `at` of the offending value; where `about` is written, whether the manifest still `applies` |
| `names.json` | An overlay `name` | `valid`, `normalized`, `variable` |
| `source.json` | A `source` string | `kind`, `location`, `ref`, `path`, or `error` |
| `digest.json` | A `tree` of files, directories, links and special files | `digest` and its `lines`, or `error` |
| `compose.json` | `overlays` by identity, `requested`, optional `files` (each overlay's files, for defaults) and `facts`, which may give each overlay's installed `packages` and the overlays `removed` | The visiting order, the composition order, missing requirements, contributions, the environment; the dependency environments, their conflicts, the overlays blocked by them and what a removed overlay leaves; or the cycle |
| `catalog.json` | A `catalog` (file `name`, `text`, and the `base` it was read from); several `catalogs`, each with its `label`, and names to `choose`; or an `icon` (`name`, `base64`, optional `limits`) | The form, informational fields, entries with absolute sources, `skills` where the catalog has them, refused entries and ignored fields, or the error; the listing, collisions and what each name picks; the icon's format and dimensions, or the refusal |
| `effective.json` | One `manifest` and the consumer's `facts`, the overlay's `files`, the `interpreters` it has among them and its installed `packages`; for setup phases, the `change` (`add`, `sync`, `activate`, `remove`), the `digest`, the `record` and the step that `fails` | The environment, the selected setup and runtime variants, the dependencies, what a probe needs, the weakenings, and the setup phase, its arguments, the steps in order, the record afterwards and whether the digest activates; or the refusal |

This repository runs every vector through a small Python reader (`tests/aos_reference.py`,
`python -m pytest`), and the digest vectors were also checked with an independent shell
implementation. A vector that disagrees with the text is a bug in the vector.

Passing the vectors does not make an overlay safe, or a consumer secure: they check that
implementations agree.
