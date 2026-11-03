"""A small reference reader for AOS, used by this repository's tests and conformance vectors.

It follows the specification's text and nothing else: where the two disagree, the specification
is right and this module has a bug. It is test code, not a library.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Iterable, Optional

import yaml
from jsonschema import Draft202012Validator, FormatChecker

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "overlay.schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())

#: Formats this reader supports, by every name a format line may use.
FORMATS = {"toml": "toml", "json": "json", "yaml": "yaml", "yml": "yaml"}
DEFAULT_MAX_BYTES = 1024 * 1024
DEFAULT_MAX_DEPTH = 64
INT_MIN, INT_MAX = -(2**63), 2**63 - 1
_SAFE_FORMAT_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


class ReadError(Exception):
    """A document AOS refuses. ``code`` is the vectors' error class."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__("%s: %s" % (code, detail) if detail else code)
        self.code = code
        self.detail = detail


# --------------------------------------------------------------------------------------------
# Reading: bytes to the data model.
# --------------------------------------------------------------------------------------------


def select_format(data: bytes) -> "tuple[str, bytes]":
    """The format name a document selects and the bytes its parser is given."""
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    if not data.startswith(b"#!"):
        return "toml", data
    end = data.find(b"\n")
    line, rest = (data[2:], b"") if end < 0 else (data[2:end], data[end + 1 :])
    try:
        text = line.decode("utf-8")
    except UnicodeDecodeError:
        raise ReadError("invalid-utf8", "the format line")
    # str.split() also splits on Unicode spaces; the rule is space, tab, form feed and CR only.
    words = [word for word in re.split(r"[ \t\x0c\r]+", text) if word]
    word = words[-1] if words else ""
    word = re.split(r"[/\\]", word)[-1].lstrip(".")
    word = "".join(c.lower() if "A" <= c <= "Z" else c for c in word)
    if not word:
        raise ReadError("no-format-named")
    return word, rest


def read_document(
    data: bytes, *, max_bytes: int = DEFAULT_MAX_BYTES, max_depth: int = DEFAULT_MAX_DEPTH
) -> "dict[str, Any]":
    """Read ``data`` as an AOS document (``overlay.cfg`` or an ``aos`` env file)."""
    if len(data) > max_bytes:
        raise ReadError("too-large")
    name, payload = select_format(data)
    if name not in FORMATS:
        shown = name if _SAFE_FORMAT_NAME.match(name) else "(not shown)"
        raise ReadError("unsupported-format", shown)
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        raise ReadError("invalid-utf8")
    if not text.strip(" \t\r\n"):
        return {}
    kind = FORMATS[name]
    if kind == "toml":
        try:
            value = tomllib.loads(text)
        except tomllib.TOMLDecodeError as error:
            raise ReadError("parse-error", str(error))
    elif kind == "json":
        value = _read_json(text)
    else:
        value = _read_yaml(text)
    if not isinstance(value, dict):
        raise ReadError("not-a-mapping")
    _check_model(value, 1, max_depth)
    return value


def _read_json(text: str) -> Any:
    def pairs(items: "list[tuple[str, Any]]") -> "dict[str, Any]":
        out: "dict[str, Any]" = {}
        for key, value in items:
            if key in out:
                raise ReadError("duplicate-key", key)
            out[key] = value
        return out

    def constant(name: str) -> Any:
        raise ReadError("parse-error", "%s is not JSON" % name)

    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except json.JSONDecodeError as error:
        raise ReadError("parse-error", str(error))


_YAML_INT = re.compile(r"^[-+]?[0-9]+$")
_YAML_OCT = re.compile(r"^0o[0-7]+$")
_YAML_HEX = re.compile(r"^0x[0-9a-fA-F]+$")
_YAML_FLOAT = re.compile(r"^[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?$")
_YAML_INF = re.compile(r"^[-+]?\.(?:inf|Inf|INF)$")
_YAML_NAN = re.compile(r"^\.(?:nan|NaN|NAN)$")


