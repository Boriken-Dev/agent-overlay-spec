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
_RELPATH = re.compile(SCHEMA["$defs"]["relPath"]["allOf"][0]["pattern"])
_RELPATH_EXCLUDED = re.compile(SCHEMA["$defs"]["relPath"]["allOf"][1]["not"]["pattern"])

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
    if text.startswith("﻿"):
        raise ReadError("parse-error", "a byte-order mark where the document starts")
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
    if any(c in text for c in "\x85  "):
        raise ReadError("parse-error", "a Unicode line break YAML 1.1 and 1.2 read differently")
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
            if event.version is not None or event.tags:
                raise ReadError("yaml-directive")
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
    """Refuse what the data model has no type for; ``depth`` counts containers, the root being 1."""
    if isinstance(value, (list, dict)) and depth > max_depth:
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


def parse_dotenv(data: bytes) -> "list[tuple[str, str, bool]]":
    """A ``dotenv`` env file's lines as ``(name, text, literal)``, in order.

    ``literal`` is true for a value in single quotes, which is never substituted.
    """
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise ReadError("invalid-utf8")
    out: "list[tuple[str, str, bool]]" = []
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
        literal = False
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            literal = value[0] == "'"
            value = value[1:-1]
        if name.upper() in (key.upper() for key, _v, _l in out):
            raise ReadError("duplicate-key", name)
        out.append((name, value, literal))
    return out


def read_dotenv(
    data: bytes,
    env: "Optional[dict[str, str]]" = None,
    windows: bool = False,
    secret_variables: "Iterable[str]" = (),
) -> "dict[str, str]":
    """A ``dotenv`` env file applied to ``env``: each line substituted against the environment
    as the earlier lines left it. Returns the values the file sets."""
    entries = parse_dotenv(data)
    built = Environment(env or {}, windows, secret_variables)
    out: "dict[str, str]" = {}
    for name, text, literal in entries:
        value = text if literal else substitute(text, built.lookup)
        built.set(name, value)
        out[name] = value
    return out


# --------------------------------------------------------------------------------------------
# Substitution in env values: ${NAME} and its operators, applied when a value is set.
# --------------------------------------------------------------------------------------------


class SubstitutionError(ReadError):
    """``undefined-variable``, ``secret-placeholder`` or ``invalid-pattern``; ``name`` is the
    placeholder's variable, or the pattern."""

    def __init__(self, code: str, name: str):
        super().__init__(code, name)
        self.name = name


_NAME_AT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_SPACE = "[ \t\n\r\f\v]"
_SLICE = re.compile(
    r":{s}*(?:\({s}*(-?[0-9]+){s}*\)|([0-9]+|{s}-[0-9]+))(?::{s}*(-?[0-9]+))?{s}*".format(s=_SPACE)
)
_DEFAULTS = (":-", ":=", ":+", "-", "=", "+")


def substitute(text: str, lookup: "Any") -> str:
    """``text`` with every placeholder replaced. ``lookup(name)`` gives a variable's value, or
    None when it is unset; it raises for a variable that holds a secret."""
    out: "list[str]" = []
    index = 0
    while index < len(text):
        char = text[index]
        if char != "$":
            out.append(char)
            index += 1
            continue
        after = text[index + 1 : index + 2]
        if after == "$":
            out.append("$")
            index += 2
            continue
        if after == "{":
            close = _closing_brace(text, index + 2)
            if close is not None:
                found = _expression(text[index + 2 : close], lookup)
                if found is not None:
                    out.append(found)
                    index = close + 1
                    continue
        # Not a placeholder: the '$' is itself, and reading goes on after it.
        out.append("$")
        index += 1
    return "".join(out)


def _closing_brace(text: str, index: int) -> "Optional[int]":
    """The '}' ending an expression that starts at ``index``: the first one that does not close
    a '${' opened inside it."""
    depth = 0
    while index < len(text):
        if text.startswith("${", index):
            depth += 1
            index += 2
            continue
        if text[index] == "}":
            if depth == 0:
                return index
            depth -= 1
        index += 1
    return None


def _required(name: str, lookup: "Any") -> str:
    value = lookup(name)
    if value is None:
        raise SubstitutionError("undefined-variable", name)
    return value


def _expression(body: str, lookup: "Any") -> "Optional[str]":
    """The text for ``${body}``, or None when it is no expression AOS defines."""
    if body.startswith("#"):
        name = _NAME_AT.fullmatch(body, 1)
        if name is not None:
            return str(len(_required(name.group(), lookup)))
    name = _NAME_AT.match(body)
    if name is None:
        return None
    key, rest = name.group(), body[name.end() :]
    if not rest:
        return _required(key, lookup)
    for operator in _DEFAULTS:
        if rest.startswith(operator):
            word = rest[len(operator) :]
            value = lookup(key)
            present = value is not None and not (operator[0] == ":" and value == "")
            if operator.endswith("+"):
                return substitute(word, lookup) if present else ""
            return value if present else substitute(word, lookup)
    if rest.startswith(":"):
        found = _SLICE.fullmatch(rest)
        if found is None:
            return None
        offset = int(found.group(1) or found.group(2))
        length = None if found.group(3) is None else int(found.group(3))
        return _slice(_required(key, lookup), offset, length)
    if rest.startswith("/"):
        spec = rest[1:]
        kind = spec[:1] if spec[:1] in ("/", "#", "%") else ""
        pattern, replacement = _split_pattern(spec[len(kind) :])
        return _replace(_required(key, lookup), kind, pattern, replacement)
    if rest[:1] in ("#", "%"):
        operator = rest[:2] if rest[:2] in ("##", "%%") else rest[:1]
        return _trim(_required(key, lookup), operator, rest[len(operator) :])
    if rest in ("^", "^^", ",", ",,"):
        value = _required(key, lookup)
        if rest == "^^":
            return value.upper()
        if rest == ",,":
            return value.lower()
        return (value[:1].upper() if rest == "^" else value[:1].lower()) + value[1:]
    return None


