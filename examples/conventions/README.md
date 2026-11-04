# conventions

An overlay with no `overlay.cfg`, in which every file takes effect by its name:

| File | Default |
| --- | --- |
| `bin/` | First on `PATH` |
| `lib/python/` | First on `PYTHONPATH` |
| `lib/python/requirements.txt` | Installed into the scope's shared Python environment; a hash on every requirement makes it a lock |
| `lib/node/` | First on `NODE_PATH` |
| `lib/node/package.json` | Installed into the scope's shared `node_modules` with `npm ci`, since `package-lock.json` is beside it |
| `rules/always.md` | An always-on rules file |
| `CONTEXT.md` | Initial context |
| `skills/check-conventions/SKILL.md` | A skill |
| `env` | An env file, read as `dotenv`: `${NAME}` placeholders substituted line by line, nothing run |
| `env.py`, `env.sh` | The env script: `env.py` where Python can run, `env.sh` on another Unix-like host |
| `setup.sh` | Setup, on Unix-like hosts, after the dependencies, told its phase: `install` on the first add, `sync` on every sync, `remove` |

The scripts run by default, and each run is reported. Installing the dependencies needs the network,
and so does a setup that declares nothing; both are reported; to deny it the network, declare an entry naming `setup.sh` in
`overlay.cfg`, where `network` defaults to `false`. Declared entries add to these defaults, and
`[defaults]` turns one off, such as `setup = false`.