def _yaml_scalar(event: "yaml.ScalarEvent") -> Any:
    """A scalar under the YAML 1.2 core schema; quoted scalars are strings."""
    if event.style is not None:
        return event.value
    value = event.value
    if value in ("", "~", "null", "Null", "NULL"):
        raise ReadError("null-value")
    if value in ("true", "True", "TRUE"):
        return True
    if value in ("false", "False", "FALSE"):
        return False
    if _YAML_INT.match(value):
        return int(value)
    if _YAML_OCT.match(value):
        return int(value[2:], 8)
    if _YAML_HEX.match(value):
        return int(value[2:], 16)
    if _YAML_FLOAT.match(value):
        return float(value)
    if _YAML_INF.match(value) or _YAML_NAN.match(value):
        raise ReadError("non-finite-float")
    return value


def _read_yaml(text: str) -> Any:
    """One YAML document, built from parser events so no tag, anchor or merge key is applied."""
    try:
        events = list(yaml.parse(text, Loader=yaml.SafeLoader))
    except yaml.YAMLError as error:
        raise ReadError("parse-error", str(error).splitlines()[0])
    stack: "list[Any]" = []
    keys: "list[Optional[str]]" = []
    root: Any = None
    documents = 0

    def add(value: Any) -> None:
        nonlocal root
        if not stack:
            root = value
            return
        top = stack[-1]
        if isinstance(top, list):
            top.append(value)
        elif keys[-1] is None:
            if not isinstance(value, str):
                raise ReadError("non-string-key")
            if value == "<<":
                raise ReadError("yaml-merge-key")
            if value in top:
                raise ReadError("duplicate-key", value)
            keys[-1] = value
        else:
            top[keys[-1]] = value
            keys[-1] = None

    for event in events:
        if isinstance(event, yaml.AliasEvent):
            raise ReadError("yaml-anchor", "alias")
        if getattr(event, "anchor", None) is not None:
            raise ReadError("yaml-anchor", "anchor")
        if getattr(event, "tag", None) is not None:
            raise ReadError("yaml-tag")
        if isinstance(event, yaml.DocumentStartEvent):
            documents += 1
            if documents > 1:
                raise ReadError("parse-error", "more than one document")
        elif isinstance(event, yaml.ScalarEvent):
            add(_yaml_scalar(event))
        elif isinstance(event, yaml.SequenceStartEvent):
            value: Any = []
            add(value)
            stack.append(value)
            keys.append(None)
        elif isinstance(event, yaml.MappingStartEvent):
            value = {}
            add(value)
            stack.append(value)
            keys.append(None)
        elif isinstance(event, (yaml.SequenceEndEvent, yaml.MappingEndEvent)):
            stack.pop()
            keys.pop()
    return {} if documents == 0 or root is None else root


def _check_model(value: Any, depth: int, max_depth: int) -> None:
    """Refuse what the data model has no type for, at any depth."""
    if depth > max_depth:
        raise ReadError("too-deep")
    if value is None:
        raise ReadError("null-value")
    if isinstance(value, bool) or isinstance(value, str):
        if isinstance(value, str):
            try:
                value.encode("utf-8")
            except UnicodeEncodeError:
                raise ReadError("invalid-unicode")
        return
    if isinstance(value, int):
        if not INT_MIN <= value <= INT_MAX:
            raise ReadError("integer-range")
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ReadError("non-finite-float")
        return
    if isinstance(value, list):
        for item in value:
            _check_model(item, depth + 1, max_depth)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ReadError("non-string-key")
            _check_model(key, depth, max_depth)
            _check_model(item, depth + 1, max_depth)
        return
    # TOML dates and times, and anything else a parser may produce.
    raise ReadError("datetime-value" if hasattr(value, "isoformat") else "unsupported-value")


_DOTENV_LINE = re.compile(r"^[ \t]*(?:export[ \t]+)?([A-Za-z_][A-Za-z0-9_]*)[ \t]*=(.*)$")