def _slice(value: str, offset: int, length: "Optional[int]") -> str:
    size = len(value)
    if offset < 0:
        offset += size
        if offset < 0:
            return ""
    end = size if length is None else (offset + length if length >= 0 else size + length)
    return value[offset:end] if end > offset else ""


def _split_pattern(spec: str) -> "tuple[str, str]":
    """A replacement's pattern and text: split at the first '/' not after a backslash."""
    index = 0
    while index < len(spec):
        if spec[index] == "\\":
            index += 2
            continue
        if spec[index] == "/":
            return spec[:index], spec[index + 1 :]
        index += 1
    return spec, ""


def _glob(pattern: str) -> "re.Pattern[str]":
    """A pattern as a regular expression matched whole: '*', '?', brackets, '\\x' for x."""
    parts: "list[str]" = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "\\" and index + 1 < len(pattern):
            parts.append(re.escape(pattern[index + 1]))
            index += 2
            continue
        if char == "*":
            parts.append(".*")
        elif char == "?":
            parts.append(".")
        elif char == "[" and pattern.find("]", index + 2) >= 0:
            close = pattern.find("]", index + 2)
            body = pattern[index + 1 : close]
            negate = body[:1] in ("!", "^")
            items = body[1:] if negate else body
            if not items:
                raise SubstitutionError("invalid-pattern", pattern)
            members: "list[str]" = []
            at = 0
            while at < len(items):
                if at + 2 < len(items) and items[at + 1] == "-":
                    low, high = items[at], items[at + 2]
                    if ord(high) < ord(low):
                        raise SubstitutionError("invalid-pattern", pattern)
                    members.append(re.escape(low) + "-" + re.escape(high))
                    at += 3
                else:
                    members.append(re.escape(items[at]))
                    at += 1
            parts.append("[" + ("^" if negate else "") + "".join(members) + "]")
            index = close + 1
            continue
        else:
            parts.append(re.escape(char))
        index += 1
    return re.compile("".join(parts), re.DOTALL)


def _ends(regex: "re.Pattern[str]", value: str, start: int) -> "list[int]":
    """Every end at which the pattern matches the text from ``start``, shortest first."""
    return [end for end in range(start, len(value) + 1) if regex.fullmatch(value, start, end)]


def _replace(value: str, kind: str, pattern: str, replacement: str) -> str:
    if not pattern:
        return value
    regex = _glob(pattern)
    if kind == "#":
        ends = _ends(regex, value, 0)
        return replacement + value[ends[-1] :] if ends else value
    if kind == "%":
        for start in range(len(value) + 1):
            if regex.fullmatch(value, start):
                return value[:start] + replacement
        return value
    out: "list[str]" = []
    position = 0
    while True:
        match = None
        for start in range(position, len(value)):
            ends = _ends(regex, value, start)
            if ends and ends[-1] > start:
                match = (start, ends[-1])
                break
        if match is None:
            break
        out.append(value[position : match[0]] + replacement)
        position = match[1]
        if kind != "/":
            break
    return "".join(out) + value[position:]


def _trim(value: str, operator: str, pattern: str) -> str:
    regex = _glob(pattern)
    if operator in ("#", "##"):
        ends = _ends(regex, value, 0)
        if not ends:
            return value
        return value[ends[0] if operator == "#" else ends[-1] :]
    starts = [s for s in range(len(value) + 1) if regex.fullmatch(value, s)]
    if not starts:
        return value
    return value[: starts[-1] if operator == "%" else starts[0]]


def read_env_script_output(data: bytes) -> "dict[str, Optional[str]]":
    """An env script's standard output: the variables it sets (a string) or unsets (None).

    The whole output is one JSON object, possibly over several lines; or else every line that is
    not blank is one. The objects apply in order.
    """
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise ReadError("invalid-utf8")
    whole = text.strip(" \t\r\n")
    if not whole:
        return {}
    try:
        objects = [_read_json(whole)]
    except ReadError as error:
        if error.code != "parse-error":
            raise
        objects = []
        for line in text.split("\n"):
            line = line[:-1] if line.endswith("\r") else line
            if line.strip(" \t"):
                objects.append(_read_json(line))
    out: "dict[str, Optional[str]]" = {}
    for value in objects:
        if not isinstance(value, dict):
            raise ReadError("env-script-output", "not an object")
        for name, item in value.items():
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name) or is_reserved_variable(name):
                raise ReadError("env-script-output", "variable name")
            if item is not None and not (isinstance(item, str) and "\0" not in item):
                raise ReadError("env-script-output", "value")
            out[name] = item
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


_RESERVED_VARIABLE = re.compile(r"^(?:AOS_.*|.*_OVERLAY_(?:ROOT|STATE))$", re.IGNORECASE)


def is_reserved_variable(name: str) -> bool:
    """Variables a consumer sets and no overlay may: ``AOS_*`` and ``*_OVERLAY_ROOT/STATE``."""
    return bool(_RESERVED_VARIABLE.match(name))


def valid_relpath(path: str) -> bool:
    """A relative path as the manifest defines it, excluded names and ``.pyc`` refused."""
    return bool(_RELPATH.match(path)) and not _RELPATH_EXCLUDED.search(path)


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
            if is_reserved_variable(name):
                found.append(("reserved-variable", "/env/%s" % name))
            env_names.setdefault(folded, name)
    paths = doc.get("paths")
    if isinstance(paths, list):
        for index, entry in enumerate(paths):
            if isinstance(entry, dict) and isinstance(entry.get("variable"), str):
                if entry["variable"].upper() in env_names:
                    found.append(("env-path-conflict", "/paths/%d/variable" % index))
                if is_reserved_variable(entry["variable"]):
                    found.append(("reserved-variable", "/paths/%d/variable" % index))
    mcp = doc.get("mcp")
    if isinstance(mcp, dict) and isinstance(mcp.get("servers"), list):
        for index, server in enumerate(mcp["servers"]):
            if isinstance(server, dict) and isinstance(server.get("env"), dict):
                for name in server["env"]:
                    if is_reserved_variable(name):
                        found.append(
                            ("reserved-variable", "/mcp/servers/%d/env/%s" % (index, name))
                        )
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
        command = server.get("command")
        if isinstance(command, str) and ("/" in command or "\\" in command):
            if not valid_relpath(command):
                found.append(("mcp-command", "/mcp/servers/%d/command" % index))
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
    env = doc.get("env")
    if isinstance(env, dict):
        added = {entry["variable"] for entry in default_paths(doc, files)}
        for name in env:
            if name.upper() in added:
                found.append(("env-path-conflict", "/env/%s" % name))
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


