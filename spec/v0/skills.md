# Skills

**Optional Extension.** `skills/<name>/SKILL.md` is the portable layout of a skill: a directory named
after the skill with a `SKILL.md` inside. The Markdown is portable content; how a runtime discovers,
presents and invokes a skill belongs to that runtime.

## Declaring skills

**Proposed.** `skills` lists the overlay's skills by name:

```toml
skills = ["summarize-docs", "search-docs"]
```

Each name matches `[A-Za-z0-9][A-Za-z0-9_.-]*`, and `skills/<name>/SKILL.md` MUST exist; a validator
refuses a listed skill without it. When `skills` is present it is the complete list: a directory under
`skills/` that is not listed is not a skill of the overlay. When it is absent, every
`skills/<name>/SKILL.md` is a skill. A consumer that delivers skills delivers exactly these.

A skill's `SKILL.md` MAY begin with front matter that names it and describes it (`name:`,
`description:`). AOS does not require front matter; a runtime may.

## Delivery

A consumer delivers a skill the way its harness takes one: natively where the harness loads skill
directories, or by a routing line naming the `SKILL.md`, since a skill is a file an agent can read.
A [harness hint](harness.md#harness-hints) can turn native delivery off for one harness.

Two active overlays with a skill of the same name collide. A consumer reports the collision, and the
skill of the overlay later in [composition order](composition.md#deterministic-ordering) is the one
delivered.

> **Status:** dotagents publishes every `skills/<name>/` directory that holds a `SKILL.md` into a
> shared skills directory (a symlink where it can, a copy otherwise), tracks which overlay published
> it, and lists skills with their front matter in the context it assembles. It does not read
> `skills`.

## Contents

A skill directory MAY contain scripts, examples, references and other assets. A consumer MUST NOT
treat a script as safe because it is under `skills/`. Dependencies a skill needs are declared by the
overlay's [`runtime`](runtime.md#runtime); a dependency file inside a skill is an asset, and nothing
installs it by its name.
