# Sources and distribution

Distribution is outside the directory format. An overlay MAY be copied, archived, served over HTTP,
listed in a registry, kept inside a larger repository, or stored in version control.

## Source form

**Optional Extension.** A consumer's configuration names where an overlay comes from with a source
string:

```text
source   = [ "git+" ] location [ "@" ref ] [ "#" path ]
```

- `location` is a local path, an `http` or `https` URL, or a Git repository: one ending in `.git`,
  starting `git@`, `ssh://` or `git://`, or prefixed `git+`.
- `ref` exists only for a Git location: a branch, tag or commit, with no `/`, `:` or `\`. It is the
  part after the last `@`, when that `@` is not part of `git@host`, a URL's user information, or a
  scheme. Absent, the remote's default branch.
- `path` is the part after the first `#`: the overlay's root inside the location, `/`-separated, with
  leading and trailing `/` removed. Absent, the location's root is the overlay.
- A Git location or ref starting with `-` is refused, since it would reach `git` as an option.

| Source | Kind | Location | Ref | Path |
| --- | --- | --- | --- | --- |
| `./overlays/rust` | directory | `./overlays/rust` | | |
| `https://github.com/example/agents.git@v2#overlays/rust` | git | `https://github.com/example/agents.git` | `v2` | `overlays/rust` |
| `git@github.com:example/agents.git` | git | `git@github.com:example/agents.git` | | |
| `git+https://example.org/agents@main#rust` | git | `https://example.org/agents` | `main` | `rust` |
| `/srv/overlays@v2` | directory | `/srv/overlays@v2` | | |
| `https://example.org/overlays/rust` | URL | `https://example.org/overlays/rust` | | |

A location is a **Git** location as above, else a **URL** when it contains `://`, else a
**directory**. Surrounding whitespace is removed first; an empty source is an error.

A **pinned source** pairs a source with a [pin](integrity.md#pins). For a reproducible install the
ref is a full commit id (40 or 64 hexadecimal digits) and the pin is the tree digest; a branch or a
tag can move.

A consumer that logs or stores a source removes any user information from it first
(`https://user:secret@host/x.git` is shown as `https://host/x.git`).

> **Status:** dotagents parses exactly this form (`<location>[@<ref>][#<path>]`) for repositories and
> overlays. It also reads registries (a JSON, TOML or YAML mapping from name or alias to source,
> relative entries resolved beside the registry) and, with optional dependencies, URI schemes such as
> `zip:`, `sftp:` and `s3:`. It consults `--repo`, then `AGENTS_OVERLAYS_REPO_<KEY>`, then
> `AGENTS_OVERLAYS_REPO`, then the project's and the user's `dotagents.{json,toml,yaml,yml}`; the
> first that offers a name wins. That order is dotagents policy.

## Provenance

A manager records, for each installed overlay, the source with its user information removed, the
resolved commit when there is one, the tree digest, and when it was fetched. It shows source and ref
before it activates an overlay for the first time, and the difference before it updates one.

AOS does not require GitHub, Git, or any registry protocol.
