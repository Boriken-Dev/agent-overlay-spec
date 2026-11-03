"""The schema and the semantic checks over the examples and fixtures."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import aos_reference as aos

ROOT = aos.ROOT
EXAMPLES = ROOT / "examples"
FIXTURES = ROOT / "tests" / "fixtures"


def example_roots() -> "list[Path]":
    """Every example overlay: a directory holding overlay.cfg, plus the manifest-free one."""
    roots = {path.parent for path in EXAMPLES.rglob("overlay.cfg")}
    roots.add(EXAMPLES / "minimal")
    return sorted(roots)


def manifest_of(root: Path) -> dict:
    path = root / "overlay.cfg"
    return aos.read_document(path.read_bytes()) if path.is_file() else {}


@pytest.mark.parametrize("root", example_roots(), ids=lambda p: p.relative_to(EXAMPLES).as_posix())
def test_example_is_valid_with_its_files(root):
    issues = aos.validate(manifest_of(root), aos.tree_files(root))
    assert not issues, issues


def test_no_example_uses_the_old_manifest_name():
    assert not list(EXAMPLES.rglob("overlay.toml"))


@pytest.mark.parametrize("root", example_roots(), ids=lambda p: p.relative_to(EXAMPLES).as_posix())
def test_example_lock_digests_match_their_files(root):
    runtime = manifest_of(root).get("runtime", {})
    for variant in runtime.get("python", []):
        if "lock_digest" in variant:
            digest = hashlib.sha256((root / variant["lock"]).read_bytes()).hexdigest()
            assert variant["lock_digest"].lower() == "sha256:" + digest, variant["lock"]


@pytest.mark.parametrize("root", example_roots(), ids=lambda p: p.relative_to(EXAMPLES).as_posix())
def test_example_env_files_read(root):
    for entry in manifest_of(root).get("env_files", []):
        entry = {"path": entry} if isinstance(entry, str) else entry
        data = (root / entry["path"]).read_bytes()
        if entry.get("format", "aos") == "dotenv":
            assert aos.read_dotenv(data)
        else:
            env = aos.read_document(data)
            assert not aos.validate({"env": env}), entry["path"]


@pytest.mark.parametrize("path", sorted((FIXTURES / "valid").glob("*.cfg")), ids=lambda p: p.name)
def test_valid_fixture(path):
    issues = aos.validate(aos.read_document(path.read_bytes()))
    assert not issues, issues


def test_one_manifest_in_three_formats_reads_the_same():
    toml, as_json, as_yaml = (
        aos.read_document((FIXTURES / "valid" / name).read_bytes())
        for name in ("complete.cfg", "complete-json.cfg", "complete-yaml.cfg")
    )
    assert toml == as_json == as_yaml


INVALID = json.loads((FIXTURES / "invalid" / "expect.json").read_text(encoding="utf-8"))


def test_every_invalid_fixture_has_an_expectation():
    assert sorted(INVALID) == sorted(p.name for p in (FIXTURES / "invalid").glob("*.cfg"))


@pytest.mark.parametrize("name", sorted(INVALID))
def test_invalid_fixture_is_refused_where_expected(name):
    issues = aos.validate(aos.read_document((FIXTURES / "invalid" / name).read_bytes()))
    at = INVALID[name]
    assert any(
        found == at or found.startswith(at + "/") or (found and at.startswith(found + "/"))
        for _code, found in issues
    ), (at, issues)


@pytest.mark.parametrize(
    "doc, at",
    [
        ({"rules": ["rules/missing.md"]}, "/rules/0"),
        ({"context": ["CONTEXT.md"]}, "/context/0"),
        ({"env_files": [{"path": "env/a.env", "format": "dotenv"}]}, "/env_files/0/path"),
        ({"setup": [{"interpreter": "sh", "path": "setup.sh"}]}, "/setup/0/path"),
        ({"runtime": {"python": [{"lock": "l.txt"}]}}, "/runtime/python/0/lock"),
        ({"scripts": {"x": "bin/x.py"}}, "/scripts/x"),
        ({"harness": {"codex": {"context": ["a.md"]}}}, "/harness/codex/context/0"),
        ({"skills": ["absent"]}, "/skills/0"),
    ],
)
def test_a_named_file_must_exist(doc, at):
    assert at in [found for _code, found in aos.validate(doc, set())]
    assert not aos.validate(doc)


def test_schema_allows_unknown_top_level_keys():
    assert not aos.validate({"name": "legacy", "organization_extension": {"mode": "custom"}})


def test_schema_refuses_null_in_unknown_keys():
    assert aos.validate({"organization_extension": {"mode": None}})


def test_schema_accepts_false_to_disable_a_script():
    assert not aos.validate({"scripts": {"old-command": False}})


def test_schema_accepts_an_empty_name():
    assert not aos.validate({"name": ""})


def test_site_copy_of_the_schema_matches():
    site = json.loads(
        (ROOT / "docs" / "schemas" / "overlay.schema.json").read_text(encoding="utf-8")
    )
    assert site == aos.SCHEMA
