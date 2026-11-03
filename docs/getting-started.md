# Getting started

## Create your first overlay

An overlay can be as small as a directory with one instruction file:

```text
review-basics/
└── instructions.md
```

There is no required manifest. Add `overlay.cfg` when you want metadata or declarations:

```toml
name = "review-basics"
description = "Shared code review guidance."
routing = ["- Reviewing code → `$REVIEW_BASICS_OVERLAY_ROOT/instructions.md`"]
```

`overlay.cfg` is TOML unless its first line names another format. The same file in JSON:

```json
#!json
{
  "name": "review-basics",
  "description": "Shared code review guidance.",
  "routing": ["- Reviewing code → `$REVIEW_BASICS_OVERLAY_ROOT/instructions.md`"]
}
```

Refer to the overlay's own files with relative paths, and keep credentials out of it: an overlay
names where a secret comes from, never its value.

## Give it tools

Put helpers in `bin/` and declare that it goes on `PATH`:

```toml
[[paths]]
variable = "PATH"
path = "bin"
```

A setup step, a runtime and environment values are declared the same way; see
[Environment](spec/v0/environment.md) and [Runtime and setup](spec/v0/runtime.md).

## Use it

Choose a consumer that reads overlay directories. dotagents, the reference implementation, installs
one from a directory of overlays:

```console
dotagents overlays add review-basics --repo ./overlays
```

That is one manager's command; AOS requires neither dotagents nor a command line. A read-only
integration can show the files without installing them.

> dotagents reads `overlay.toml` today; see [Compatibility](compatibility.md).

## Next

Read [Authoring](authoring.md), then the [manifest](spec/v0/manifest.md),
[composition](spec/v0/composition.md) and [security](spec/v0/security.md).
