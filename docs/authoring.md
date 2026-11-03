# Authoring overlays

## Package layout

Keep each overlay in its own directory. Use paths that describe the asset type and use relative references to files in that overlay. Common paths include `rules/`, `skills/`, `kb/`, `references/`, `workflows/`, `cmds/`, `bin/`, and `lib/`; only `overlay.toml` and `skills/<name>/SKILL.md` have named conventions in this draft.

## Optional manifest

Start with only the fields your consumers use:

```toml
name = "team-review"
description = "Review conventions for shared services."
requires = ["engineering-basics"]
routing = ["- Service reviews → `$TEAM_REVIEW_OVERLAY_ROOT/kb/review.md`"]
rules = ["rules/review.md"]
priority = 450
```

See the [manifest field reference](spec/v0/manifest.md) for types, defaults, and dotagents compatibility details. Do not add a required format version; this draft does not define one.

## Skills and commands

Put a skill in `skills/<skill-name>/SKILL.md`. Additional files can be placed beside it. A `bin/` script or `[scripts]` mapping is optional and does not guarantee another manager can run it. State the required runtime in your documentation.

## Authoring checks

Validate TOML syntax, paths, and field types before distribution. Keep credentials out of manifests. Review setup hooks, scripts, and dependency declarations as code. Run this repository's fixtures with `python -m pytest` when changing the schema or examples.