# --------------------------------------------------------------------------------------------
# Integrity: the tree digest.
# --------------------------------------------------------------------------------------------

EXCLUDED_COMPONENTS = frozenset(
    (
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "node_modules",
    )
)
_REPARSE_POINT = 0x400  # FILE_ATTRIBUTE_REPARSE_POINT: symlinks and junctions on Windows
DIGEST_FORM = re.compile(r"^sha256:[0-9a-fA-F]{64}$")


class DigestError(Exception):
    """A tree whose digest cannot be computed. ``code`` is the vectors' error class."""

    def __init__(self, code: str, path: str = ""):
        super().__init__("%s: %s" % (code, path) if path else code)
        self.code = code
        self.path = path


def sha256_digest(data: bytes) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(data).hexdigest()


def same_digest(a: str, b: str) -> bool:
    """Digests compare by their hexadecimal digits, without regard to case."""
    if not (DIGEST_FORM.match(a) and DIGEST_FORM.match(b)):
        raise ValueError("not a digest")
    return a.lower() == b.lower()


def digest_entries(
    entries: "Iterable[tuple[tuple[bytes, ...], str, bytes]]",
) -> "tuple[str, list[bytes]]":
    """The tree digest of abstract entries ``(components, kind, data)``, and its lines.

    ``kind`` is ``file``, ``dir``, ``symlink`` or ``special``; ``data`` is a file's bytes.
    """
    lines = []
    for components, kind, data in entries:
        if kind == "dir":
            continue
        names = _names(components)
        if any(name in EXCLUDED_COMPONENTS for name in names) or names[-1].endswith(".pyc"):
            continue  # an excluded name, or inside an excluded directory, never entered
        if kind == "symlink":
            raise DigestError("symlink", _shown(components))
        if kind != "file":
            raise DigestError("special-file", _shown(components))
        for component in components:
            try:
                component.decode("utf-8")
            except UnicodeDecodeError:
                raise DigestError("non-utf8-name", _shown(components))
        path = b"/".join(components)
        if not valid_relpath(path.decode("utf-8")):
            raise DigestError("invalid-name", _shown(components))
        lines.append(path + b"\0" + sha256_digest(data).encode("ascii") + b"\n")
    folded: "dict[bytes, bytes]" = {}
    for line in lines:
        path = line.split(b"\0", 1)[0]
        other = folded.setdefault(path.lower(), path)
        if other != path:
            raise DigestError("case-collision", path.decode("utf-8"))
    lines.sort(key=lambda line: line.split(b"\0", 1)[0])
    return sha256_digest(b"".join(lines)), lines


def _names(components: "Iterable[bytes]") -> "list[str]":
    return [c.decode("utf-8", "replace") for c in components]


def _shown(components: "tuple[bytes, ...]") -> str:
    return "/".join(_names(components))


def tree_entries(root: Path) -> "list[tuple[tuple[bytes, ...], str, bytes]]":
    """A directory's entries for :func:`digest_entries`, read without following any link."""
    import os
    import stat

    out: "list[tuple[tuple[bytes, ...], str, bytes]]" = []

    def walk(directory: Path, prefix: "tuple[bytes, ...]") -> None:
        for entry in sorted(os.scandir(directory), key=lambda e: e.name):
            components = prefix + (os.fsencode(entry.name),)
            info = entry.stat(follow_symlinks=False)
            reparse = getattr(info, "st_file_attributes", 0) & _REPARSE_POINT
            if entry.name in EXCLUDED_COMPONENTS:
                out.append((components, "dir" if stat.S_ISDIR(info.st_mode) else "file", b""))
                continue
            if stat.S_ISLNK(info.st_mode) or reparse:
                out.append((components, "symlink", b""))
            elif stat.S_ISDIR(info.st_mode):
                out.append((components, "dir", b""))
                walk(Path(entry.path), components)
            elif stat.S_ISREG(info.st_mode):
                out.append((components, "file", Path(entry.path).read_bytes()))
            else:
                out.append((components, "special", b""))

    walk(root, ())
    return out


def tree_digest(root: Path) -> str:
    """The tree digest of the overlay at ``root``."""
    return digest_entries(tree_entries(root))[0]


# --------------------------------------------------------------------------------------------
# Names and sources.
# --------------------------------------------------------------------------------------------


def root_variable(identity: str) -> str:
    """``<NAME>_OVERLAY_ROOT`` for an overlay identity."""
    return re.sub(r"[^A-Z0-9]", "_", normalize_name(identity).upper()) + "_OVERLAY_ROOT"


_GIT_PREFIXES = ("git@", "ssh://", "git://")


def _is_git_location(location: str) -> bool:
    return location.endswith(".git") or location.startswith(_GIT_PREFIXES)


