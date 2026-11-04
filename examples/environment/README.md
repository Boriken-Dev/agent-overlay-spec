# docs-tools

An overlay whose environment is declared, not computed: `overlay.cfg` sets literals, a path under
the overlay root, and two secret references, reads three env files, and puts `bin/` first on `PATH`
and `lib/python/` last on `PYTHONPATH`. `bin/` is there by default; the declared `paths` entry
names `lib/python`, so it replaces that default and appends it instead of prepending it.
