"""Importable through PYTHONPATH, which the overlay appends `lib/` to."""


def banner() -> str:
    import os

    return os.environ.get("TOOL_BANNER", "")