def parse_source(text: str) -> "dict[str, Optional[str]]":
    """``[git+]<location>[@<ref>][#<path>]`` as ``{kind, location, ref, path}``."""
    raw = text.strip()
    if not raw:
        raise ValueError("empty")
    explicit_git = raw.startswith("git+")
    if explicit_git:
        raw = raw[len("git+") :]
    body, hash_sep, path = raw.partition("#")
    path = (path.strip().strip("/") or None) if hash_sep else None
    location, ref = body.strip(), None
    head, at, tail = location.rpartition("@")
    if (
        at
        and head
        and tail
        and not re.search(r"[/:\\]", tail)
        and not head.endswith(("://", ":"))
        and (explicit_git or _is_git_location(head))
    ):
        location, ref = head, tail
    if path is not None and not valid_relpath(path):
        raise ValueError("path")
    if explicit_git or _is_git_location(location):
        if location.startswith("-") or (ref or "").startswith("-"):
            raise ValueError("option-like")
        if "::" in location:
            raise ValueError("git remote helper")
        if "://" in location:
            scheme, rest = location.split("://", 1)
            if scheme.lower() not in ("https", "http", "ssh", "git", "file"):
                raise ValueError("scheme")
            host = rest.split("/", 1)[0].rsplit("@", 1)[-1]
        else:
            host = location.split(":", 1)[0].rsplit("@", 1)[-1] if "@" in location else ""
        if host.startswith("-"):
            raise ValueError("option-like host")
        return {"kind": "git", "location": location, "ref": ref, "path": path}
    kind = "url" if "://" in location else "directory"
    return {"kind": kind, "location": location, "ref": None, "path": path}


# --------------------------------------------------------------------------------------------
# Resolution and composition.
# --------------------------------------------------------------------------------------------


class ResolveError(Exception):
    def __init__(self, code: str, chain: "list[str]"):
        super().__init__("%s: %s" % (code, " -> ".join(chain)))
        self.code = code
        self.chain = chain


def resolve(
    available: "dict[str, dict[str, Any]]", requested: "list[str]"
) -> "tuple[list[str], list[list[str]]]":
    """The visiting order of the active overlays and the missing requirements, or a cycle.

    ``available`` maps a normalized identity to its manifest.
    """
    order: "list[str]" = []
    missing: "list[list[str]]" = []

    def visit(name: str, chain: "list[str]") -> None:
        if name in order:
            return
        if name in chain:
            raise ResolveError("cycle", chain[chain.index(name) :] + [name])
        if name not in available:
            missing.append([chain[-1] if chain else "", name])
            return
        for dep in available[name].get("requires", []):
            visit(normalize_name(dep), chain + [name])
        order.append(name)

    for name in requested:
        visit(normalize_name(name), [])
    return order, missing


def composition_order(
    overlays: "dict[str, dict[str, Any]]", active: "Iterable[str]"
) -> "list[str]":
    """Ascending ``(priority, name, identity)``; strings by code point."""

    def key(identity: str) -> "tuple[int, str, str]":
        manifest = overlays[identity]
        name = manifest.get("name")
        return (
            manifest.get("priority", 500),
            name if isinstance(name, str) and name else identity,
            identity,
        )

    return sorted(active, key=key)


# --------------------------------------------------------------------------------------------
# Defaults: what conventional files contribute unless ``defaults`` turns them off.
# --------------------------------------------------------------------------------------------

#: The keys of ``defaults``; each is true unless the manifest writes it false.
DEFAULT_KEYS = ("bin", "lib", "env", "env_scripts", "setup", "context", "skills", "rules")
#: Default path additions as ``(key, variable, directory)``, in the order they apply.
DEFAULT_PATHS = (("bin", "PATH", "bin"), ("lib", "PYTHONPATH", "lib/python"))
#: Default script extensions in the order a consumer tries them, with the OSes each applies on
#: (``None``: every OS).
DEFAULT_SCRIPTS = (
    (".py", "python", None),
    (".js", "node", None),
    (".mjs", "node", None),
    (".cjs", "node", None),
    (".ps1", "powershell", ["windows"]),
    (".bash", "bash", ["unix"]),
    (".sh", "sh", ["unix"]),
)
INTERPRETERS = ("python", "node", "powershell", "bash", "sh")
_SKILL_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_RULES_FILE = re.compile(r"^rules/[^/]+\.md$")


def default_on(manifest: "dict[str, Any]", key: str) -> bool:
    defaults = manifest.get("defaults")
    return not (isinstance(defaults, dict) and defaults.get(key) is False)


def _members(files: "Iterable[str]") -> "list[str]":
    """The files that make a path present: digest members, so no excluded name or ``.pyc``."""
    return [path for path in files if valid_relpath(path)]


def _by_bytes(paths: "Iterable[str]") -> "list[str]":
    return sorted(paths, key=lambda path: path.encode("utf-8"))


def _named(entry: Any) -> Any:
    """The file or directory an entry names: a string entry, or a mapping's ``path``."""
    return entry.get("path") if isinstance(entry, dict) else entry


def _declared(manifest: "dict[str, Any]", field: str) -> "list[Any]":
    value = manifest.get(field)
    return list(value) if isinstance(value, list) else []


def _merge(defaults: "list[Any]", declared: "list[Any]") -> "list[Any]":
    """Default entries first, then declared ones; a declared entry naming the same file or
    directory as a default entry replaces it."""
    named = {_named(entry) for entry in declared}
    return [entry for entry in defaults if _named(entry) not in named] + declared


def default_paths(manifest: "dict[str, Any]", files: "Iterable[str]") -> "list[dict[str, Any]]":
    """The default path additions that are on, present, and not replaced by a declared entry."""
    members = _members(files)
    found = [
        {"variable": variable, "path": directory}
        for key, variable, directory in DEFAULT_PATHS
        if default_on(manifest, key) and any(p.startswith(directory + "/") for p in members)
    ]
    named = {_named(entry) for entry in _declared(manifest, "paths")}
    return [entry for entry in found if entry["path"] not in named]


def paths_of(manifest: "dict[str, Any]", files: "Iterable[str]") -> "list[dict[str, Any]]":
    """The defaults ``bin`` and ``lib``, then ``paths``."""
    return default_paths(manifest, files) + _declared(manifest, "paths")


