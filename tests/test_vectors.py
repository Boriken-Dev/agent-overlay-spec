"""Every conformance vector in tests/vectors/, run through the reference reader."""

from __future__ import annotations

import base64
import json

import pytest

import aos_reference as aos

VECTORS = aos.ROOT / "tests" / "vectors"


def cases(name: str) -> "list[dict]":
    return json.loads((VECTORS / name).read_text(encoding="utf-8"))["cases"]


def ids(items: "list[dict]") -> "list[str]":
    return [case["id"] for case in items]


def strict(value):
    """A value with its types made visible, so 30 and 30.0, or 1 and True, never compare equal."""
    if isinstance(value, dict):
        return {key: strict(item) for key, item in value.items()}
    if isinstance(value, list):
        return [strict(item) for item in value]
    return (type(value).__name__, value)


def test_every_vector_file_is_run():
    run = {
        "digest.json",
        "reading.json",
        "validation.json",
        "names.json",
        "source.json",
        "compose.json",
        "effective.json",
    }
    assert {path.name for path in VECTORS.glob("*.json")} == run


def test_case_ids_are_unique():
    for path in VECTORS.glob("*.json"):
        found = ids(cases(path.name))
        assert len(found) == len(set(found)), path.name


READING = cases("reading.json")


@pytest.mark.parametrize("case", READING, ids=ids(READING))
def test_reading(case):
    data = base64.b64decode(case["base64"]) if "base64" in case else case["text"].encode("utf-8")
    limits = {"max_" + key[4:]: value for key, value in case.get("limits", {}).items()}
    expect = case["expect"]
    read = {
        "aos": aos.read_document,
        "dotenv": aos.read_dotenv,
        "env-script": aos.read_env_script_output,
    }[case["format"]]
    if "error" in expect and "data" in expect:
        try:
            got = read(data, **limits)
        except aos.ReadError as error:
            assert error.code == expect["error"]
        else:
            assert strict(got) == strict(expect["data"])
    elif "error" in expect:
        allowed = expect["error"] if isinstance(expect["error"], list) else [expect["error"]]
        with pytest.raises(aos.ReadError) as raised:
            read(data, **limits)
        assert raised.value.code in allowed
    else:
        assert strict(read(data, **limits)) == strict(expect["data"])


VALIDATION = cases("validation.json")


@pytest.mark.parametrize("case", VALIDATION, ids=ids(VALIDATION))
def test_validation(case):
    files = set(case["files"]) if "files" in case else None
    issues = aos.validate(case["document"], files)
    if case["expect"]["valid"]:
        assert not issues, issues
    else:
        at = case["expect"]["at"]
        assert any(
            found == at or found.startswith(at + "/") or (found and at.startswith(found + "/"))
            for _code, found in issues
        ), (at, issues)


NAMES = cases("names.json")


@pytest.mark.parametrize("case", NAMES, ids=ids(NAMES))
def test_names(case):
    expect = case["expect"]
    assert aos.valid_overlay_name(case["name"]) is expect["valid"]
    if expect["valid"]:
        assert aos.normalize_name(case["name"]) == expect["normalized"]
        assert aos.root_variable(case["name"]) == expect["variable"]


SOURCES = cases("source.json")


@pytest.mark.parametrize("case", SOURCES, ids=ids(SOURCES))
def test_source(case):
    if "error" in case["expect"]:
        with pytest.raises(ValueError):
            aos.parse_source(case["source"])
    else:
        assert aos.parse_source(case["source"]) == case["expect"]


COMPOSE = cases("compose.json")


@pytest.mark.parametrize("case", COMPOSE, ids=ids(COMPOSE))
def test_compose(case):
    result = aos.compose(case["overlays"], case["requested"], case.get("files"), case.get("facts"))
    if "facts" in case:
        result = {"active": result["active"], "env": result.get("env", result.get("env_error"))}
    assert json.loads(json.dumps(result)) == case["expect"]


EFFECTIVE = cases("effective.json")


@pytest.mark.parametrize("case", EFFECTIVE, ids=ids(EFFECTIVE))
def test_effective(case):
    result = aos.effective(case["manifest"], case["facts"])
    assert strict(json.loads(json.dumps(result))) == strict(case["expect"])
