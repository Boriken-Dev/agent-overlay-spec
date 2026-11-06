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
        "catalog.json",
        "front_matter.json",
        "skills.json",
        "hooks.json",
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
        "dotenv": lambda data: aos.read_dotenv(
            data,
            case.get("env", {}),
            case.get("os") == "windows",
            case.get("secret_variables", ()),
        ),
        "env-script": aos.read_env_script_output,
        "catalog": lambda data, **limits: aos.read_catalog_document(data, case["name"], **limits),
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
    if "applies" in case["expect"]:
        assert aos.applies(issues) is case["expect"]["applies"], issues
    if case["expect"]["valid"]:
        assert not issues, issues
        if files is not None:
            flags = [at for _code, at in aos.skill_flags(case["document"], files)]
            assert flags == case["expect"].get("flags", [])
    else:
        at = case["expect"]["at"]
        if "class" in case["expect"]:
            assert (case["expect"]["class"], at) in issues, issues
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
        reduced = {"active": result["active"], "env": result.get("env", result.get("env_error"))}
        # Dependency environments and hook reports are checked where a case states them.
        for key in (
            "environments",
            "conflicts",
            "blocked",
            "left",
            "hook_reports",
            "hook_weakenings",
        ):
            if key in case["expect"]:
                reduced[key] = result[key]
        result = reduced
    assert json.loads(json.dumps(result)) == case["expect"]


EFFECTIVE = cases("effective.json")


@pytest.mark.parametrize("case", EFFECTIVE, ids=ids(EFFECTIVE))
def test_effective(case):
    result = aos.effective(case["manifest"], case["facts"])
    assert strict(json.loads(json.dumps(result))) == strict(case["expect"])


CATALOG = cases("catalog.json")


def read_catalog(item: dict) -> dict:
    return aos.read_catalog(item["text"].encode("utf-8"), item["name"], item.get("base"))


@pytest.mark.parametrize("case", CATALOG, ids=ids(CATALOG))
def test_catalog(case):
    if "icon" in case:
        icon = case["icon"]
        try:
            got = aos.read_icon(
                base64.b64decode(icon["base64"]), icon["name"], **icon.get("limits", {})
            )
        except aos.IconError as error:
            got = {"error": error.code}
    elif "catalogs" in case:
        try:
            listing = aos.list_catalogs(
                [(item["label"], read_catalog(item)) for item in case["catalogs"]]
            )
        except aos.ReadError as error:
            got = {"error": error.code}
        else:
            got = dict(listing, chosen={name: aos.choose(listing, name) for name in case["choose"]})
    else:
        try:
            got = read_catalog(case["catalog"])
        except aos.ReadError as error:
            got = {"error": error.code}
    assert strict(json.loads(json.dumps(got))) == strict(case["expect"])


FRONT_MATTER = cases("front_matter.json")


def document_bytes(case: dict) -> bytes:
    if "parts" in case:
        return "".join(text * times for text, times in case["parts"]).encode("utf-8")
    if "base64" in case:
        return base64.b64decode(case["base64"])
    return case["text"].encode("utf-8")


def slice_of(expect: dict, key: str, data: bytes) -> None:
    """A slice of the input, against how the vector gives it: text, base64 or its size."""
    if key + "_size" in expect:
        assert len(data) == expect[key + "_size"]
    elif key + "_base64" in expect:
        assert data == base64.b64decode(expect[key + "_base64"])
    else:
        assert data == expect[key].encode("utf-8")


def check_document(case: dict) -> None:
    data = document_bytes(case)
    found = aos.read_front_matter(data, **case.get("limits", {}))
    expect = case["expect"]
    assert found["case"] == expect["case"]
    for key in ("metadata_offset", "metadata_line", "body_offset", "body_line", "format"):
        assert found.get(key) == expect.get(key), key
    allowed = expect.get("error")
    allowed = allowed if isinstance(allowed, list) else [allowed]
    assert found.get("error") in allowed
    if "line" in expect:
        assert found["line"] == expect["line"]
    if "metadata_offset" in expect:
        slice_of(expect, "metadata", found["metadata"])
    if "body_offset" in expect:
        slice_of(expect, "body", data[expect["body_offset"] :])
    if "data" in expect:
        assert strict(found["data"]) == strict(expect["data"])
    else:
        assert "data" not in found


