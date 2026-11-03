from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "overlay.schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


def manifests():
    yield {}  # A manifest-free overlay parses as an empty document.
    yield from (
        tomllib.loads(path.read_text(encoding="utf-8"))
        for path in sorted((ROOT / "examples").rglob("overlay.toml"))
    )


@pytest.mark.parametrize("manifest", list(manifests()))
def test_examples_validate_against_schema(manifest):
    errors = sorted(VALIDATOR.iter_errors(manifest), key=lambda error: list(error.path))
    assert not errors, "\n".join(error.message for error in errors)


@pytest.mark.parametrize("path", sorted((ROOT / "tests" / "fixtures" / "invalid").glob("*.toml")))
def test_invalid_fixtures_fail_schema(path):
    manifest = tomllib.loads(path.read_text(encoding="utf-8"))
    assert list(VALIDATOR.iter_errors(manifest)), path.name


@pytest.mark.parametrize("path", sorted((ROOT / "tests" / "fixtures" / "valid").glob("*.toml")))
def test_valid_fixtures_pass_schema(path):
    manifest = tomllib.loads(path.read_text(encoding="utf-8"))
    errors = sorted(VALIDATOR.iter_errors(manifest), key=lambda error: list(error.path))
    assert not errors, "\n".join(error.message for error in errors)


def test_schema_allows_unknown_top_level_extension_fields():
    assert VALIDATOR.is_valid({"name": "legacy", "organization_extension": {"mode": "custom"}})


def test_schema_accepts_false_script_disable_value():
    assert VALIDATOR.is_valid({"scripts": {"old-command": False}})


def test_schema_accepts_empty_name_used_by_reference_fallback():
    assert VALIDATOR.is_valid({"name": ""})


def test_downloaded_docs_schema_matches_normative_schema():
    docs_schema = json.loads((ROOT / "docs" / "schemas" / "overlay.schema.json").read_text(encoding="utf-8"))
    assert docs_schema == SCHEMA