def rules_of(manifest: "dict[str, Any]", files: "Iterable[str]") -> "list[str]":
    """Every ``rules/<name>.md`` by path bytes, then ``rules``."""
    found = []
    if default_on(manifest, "rules"):
        found = [path for path in _by_bytes(_members(files)) if _RULES_FILE.match(path)]
    return _merge(found, _declared(manifest, "rules"))


def context_of(manifest: "dict[str, Any]", files: "Iterable[str]") -> "list[str]":
    """The root ``CONTEXT.md``, then ``context``."""
    found = []
    if default_on(manifest, "context") and "CONTEXT.md" in _members(files):
        found = ["CONTEXT.md"]
    return _merge(found, _declared(manifest, "context"))


def skills_of(manifest: "dict[str, Any]", files: "Iterable[str]") -> "list[str]":
    """Every ``skills/<name>/SKILL.md`` with a skill name, and the skills ``skills`` lists."""
    found = set(_declared(manifest, "skills"))
    if default_on(manifest, "skills"):
        for path in _members(files):
            parts = path.split("/")
            if len(parts) == 3 and parts[0] == "skills" and parts[2] == "SKILL.md":
                if _SKILL_NAME.match(parts[1]):
                    found.add(parts[1])
    return _by_bytes(found)


def env_files_of(manifest: "dict[str, Any]", files: "Iterable[str]") -> "list[Any]":
    """The root file ``env`` read as dotenv, then ``env_files``."""
    found = []
    if default_on(manifest, "env") and "env" in _members(files):
        found = [{"path": "env", "format": "dotenv"}]
    return _merge(found, _declared(manifest, "env_files"))


def default_script(
    manifest: "dict[str, Any]",
    field: str,
    stem: str,
    files: "Iterable[str]",
    os_name: str,
    interpreters: "Iterable[str]",
) -> "tuple[Optional[dict[str, Any]], bool, list[str], list[Any]]":
    """The default ``<stem>.<ext>`` a consumer runs for ``field``.

    Returns the chosen entry, whether a declared entry configured it, the candidate files
    present (reported when none is chosen), and the declared entries that name no candidate.
    A declared entry naming a candidate takes its place in the order, with its own settings.
    """
    declared = _declared(manifest, field)
    if not default_on(manifest, field):
        return None, False, [], declared
    members = set(_members(files))
    present = [stem + ext for ext, _i, _o in DEFAULT_SCRIPTS if stem + ext in members]
    configured = {
        entry["path"]: entry
        for entry in declared
        if isinstance(entry, dict) and entry.get("path") in present
    }
    others = [entry for entry in declared if _named(entry) not in configured]
    for ext, interpreter, names in DEFAULT_SCRIPTS:
        path = stem + ext
        if path not in present:
            continue
        entry = configured.get(path, {"interpreter": interpreter, "path": path, "os": names})
        if os_matches(entry, os_name) and entry["interpreter"] in interpreters:
            return entry, path in configured, present, others
    return None, False, present, others


# --------------------------------------------------------------------------------------------
# Applying declarations: the effective environment, setup, runtime and weakenings.
# --------------------------------------------------------------------------------------------

SENSITIVE_NAMES = frozenset(
    """PATH PATHEXT HOME USERPROFILE SHELL COMSPEC SYSTEMROOT BASH_ENV ENV ZDOTDIR PROMPT_COMMAND
    IFS EDITOR VISUAL PAGER LESSOPEN LESSCLOSE XDG_CONFIG_HOME XDG_DATA_HOME APPDATA LOCALAPPDATA
    TMPDIR TEMP TMP PSMODULEPATH CLASSPATH JAVA_TOOL_OPTIONS _JAVA_OPTIONS JDK_JAVA_OPTIONS
    PERL5OPT PERL5LIB RUBYOPT RUBYLIB RUSTFLAGS GOPROXY GONOSUMDB GONOSUMCHECK GOPRIVATE GOFLAGS
    SSH_ASKPASS SSLKEYLOGFILE REQUESTS_CA_BUNDLE CURL_CA_BUNDLE""".split()
)
SENSITIVE_PREFIXES = (
    "LD_",
    "DYLD_",
    "GIT_",
    "PYTHON",
    "NODE_",
    "NPM_CONFIG_",
    "PIP_",
    "UV_",
    "CARGO_",
    "RUSTC_",
    "DOTNET_",
    "COR_",
    "CORECLR_",
    "SSL_",
)
SENSITIVE_SUFFIXES = ("_PROXY", "_BASE_URL")
#: Path additions exist for these, so adding to them is not a weakening.
PATH_VARIABLES = frozenset(("PATH", "PYTHONPATH"))
UNIX_NAMES = frozenset(("macos", "linux", "freebsd", "openbsd", "netbsd"))
SCRIPT_EXTENSIONS = {
    ".py": "python",
    ".sh": "sh",
    ".bash": "bash",
    ".ps1": "powershell",
    ".js": "node",
    ".mjs": "node",
    ".cjs": "node",
}


class Refused(Exception):
    """A declaration the consumer refuses to apply; ``code`` is the vectors' class."""

    def __init__(self, code: str, subject: str):
        super().__init__("%s: %s" % (code, subject))
        self.code = code
        self.subject = subject


def os_matches(entry: Any, current: str) -> bool:
    names = entry.get("os") if isinstance(entry, dict) else None
    if names is None:
        return True
    return current in names or ("unix" in names and current != "windows" and current in UNIX_NAMES)


def first_variant(variants: "list[dict[str, Any]]", current: str) -> "Optional[dict[str, Any]]":
    for variant in variants:
        if os_matches(variant, current):
            return variant
    return None


def is_sensitive(name: str) -> bool:
    upper = name.upper()
    return (
        upper in SENSITIVE_NAMES
        or upper.startswith(SENSITIVE_PREFIXES)
        or upper.endswith(SENSITIVE_SUFFIXES)
    )


