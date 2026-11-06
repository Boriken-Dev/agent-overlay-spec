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
MANIFEST_FREE = ("minimal", "bin-only", "conventions", "hook-script")


def example_roots() -> "list[Path]":
    """Every example overlay: a directory holding a manifest, plus the manifest-free ones."""
    roots = {path.parent for name in aos.MANIFEST_FILES for path in EXAMPLES.rglob(name)}
    roots.update(EXAMPLES / name for name in MANIFEST_FREE)
    return sorted(roots)


def manifest_of(root: Path) -> dict:
    files = {
        name: (root / name).read_bytes() for name in aos.MANIFEST_FILES if (root / name).is_file()
    }
    return aos.read_overlay(files)["manifest"]


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
    packages = {"python": "/envs/python/site-packages", "node": "/envs/node/node_modules"}
    result = aos.effective({}, dict(facts, files=texts, packages=packages))
    assert result["env"]["PATH"] == "/ov/c/bin"
    assert result["env"]["PYTHONPATH"] == "/ov/c/lib/python:/envs/python/site-packages"
    assert result["env"]["NODE_PATH"] == "/ov/c/lib/node:/envs/node/node_modules"
    assert result["dependencies"] == [
        {
            "runtime": "python",
            "file": "lib/python/requirements.txt",
            "lock": "lib/python/requirements.txt",
            "environment": "shared",
        },
        {
            "runtime": "node",
            "file": "lib/node/package.json",
            "lock": "lib/node/package-lock.json",
            "environment": "shared",
        },
    ]
    assert result["env"]["TOOL_BANNER"] == "Conventions: read only"
    assert result["env"]["TOOL_HOME"] == "/ov/c/tool"
    assert result["env"]["TOOL_CACHE"] == "/ov/c/tool/cache"
    assert [s["path"] for s in result["env_scripts"]] == ["env.py"]
    assert result["setup"]["path"] == "setup.sh" and result["setup"]["network"] is True
    added = aos.effective({}, dict(facts, files=texts, change="add", digest="sha256:" + "1" * 64))
    assert added["setup_arguments"] == ["install"]
    assert added["steps"] == ["empty-state", "deps:python", "deps:node", "setup", "record"]
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


def test_one_manifest_as_front_matter_reads_as_overlay_cfg():
    """Every field reads the same whichever file carries it, and in whichever format."""
    for name, line in (
        ("complete.cfg", "#!toml\n"),
        ("complete-json.cfg", ""),
        ("complete-yaml.cfg", ""),
    ):
        text = (FIXTURES / "valid" / name).read_bytes().decode("utf-8")
        wrapped = "---\n" + line + text + "---\nBody.\n"
        expected = aos.read_document(text.encode("utf-8"))
        found = aos.read_front_matter(wrapped.encode("utf-8"))
        assert found["case"] == "mapping", found
        assert found["data"] == expected


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
        ({"hooks": {"prompt": "hooks/prompt.py"}}, "/hooks/prompt"),
        ({"hooks": {"pre-tool": {"run": "hooks/guard.sh"}}}, "/hooks/pre-tool/run"),
        ({"hooks": {"pre-tool": {"match": ["execute"]}}}, "/hooks/pre-tool"),
    ],
)
def test_a_named_file_must_exist(doc, at):
    assert at in [found for _code, found in aos.validate(doc, set())]
    assert not aos.validate(doc)


def test_a_listed_skill_needs_no_directory_but_is_flagged():
    doc = {"skills": ["absent", {"name": "fetched", "source": "https://example.org/skills/x"}]}
    assert not aos.validate(doc, set())
    assert aos.skill_flags(doc, set()) == [("skill-from-catalog", "/skills/0")]
    assert aos.skill_flags(doc, {"skills/absent/SKILL.md"}) == []


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


REGISTRY = EXAMPLES / "registry"


def test_a_problem_in_about_never_stops_a_manifest_from_applying():
    for name, at in INVALID.items():
        if at == "/about" or at.startswith("/about/"):
            issues = aos.validate(aos.read_document((FIXTURES / "invalid" / name).read_bytes()))
            assert issues and aos.applies(issues), name


def test_about_changes_nothing_a_consumer_applies():
    root = EXAMPLES / "about"
    manifest = manifest_of(root)
    bare = {key: value for key, value in manifest.items() if key != "about"}
    assert manifest["about"] and bare != manifest
    files = {path: "" for path in aos.tree_files(root)}
    facts = {"os": "linux", "root": "/ov/a", "identity": "release-notes", "pinned": True}
    assert aos.effective(manifest, dict(facts, files=files)) == aos.effective(
        bare, dict(facts, files=files)
    )
    tree = {"release-notes": sorted(files)}
    assert aos.compose({"release-notes": manifest}, ["release-notes"], tree) == aos.compose(
        {"release-notes": bare}, ["release-notes"], tree
    )


