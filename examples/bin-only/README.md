# bin-only

An overlay with no `overlay.cfg` and a `bin/`. That is a working overlay: a consumer puts `bin/`
first on `PATH`, so the agent can call `todo-scan`. Nothing is declared, and nothing runs until
something calls it.