def read_dotenv(data: bytes) -> "dict[str, str]":
    """A ``dotenv`` env file: literal values, no references, escapes or expansion."""
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise ReadError("invalid-utf8")
    out: "dict[str, str]" = {}
    for line in text.split("\n"):
        if line.endswith("\r"):
            line = line[:-1]
        stripped = line.strip(" \t")
        if not stripped or stripped.startswith("#"):
            continue
        match = _DOTENV_LINE.match(line)
        if not match:
            raise ReadError("dotenv-syntax")
        name, value = match.group(1), match.group(2).strip(" \t")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if name in out:
            raise ReadError("duplicate-key", name)
        out[name] = value
    return out


# --------------------------------------------------------------------------------------------
# Validation: the schema, then the rules JSON Schema cannot express.
# --------------------------------------------------------------------------------------------

RESERVED_NAMES = {"default", "overlay", "system", "user", "project", "project-root"}
DEVICE_NAMES = {"con", "prn", "aux", "nul"} | {"com%d" % i for i in range(1, 10)}
DEVICE_NAMES |= {"lpt%d" % i for i in range(1, 10)}
OVERLAY_NAME = re.compile(r"^[A-Za-z](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?$")


def pointer(parts: Iterable[Any]) -> str:
    return "".join("/" + str(part) for part in parts)


def valid_overlay_name(name: str) -> bool:
    return (
        bool(OVERLAY_NAME.match(name))
        and name.lower() not in RESERVED_NAMES
        and name.split(".", 1)[0].lower() not in DEVICE_NAMES
    )


def normalize_name(name: str) -> str:
    return name.lower().replace("_", "-").replace(".", "-")


def validate(doc: "dict[str, Any]", files: "Optional[set[str]]" = None) -> "list[tuple[str, str]]":
    """Problems with a data model value, as ``(code, pointer)``; empty when valid.

    ``files`` is the set of the overlay's relative file paths; when given, every file a field
    names must be in it.
    """
    issues = [("schema", pointer(error.absolute_path)) for error in VALIDATOR.iter_errors(doc)]
    issues += _integers(doc)
    issues += _semantic(doc)
    if files is not None:
        issues += _files(doc, files)
    return sorted(set(issues), key=lambda issue: (issue[1], issue[0]))


def _integers(doc: "dict[str, Any]") -> "list[tuple[str, str]]":
    """Fields that take an integer refuse a float of equal value."""
    found = []

    def check(value: Any, at: str) -> None:
        if isinstance(value, float):
            found.append(("integer-required", at))

    check(doc.get("priority"), "/priority")
    for key in ("env_scripts", "setup"):
        items = doc.get(key)
        if isinstance(items, list):
            for index, item in enumerate(items):
                if isinstance(item, dict):
                    check(item.get("timeout"), "/%s/%d/timeout" % (key, index))
    return found


def _semantic(doc: "dict[str, Any]") -> "list[tuple[str, str]]":
    found: "list[tuple[str, str]]" = []
    requires = doc.get("requires")
    if isinstance(requires, list):
        for index, name in enumerate(requires):
            if isinstance(name, str) and OVERLAY_NAME.match(name) and not valid_overlay_name(name):
                found.append(("reserved-name", "/requires/%d" % index))
    env = doc.get("env")
    env_names: "dict[str, str]" = {}
    if isinstance(env, dict):
        for name in env:
            folded = name.upper()
            if folded in env_names:
                found.append(("env-name-case-duplicate", "/env/%s" % name))
            env_names.setdefault(folded, name)
    paths = doc.get("paths")
    if isinstance(paths, list):
        for index, entry in enumerate(paths):
            if isinstance(entry, dict) and isinstance(entry.get("variable"), str):
                if entry["variable"].upper() in env_names:
                    found.append(("env-path-conflict", "/paths/%d/variable" % index))
    found += _mcp(doc.get("mcp"))
    return found


