# conventions

An overlay with no `overlay.cfg`, in which every file takes effect by its name:

| File | Default |
| --- | --- |
| `bin/` | First on `PATH` |
| `lib/` | First on `PYTHONPATH` |
| `rules/always.md` | An always-on rules file |
| `CONTEXT.md` | Initial context |
| `skills/check-conventions/SKILL.md` | A skill |
| `env` | An env file, read as `dotenv`: literal values, nothing expanded |
| `env.py`, `env.sh` | The env script: `env.py` where Python can run, `env.sh` on another Unix-like host |
| `setup.sh` | Setup, on Unix-like hosts, once per digest |

The scripts run by default, and each run is reported. A setup that declares nothing is taken to need
the network, which is reported too; to deny it the network, declare it in `overlay.cfg` with
`network = false`. Writing any of these fields replaces its default, and an empty list turns it off.