class Environment:
    """A variable mapping; on Windows names compare without regard to ASCII case.

    ``secret`` holds the variables whose value came from a secret reference, which no
    placeholder may read. ``extra`` holds names a placeholder sees that are not set in the
    environment (an overlay's own ``AOS_OVERLAY_*``).
    """

    def __init__(
        self,
        values: "dict[str, str]",
        windows: bool,
        secret: "Iterable[str]" = (),
        extra: "Optional[dict[str, str]]" = None,
    ):
        self.windows = windows
        self.values = dict(values)
        self.secret = {key for key in (self._key(name) for name in secret) if key is not None}
        self.extra = dict(extra or {})

    def _key(self, name: str) -> "Optional[str]":
        if name in self.values:
            return name
        if self.windows:
            for key in self.values:
                if key.upper() == name.upper():
                    return key
        return None

    def get(self, name: str) -> "Optional[str]":
        key = self._key(name)
        return None if key is None else self.values[key]

    def lookup(self, name: str) -> "Optional[str]":
        """What a placeholder reads: refused for a secret, unset when absent."""
        for extra, value in self.extra.items():
            if extra == name or (self.windows and extra.upper() == name.upper()):
                return value
        key = self._key(name)
        if key is None:
            return None
        if key in self.secret:
            raise SubstitutionError("secret-placeholder", name)
        return self.values[key]

    def set(self, name: str, value: str, secret: bool = False) -> None:
        key = self._key(name) or name
        self.values[key] = value
        if secret:
            self.secret.add(key)
        else:
            self.secret.discard(key)

    def copy(self) -> "Environment":
        copied = Environment(self.values, self.windows, (), self.extra)
        copied.secret = set(self.secret)
        return copied


def resolve_path(root: str, relative: str, windows: bool) -> str:
    separator = "\\" if windows else "/"
    return root.rstrip("/\\") + separator + relative.replace("/", separator)


def reference_name(entry: "dict[str, Any]") -> str:
    """How a report names a reference: never a value, never a provider's other fields."""
    if "secret" in entry:
        return "secret:" + entry["secret"]
    return "%s:%s" % (entry["provider"], entry["key"])


def granted(entry: "dict[str, Any]", facts: "dict[str, Any]") -> bool:
    """Whether the consumer's configuration lets this overlay read this reference."""
    grants = facts.get("grants", {})
    if "secret" in entry:
        return entry["secret"] in grants.get("secret", [])
    return entry["key"] in grants.get(entry["provider"], [])


def _secret(entry: "dict[str, Any]", facts: "dict[str, Any]", windows: bool) -> "Optional[str]":
    """A granted secret reference's value, or None when it cannot be resolved."""
    if "provider" in entry and entry["provider"] == "file" and not valid_relpath(entry["key"]):
        raise Refused("invalid-reference", entry["key"])
    if not granted(entry, facts):
        return None
    if "secret" in entry:
        return facts.get("secrets", {}).get(entry["secret"])
    provider = entry["provider"]
    if provider not in facts.get("providers", ["env", "file"]):
        return None
    if provider == "env":
        return Environment(facts.get("host_env", {}), windows).get(entry["key"])
    if provider == "file":
        files = facts.get("secret_files")
        if files is None or entry["key"] not in files:
            return None
        value = files[entry["key"]]
        for ending in ("\r\n", "\n"):
            if value.endswith(ending):
                return value[: -len(ending)]
        return value
    return facts.get("provider_values", {}).get(provider, {}).get(entry["key"])


def _apply_mapping(
    env: Environment,
    mapping: "dict[str, Any]",
    facts: "dict[str, Any]",
    root: str,
    weakenings: "list[list[str]]",
) -> None:
    windows = env.windows
    before = env.copy()
    for name, entry in mapping.items():
        if is_reserved_variable(name):
            raise Refused("reserved-variable", name)
        if isinstance(entry, str):
            entry = {"value": entry}
        if entry.get("if_unset") and before.get(name) is not None:
            continue
        secret = False
        if "value" in entry:
            # Text is substituted against the environment as it was before this mapping:
            # mapping order carries no meaning, so no entry sees another of the same mapping.
            try:
                value: Optional[str] = substitute(entry["value"], before.lookup)
            except SubstitutionError as error:
                raise Refused(error.code, name)
        elif "path" in entry:
            value = resolve_path(root, entry["path"], windows)
        else:
            value = _secret(entry, facts, windows)
            if value is None:
                if entry.get("optional"):
                    continue
                raise Refused("unresolved-reference", name)
            secret = True
            if entry.get("provider") == "env":
                weakenings.append(["env-passthrough", entry["key"]])
            else:
                weakenings.append(["secret-read", reference_name(entry)])
        if is_sensitive(name):
            weakenings.append(["env-sensitive", name])
        env.set(name, value, secret)


def _apply_dotenv(
    env: Environment,
    entries: "list[tuple[str, str, bool]]",
    weakenings: "list[list[str]]",
) -> None:
    """A dotenv file's lines in order: each sees the environment the earlier lines left."""
    for name, text, literal in entries:
        if is_reserved_variable(name):
            raise Refused("reserved-variable", name)
        try:
            value = text if literal else substitute(text, env.lookup)
        except SubstitutionError as error:
            raise Refused(error.code, name)
        if is_sensitive(name):
            weakenings.append(["env-sensitive", name])
        env.set(name, value)