@pytest.mark.parametrize("root", example_roots(), ids=lambda p: p.relative_to(EXAMPLES).as_posix())
def test_example_icon_is_one_a_store_shows(root):
    icon = manifest_of(root).get("about", {}).get("icon")
    if icon is not None:
        assert aos.read_icon((root / icon).read_bytes(), icon)


@pytest.mark.parametrize("name", ["registry.json", "registry.toml", "registry.yaml"])
def test_a_registry_is_a_catalog_in_the_minimal_form(name):
    data = (REGISTRY / name).read_bytes()
    assert not list(aos.CATALOG_VALIDATOR.iter_errors(aos.read_catalog_document(data, name)))
    catalog = aos.read_catalog(data, name, (REGISTRY / name).as_posix())
    assert catalog["form"] == "minimal"
    assert catalog["refused"] == [] and catalog["ignored"] == []
    assert sorted(catalog["entries"]) == ["engineering", "python-review"]


def test_the_example_overlay_md_reads_as_its_overlay_cfg_twin_would():
    root = EXAMPLES / "overlay-md"
    files = {path: (root / path).read_bytes() for path in aos.tree_files(root)}
    read = aos.read_overlay(files)
    assert read["manifest_file"] == "OVERLAY.md"
    assert read["context"] == ["OVERLAY.md", "kb/style.md"]
    assert read["context_ignored"] == []
    assert not read["issues"]
    assert read["manifest"]["name"] == "release-notes-md"
    assert read["manifest"]["about"]["summary"]
    body = aos.split_front_matter(files["OVERLAY.md"])
    assert files["OVERLAY.md"][body["body_offset"] :].strip()


def test_the_example_naming_skills_from_elsewhere():
    root = EXAMPLES / "skills-from-elsewhere"
    catalog_path = REGISTRY / "catalog.toml"
    catalog = aos.read_catalog(
        catalog_path.read_bytes(), catalog_path.name, catalog_path.as_posix()
    )
    manifest = manifest_of(root)
    files = aos.tree_files(root)
    assert [at for _code, at in aos.skill_flags(manifest, files)] == ["/skills/1"]
    found = aos.resolve_skills({"x": manifest}, ["x"], {"x": files}, [("examples", catalog)])
    assert {item["name"]: item["origin"] for item in found["skills"]} == {
        "summarize-docs": "bundled",
        "pdf": "catalog",
        "review": "source",
    }
    assert found["missing"] == [] and found["ambiguous"] == []
    assert found["unpinned"] == [["pdf", "x"]]


def test_the_example_catalog():
    path = REGISTRY / "catalog.toml"
    data = path.read_bytes()
    assert not list(aos.CATALOG_VALIDATOR.iter_errors(aos.read_catalog_document(data, path.name)))
    catalog = aos.read_catalog(data, path.name, path.as_posix())
    assert catalog["form"] == "full"
    assert catalog["refused"] == [] and catalog["ignored"] == []
    assert len(catalog["entries"]) == 3
    assert sorted(catalog["skills"]["entries"]) == ["pdf"] and not catalog["skills"]["refused"]
    for name, entry in catalog["entries"].items():
        icon = entry["about"]["icon"]
        assert aos.read_icon((REGISTRY / icon).read_bytes(), icon)
        root = Path(entry["source"]["location"])
        assert aos.normalize_name(manifest_of(root).get("name", root.name)) == name
        if "pin" in entry:
            assert aos.same_digest(entry["pin"], aos.tree_digest(root)), name


def test_the_example_hook_script_gets_the_events_without_content():
    root = EXAMPLES / "hook-script"
    plan = aos.hook_plan({}, {"os": "linux", "files": aos.tree_files(root), "scope": "user"})
    assert [entry["event"] for entry in plan["hooks"]] == [
        "pre-env",
        "session-start",
        "session-end",
        "turn-end",
        "cd",
        "pre-compact",
    ]
    assert {entry["path"] for entry in plan["hooks"]} == {"hook.py"}


def test_the_example_hooks_table():
    root = EXAMPLES / "hooks-table"
    manifest = manifest_of(root)
    plan = aos.hook_plan(manifest, {"os": "windows", "files": aos.tree_files(root)})
    by_event = {entry["event"]: entry for entry in plan["hooks"]}
    assert "turn-end" not in by_event and "prompt" not in by_event
    assert by_event["session-start"]["match"] == ["new", "resume"]
    assert by_event["pre-tool"]["path"] == "hook.py"
    assert by_event["pre-tool"]["on_failure"] == "refuse"
    assert by_event["post-tool"]["path"] == "hooks/after_edit.py"
    assert plan["on"] is False and plan["reports"] == [["hook-not-allowed", ""]]
