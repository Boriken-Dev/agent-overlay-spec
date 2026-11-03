# Skills

**Optional Extension.** `skills/<name>/SKILL.md` is a portable convention for a skill package. The Markdown instructions are portable content; runtime discovery, front matter, publication path, and invocation semantics belong to the target runtime or manager.

Dotagents publishes each overlay skill directory into a scope's shared skills directory, preferring symlinks where possible and using copies where needed. It tracks ownership so removing an overlay can unpublish its skill without removing a separately owned copy. A skill must contain `SKILL.md` for dotagents discovery. Other runtimes may impose additional metadata.

Skill folders MAY contain scripts, examples, references, and assets. An implementation MUST NOT assume these scripts are safe because they are stored under `skills/`. It MAY support scripts in any language. Python execution is not a core requirement.

`requirements.txt`, `package.json`, lock files, and other dependency manifests MAY be included as assets. Installing dependencies is optional and requires an explicit manager policy and trust decision. AOS defines no universal dependency installation step or environment variable contract.
