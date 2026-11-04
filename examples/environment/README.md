# docs-tools

An overlay whose environment is declared, not computed: `overlay.cfg` sets literals, a path under
the overlay root, and two secret references, reads three env files, and puts `bin/` first on `PATH`
and `lib/` last on `PYTHONPATH`. A written `paths` replaces the default one, so it names `bin/` too.
