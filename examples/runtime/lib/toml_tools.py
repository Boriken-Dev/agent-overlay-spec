"""Prints the top-level keys of a TOML file, with the locked tomli on Python 3.9 and 3.10."""

import sys

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

if __name__ == "__main__":
    with open(sys.argv[1], "rb") as handle:
        print("\n".join(sorted(tomllib.load(handle))))