def _mcp(mcp: Any) -> "list[tuple[str, str]]":
    found: "list[tuple[str, str]]" = []
    if not isinstance(mcp, dict):
        return found
    servers = mcp.get("servers") if isinstance(mcp.get("servers"), list) else []
    names: "set[str]" = set()
    for index, server in enumerate(servers):
        if not isinstance(server, dict):
            continue
        name = server.get("name")
        if name in names:
            found.append(("mcp-duplicate-server", "/mcp/servers/%d/name" % index))
        names.add(name)
        url = server.get("url")
        if isinstance(url, str) and ("#" in url or "@" in url.split("://", 1)[-1].split("/", 1)[0]):
            found.append(("mcp-url", "/mcp/servers/%d/url" % index))
        if isinstance(server.get("env"), dict):
            seen: "set[str]" = set()
            for var in server["env"]:
                if var.upper() in seen:
                    found.append(
                        ("env-name-case-duplicate", "/mcp/servers/%d/env/%s" % (index, var))
                    )
                seen.add(var.upper())
    skills = mcp.get("skills") if isinstance(mcp.get("skills"), list) else []
    linked: "set[str]" = set()
    for index, link in enumerate(skills):
        if not isinstance(link, dict):
            continue
        if link.get("name") in linked:
            found.append(("mcp-duplicate-skill", "/mcp/skills/%d/name" % index))
        linked.add(link.get("name"))
        if link.get("server") not in names:
            found.append(("mcp-unknown-server", "/mcp/skills/%d/server" % index))
    return found


def named_files(doc: "dict[str, Any]") -> "list[tuple[str, str]]":
    """Every ``(pointer, relative path)`` of a file a field requires to exist."""
    out: "list[tuple[str, str]]" = []

    def each(key: str, items: Any, field: Optional[str] = None) -> None:
        if not isinstance(items, list):
            return
        for index, item in enumerate(items):
            if field is None and isinstance(item, str):
                out.append(("/%s/%d" % (key, index), item))
            elif isinstance(item, dict) and isinstance(item.get(field or "path"), str):
                out.append(("/%s/%d/%s" % (key, index, field or "path"), item[field or "path"]))

    each("rules", doc.get("rules"))
    each("context", doc.get("context"))
    files = doc.get("env_files")
    if isinstance(files, list):
        for index, item in enumerate(files):
            if isinstance(item, str):
                out.append(("/env_files/%d" % index, item))
            elif isinstance(item, dict) and isinstance(item.get("path"), str):
                out.append(("/env_files/%d/path" % index, item["path"]))
    each("env_scripts", doc.get("env_scripts"), "path")
    each("setup", doc.get("setup"), "path")
    runtime = doc.get("runtime")
    if isinstance(runtime, dict) and isinstance(runtime.get("python"), list):
        for index, variant in enumerate(runtime["python"]):
            if isinstance(variant, dict):
                for field in ("requirements", "lock"):
                    if isinstance(variant.get(field), str):
                        out.append(("/runtime/python/%d/%s" % (index, field), variant[field]))
    scripts = doc.get("scripts")
    if isinstance(scripts, dict):
        for name, target in scripts.items():
            if isinstance(target, str):
                out.append(("/scripts/%s" % name, target))
            elif isinstance(target, dict) and isinstance(target.get("path"), str):
                out.append(("/scripts/%s/path" % name, target["path"]))
    harness = doc.get("harness")
    if isinstance(harness, dict):
        for harness_id, hints in harness.items():
            if isinstance(hints, dict) and isinstance(hints.get("context"), list):
                for index, path in enumerate(hints["context"]):
                    if isinstance(path, str):
                        out.append(("/harness/%s/context/%d" % (harness_id, index), path))
    return out


def _files(doc: "dict[str, Any]", files: "set[str]") -> "list[tuple[str, str]]":
    found = [("missing-file", at) for at, path in named_files(doc) if path not in files]
    skills = doc.get("skills")
    if isinstance(skills, list):
        for index, name in enumerate(skills):
            if isinstance(name, str) and "skills/%s/SKILL.md" % name not in files:
                found.append(("missing-skill", "/skills/%d" % index))
    mcp = doc.get("mcp")
    if isinstance(mcp, dict) and isinstance(mcp.get("skills"), list):
        for index, link in enumerate(mcp["skills"]):
            name = link.get("name") if isinstance(link, dict) else None
            if isinstance(name, str) and "skills/%s/SKILL.md" % name not in files:
                found.append(("missing-skill", "/mcp/skills/%d/name" % index))
    return found


def tree_files(root: Path) -> "set[str]":
    """The relative paths of the regular files under ``root``."""
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }
