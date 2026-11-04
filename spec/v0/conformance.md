# Conformance

An implementation claims conformance only for named classes, and names the edition. It MUST say which
optional extensions it does not support, and MUST NOT present reading a declaration as having applied
it. A class that applies a field applies its [default](package.md#defaults) when the manifest does
not write it.

## Classes

| Class | Obligations | Vectors |
| --- | --- | --- |
| **Read-only consumer** | Lists and reads overlay files; treats an absent manifest as valid; says when it ignored an unreadable one. | |
| **Manifest reader** | Reads `overlay.cfg` as [Manifest](manifest.md) says: the format line, TOML, the data model, static reading, limits. States which optional formats it reads. Preserves unknown top-level keys. | `reading.json` |
| **Validator** | Validates the data model against the schema and the semantic rules, including that named files exist and, given the files, that `env` sets no variable the default `paths` adds to. | `validation.json` |
| **Environment** | Builds the environment from root variables, `env`, `env_files` and `paths` in the [order of application](environment.md#order-of-application); resolves secret references or refuses; reports weakenings. | `effective.json`, `compose.json` |
| **Runtime and setup** | Selects variants per OS and [default scripts](runtime.md#default-scripts), probes what an overlay needs, runs setup as [Runtime and setup](runtime.md#setup) says, reports weakenings. | `effective.json` |
| **Integrity** | Computes the [tree digest](integrity.md#tree-digest) and enforces pins. | `digest.json` |
| **Resolver** | Parses [sources](distribution.md#source-form), validates and normalizes [identities](package.md#names-and-paths), resolves `requires`, orders the active overlays. | `source.json`, `names.json`, `compose.json` |
| **Manager** | Installs, updates and removes overlays; documents scopes, merge targets, collisions and execution policy; protects user-owned data; never runs code because an overlay was fetched. | |

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
| `reading.json` | Document bytes (`text` or `base64`), `format` (`aos` or `dotenv`), optional `limits` | `data`, or `error` |
| `validation.json` | A data model `document`, optional `files` | `valid`, and for an invalid one the pointer `at` of the offending value |
| `names.json` | An overlay `name` | `valid`, `normalized`, `variable` |
| `source.json` | A `source` string | `kind`, `location`, `ref`, `path`, or `error` |
| `digest.json` | A `tree` of files, directories, links and special files | `digest` and its `lines`, or `error` |
| `compose.json` | `overlays` by identity, `requested`, optional `files` (each overlay's files, for defaults) and `facts` | The visiting order, the composition order, missing requirements, contributions, the environment; or the cycle |
| `effective.json` | One `manifest` and the consumer's `facts`, the overlay's `files` and the `interpreters` it has among them | The environment, the selected setup and runtime variants, what a probe needs, the weakenings; or the refusal |

This repository runs every vector through a small Python reader (`tests/aos_reference.py`,
`python -m pytest`), and the digest vectors were also checked with an independent shell
implementation. A vector that disagrees with the text is a bug in the vector.

Passing the vectors does not make an overlay safe, or a consumer secure: they check that
implementations agree.
