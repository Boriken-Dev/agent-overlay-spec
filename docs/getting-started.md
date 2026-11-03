# Getting started

## Create your first overlay

An overlay can be as small as a directory containing one instruction file:

```text
review-basics/
└── instructions.md
```

There is no required manifest. Add `overlay.toml` when you want metadata or supported declarations:

```toml
name = "review-basics"
description = "Shared code review guidance."
routing = ["- Reviewing code → `$REVIEW_BASICS_OVERLAY_ROOT/instructions.md`"]
```

Keep an overlay portable by referring to included assets with relative paths. Do not place credentials in the package.

## Use it

Choose a manager that can read local overlay directories. For example, dotagents can add a directory containing one or more overlays:

```console
dotagents overlays add review-basics --repo ./overlays
```

This is one manager's command; AOS does not require dotagents or a CLI. A read-only integration can also display the files without installing them.

## Next

Read [Authoring](authoring.md), then the [manifest reference](spec/v0/manifest.md), [composition model](spec/v0/composition.md), and [security guidance](spec/v0/security.md).
