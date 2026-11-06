---
name: shell-guard
description: Refuses force pushes from the agent's shell, and checks files after they are edited.
hooks:
  session-start:
    match: [new, resume]
  pre-tool:
    match: [execute]
    timeout: 5
    on_failure: refuse
  post-tool:
    run: hooks/after_edit.py
    match: [edit]
  turn-end: false
---
# Shell guard

A shell command that force-pushes is refused before it runs. Push with `--force-with-lease` instead, and
only to a branch you created.