def _apply_paths(
    env: Environment,
    paths: "list[dict[str, Any]]",
    root: str,
    os_name: str,
    weakenings: "list[list[str]]",
) -> None:
    windows = env.windows
    separator = ";" if windows else ":"
    grouped: "dict[str, list[dict[str, Any]]]" = {}
    names: "dict[str, str]" = {}
    for entry in paths:
        if not os_matches(entry, os_name):
            continue
        key = entry["variable"].upper() if windows else entry["variable"]
        names.setdefault(key, entry["variable"])
        grouped.setdefault(key, []).append(entry)
    for key, entries in grouped.items():
        variable = names[key]
        if is_sensitive(variable) and variable.upper() not in PATH_VARIABLES:
            weakenings.append(["env-sensitive", variable])
        prepend: "list[str]" = []
        append: "list[str]" = []
        seen: "set[str]" = set()
        for entry in entries:
            resolved = resolve_path(root, entry["path"], windows)
            if resolved in seen:
                continue
            seen.add(resolved)
            (append if entry.get("position") == "append" else prepend).append(resolved)
        current = env.get(variable) or ""
        kept = [c for c in current.split(separator) if c and c not in seen]
        env.set(variable, separator.join(prepend + kept + append), env._key(variable) in env.secret)


def apply_overlay(
    env: Environment,
    manifest: "dict[str, Any]",
    facts: "dict[str, Any]",
    root: str,
    weakenings: "list[list[str]]",
    tree: "Iterable[str]" = (),
    identity: str = "",
    state: "Optional[str]" = None,
) -> "list[dict[str, Any]]":
    """Steps 2.1 to 2.3 of the order of application; returns the env scripts that run.

    ``tree`` is the overlay's files, from which the defaults of unwritten fields follow. Its
    placeholders also see the ``AOS_OVERLAY_*`` values a step of this overlay receives.
    """
    os_name = facts["os"]
    env.extra = {"AOS_OVERLAY_ROOT": root, "AOS_OVERLAY_NAME": normalize_name(identity)}
    if state is not None:
        env.extra["AOS_OVERLAY_STATE"] = state
    try:
        return _apply_overlay(env, manifest, facts, root, weakenings, tree)
    finally:
        env.extra = {}


def _apply_overlay(
    env: Environment,
    manifest: "dict[str, Any]",
    facts: "dict[str, Any]",
    root: str,
    weakenings: "list[list[str]]",
    tree: "Iterable[str]",
) -> "list[dict[str, Any]]":
    os_name = facts["os"]
    paths = paths_of(manifest, tree)
    listed = {entry["variable"].upper() for entry in paths}
    for name in manifest.get("env", {}):
        if name.upper() in listed:
            raise Refused("env-path-conflict", name)
    for item in env_files_of(manifest, tree):
        item = {"path": item} if isinstance(item, str) else item
        if not os_matches(item, os_name):
            continue
        text = facts.get("files", {}).get(item["path"])
        if text is None:
            raise Refused("missing-file", item["path"])
        try:
            if item.get("format", "aos") == "dotenv":
                lines = parse_dotenv(text.encode("utf-8"))
                names = [name for name, _t, _l in lines]
            else:
                mapping: "dict[str, Any]" = read_document(text.encode("utf-8"))
                names = list(mapping)
        except ReadError:
            raise Refused("invalid-env-file", item["path"])
        if item.get("format", "aos") != "dotenv" and validate({"env": mapping}):
            raise Refused("invalid-env-file", item["path"])
        for name in names:
            if name.upper() in listed:
                raise Refused("env-path-conflict", name)
        if item.get("format", "aos") == "dotenv":
            _apply_dotenv(env, lines, weakenings)
        else:
            _apply_mapping(env, mapping, facts, root, weakenings)
    _apply_mapping(env, manifest.get("env", {}), facts, root, weakenings)
    _apply_paths(env, paths, root, os_name, weakenings)
    scripts = []
    if facts.get("env_scripts_enabled", True):
        chosen, _configured, present, others = default_script(
            manifest, "env_scripts", "env", tree, os_name, facts.get("interpreters", INTERPRETERS)
        )
        if chosen is None:
            weakenings.extend(["script-not-run", path] for path in present)
        for script in ([chosen] if chosen else []) + others:
            if os_matches(script, os_name):
                selected = {"interpreter": script["interpreter"], "path": script["path"]}
                selected["args"] = script.get("args", [])
                selected["timeout"] = script.get("timeout", 60)
                scripts.append(selected)
                weakenings.append(["env-script", script["path"]])
                if selected["timeout"] == 0:
                    weakenings.append(["no-timeout", script["path"]])
    return scripts


