# hook-script

An overlay whose only file is `hook.py`. With no manifest, it runs by default at the events that carry
no content (`pre-env`, `session-start`, `session-end`, `turn-end`, `cd`, `pre-compact`), and never at
`prompt`, `pre-tool` or `post-tool`, which only `hooks` can give it. Like every overlay's hook, it is off
until the user allows it at the overlay's digest.
