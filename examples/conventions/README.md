# conventions

An overlay with no `overlay.cfg`, in which every file takes effect by its name:

| File | Default |
| --- | --- |
| `bin/` | First on `PATH` |
| `lib/python/` | First on `PYTHONPATH` |
| `rules/always.md` | An always-on rules file |
| `CONTEXT.md` | Initial context |
| `skills/check-conventions/SKILL.md` | A skill |
| `env` | An env file, read as `dotenv`: `${NAME}` placeholders substituted line by line, nothing run |
| `env.py`, `env.sh` | The env script: `env.py` where Python can run, `env.sh` on another Unix-like host |
| `setup.sh` | Setup, on Unix-like hosts, told its phase: `install`, `sync` for each new digest, `remove` |

The scripts run by default, and each run is reported. A setup that declares nothing is taken to need
the network, which is reported too; to deny it the network, declare an entry naming `setup.sh` in
`overlay.cfg`, where `network` defaults to `false`. Declared entries add to these defaults, and
`[defaults]` turns one off, such as `setup = false`.
