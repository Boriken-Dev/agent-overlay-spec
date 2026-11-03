# Commands and executable assets

**Optional Extension.** `cmds/`, `bin/`, `scripts/`, and `lib/` are common conventions. Their presence does not make a package executable by itself.

Dotagents recognizes top-level `bin/<name>.py` files as Python command launchers and supports a `[scripts]` table to map names to relative script paths or disable discovered launchers with `false`. It also discovers dotagents command modules from `cmds/` under its own command model. These are **dotagents-specific** behaviors.

An implementation that advertises command execution MUST document command name resolution, arguments, working directory, environment, interpreter selection, permissions, timeout, output handling, and collision policy. It MUST NOT assume that Python is installed or required for AOS compliance.

`setup.py` or `setup.sh` at the root is an optional dotagents setup hook convention. It may run automatically during installation. Setup is executable code and MUST be treated as a trust boundary. AOS does not require setup hooks and does not define a cross-manager setup lifecycle.

Portable assets include the file bytes and their relative paths. Command launchers, environment-variable injection, library search paths, dependency installation, and setup behavior are implementation extensions.