def check_context_file(case: dict) -> None:
    data = case["context_file"].encode("utf-8")
    try:
        got = {"text": aos.context_file_text(data, **case.get("limits", {})).decode("utf-8")}
    except aos.ReadError as error:
        got = {"error": error.code}
    assert got == case["expect"]


def check_overlay(case: dict) -> None:
    files = {
        path: (
            base64.b64decode(value["base64"]) if isinstance(value, dict) else value.encode("utf-8")
        )
        for path, value in case["files"].items()
    }
    expect = case["expect"]
    if "error" in expect:
        with pytest.raises(aos.ReadError) as raised:
            aos.read_overlay(files, **case.get("limits", {}))
        assert raised.value.code == expect["error"]
        if "line" in expect:
            assert raised.value.line == expect["line"]
        return
    got = aos.read_overlay(files, **case.get("limits", {}))
    got["applies"] = aos.applies(aos.validate(got["manifest"], set(files)))
    if "digest" in expect:
        got["digest"] = aos.digest_entries(
            [((path.encode("utf-8"),), "file", value) for path, value in files.items()]
        )[0]
    assert strict(got) == strict(expect)


@pytest.mark.parametrize("case", FRONT_MATTER, ids=ids(FRONT_MATTER))
def test_front_matter(case):
    if "files" in case:
        check_overlay(case)
    elif "context_file" in case:
        check_context_file(case)
    else:
        check_document(case)


SKILLS = cases("skills.json")


@pytest.mark.parametrize("case", SKILLS, ids=ids(SKILLS))
def test_skills(case):
    if "fetched" in case:
        try:
            got = aos.read_fetched_skill(case["name"], case["fetched"], case.get("pin"))
        except aos.ReadError as error:
            got = {"error": error.code}
    else:
        catalogs = [(item["label"], read_catalog(item)) for item in case.get("catalogs", [])]
        got = aos.resolve_skills(
            case["overlays"],
            case["requested"],
            case.get("files", {}),
            catalogs,
            case.get("order", ()),
            case.get("fetches", True),
        )
    assert strict(json.loads(json.dumps(got))) == strict(case["expect"])


HOOKS = cases("hooks.json")


def hook_plan(case: dict) -> dict:
    facts = dict(case["facts"])
    files = facts["files"]
    if "manifest" in case:
        manifest = case["manifest"]
        issues = [at for _code, at in aos.validate(manifest, set(files))]
    else:
        read = aos.read_overlay({path: text.encode("utf-8") for path, text in files.items()})
        manifest, issues = read["manifest"], read["issues"]
    facts["files"] = list(files)
    return dict(aos.hook_plan(manifest, facts), issues=sorted(set(issues)))


@pytest.mark.parametrize("case", HOOKS, ids=ids(HOOKS))
def test_hooks(case):
    kind = case["id"].split("-", 1)[0]
    if kind == "plan":
        got = hook_plan(case)
    elif kind == "payload":
        got = aos.hook_payload(case["event"], case["known"])
    elif kind == "output":
        try:
            got = {"output": aos.hook_result(case["event"], case["run"], case.get("limits", {}))}
        except aos.HookFailure as failure:
            got = {"failed": failure.cause}
    elif kind == "match":
        got = {"runs": aos.hook_matches(case["event"], case["match"], case["value"])}
    else:
        got = aos.fire_event(
            case["event"],
            case["runs"],
            case.get("applies"),
            case.get("limits"),
            case.get("os") == "windows",
        )
    assert strict(json.loads(json.dumps(got))) == strict(case["expect"])
