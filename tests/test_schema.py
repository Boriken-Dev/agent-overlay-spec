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


#: Example overlays with no manifest.
MANIFEST_FREE = ("minimal", "bin-only", "conventions")


def example_roots() -> "list[Path]":
    """Every example overlay: a directory holding overlay.cfg, plus the manifest-free ones."""
    roots = {path.parent for path in EXAMPLES.rglob("overlay.cfg")}
    roots.update(EXAMPLES / name for name in MANIFEST_FREE)
    return sorted(roots)


def manifest_of(root: Path) -> dict:
    path = root / "overlay.cfg"
    return aos.read_document(path.read_bytes()) if path.is_file() else {}


@pytest.mark.parametrize("root", example_roots(), ids=lambda p: p.relative_to(EXAMPLES).as_posix())
def test_example_is_valid_with_its_files(root):
    issues = aos.validate(manifest_of(root), aos.tree_files(root))
    assert not issues, issues


def test_no_example_file_is_ignored_by_git():
    """A case-insensitive checkout can ignore a file another platform's checkout needs."""
    import shutil
    import subprocess

    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    ignored = subprocess.run(
        [
            "git",
            "ls-files",
            "--others",
            "--ignored",
            "--exclude-standard",
            "--",
            "examples",
            "tests",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert [path for path in ignored if "__pycache__" not in path] == []


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
    for entry in aos.env_files_of(manifest_of(root), aos.tree_files(root)):
        entry = {"path": entry} if isinstance(entry, str) else entry
        data = (root / entry["path"]).read_bytes()
        if entry.get("format", "aos") == "dotenv":
            assert aos.parse_dotenv(data)
        else:
            env = aos.read_document(data)
            assert not aos.validate({"env": env}), entry["path"]


def test_a_bin_alone_is_a_working_overlay():
    root = EXAMPLES / "bin-only"
    assert not (root / "overlay.cfg").exists()
    files = {path: "" for path in aos.tree_files(root)}
    facts = {"os": "linux", "root": "/ov/bin-only", "identity": "bin-only", "pinned": True}
    result = aos.effective({}, dict(facts, files=files, base_env={"PATH": "/usr/bin"}))
    assert result["env"]["PATH"] == "/ov/bin-only/bin:/usr/bin"
    assert result["env_scripts"] == [] and result["setup"] is None


def test_every_default_in_the_conventions_example():
    root = EXAMPLES / "conventions"
    files = aos.tree_files(root)
    facts = {"os": "linux", "root": "/ov/c", "identity": "conventions", "pinned": True}
    texts = {path: (root / path).read_text(encoding="utf-8") for path in files}
    result = aos.effective({}, dict(facts, files=texts))
    assert result["env"]["PATH"] == "/ov/c/bin"
    assert result["env"]["PYTHONPATH"] == "/ov/c/lib/python"
    assert result["env"]["TOOL_BANNER"] == "Conventions: read only"
    assert result["env"]["TOOL_HOME"] == "/ov/c/tool"
    assert result["env"]["TOOL_CACHE"] == "/ov/c/tool/cache"
    assert [s["path"] for s in result["env_scripts"]] == ["env.py"]
    assert result["setup"]["path"] == "setup.sh" and result["setup"]["network"] is True
    added = aos.effective({}, dict(facts, files=texts, change="add", digest="sha256:" + "1" * 64))
    assert added["setup_arguments"] == ["install"]
    assert aos.rules_of({}, files) == ["rules/always.md"]
    assert aos.context_of({}, files) == ["CONTEXT.md"]
    assert aos.skills_of({}, files) == ["check-conventions"]


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
