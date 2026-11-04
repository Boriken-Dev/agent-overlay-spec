# Integrity

**Optional Extension, Proposed.** A consumer pins an overlay by one digest of its whole tree, and
refuses an overlay whose files no longer match. Two implementations that compute the digest as this
section says agree on it, whatever their language or platform.

> **Status:** dotagents records the SHA-256 of each file it installs, and the source it installed
> from, in its install record; it computes no tree digest and enforces no pin.

## Digest form

A digest is written `sha256:` followed by 64 hexadecimal digits: the SHA-256 of the input, as
lowercase hexadecimal when written. A reader compares the hexadecimal digits without regard to case,
and MUST refuse a digest with another prefix or length. `sha256` is the only algorithm this edition
defines; another edition may define more, under another prefix.

## Tree digest

The tree digest of an overlay is computed from its root directory:

1. **Members.** Every regular file at any depth under the root, except:
    - anything with a path component (a directory, or the entry itself) named `.git`, `.hg`,
      `.svn`, `__pycache__`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `.tox`, `.venv` or
      `node_modules`, compared exactly; an excluded directory is not entered;
    - anything other than a directory whose name ends in `.pyc`.

    Directories are not members, so an empty directory changes nothing. The manifest is a member
    like any other file.
2. **Refusals.** The digest cannot be computed, and is an error, when the tree holds, other than as
   an excluded entry or inside one:
    - a symbolic link, a junction or another reparse point, to anything;
    - anything that is not a regular file or a directory (a device, a pipe, a socket);
    - a name that is not valid UTF-8 (a sequence of Unicode scalar values);
    - a member whose path is not a [relative path](manifest.md#fields): this refuses `.GIT`,
      `.git.`, `Node_Modules`, `x.PYC`, `GIT~1`, device names, `:`, control characters (the zero
      byte included) and the other names a platform would alias or alter;
    - two members whose paths are equal after ASCII lowercasing, which a case-insensitive filesystem
      holds as one file.
3. **Paths.** Each member's path is its components from the root joined by `/`, as UTF-8 bytes of
   the names exactly as stored: no case folding, no Unicode normalization.
4. **Lines.** For each member, the line is its path, a zero byte (`0x00`), the member's
   [digest](#digest-form) of its bytes (`sha256:` and lowercase hex), and a line feed (`0x0A`).
5. **Order.** Lines are sorted by their path bytes, compared as unsigned bytes, which is the order of
   Unicode scalar values. Languages whose strings compare by UTF-16 code units (Dart, Java,
   JavaScript, C#) sort `😀` before `�`; they compare the UTF-8 bytes instead.
6. **Digest.** The tree digest is the [digest](#digest-form) of the concatenated lines. A tree with no
   members has the digest of no bytes,
   `sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

A member's bytes are its bytes as stored. Nothing is normalized: not line endings, not a byte-order
mark, not encoding. File modes, timestamps and owners are not part of the digest.

For example, a tree of `overlay.cfg` holding `name = "x"\n` and `kb/a.md` holding `# A\n` gives the
lines

```text
kb/a.md\0sha256:<sha256 of "# A\n">\n
overlay.cfg\0sha256:<sha256 of "name = \"x\"\n">\n
```

and the tree digest is the SHA-256 of those two lines. The [vectors](conformance.md#vectors) give
the values.

### Line endings

A file checked out with line-ending conversion has other bytes, so another digest. A consumer
computes the digest over the bytes as published:

- **Git:** the blob bytes at the commit, as `git cat-file blob <commit>:<path>` prints them, with no
  checkout filter, `text`/`eol` conversion, `working-tree-encoding`, `ident` or `export-subst`
  applied. A tree entry that is a symbolic link (mode `120000`) or a submodule (mode `160000`) is a
  refusal, as on a filesystem. With a `#path`, only that subtree is the overlay.
- **A directory:** its files as they are.
- **An archive:** its entries' bytes. An entry that is a link of any kind (hard links included), an
  entry named twice, and a name that normalizes to another (`a/../b`, `./a`, a trailing `/` on a
  file) are refusals; where a format holds a name twice (a zip's local and central headers, a tar's
  ustar and PAX names) the two must agree.

**The copy a consumer uses is the copy it hashed.** A consumer writes each member, from the bytes it
hashed, into a fresh directory it owns, and nothing else: no checkout filter, no excluded entry, no
file outside the `#path` subtree. When it verifies an installed copy again, an entry that is not a
member (an excluded name included) counts as a mismatch. The copy is read-only to the agent and to
the overlay's own processes.

An overlay author keeps a repository's `.gitattributes` at `* text=auto eol=lf` so that a checkout
and the blobs hold the same bytes on every platform.

## Pins

A **pin** is a tree digest a consumer requires an overlay to have. It lives in the consumer's own
configuration, beside the overlay's [source](distribution.md#source-form), never in the overlay. A
[catalog](catalog.md#trust) entry may carry one, which a consumer checks and then records in its
own configuration:

```toml
[overlays.engineering]
source = "https://github.com/example/overlays.git@4b825dc642cb6eb9a060e54bf8d69288fbee4904#overlays/engineering"
pin = "sha256:5d0c5b1e7b2b1c2f0a7f3e8e8f2a1c4b6e9d0a3b7c8d9e0f1a2b3c4d5e6f7a8b"
```

A consumer that enforces pins:

- computes the tree digest of what it fetched before it installs, sets up or exposes anything of it;
- computes it again whenever it activates the overlay from a copy that could have changed since,
  such as the start of each session;
- on a mismatch, **refuses** the overlay, and with it whatever needed it (an install, a session),
  reporting the overlay, the expected and the computed digest; it uses no file of that copy, and does
  not offer to continue;
- keeps every copy it verified unchanged: setup and tools write into the
  [state directory](runtime.md#what-a-step-receives) and packages go into
  [environments](runtime.md#environments), both outside the root and never part of its digest,
  and a consumer that cannot keep the copy read-only verifies it before each use;
- opens the files it uses so that they cannot leave the copy (see
  [relative paths](manifest.md#fields)), since a file can change between being hashed and being
  read only where something can write the copy.

An overlay installed without a pin is a [weakening](security.md#weakenings), `unpinned`, that the
consumer reports every time it activates the overlay. A pin cannot be overridden: to accept other
bytes, the user changes the pin.

A Git commit id names a revision, but most repositories still name commits by SHA-1, a branch or tag
can move, and a checked-out copy can change after checkout. A consumer pins by tree digest, and MAY
also record the commit.

## Lock files

`lock_digest` in a [Python runtime variant](runtime.md#runtime) is the [digest](#digest-form) of the
lock file's bytes. A consumer checks it before it installs anything from the lock, and refuses the
install on a mismatch. It lets a consumer key and check the dependency set alone; the tree digest
already covers the lock file when the overlay is pinned. A pin covers one overlay's dependency
file, its lock and the hashes in them, never what other overlays put in a shared environment.
