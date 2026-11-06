# Skills

**Optional Extension.** `skills/<name>/SKILL.md` is the portable layout of a skill in an overlay: a
directory named after the skill with a `SKILL.md` inside, which is a skill as the
[Agent Skills specification](https://agentskills.io/specification) defines one. The Markdown is
portable content; how a runtime discovers, presents and invokes a skill belongs to that runtime.

## Declaring skills

**Proposed.** `skills` lists the skills the overlay offers. Each entry is a name, or a table with a
`name` and the `source` to fetch it from:

```toml
skills = [
  "summarize-docs",
  "pdf",
  { name = "review", source = "https://github.com/example/skills.git#skills/review", pin = "sha256:8280aaf5de7c4f61342f648586d534e481ae095cef223dded70f5b1db5bd84a1" },
]
```

What an entry means follows from the entry and the overlay's files, and nothing else:

| Entry | Skill | Comes from |
| --- | --- | --- |
| A name, with `skills/<name>/SKILL.md` in the overlay | **bundled** | The overlay, under its tree digest |
| Any other name | **named** | The consumer's [catalogs](#resolving-a-name), as `pip` resolves a name through its index |
| A table | **sourced** | Its `source`, optionally with a `ref` and a `pin` |

The `skills` [default](package.md#defaults), every `skills/<name>/SKILL.md` whose `<name>` is a skill
name, comes first and the entries add to it. To offer only some bundled skills, turn the default off
with `[defaults] skills = false` and list them. A consumer that delivers skills delivers exactly
these, or says which it did not ([compatibility](#a-consumer-that-does-not-fetch)).

**A skill name** matches `[A-Za-z0-9][A-Za-z0-9_.-]*` and is a valid single component of a
[relative path](manifest.md#fields), since a consumer makes a directory of it: `con`, `NUL.txt`,
`pdf.` and `PROGRA~1` are not names. Names compare without regard to ASCII case. Authors SHOULD write
the [Agent Skills](https://agentskills.io/specification#name-field) form, at most 64 lowercase
letters, digits and single hyphens, equal to the skill's directory name, which every runtime of that
specification reads.

A table has these keys and no other, since a misspelt `pin` must not fetch a skill unpinned:

| Key | Type | Meaning |
| --- | --- | --- |
| `name` | skill name | Required. The name the skill is delivered under |
| `source` | string | Required. A [source](distribution.md#source-form) whose location, at its `#path`, is the skill's own directory |
| `ref` | string | The Git ref, for a Git source written without `@ref`, in the form a [catalog entry](catalog.md#entries-and-forms) takes |
| `pin` | digest | The skill directory's [tree digest](integrity.md#digest-form) |

**A manifest names no place on the consumer's machine and holds no credential**, whoever wrote it and
wherever it was read from, since the same overlay reaches other machines:

- a local source is refused (`local-source`): a directory, relative or absolute, a Git location that
  is a local path, any location starting `file:`, and a host that is the consumer's machine as its text
  says: `localhost` or a name under it, and a loopback, link-local or unspecified address, IPv4-mapped or
  not;
- a location with user information over `http` or `https`, a password in any URL, or a query is
  refused (`source-credentials`). An SSH account (`git@host:path`, `ssh://git@host/path`) is not a
  credential;
- a location that is not Git is an `http` or `https` URL (`invalid-source`);
- a `ref` beside an `@ref` or on a source that is not Git is refused (`ref-not-allowed`).

A source over plain `http` or `git://` is reported as the [weakening](security.md#weakenings)
`insecure-transport`, and one whose host is a private network address as `private-source`, when the
skill is resolved; a consumer that resolves a host name checks the address it connects to the same way.
A consumer fetches what a manifest names **without the user's credentials**, SSH agent or prompts, and
follows no redirect to another host: a manifest holds no credential, so none is owed to the host it
picked.

A validator refuses, at the entry:

- two entries whose names are equal without regard to ASCII case (`skill-duplicate`);
- a table whose name is also bundled, without regard to ASCII case and whether or not the default
  offers it (`skill-ambiguous`): which of the two is meant cannot be read from the overlay;
- a name that differs only in case from a bundled skill (`skill-case`), which is one directory on
  Windows and macOS and another on Linux.

A validator that knows the files **flags** every name that is neither bundled nor sourced
(`skill-from-catalog`), so a typo is seen before anything is looked up. A flag does not make a manifest
invalid: only a consumer's catalogs can tell a typo from a skill.

A skill's `SKILL.md` MAY begin with [front matter](manifest.md#the-split) that names it and describes
it (`name:`, `description:`). AOS does not require front matter; a runtime may, and the Agent Skills
specification does.

## Resolving a name

**Proposed.** A named skill is resolved through the `skills` tables of the consumer's
[catalogs](catalog.md#catalogs), comparing names without regard to ASCII case. Resolving reads catalogs
and nothing of any skill:

- **Missing.** No catalog offers the name. A catalog's overlay of that name is not a skill, and neither
  is another active overlay's bundled skill of that name: nothing says the two are one skill, so the name
  is reported missing and the bundled skill is delivered as its own overlay's.
- **Ambiguous.** More than one catalog offers it, even with one source: a consumer MUST NOT pick one by
  itself. It reports both labels, and may follow an order of catalogs the user configured for this, as
  for [overlays](catalog.md#several-catalogs), reporting which it took.

A consumer reports every missing and ambiguous name with the overlay naming it, before it applies any
composition, and **never guesses**. As for a [missing requirement](dependencies.md#resolution), it MAY
refuse (a session that must be complete) or continue without the skill (an interactive install), and
says which it does.

**Listing runs nothing and reads no skill's files until they are fetched.** Showing a manifest's
`skills`, validating them and resolving them read the manifest, the overlay's list of files and the
catalogs. [What an overlay would do](catalog.md#before-installing) lists every skill from elsewhere
with its source, its catalog's label when it came through one, and whether it is pinned, before
anything of it is fetched; a source is shown without user information or query.

An entry with no pin, in the table or in the catalog, is reported as the
[weakening](security.md#weakenings) `unpinned`, with the skill as its subject.

Two overlays naming one skill alike are one skill: the same name, resolving to the same source, in
full as it is fetched (user information and query included), and the same pin. Otherwise they fall
under [collisions](#delivery).

**What was accepted is recorded.** A consumer records, for each skill from elsewhere it fetched, the
catalog's label, the source, the ref and the pin or the digest it fetched. A later resolution that gives
another is an update, shown and accepted as one, never applied because a catalog changed.

## Fetching

**Proposed.** A consumer that fetches a skill does so only for an overlay the user accepted, with the
same [trust decision](security.md#execution-and-dependencies): an overlay from a project or a catalog
never fetches before that decision. Fetching runs nothing. Then, before it delivers the skill:

1. It computes the fetched directory's [tree digest](integrity.md#tree-digest), under the same rules
   as an overlay's, and refuses it on a mismatch with the pin (`pin-mismatch`), before reading any of
   its files. Both a table's pin and a pin in the user's configuration MUST match.
2. The directory has a `SKILL.md` at its root, or it is no skill (`not-a-skill`).
3. Its `SKILL.md` begins with [front matter](manifest.md#the-split) in the
   [restricted YAML](manifest.md#restricted-yaml), with no format line, as the Agent Skills
   specification requires. What a gate refuses, a malformed fence included, this refuses, and so a
   `SKILL.md` without front matter (`skill-unreadable`).
4. Its `name` is the entry's name, exactly, or the skill is refused (`skill-name-mismatch`): a harness
   would load it as that other name, which is not the skill that was shown and accepted.
5. Its front matter keys and its list of files are shown before it is delivered. Each key other than
   `name`, `description`, `license`, `compatibility` and `metadata` is reported as the
   [weakening](security.md#weakenings) `skill-keys`, with the skill and the key as its subject, since a
   harness may take such a key as a grant (`allowed-tools` pre-approves tools) or as code to run; a
   consumer MAY refuse the skill instead, and SHOULD for native delivery.

A refusal is reported with the overlay naming the skill, and the skill is not delivered.

**A fetched skill is a skill and nothing more.** Nothing in it is an overlay: a manifest inside it is a
file like any other, its `skills` and `requires` name nothing further, and nothing else is fetched
because of it. Nothing in it runs by default, no `setup.<ext>` or `env.<ext>` included, and nothing
installs a dependency file by its name, as for a [bundled skill](#contents).

## A consumer that does not fetch

**A consumer never goes without a skill silently.** A consumer that does not fetch skills, or has not
fetched these, delivers the bundled ones, and MUST report each skill from elsewhere as not delivered,
with the overlay naming it, wherever it reports what it did not apply. A read-only consumer lists them
as named, not as present. [Compatibility](../../compatibility.md#overlaymd-yaml-and-named-skills)
says what today's consumers do.

## Delivery

A consumer delivers a skill the way its harness takes one: natively where the harness loads skill
directories, or by a routing line naming the `SKILL.md`, since a skill is a file an agent can read.
A [harness hint](harness.md#harness-hints) can turn native delivery off for one harness. A fetched
skill is delivered like a bundled one. A consumer that reads a bundled `SKILL.md` whose front matter
gives another `name` does not deliver it under this one (`skill-name-mismatch`); one whose front matter
it cannot read it delivers as before, leaving that to the harness.

Two active overlays with skills whose names are equal without regard to ASCII case collide, since
a shared skills directory on Windows or macOS holds them as one, unless they name one skill from
elsewhere [alike](#resolving-a-name). A consumer reports the collision; by default the skill of the
overlay later in [composition order](composition.md#deterministic-ordering) is the one delivered, and
a consumer SHOULD let its configuration refuse the collision or name the winner instead. **A skill from
elsewhere never takes a name by default**: where it would win, the skill already holding the name stays
delivered and it is reported, whatever `priority` its overlay declares, since `priority` is the
overlay's own claim. Only the user's configuration can name it the winner.

> **Status:** dotagents publishes every `skills/<name>/` directory that holds a `SKILL.md` into a
> shared skills directory (a symlink where it can, a copy otherwise), tracks which overlay published
> it, and lists skills with their front matter in the context it assembles: the `skills` default.
> It does not read `skills`, except to refuse an overlay whose `skills` holds a name with no directory,
> or a table.

## Contents

A skill directory MAY contain scripts, examples, references and other assets. A consumer MUST NOT
treat a script as safe because it is under `skills/`. Dependencies a skill needs are declared by the
overlay's [`runtime`](runtime.md#runtime); a dependency file inside a skill is an asset, and nothing
installs it by its name.