def effective(manifest: "dict[str, Any]", facts: "dict[str, Any]") -> "dict[str, Any]":
    """What a consumer applies for one overlay: environment, setup, runtime, needs, weakenings."""
    os_name = facts["os"]
    windows = os_name == "windows"
    root = facts["root"]
    weakenings: "list[list[str]]" = []
    if not facts.get("pinned", False):
        weakenings.append(["unpinned", ""])
    runtime = manifest.get("runtime", {})
    supported = "os" not in runtime or os_matches(runtime, os_name)
    env = Environment(facts.get("base_env", {}), windows)
    env.set(root_variable(facts["identity"]), root)
    if "state" in facts:
        env.set(root_variable(facts["identity"])[: -len("ROOT")] + "STATE", facts["state"])
    try:
        scripts = apply_overlay(
            env,
            manifest,
            facts,
            root,
            weakenings,
            facts.get("files", {}),
            facts["identity"],
            facts.get("state"),
        )
    except Refused as refused:
        return {"error": refused.code, "subject": refused.subject}
    chosen, configured, present, others = default_script(
        manifest,
        "setup",
        "setup",
        facts.get("files", {}),
        os_name,
        facts.get("interpreters", INTERPRETERS),
    )
    # Declared variants come first; the default setup is the last one.
    setup = first_variant(others, os_name)
    network = False
    if setup is None:
        setup = chosen
        # A default setup that declares nothing is taken to need the network.
        network = not configured
        if setup is None:
            weakenings.extend(["script-not-run", path] for path in present)
    if setup is not None:
        setup = {
            "interpreter": setup["interpreter"],
            "path": setup["path"],
            "args": setup.get("args", []),
            "timeout": setup.get("timeout", 300),
            "network": setup.get("network", network),
        }
        if setup["network"]:
            weakenings.append(["setup-network", setup["path"]])
        elif not facts.get("enforces_network", True):
            weakenings.append(["network-not-enforced", setup["path"]])
        if setup["timeout"] == 0:
            weakenings.append(["no-timeout", setup["path"]])
    python = first_variant(runtime.get("python", []), os_name)
    if python is not None:
        python = {key: value for key, value in python.items() if key != "os"}
        if "requirements" in python:
            weakenings.append(["unlocked-dependencies", python["requirements"]])
    node = first_variant(runtime.get("node", []), os_name)
    if node is not None:
        node = {key: value for key, value in node.items() if key != "os"}
    interpreters = {s["interpreter"] for s in scripts}
    if setup is not None:
        interpreters.add(setup["interpreter"])
    for target in manifest.get("scripts", {}).values():
        if isinstance(target, str):
            interpreters.add(SCRIPT_EXTENSIONS[target[target.rindex(".") :]])
        elif isinstance(target, dict) and os_matches(target, os_name):
            interpreters.add(target["interpreter"])
    if python is not None:
        interpreters.add("python")
    if node is not None:
        interpreters.add("node")
    commands = []
    for command in runtime.get("commands", []):
        if isinstance(command, str):
            commands.append(command)
        elif os_matches(command, os_name):
            commands.append(command["name"])
    ungranted: "set[str]" = set()
    host_grants = facts.get("grants", {}).get("env", [])
    for server in manifest.get("mcp", {}).get("servers", []):
        for value in server.get("env", {}).values():
            if isinstance(value, dict) and ("provider" in value or "secret" in value):
                if not granted(value, facts):
                    ungranted.add(reference_name(value))
                elif value.get("provider") == "env":
                    weakenings.append(["env-passthrough", value["key"]])
                else:
                    weakenings.append(["secret-read", reference_name(value)])
        for name in list(server.get("env_passthrough", [])) + list(
            server.get("headers_env", {}).values()
        ):
            if name in host_grants:
                weakenings.append(["env-passthrough", name])
            else:
                ungranted.add("env:" + name)
        url = server.get("url", "")
        if url[:7].lower() == "http://":
            host = url[7:].split("/", 1)[0].split("?", 1)[0].rsplit(":", 1)[0].lower()
            if host not in ("localhost", "[::1]") and not host.startswith("127."):
                weakenings.append(["insecure-transport", server["name"]])
    for name, entry in manifest.get("env", {}).items():
        if isinstance(entry, dict) and ("provider" in entry or "secret" in entry):
            if entry.get("optional") and not granted(entry, facts):
                ungranted.add(reference_name(entry))
    phase = None
    if "change" in facts:
        phase = setup_phase(facts["change"], facts.get("recorded_digest"), facts.get("digest"))
        if setup is None:
            phase = None
    result = {
        "ungranted": sorted(ungranted),
        "supported": supported,
        "env": env.values,
        "env_scripts": scripts,
        "setup": setup,
        "python": python,
        "node": node,
        "needs": {"interpreters": sorted(interpreters), "commands": sorted(set(commands))},
        "weakenings": sorted({tuple(w) for w in weakenings}),
    }
    if "change" in facts:
        result["setup_phase"] = phase
        result["setup_arguments"] = None if phase is None else [phase] + setup["args"]
    return result


#: What a consumer is doing to an overlay when it decides whether setup runs.
CHANGES = ("add", "update", "rerun", "remove")


def setup_phase(change: str, recorded: "Optional[str]", digest: "Optional[str]") -> "Optional[str]":
    """The phase setup runs in, or None when it does not run.

    ``recorded`` is the digest of the last setup of this overlay that succeeded on this OS, which
    the consumer keeps and forgets when the overlay is removed.
    """
    if change == "remove":
        return "remove" if recorded is not None else None
    if recorded is None:
        return "install"
    if change == "rerun" or recorded != digest:
        return "sync"
    return None


def compose(
    overlays: "dict[str, dict[str, Any]]",
    requested: "list[str]",
    files: "Optional[dict[str, list[str]]]" = None,
    facts: "Optional[dict[str, Any]]" = None,
) -> "dict[str, Any]":
    """Resolution, composition order and what the active overlays contribute together."""
    files = files or {}
    try:
        visited, missing = resolve(overlays, requested)
    except ResolveError as error:
        return {"error": error.code, "chain": error.chain}
    active = composition_order(overlays, visited)
    result: "dict[str, Any]" = {
        "install_order": visited,
        "active": active,
        "missing": missing,
        "root_variables": {identity: root_variable(identity) for identity in active},
        "routing": [line for i in active for line in overlays[i].get("routing", [])],
        "rules": [[i, path] for i in active for path in rules_of(overlays[i], files.get(i, []))],
        "context": [
            [i, path] for i in active for path in context_of(overlays[i], files.get(i, []))
        ],
    }
    winners: "dict[str, tuple[str, str]]" = {}
    collisions: "set[str]" = set()
    for identity in active:
        for name in skills_of(overlays[identity], files.get(identity, [])):
            if name.lower() in winners:
                collisions.add(name.lower())
            winners[name.lower()] = (name, identity)
    result["skills"] = {name: identity for name, identity in winners.values()}
    result["skill_collisions"] = sorted(collisions)
    if facts is not None:
        env = Environment(facts.get("base_env", {}), facts["os"] == "windows")
        roots = facts["roots"]
        for identity in active:
            env.set(root_variable(identity), roots[identity])
        weakenings: "list[list[str]]" = []
        try:
            for identity in active:
                tree = files.get(identity, [])
                # A mapping of path to text gives the text of the files read as env files.
                texts = tree if isinstance(tree, dict) else {}
                apply_overlay(
                    env,
                    overlays[identity],
                    dict(facts, files=texts),
                    roots[identity],
                    weakenings,
                    files.get(identity, []),
                    identity,
                )
        except Refused as refused:
            result["env_error"] = {"error": refused.code, "subject": refused.subject}
        else:
            result["env"] = env.values
    return result
