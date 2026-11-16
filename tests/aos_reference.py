"""A small reference reader for AOS, used by this repository's tests and conformance vectors.

It follows the specification's text and nothing else: where the two disagree, the specification
is right and this module has a bug. It is test code, not a library.
"""

from __future__ import annotations

import base64
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


def _ecma_pattern(pattern: str) -> str:
    """A schema pattern for Python's ``re``, which reads ``$`` as matching before a final line
    feed too; ECMA-262, which JSON Schema names, reads it as the end of the string."""
    out, index, in_class = [], 0, False
    while index < len(pattern):
        char = pattern[index]
        if char == "\\":
            out.append(pattern[index : index + 2])
            index += 2
            continue
        if char == "[":
            in_class = True
        elif char == "]":
            in_class = False
        out.append("\\Z" if char == "$" and not in_class else char)
        index += 1
    return "".join(out)


def _pattern(validator: Any, pattern: str, instance: Any, schema: Any) -> Any:
    from jsonschema.exceptions import ValidationError

    if isinstance(instance, str) and not re.search(_ecma_pattern(pattern), instance):
        yield ValidationError("%r does not match %r" % (instance, pattern))


from jsonschema import validators as _validators  # noqa: E402

_Validator = _validators.extend(Draft202012Validator, {"pattern": _pattern})
VALIDATOR = _Validator(SCHEMA, format_checker=FormatChecker())
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

    def __init__(
        self,
        code: str,
        detail: str = "",
        line: "Optional[int]" = None,
        column: "Optional[int]" = None,
    ):
        super().__init__("%s: %s" % (code, detail) if detail else code)
        self.code = code
        self.detail = detail
        #: Where in the document, from 1, when the reader knows: the first line of the file is 1.
        self.line = line
        self.column = column


# --------------------------------------------------------------------------------------------
# Reading: bytes to the data model.
# --------------------------------------------------------------------------------------------


def select_format(data: bytes) -> "tuple[str, bytes]":
    """The format name a document selects and the bytes its parser is given."""
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return _format_line(data, "toml")


def _format_line(data: bytes, default: str) -> "tuple[str, bytes]":
    """A first line ``#!`` names the format; otherwise ``default``. A byte-order mark is not
    dropped here: where the parser's text starts it is an error."""
    if not data.startswith(b"#!"):
        return default, data
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
    return _parse(_known_format(name), payload, max_depth)


def _known_format(name: str) -> str:
    if name not in FORMATS:
        shown = name if _SAFE_FORMAT_NAME.match(name) else "(not shown)"
        raise ReadError("unsupported-format", shown)
    return FORMATS[name]


_TOML_POSITION = re.compile(r"at line (\d+), column (\d+)")


def _parse(kind: str, payload: bytes, max_depth: int) -> "dict[str, Any]":
    """The text after any format line, parsed as ``kind`` and checked against the data model."""
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        raise ReadError("invalid-utf8")
    if text.startswith("﻿"):
        raise ReadError("parse-error", "a byte-order mark where the document starts", 1, 1)
    if not text.strip(" \t\r\n"):
        return {}
    try:
        if kind == "toml":
            try:
                value = tomllib.loads(text)
            except tomllib.TOMLDecodeError as error:
                at = _TOML_POSITION.search(str(error))
                raise ReadError(
                    "parse-error",
                    str(error),
                    int(at.group(1)) if at else None,
                    int(at.group(2)) if at else None,
                )
        elif kind == "json":
            value = _read_json(text)
        else:
            value = _read_yaml(text, max_depth)
    except RecursionError:
        # A parser that recurses on its input stops here, however deep the text goes.
        raise ReadError("too-deep")
    except (ValueError, OverflowError) as error:
        # What a parser cannot convert: an integer too long to read, an escape past Unicode.
        raise ReadError("integer-range" if "digits" in str(error) else "parse-error", str(error))
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

    def integer(digits: str) -> int:
        return _int(digits.lstrip("-").lstrip("0") or "0", 10, digits.startswith("-"))

    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=constant, parse_int=integer)
    except json.JSONDecodeError as error:
        raise ReadError("parse-error", str(error), error.lineno, error.colno)


_YAML_INT = re.compile(r"^[-+]?[0-9]+$")
_YAML_OCT = re.compile(r"^0o[0-7]+$")
_YAML_HEX = re.compile(r"^0x[0-9a-fA-F]+$")
_YAML_FLOAT = re.compile(r"^[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?$")
_YAML_INF = re.compile(r"^[-+]?\.(?:inf|Inf|INF)$")
_YAML_NAN = re.compile(r"^\.(?:nan|NaN|NAN)$")


def _int(digits: str, base: int, negative: bool = False) -> int:
    if len(digits) > {10: 19, 8: 22, 16: 16}[base]:
        raise ReadError("integer-range")
    return -int(digits, base) if negative else int(digits, base)


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
    # Past 64 bits a number is refused unread: some runtimes refuse to convert one this long.
    if _YAML_INT.match(value):
        return _int(value.lstrip("+-0") or "0", 10, value.startswith("-"))
    if _YAML_OCT.match(value):
        return _int(value[2:].lstrip("0") or "0", 8)
    if _YAML_HEX.match(value):
        return _int(value[2:].lstrip("0") or "0", 16)
    if _YAML_FLOAT.match(value):
        return float(value)
    if _YAML_INF.match(value) or _YAML_NAN.match(value):
        raise ReadError("non-finite-float")
    return value


def _read_yaml(text: str, max_depth: int = DEFAULT_MAX_DEPTH) -> Any:
    """One YAML document, built from parser events so no tag, anchor or merge key is applied.

    Events are taken one at a time, so a refusal comes at the first node that earns it, before
    the rest of the document is parsed and with nothing expanded.
    """
    if any(c in text for c in "\x85\u2028\u2029\ufeff"):
        raise ReadError("parse-error", "a Unicode line break YAML 1.1 and 1.2 read differently")
    stack: "list[Any]" = []
    keys: "list[Optional[str]]" = []
    root: Any = None
    documents = 0

    def refuse(code: str, event: Any, detail: str = "") -> ReadError:
        mark = event.start_mark
        return ReadError(code, detail, mark.line + 1, mark.column + 1)

    def add(value: Any, event: Any) -> None:
        nonlocal root
        if not stack:
            root = value
            return
        top = stack[-1]
        if isinstance(top, list):
            top.append(value)
        elif keys[-1] is None:
            if not isinstance(value, str):
                raise refuse("non-string-key", event)
            if value == "<<":
                raise refuse("yaml-merge-key", event)
            if value in top:
                raise refuse("duplicate-key", event, value)
            keys[-1] = value
        else:
            top[keys[-1]] = value
            keys[-1] = None

    try:
        for event in yaml.parse(text, Loader=yaml.SafeLoader):
            if isinstance(event, yaml.AliasEvent):
                raise refuse("yaml-anchor", event, "alias")
            if getattr(event, "anchor", None) is not None:
                raise refuse("yaml-anchor", event, "anchor")
            if getattr(event, "tag", None) is not None:
                raise refuse("yaml-tag", event)
            if isinstance(event, yaml.DocumentStartEvent):
                if event.version is not None or event.tags:
                    raise refuse("yaml-directive", event)
                documents += 1
                if documents > 1:
                    raise refuse("parse-error", event, "more than one document")
            elif isinstance(event, yaml.ScalarEvent):
                try:
                    scalar = _yaml_scalar(event)
                except ReadError as error:
                    raise refuse(error.code, event)
                add(scalar, event)
            elif isinstance(event, (yaml.SequenceStartEvent, yaml.MappingStartEvent)):
                if len(stack) + 1 > max_depth:
                    raise refuse("too-deep", event)
                value: Any = [] if isinstance(event, yaml.SequenceStartEvent) else {}
                add(value, event)
                stack.append(value)
                keys.append(None)
            elif isinstance(event, (yaml.SequenceEndEvent, yaml.MappingEndEvent)):
                stack.pop()
                keys.pop()
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        raise ReadError(
            "parse-error",
            str(error).splitlines()[0],
            mark.line + 1 if mark else None,
            mark.column + 1 if mark else None,
        )
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


# --------------------------------------------------------------------------------------------
# Front matter: OVERLAY.md, and the leading block of a context file or a SKILL.md.
# --------------------------------------------------------------------------------------------

BYTE_ORDER_MARK = b"\xef\xbb\xbf"
WHITE_SPACE = b" \t\r\n"
_FENCES = (b"---", b"...")


def _fence(line: bytes, ended: bool) -> "Optional[bytes]":
    """``---`` or ``...`` when the line is one. ``line`` excludes its LF; ``ended`` says one
    followed, since a CR is part of a line end only before a LF."""
    if ended and line.endswith(b"\r"):
        line = line[:-1]
    line = line.rstrip(b" \t")
    return line if line in _FENCES else None


def _may_open(head: bytes) -> bool:
    """Whether a first line cut off at the bound could still be an opening fence."""
    tail = head[3:]
    if tail.endswith(b"\r"):
        tail = tail[:-1]
    return b"---".startswith(head[:3]) and not tail.strip(b" \t")


def split_front_matter(data: bytes, *, max_bytes: int = DEFAULT_MAX_BYTES) -> "dict[str, Any]":
    """Splits a document's bytes without parsing or changing them.

    ``case`` is ``none``, ``unterminated``, ``too-large``, ``empty`` or ``present``. Offsets count
    from the first byte of the file; ``max_bytes`` bounds the head, from after a byte-order mark
    through the closing fence's line end, and nothing past it is read.
    """
    start = 3 if data.startswith(BYTE_ORDER_MARK) else 0
    limit = start + max_bytes
    whole = {"body_offset": start, "body_line": 1}
    end = data.find(b"\n", start, limit)
    if end < 0 and len(data) > limit:
        if _may_open(data[start:limit]):
            return {"case": "too-large"}
        return dict(whole, case="none")
    first = data[start:] if end < 0 else data[start:end]
    if _fence(first, end >= 0) != b"---":
        return dict(whole, case="none")
    if end < 0:
        return dict(whole, case="unterminated")
    metadata_offset = at = end + 1
    while True:
        lf = data.find(b"\n", at, limit)
        if lf < 0:
            if len(data) > limit:
                return {"case": "too-large"}
            if _fence(data[at:], False) is None:
                return dict(whole, case="unterminated")
            body_offset = len(data)
        elif _fence(data[at:lf], True) is None:
            at = lf + 1
            continue
        else:
            body_offset = lf + 1
        metadata = data[metadata_offset:at]
        return {
            "case": "present" if metadata.strip(WHITE_SPACE) else "empty",
            "metadata": metadata,
            "metadata_offset": metadata_offset,
            "metadata_line": 2,
            "body_offset": body_offset,
            "body_line": 1 + data.count(b"\n", start, body_offset),
        }


def _almost_a_fence(data: bytes) -> bool:
    """A document that is no block but that a person, or a laxer reader, would take for one:
    a fence after white space or a second byte-order mark, a first line that only starts like a
    fence, or a format line before one."""
    lead = data
    while lead[:1] in (b" ", b"\t", b"\r", b"\n") or lead.startswith(BYTE_ORDER_MARK):
        lead = lead[3:] if lead.startswith(BYTE_ORDER_MARK) else lead[1:]
    if lead.startswith((b"---", b"...")):
        return True
    start = 3 if data.startswith(BYTE_ORDER_MARK) else 0
    if data.startswith(b"#!", start):
        end = data.find(b"\n", start)
        if end >= 0:
            second = data.find(b"\n", end + 1)
            line = data[end + 1 :] if second < 0 else data[end + 1 : second]
            return _fence(line, second >= 0) is not None
    return False


def read_front_matter(
    data: bytes, *, max_bytes: int = DEFAULT_MAX_BYTES, max_depth: int = DEFAULT_MAX_DEPTH
) -> "dict[str, Any]":
    """The split, then the metadata read: YAML unless its first line names another format.

    ``case`` tells apart ``none``, ``malformed``, ``unterminated``, ``too-large``, ``empty``,
    ``unknown-format``, ``does-not-parse``, ``not-a-mapping`` and ``mapping``, so a viewer can show
    the text. ``error``
    and ``line`` are what a gate refuses with; ``data`` is the manifest where there is one.
    """
    found = split_front_matter(data, max_bytes=max_bytes)
    case = found["case"]
    if case == "none" and _almost_a_fence(data):
        return dict(found, case="malformed", error="malformed-fence", line=1)
    if case in ("none", "empty"):
        return dict(found, data={})
    if case == "unterminated":
        return dict(found, error="unterminated-front-matter", line=1)
    if case == "too-large":
        return dict(found, error="too-large", line=1)
    metadata = found["metadata"]
    first_line = found["metadata_line"]
    named = metadata.startswith(b"#!")
    try:
        name, payload = _format_line(metadata, "yaml")
        kind = _known_format(name)
        found["format"] = kind
        parsed = _parse(kind, payload, max_depth)
    except ReadError as error:
        if error.code in ("unsupported-format", "no-format-named"):
            case = "unknown-format"
        elif error.code == "not-a-mapping":
            case = "not-a-mapping"
        else:
            case = "does-not-parse"
        line = first_line + (1 if named else 0) + error.line - 1 if error.line else first_line
        return dict(found, case=case, error=error.code, line=line)
    if not payload.strip(WHITE_SPACE):
        return dict(found, case="empty", data=parsed)
    return dict(found, case="mapping", data=parsed)


MANIFEST_FILES = ("OVERLAY.md", "overlay.cfg")


def _as_bytes(value: Any) -> bytes:
    return value if isinstance(value, bytes) else value.encode("utf-8")


def _has_body(files: Any) -> bool:
    """Whether the overlay's ``OVERLAY.md`` has a body. ``files`` holds the text of its files;
    a bare list of paths says nothing about a body."""
    if not isinstance(files, dict) or "OVERLAY.md" not in files:
        return False
    data = _as_bytes(files["OVERLAY.md"])
    # The bound was a matter for reading the manifest; this only looks for the body it found.
    found = split_front_matter(data, max_bytes=len(data))
    return bool(data[found["body_offset"] :].strip(WHITE_SPACE))


def read_overlay(
    files: "dict[str, Any]",
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_context_bytes: int = DEFAULT_MAX_BYTES,
) -> "dict[str, Any]":
    """What a gate reads from an overlay's files, by relative path: the manifest, the file it came
    from, the context entries, the context files it ignores, and the problems of the manifest."""
    present = [name for name in MANIFEST_FILES if name in files]
    if len(present) > 1:
        raise ReadError("two-manifests", "OVERLAY.md and overlay.cfg")
    manifest: "dict[str, Any]" = {}
    body = b""
    body_line = 1
    if present == ["overlay.cfg"]:
        manifest = read_document(
            _as_bytes(files["overlay.cfg"]), max_bytes=max_bytes, max_depth=max_depth
        )
    elif present:
        data = _as_bytes(files["OVERLAY.md"])
        found = read_front_matter(data, max_bytes=max_bytes, max_depth=max_depth)
        if "error" in found:
            raise ReadError(found["error"], "OVERLAY.md", found["line"])
        manifest = found["data"]
        body = data[found["body_offset"] :]
        body_line = found["body_line"]
    context = context_of(manifest, files)
    harness = manifest.get("harness") if isinstance(manifest.get("harness"), dict) else {}
    named = list(context)
    for harness_id, hints in harness.items():
        if isinstance(hints, dict) and "context" in hints:
            named += harness_context_of(manifest, harness_id, files)
    if "OVERLAY.md" in named and _has_body(files):
        if len(body) > max_context_bytes:
            raise ReadError("too-large", "the body of OVERLAY.md", body_line)
        try:
            body.decode("utf-8")
        except UnicodeDecodeError:
            raise ReadError("invalid-utf8", "the body of OVERLAY.md", body_line)
    result: "dict[str, Any]" = {
        "manifest_file": present[0] if present else None,
        "manifest": manifest,
        "context": context,
        "context_ignored": context_ignored(manifest, files),
        "issues": [at for _code, at in validate(manifest, set(files))],
    }
    if isinstance(manifest.get("harness"), dict):
        result["harness_context"] = {
            harness: harness_context_of(manifest, harness, files)
            for harness, hints in manifest["harness"].items()
            if isinstance(hints, dict) and "context" in hints
        }
    return result


def context_file_text(data: bytes, *, max_bytes: int = DEFAULT_MAX_BYTES) -> bytes:
    """A context file's bytes as context: a closed block is dropped unread; the rest is kept."""
    found = split_front_matter(data, max_bytes=max_bytes)
    if found["case"] == "too-large":
        raise ReadError("too-large", "front matter", 1)
    return data[found["body_offset"] :]


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


# --------------------------------------------------------------------------------------------
# Templating: ${NAME} in context and skill bodies, applied when the consumer serves them.
# --------------------------------------------------------------------------------------------

#: The names an overlay's own text can read, besides its options, and the fact giving each one.
TEMPLATE_NAMES = (
    ("AOS_OVERLAY_ROOT", "root"),
    ("AOS_OVERLAY_STATE", "state"),
    ("AOS_OVERLAY_NAME", "name"),
    ("AOS_OVERLAY_SCOPE", "scope"),
    ("AOS_PROJECT_ROOT", "project"),
)
_TEMPLATE_PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _option_text(declared: "dict[str, Any]", name: str, value: Any) -> str:
    """An option's value as text, or ``invalid-option`` when it is not of the declared type."""
    kind = declared.get("type")
    if kind == "string" and isinstance(value, str):
        return value
    if kind == "integer" and isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if kind == "boolean" and isinstance(value, bool):
        return "true" if value else "false"
    raise ReadError("invalid-option", name)


def template_values(manifest: "dict[str, Any]", facts: "dict[str, Any]") -> "dict[str, str]":
    """The names that are replaced and their text. A name with no value is not in it, and so is
    left as written; a sensitive option never is. ``facts`` holds ``root``, ``state``, ``name``,
    ``scope`` and ``project`` when known, and ``options``: the values the user configured."""
    values = {name: facts[key] for name, key in TEMPLATE_NAMES if facts.get(key) is not None}
    options = manifest.get("options")
    configured = facts.get("options", {})
    for name, declared in (options if isinstance(options, dict) else {}).items():
        if declared.get("sensitive") is True:
            continue
        if name in configured:
            values[name] = _option_text(declared, name, configured[name])
        elif "default" in declared:
            values[name] = _option_text(declared, name, declared["default"])
    return values


def template(text: str, values: "dict[str, str]") -> str:
    """``text`` with each ``${NAME}`` whose name is in ``values`` replaced, read from left to
    right; ``$${`` is ``${``, and everything else is itself. A value is never read again."""
    out: "list[str]" = []
    index = 0
    while index < len(text):
        if text.startswith("$${", index):
            out.append("${")
            index += 3
            continue
        found = _TEMPLATE_PLACEHOLDER.match(text, index)
        if found and found.group(1) in values:
            out.append(values[found.group(1)])
            index = found.end()
            continue
        out.append(text[index])
        index += 1
    return "".join(out)


def _utf8(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ReadError("invalid-utf8", str(error)) from None


def context_text(data: bytes, manifest: "dict[str, Any]", facts: "dict[str, Any]") -> str:
    """A context file as the agent receives it: its front matter dropped, then templated."""
    return template(_utf8(context_file_text(data)), template_values(manifest, facts))


def skill_text(data: bytes, manifest: "dict[str, Any]", facts: "dict[str, Any]") -> str:
    """A bundled skill's ``SKILL.md`` as served: the front matter exactly as written, the body
    templated."""
    found = split_front_matter(data)
    if found["case"] == "too-large":
        raise ReadError("too-large", "front matter", 1)
    values = template_values(manifest, facts)
    offset = found["body_offset"]
    return _utf8(data[:offset]) + template(_utf8(data[offset:]), values)


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
    hooks = doc.get("hooks")
    if isinstance(hooks, dict):
        for event, entry in hooks.items():
            if isinstance(entry, dict):
                check(entry.get("timeout"), "/hooks/%s/timeout" % event)
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
    found += _options(doc.get("options"))
    found += _mcp(doc.get("mcp"))
    about = doc.get("about")
    if isinstance(about, dict) and isinstance(about.get("license"), str):
        if not valid_license(about["license"]):
            found.append(("license-expression", "/about/license"))
    found += _skills(doc.get("skills"))
    found += _manifest_named(doc)
    return found


def _options(options: Any) -> "list[tuple[str, str]]":
    """A default is of its option's type, and a sensitive option has none."""
    found: "list[tuple[str, str]]" = []
    if not isinstance(options, dict):
        return found
    for name, declared in options.items():
        if not isinstance(declared, dict) or "default" not in declared:
            continue
        at = "/options/%s" % name
        if declared.get("sensitive") is True:
            found.append(("option-sensitive-default", at + "/default"))
        try:
            _option_text(declared, name, declared["default"])
        except ReadError:
            found.append(("option-default-type", at + "/default"))
    return found


def _skill_at(entry: Any, index: int) -> str:
    """The pointer of an entry's name: the entry, or the ``name`` of a table."""
    return "/skills/%d/name" % index if isinstance(entry, dict) else "/skills/%d" % index


def _skills(skills: Any) -> "list[tuple[str, str]]":
    """The rules of ``skills`` that need no files: names, and what a table's source may be."""
    found: "list[tuple[str, str]]" = []
    if not isinstance(skills, list):
        return found
    seen: "set[str]" = set()
    for index, entry in enumerate(skills):
        name = skill_name(entry)
        if not isinstance(name, str):
            continue
        at = _skill_at(entry, index)
        if _SKILL_NAME.match(name) and not valid_relpath(name):
            found.append(("skill-name", at))
        if name.lower() in seen:
            found.append(("skill-duplicate", at))
        seen.add(name.lower())
        if isinstance(entry, dict) and isinstance(entry.get("source"), str):
            found += _manifest_source(entry, "/skills/%d" % index)
    return found


def _manifest_source(entry: "dict[str, Any]", at: str) -> "list[tuple[str, str]]":
    """A manifest names a source on no machine in particular, and holds no credential."""
    found: "list[tuple[str, str]]" = []
    try:
        parsed = parse_source(entry["source"])
    except ValueError:
        return [("invalid-source", at + "/source")]
    if local_source(parsed):
        found.append(("local-source", at + "/source"))
    elif parsed["kind"] == "url" and not _WEB_URL.match(parsed["location"] or ""):
        found.append(("invalid-source", at + "/source"))
    elif _holds_credentials(parsed["location"] or ""):
        found.append(("source-credentials", at + "/source"))
    if "ref" in entry and (parsed["kind"] != "git" or parsed["ref"] is not None):
        found.append(("ref-not-allowed", at + "/ref"))
    return found


_WEB_URL = re.compile(r"^https?://", re.IGNORECASE)


def _holds_credentials(location: str) -> bool:
    """A query, a password anywhere, or a user over a web URL: what a source shows without.

    ``ssh://git@host`` and ``git@host:path`` name an account, not a secret."""
    if "://" not in location:
        return False
    scheme, authority, rest = _authority(location)
    user = authority.rpartition("@")[0]
    return "?" in rest or ":" in user or bool(user and scheme.lower() in ("http", "https"))


def source_host(location: str) -> "Optional[str]":
    """The host a source reaches, lowercased and without brackets, or None for a path."""
    if "://" in location:
        hostport = _authority(location)[1].rpartition("@")[2]
    elif re.match(r"^[^/\\:]+:", location) and not _DRIVE.match(location):
        hostport = location.split(":", 1)[0].rpartition("@")[2]
        return hostport.lower() or None
    else:
        return None
    if hostport.startswith("["):
        return hostport[1:].split("]", 1)[0].lower()
    return hostport.rsplit(":", 1)[0].lower() if ":" in hostport else hostport.lower()


def _ipv4_part(part: str) -> "Optional[int]":
    """One part of a host written as a URL parser reads it: decimal, ``0x`` hexadecimal or octal
    with a leading zero."""
    if part[:2] in ("0x", "0X"):
        digits, base = part[2:] or "0", 16
    elif len(part) > 1 and part[0] == "0":
        digits, base = part[1:], 8
    else:
        digits, base = part, 10
    allowed = {8: "01234567", 10: "0123456789", 16: "0123456789abcdefABCDEF"}[base]
    if len(digits) > 12 or not all(char in allowed for char in digits):
        return None
    return int(digits, base)


def url_ipv4(host: str) -> "Optional[Any]":
    """The IPv4 address a URL parser reads ``host`` as, or None: one to four parts, each decimal,
    hexadecimal or octal, the last filling the bytes the others leave (``127.1``, ``2130706433``,
    ``0x7f.0.0.1``, ``0177.0.0.1``); one trailing dot is allowed."""
    import ipaddress

    parts = host.split(".")
    if len(parts) > 1 and parts[-1] == "":
        parts.pop()
    if not 1 <= len(parts) <= 4 or "" in parts:
        return None
    numbers = [_ipv4_part(part) for part in parts]
    if any(number is None for number in numbers):
        return None
    *head, last = numbers
    if any(number > 255 for number in head) or last >= 256 ** (5 - len(parts)):
        return None
    value = last
    for position, number in enumerate(head):
        value += number * 256 ** (3 - position)
    return ipaddress.IPv4Address(value)


def host_scope(host: "Optional[str]") -> str:
    """``local`` for this machine (loopback, link-local, unspecified, ``localhost``), ``private``
    for a private network address (the shared address space ``100.64.0.0/10`` included), ``public``
    otherwise, judged on the text alone. An IPv4 address is read as a URL parser reads it."""
    import ipaddress

    if host is None:
        return "public"
    if host == "localhost" or host.endswith(".localhost"):
        return "local"
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = url_ipv4(host)
        if address is None:
            return "public"
    mapped = getattr(address, "ipv4_mapped", None)
    address = mapped or address
    if address.is_loopback or address.is_link_local or address.is_unspecified:
        return "local"
    shared = address.version == 4 and address in ipaddress.ip_network("100.64.0.0/10")
    return "private" if address.is_private or shared else "public"


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
    if isinstance(runtime, dict) and isinstance(runtime.get("node"), list):
        for index, variant in enumerate(runtime["node"]):
            if isinstance(variant, dict) and isinstance(variant.get("package"), str):
                out.append(("/runtime/node/%d/package" % index, variant["package"]))
    scripts = doc.get("scripts")
    if isinstance(scripts, dict):
        for name, target in scripts.items():
            if isinstance(target, str):
                out.append(("/scripts/%s" % name, target))
            elif isinstance(target, dict) and isinstance(target.get("path"), str):
                out.append(("/scripts/%s/path" % name, target["path"]))
    hooks = doc.get("hooks")
    if isinstance(hooks, dict):
        for event, entry in hooks.items():
            if isinstance(entry, str):
                out.append(("/hooks/%s" % event, entry))
            elif isinstance(entry, dict) and isinstance(entry.get("run"), str):
                out.append(("/hooks/%s/run" % event, entry["run"]))
    harness = doc.get("harness")
    if isinstance(harness, dict):
        for harness_id, hints in harness.items():
            if isinstance(hints, dict) and isinstance(hints.get("context"), list):
                for index, path in enumerate(hints["context"]):
                    if isinstance(path, str):
                        out.append(("/harness/%s/context/%d" % (harness_id, index), path))
    about = doc.get("about")
    if isinstance(about, dict) and isinstance(about.get("icon"), str):
        out.append(("/about/icon", about["icon"]))
    return out


def _files(doc: "dict[str, Any]", files: "set[str]") -> "list[tuple[str, str]]":
    found = [("missing-file", at) for at, path in named_files(doc) if path not in files]
    found += _manifest_named(doc)
    hooks = doc.get("hooks")
    if isinstance(hooks, dict) and not default_hook(files, "", ())[1]:
        # A table with no run runs hook.<ext>, which has to be there.
        for event, entry in hooks.items():
            if isinstance(entry, dict) and "run" not in entry:
                found.append(("missing-file", "/hooks/%s" % event))
    env = doc.get("env")
    if isinstance(env, dict):
        added = {entry["variable"] for entry in default_paths(doc, files)}
        for name in env:
            if name.upper() in added:
                found.append(("env-path-conflict", "/env/%s" % name))
    skills = doc.get("skills")
    if isinstance(skills, list):
        bundled = bundled_skills(files)
        folded = {name.lower() for name in bundled}
        for index, entry in enumerate(skills):
            name = skill_name(entry)
            if not isinstance(name, str) or name.lower() not in folded:
                continue
            if isinstance(entry, dict):
                found.append(("skill-ambiguous", _skill_at(entry, index)))
            elif name not in bundled:
                found.append(("skill-case", _skill_at(entry, index)))
    if "OVERLAY.md" in files and "overlay.cfg" in files:
        found.append(("two-manifests", ""))
    mcp = doc.get("mcp")
    if isinstance(mcp, dict) and isinstance(mcp.get("skills"), list):
        for index, link in enumerate(mcp["skills"]):
            name = link.get("name") if isinstance(link, dict) else None
            if isinstance(name, str) and "skills/%s/SKILL.md" % name not in files:
                found.append(("missing-skill", "/mcp/skills/%d/name" % index))
    return found


def _manifest_named(doc: "dict[str, Any]") -> "list[tuple[str, str]]":
    """A manifest is never another field's file: only ``context`` names ``OVERLAY.md``, for its
    body, and nothing names ``overlay.cfg``, so no field of either reaches an agent as text."""
    found = []
    for at, path in named_files(doc):
        is_context = at.startswith("/context/") or "/context/" in at and at.startswith("/harness/")
        if path == "overlay.cfg" or (path == "OVERLAY.md" and not is_context):
            found.append(("manifest-file", at))
    return found


def skill_flags(doc: "dict[str, Any]", files: "Iterable[str]") -> "list[tuple[str, str]]":
    """What a validator flags without refusing: each name neither bundled nor given a source,
    which only a consumer's catalogs can resolve, so a typo is seen before it is looked up."""
    skills = doc.get("skills")
    if not isinstance(skills, list):
        return []
    folded = {name.lower() for name in bundled_skills(files)}
    return [
        ("skill-from-catalog", "/skills/%d" % index)
        for index, entry in enumerate(skills)
        if isinstance(entry, str) and entry.lower() not in folded
    ]


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


def _authority(location: str) -> "tuple[str, str, str]":
    """A URL's scheme, authority and the rest: the authority ends at the first ``/`` or ``?``."""
    scheme, rest = location.split("://", 1)
    cut = len(rest)
    for char in "/?":
        found = rest.find(char)
        if 0 <= found < cut:
            cut = found
    return scheme, rest[:cut], rest[cut:]


def shown_source(parsed: "dict[str, Optional[str]]", ref: "Optional[str]" = None) -> str:
    """A parsed source as a consumer shows it: no user information or query in a URL."""
    location = parsed["location"] or ""
    if "://" in location:
        scheme, authority, rest = _authority(location)
        location = "%s://%s%s" % (scheme, authority.rpartition("@")[2], rest.split("?", 1)[0])
    ref = ref if ref is not None else parsed["ref"]
    return location + ("@" + ref if ref else "") + ("#" + parsed["path"] if parsed["path"] else "")


def source_key(parsed: "dict[str, Optional[str]]", ref: "Optional[str]" = None) -> str:
    """A parsed source in full, as it is fetched: what two entries must share to be one."""
    ref = ref if ref is not None else parsed["ref"]
    return (
        (parsed["location"] or "")
        + ("@" + ref if ref else "")
        + ("#" + parsed["path"] if parsed["path"] else "")
    )


#: Characters no source holds: controls, line separators and what reorders displayed text.
_SOURCE_CONTROL = re.compile(
    "[\x00-\x1f\x7f-\x9f\u2028\u2029\u200e\u200f\u202a-\u202e\u2066-\u2069]"
)


def parse_source(text: str) -> "dict[str, Optional[str]]":
    """``[git+]<location>[@<ref>][#<path>]`` as ``{kind, location, ref, path}``."""
    from urllib.parse import unquote

    raw = text.strip()
    if not raw:
        raise ValueError("empty")
    if _SOURCE_CONTROL.search(raw):
        raise ValueError("control character")
    explicit_git = raw.startswith("git+")
    if explicit_git:
        raw = raw[len("git+") :]
    body, hash_sep, path = raw.partition("#")
    path = (path.strip().strip("/") or None) if hash_sep else None
    location, ref = body.strip(), None
    head, at, tail = location.rpartition("@")
    # An @ inside a URL's authority is user information, never the start of a ref.
    in_authority = "://" in location and len(head) < len(location) - len(_authority(location)[2])
    if (
        at
        and head
        and tail
        and not in_authority
        and not re.search(r"[/:\\]", tail)
        and not head.endswith(("://", ":"))
        and (explicit_git or _is_git_location(head))
    ):
        location, ref = head, tail
    if path is not None and not valid_relpath(path):
        raise ValueError("path")
    parts: "list[str]" = []
    if "://" in location:
        scheme, authority, _rest = _authority(location)
        if "\\" in authority:
            raise ValueError("backslash in the authority")
        user, _at, hostport = authority.rpartition("@")
        host, _colon, port = (
            hostport.rpartition(":") if not hostport.endswith("]") else (hostport, "", "")
        )
        parts = [user, host or hostport, port]
    elif re.match(r"^[^/\\:]+:", location) and not _DRIVE.match(location):
        hostpart, _colon, rest = location.partition(":")
        parts = [hostpart.rpartition("@")[0], hostpart.rpartition("@")[2], rest]
    if any(unquote(part).startswith("-") for part in parts):
        raise ValueError("option-like")
    if explicit_git or _is_git_location(location):
        if location.startswith("-") or (ref or "").startswith("-"):
            raise ValueError("option-like")
        if "::" in location:
            raise ValueError("git remote helper")
        if "://" in location:
            scheme = location.split("://", 1)[0]
            if scheme.lower() not in ("https", "http", "ssh", "git", "file"):
                raise ValueError("scheme")
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
DEFAULT_KEYS = (
    "bin",
    "lib",
    "env",
    "env_scripts",
    "setup",
    "deps",
    "context",
    "skills",
    "rules",
    "hooks",
)
#: Default path additions as ``(key, variable, directory)``, in the order they apply.
DEFAULT_PATHS = (
    ("bin", "PATH", "bin"),
    ("lib", "PYTHONPATH", "lib/python"),
    ("lib", "NODE_PATH", "lib/node"),
)
#: The default dependency file of each runtime, and the lock looked for beside it (``None``: the
#: file itself is a lock when every requirement in it carries a hash).
DEFAULT_DEPENDENCIES = (
    ("python", "lib/python/requirements.txt", None),
    ("node", "lib/node/package.json", "lib/node/package-lock.json"),
)
#: The list variable each runtime's installed packages are added to.
PACKAGE_VARIABLES = {"python": "PYTHONPATH", "node": "NODE_PATH"}
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


def requirements_locked(text: str, path: str) -> bool:
    """Whether a requirements file is a lock: every requirement in it carries ``--hash``.

    A file where only some do is refused: pip would check hashes for all of them.
    """
    hashed = []
    for line in re.sub(r"\\\r?\n", " ", text).splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            hashed.append(re.search(r"(?:^|\s)--hash[=\s]", line) is not None)
    if hashed and all(hashed):
        return True
    if any(hashed):
        raise Refused("partial-lock", path)
    return False


def environment_name(variant: "dict[str, Any]") -> str:
    """The environment a runtime variant installs into: ``shared``, ``isolated`` or a name."""
    return normalize_name(variant.get("environment", "shared"))


def dependencies_of(
    manifest: "dict[str, Any]", files: "Iterable[str]", os_name: str
) -> "list[dict[str, Any]]":
    """The dependency files a consumer installs, one per runtime, with the lock and environment.

    A selected variant that names a file replaces the default one; a variant that names none
    still chooses the environment of the default file.
    """
    runtime = manifest.get("runtime")
    runtime = runtime if isinstance(runtime, dict) else {}
    members = _members(files)
    texts = files if isinstance(files, dict) else {}
    found = []
    for name, default, beside in DEFAULT_DEPENDENCIES:
        variant = first_variant(runtime.get(name, []), os_name) or {}
        lock: "Optional[str]"
        if name == "python" and ("lock" in variant or "requirements" in variant):
            path = variant.get("lock", variant.get("requirements"))
            lock = variant.get("lock")
        elif name == "node" and "package" in variant:
            path = variant["package"]
            candidate = path[: -len("package.json")] + "package-lock.json"
            lock = candidate if candidate in members else None
        elif default_on(manifest, "deps") and default in members:
            path = default
            if beside is None:
                text = texts.get(path)
                lock = path if text is not None and requirements_locked(text, path) else None
            else:
                lock = beside if beside in members else None
        else:
            continue
        found.append(
            {"runtime": name, "file": path, "lock": lock, "environment": environment_name(variant)}
        )
    return found


def rules_of(manifest: "dict[str, Any]", files: "Iterable[str]") -> "list[str]":
    """Every ``rules/<name>.md`` by path bytes, then ``rules``."""
    found = []
    if default_on(manifest, "rules"):
        found = [path for path in _by_bytes(_members(files)) if _RULES_FILE.match(path)]
    return _merge(found, _declared(manifest, "rules"))


def _body_is_context(manifest: "dict[str, Any]", files: "Iterable[str]") -> bool:
    if not _has_body(files):
        return False
    return default_on(manifest, "context") or "OVERLAY.md" in _declared(manifest, "context")


def context_of(manifest: "dict[str, Any]", files: "Iterable[str]") -> "list[str]":
    """The body of ``OVERLAY.md`` or else the root ``CONTEXT.md``, then ``context``.

    While a body is context, ``CONTEXT.md`` is not, wherever it is named.
    """
    found = []
    if default_on(manifest, "context"):
        if _has_body(files):
            found = ["OVERLAY.md"]
        elif "CONTEXT.md" in _members(files):
            found = ["CONTEXT.md"]
    merged = _merge(found, _declared(manifest, "context"))
    if _body_is_context(manifest, files):
        return [entry for entry in merged if entry != "CONTEXT.md"]
    return merged


def context_ignored(manifest: "dict[str, Any]", files: "Iterable[str]") -> "list[str]":
    """The file a consumer reports as ignored because a body is the context instead."""
    if _body_is_context(manifest, files) and "CONTEXT.md" in _members(files):
        return ["CONTEXT.md"]
    return []


def harness_context_of(
    manifest: "dict[str, Any]", harness: str, files: "Iterable[str]"
) -> "list[str]":
    """One harness's ``context``, without ``CONTEXT.md`` while a body is context."""
    hints = manifest.get("harness", {}).get(harness, {})
    listed = list(hints.get("context", []))
    if _body_is_context(manifest, files):
        return [entry for entry in listed if entry != "CONTEXT.md"]
    return listed


def skill_name(entry: Any) -> Any:
    """The name of an entry of ``skills``: the string, or a table's ``name``."""
    return entry.get("name") if isinstance(entry, dict) else entry


def bundled_skills(files: "Iterable[str]") -> "set[str]":
    """The names with a ``skills/<name>/SKILL.md`` in the overlay."""
    found = set()
    for path in _members(files):
        parts = path.split("/")
        if len(parts) == 3 and parts[0] == "skills" and parts[2] == "SKILL.md":
            if _SKILL_NAME.match(parts[1]):
                found.add(parts[1])
    return found


def skill_entries(manifest: "dict[str, Any]", files: "Iterable[str]") -> "list[dict[str, Any]]":
    """Every skill the overlay offers, by name bytes: ``bundled``, from a ``source``, or a name
    for the consumer's ``catalog`` to resolve."""
    bundled = bundled_skills(files)
    found: "dict[str, dict[str, Any]]" = {}
    if default_on(manifest, "skills"):
        found = {name: {"name": name, "origin": "bundled"} for name in bundled}
    for entry in _declared(manifest, "skills"):
        if isinstance(entry, dict):
            parsed = parse_source(entry["source"])
            source = shown_source(parsed, entry.get("ref"))
            item = {"name": entry["name"], "origin": "source", "source": source}
            item["key"] = source_key(parsed, entry.get("ref"))
            if "pin" in entry:
                item["pin"] = entry["pin"]
            found[entry["name"]] = item
        elif entry in bundled:
            found[entry] = {"name": entry, "origin": "bundled"}
        else:
            found[entry] = {"name": entry, "origin": "catalog"}
    return [found[name] for name in _by_bytes(found)]


def skills_of(manifest: "dict[str, Any]", files: "Iterable[str]") -> "list[str]":
    """The names of :func:`skill_entries`."""
    return [entry["name"] for entry in skill_entries(manifest, files)]


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
# Applying declarations: the effective environment, setup, runtime and non_defaults.
# --------------------------------------------------------------------------------------------

SENSITIVE_NAMES = frozenset(
    """PATH PATHEXT HOME USERPROFILE SHELL COMSPEC SYSTEMROOT BASH_ENV ENV ZDOTDIR PROMPT_COMMAND
    IFS EDITOR VISUAL PAGER LESSOPEN LESSCLOSE XDG_CONFIG_HOME XDG_DATA_HOME APPDATA LOCALAPPDATA
    TMPDIR TEMP TMP PSMODULEPATH CLASSPATH JAVA_TOOL_OPTIONS _JAVA_OPTIONS JDK_JAVA_OPTIONS
    PERL5OPT PERL5LIB RUBYOPT RUBYLIB RUSTFLAGS GOPROXY GONOSUMDB GONOSUMCHECK GOPRIVATE GOFLAGS
    SSH_ASKPASS SSLKEYLOGFILE REQUESTS_CA_BUNDLE CURL_CA_BUNDLE CLAUDE_CONFIG_DIR CODEX_HOME""".split()
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
#: Path additions exist for these, so adding to them is not a non_default.
PATH_VARIABLES = frozenset(("PATH", "PYTHONPATH", "NODE_PATH"))
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


SUBJECT_LIMIT = 256


def safe_subject(subject: str) -> str:
    """A refusal's subject with each control, format, line- and paragraph-separator, surrogate,
    private-use and unassigned character written as ``\\xNN``, ``\\uNNNN`` or ``\\UNNNNNNNN`` in
    lowercase hexadecimal, and the whole cut to 256 characters, then ``...``."""
    import unicodedata

    out = []
    for char in subject[: SUBJECT_LIMIT + 1]:
        if unicodedata.category(char) in ("Cc", "Cf", "Zl", "Zp", "Cs", "Co", "Cn"):
            code = ord(char)
            out.append(
                "\\x%02x" % code
                if code < 0x100
                else "\\u%04x" % code if code < 0x10000 else "\\U%08x" % code
            )
        else:
            out.append(char)
    text = "".join(out)
    return text if len(text) <= SUBJECT_LIMIT else text[:SUBJECT_LIMIT] + "..."


class Refused(Exception):
    """A declaration the consumer refuses to apply; ``code`` is the vectors' class."""

    def __init__(self, code: str, subject: str):
        subject = safe_subject(subject)
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
        #: Every ``set``, as ``(name, value, secret, join)``, so a caller can replay one overlay's
        #: writes onto another environment; ``join`` is a path addition's parts.
        self.writes: "list[tuple[str, str, bool, Any]]" = []

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

    def set(self, name: str, value: str, secret: bool = False, join: Any = None) -> None:
        self.writes.append((name, value, secret, join))
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
    non_defaults: "list[list[str]]",
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
                non_defaults.append(["env-passthrough", entry["key"]])
            else:
                non_defaults.append(["secret-read", reference_name(entry)])
        if is_sensitive(name):
            non_defaults.append(["env-sensitive", name])
        env.set(name, value, secret)


def _apply_dotenv(
    env: Environment,
    entries: "list[tuple[str, str, bool]]",
    non_defaults: "list[list[str]]",
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
            non_defaults.append(["env-sensitive", name])
        env.set(name, value)


def _apply_paths(
    env: Environment,
    paths: "list[dict[str, Any]]",
    root: str,
    os_name: str,
    non_defaults: "list[list[str]]",
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
            non_defaults.append(["env-sensitive", variable])
        prepend: "list[str]" = []
        append: "list[str]" = []
        seen: "set[str]" = set()
        for entry in entries:
            if "packages" in entry:
                resolved = entry["packages"]
            else:
                resolved = resolve_path(root, entry["path"], windows)
            if resolved in seen:
                continue
            seen.add(resolved)
            (append if entry.get("position") == "append" else prepend).append(resolved)
        current = env.get(variable) or ""
        kept = [c for c in current.split(separator) if c and c not in seen]
        env.set(
            variable,
            separator.join(prepend + kept + append),
            env._key(variable) in env.secret,
            (separator, prepend, seen, append),
        )


def require_applicable(manifest: "dict[str, Any]") -> None:
    """Refuse a manifest that would make the consumer touch what a manifest may not name: a
    variable whose name is not a name (``A=B``, a line break) or a path that leaves the overlay
    (``../x``, an absolute path, a device name). Nothing else is checked here; the rest of a
    manifest's faults are for ``validate``. Raises ``invalid-reference`` with the name or path."""
    env = manifest.get("env")
    for name in env if isinstance(env, dict) else ():
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise Refused("invalid-reference", name)

    def check(path: Any) -> None:
        if isinstance(path, str) and not valid_relpath(path):
            raise Refused("invalid-reference", path)

    for field in ("paths", "env_files", "env_scripts", "setup"):
        entries = manifest.get(field)
        for entry in entries if isinstance(entries, list) else ():
            check(entry.get("path") if isinstance(entry, dict) else entry)
    scripts = manifest.get("scripts")
    for target in scripts.values() if isinstance(scripts, dict) else ():
        check(target.get("path") if isinstance(target, dict) else target)
    runtime = manifest.get("runtime")
    for variants in runtime.values() if isinstance(runtime, dict) else ():
        for variant in variants if isinstance(variants, list) else ():
            for key in ("lock", "requirements", "package"):
                check(variant.get(key) if isinstance(variant, dict) else None)


def apply_overlay(
    env: Environment,
    manifest: "dict[str, Any]",
    facts: "dict[str, Any]",
    root: str,
    non_defaults: "list[list[str]]",
    tree: "Iterable[str]" = (),
    identity: str = "",
    state: "Optional[str]" = None,
) -> "list[dict[str, Any]]":
    """Steps 2.1 to 2.3 of the order of application; returns the env scripts that run.

    ``tree`` is the overlay's files, from which the defaults of unwritten fields follow. Its
    placeholders also see the ``AOS_OVERLAY_*`` values a step of this overlay receives.
    """
    require_applicable(manifest)
    os_name = facts["os"]
    env.extra = {"AOS_OVERLAY_ROOT": root, "AOS_OVERLAY_NAME": normalize_name(identity)}
    if state is not None:
        env.extra["AOS_OVERLAY_STATE"] = state
    try:
        return _apply_overlay(env, manifest, facts, root, non_defaults, tree)
    finally:
        env.extra = {}


def _apply_overlay(
    env: Environment,
    manifest: "dict[str, Any]",
    facts: "dict[str, Any]",
    root: str,
    non_defaults: "list[list[str]]",
    tree: "Iterable[str]",
) -> "list[dict[str, Any]]":
    os_name = facts["os"]
    # The installed packages of each runtime follow the default additions, so lib/python/ and
    # lib/node/ come first and declared entries after.
    defaults = default_paths(manifest, tree)
    installed = facts.get("packages", {})
    packages = [
        {"variable": PACKAGE_VARIABLES[dep["runtime"]], "packages": installed[dep["runtime"]]}
        for dep in dependencies_of(manifest, tree, os_name)
        if dep["runtime"] in installed
    ]
    paths = defaults + packages + _declared(manifest, "paths")
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
            _apply_dotenv(env, lines, non_defaults)
        else:
            _apply_mapping(env, mapping, facts, root, non_defaults)
    _apply_mapping(env, manifest.get("env", {}), facts, root, non_defaults)
    _apply_paths(env, paths, root, os_name, non_defaults)
    scripts = []
    if facts.get("env_scripts_enabled", True):
        chosen, _configured, present, others = default_script(
            manifest, "env_scripts", "env", tree, os_name, facts.get("interpreters", INTERPRETERS)
        )
        if not env_scripts_allowed(facts):
            # Off until the user allows the digest: the overlay is otherwise applied.
            if chosen or present or any(os_matches(script, os_name) for script in others):
                non_defaults.append(["env-script-not-allowed", facts.get("identity", "")])
            return scripts
        if chosen is None:
            non_defaults.extend(["script-not-run", path] for path in present)
        for script in ([chosen] if chosen else []) + others:
            if os_matches(script, os_name):
                selected = {"interpreter": script["interpreter"], "path": script["path"]}
                selected["args"] = script.get("args", [])
                selected["timeout"] = script.get("timeout", 60)
                scripts.append(selected)
                non_defaults.append(["env-script", script["path"]])
                if selected["timeout"] == 0:
                    non_defaults.append(["no-timeout", script["path"]])
    return scripts


#: Report ids that ``effective`` gives under ``reports`` rather than ``non_defaults``.
REPORT_IDS = ("env-script-not-allowed",)


def env_scripts_allowed(facts: "dict[str, Any]") -> bool:
    """Whether the overlay's env scripts may run: its ``digest`` is the one ``allowed``, which is
    the allowance of its hooks. A case that states no ``allowed`` leaves the allowance out of play
    (``null`` is a consumer that allowed nothing)."""
    if "allowed" not in facts:
        return True
    digest, allowed = facts.get("digest"), facts["allowed"]
    return digest is not None and allowed is not None and same_digest(digest, allowed)


def effective(manifest: "dict[str, Any]", facts: "dict[str, Any]") -> "dict[str, Any]":
    """What a consumer applies for one overlay: environment, setup, runtime, needs, non_defaults.

    An env script the allowance does not cover is not selected, and the result's ``reports``
    (present only when there is one) say so.
    """
    os_name = facts["os"]
    windows = os_name == "windows"
    root = facts["root"]
    non_defaults: "list[list[str]]" = []
    if not facts.get("pinned", False):
        non_defaults.append(["unpinned", ""])
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
            non_defaults,
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
            non_defaults.extend(["script-not-run", path] for path in present)
    if setup is not None:
        setup = {
            "interpreter": setup["interpreter"],
            "path": setup["path"],
            "args": setup.get("args", []),
            "timeout": setup.get("timeout", 300),
            "network": setup.get("network", network),
        }
        if setup["network"]:
            non_defaults.append(["setup-network", setup["path"]])
        elif not facts.get("enforces_network", True):
            non_defaults.append(["network-not-enforced", setup["path"]])
        if setup["timeout"] == 0:
            non_defaults.append(["no-timeout", setup["path"]])
    python = first_variant(runtime.get("python", []), os_name)
    if python is not None:
        python = {key: value for key, value in python.items() if key != "os"}
    try:
        dependencies = dependencies_of(manifest, facts.get("files", {}), os_name)
    except Refused as refused:
        return {"error": refused.code, "subject": refused.subject}
    for dependency in dependencies:
        # Installing fetches packages: it needs the network, locked or not.
        non_defaults.append(["deps-network", dependency["file"]])
        if dependency["lock"] is None:
            non_defaults.append(["unlocked-dependencies", dependency["file"]])
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
    for dependency in dependencies:
        interpreters.add(dependency["runtime"])
        if dependency["runtime"] == "node":
            commands.append("npm")
    ungranted: "set[str]" = set()
    host_grants = facts.get("grants", {}).get("env", [])
    for server in manifest.get("mcp", {}).get("servers", []):
        for value in server.get("env", {}).values():
            if isinstance(value, dict) and ("provider" in value or "secret" in value):
                if not granted(value, facts):
                    ungranted.add(reference_name(value))
                elif value.get("provider") == "env":
                    non_defaults.append(["env-passthrough", value["key"]])
                else:
                    non_defaults.append(["secret-read", reference_name(value)])
        for name in list(server.get("env_passthrough", [])) + list(
            server.get("headers_env", {}).values()
        ):
            if name in host_grants:
                non_defaults.append(["env-passthrough", name])
            else:
                ungranted.add("env:" + name)
        url = server.get("url", "")
        if url[:7].lower() == "http://":
            host = url[7:].split("/", 1)[0].split("?", 1)[0].rsplit(":", 1)[0].lower()
            if host not in ("localhost", "[::1]") and not host.startswith("127."):
                non_defaults.append(["insecure-transport", server["name"]])
    for name, entry in manifest.get("env", {}).items():
        if isinstance(entry, dict) and ("provider" in entry or "secret" in entry):
            if entry.get("optional") and not granted(entry, facts):
                ungranted.add(reference_name(entry))
    result = {
        "ungranted": sorted(ungranted),
        "supported": supported,
        "env": env.values,
        "env_scripts": scripts,
        "setup": setup,
        "python": python,
        "node": node,
        "dependencies": dependencies,
        "needs": {"interpreters": sorted(interpreters), "commands": sorted(set(commands))},
        "non_defaults": sorted({tuple(w) for w in non_defaults if w[0] not in REPORT_IDS}),
    }
    reports = sorted({tuple(w) for w in non_defaults if w[0] in REPORT_IDS})
    if reports:
        result["reports"] = reports
    if "change" in facts:
        result.update(
            preparation(
                facts["change"],
                facts.get("record"),
                facts.get("digest"),
                setup,
                dependencies,
                facts.get("fails"),
            )
        )
    return result


#: What a consumer is doing to an overlay when it decides whether setup runs: adding it, a sync
#: (a fetch of its source, a change of ref or pin, or setup run again on request), preparing a
#: digest for activation outside a sync, and removing it.
CHANGES = ("add", "sync", "activate", "remove")


def setup_phase(change: str, recorded: "Optional[str]", digest: "Optional[str]") -> "Optional[str]":
    """The phase of the preparation, or None when nothing runs.

    ``recorded`` is the digest of the last preparation of this overlay that succeeded on this OS,
    which the consumer keeps per identity and forgets when the overlay is removed.
    """
    if change not in CHANGES:
        raise ValueError(change)
    if change == "remove":
        return "remove" if recorded is not None else None
    if recorded is None:
        return "install"
    if change != "activate" or recorded != digest:
        return "sync"
    return None


def preparation(
    change: str,
    record: "Optional[dict[str, str]]",
    digest: "Optional[str]",
    setup: "Optional[dict[str, Any]]",
    dependencies: "list[dict[str, Any]]",
    fails: "Optional[str]" = None,
) -> "dict[str, Any]":
    """The phase, the steps in order, the record after them, and whether the digest activates.

    ``fails`` names the step that fails (``deps`` or ``setup``); the steps stop there, except
    that a removal still deletes everything.
    """
    recorded = record["digest"] if record else None
    phase = None
    if setup is not None or dependencies:
        phase = setup_phase(change, recorded, digest)
    steps: "list[str]" = []
    if phase == "install":
        steps.append("empty-state")
    if phase in ("install", "sync"):
        steps += ["deps:" + dependency["runtime"] for dependency in dependencies]
    if phase is not None and setup is not None:
        steps.append("setup")
    failed = False
    if fails is not None:
        for index, step in enumerate(steps):
            if step.split(":")[0] == fails:
                steps, failed = steps[: index + 1], True
                break
    if change == "remove":
        steps.append("delete")
        after, activates = None, False
    elif phase is None:
        after, activates = record, True
    elif failed:
        # The record still names the last digest that was prepared; only that one stays usable.
        after, activates = record, recorded == digest
    else:
        steps.append("record")
        after, activates = {"digest": digest, "phase": phase}, True
    arguments = None
    if phase is not None and setup is not None:
        arguments = [phase] + setup["args"]
    return {
        "setup_phase": phase,
        "setup_arguments": arguments,
        "steps": steps,
        "record": after,
        "activates": activates,
    }


_PINNED_REQUIREMENT = re.compile(
    r"^([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)\s*(?:\[[^\]]*\])?\s*===?\s*([^\s;\\]+)"
)


def _pins(dependency: "dict[str, Any]", text: "Optional[str]") -> "dict[str, str]":
    """Package name to the exact version or range a dependency file asks for."""
    if text is None:
        return {}
    if dependency["runtime"] == "node":
        try:
            declared = json.loads(text).get("dependencies", {})
        except (ValueError, AttributeError):
            return {}
        return {name: str(spec) for name, spec in declared.items()}
    pins = {}
    for line in re.sub(r"\\\r?\n", " ", text).splitlines():
        match = _PINNED_REQUIREMENT.match(line.strip())
        if match:
            pins[re.sub(r"[-_.]+", "-", match.group(1)).lower()] = match.group(2)
    return pins


def environments(
    overlays: "dict[str, dict[str, Any]]",
    active: "list[str]",
    files: "dict[str, Any]",
    os_name: str,
    removed: "Iterable[str]" = (),
) -> "dict[str, Any]":
    """The environments the active overlays install into, the conflicts that block overlays, and
    what each removed overlay leaves.

    A shared or named environment holds every overlay that chose it, in composition order, and
    is installed from all their files at once. Two members asking for one package at different
    versions conflict, and both stay inactive.
    """

    def key(dependency: "dict[str, Any]", identity: str) -> "tuple[str, str, str]":
        isolated = dependency["environment"] == "isolated"
        return (dependency["runtime"], dependency["environment"], identity if isolated else "")

    groups: "dict[tuple[str, str, str], list[tuple[str, dict[str, Any]]]]" = {}
    for identity in active:
        for dependency in dependencies_of(overlays[identity], files.get(identity, []), os_name):
            groups.setdefault(key(dependency, identity), []).append((identity, dependency))
    conflicts = []
    blocked: "set[str]" = set()
    for (runtime, name, _owner), members in groups.items():
        asked: "dict[str, dict[str, list[str]]]" = {}
        for identity, dependency in members:
            tree = files.get(identity, [])
            text = tree.get(dependency["file"]) if isinstance(tree, dict) else None
            for package, version in _pins(dependency, text).items():
                asked.setdefault(package, {}).setdefault(version, []).append(identity)
        for package in sorted(asked, key=lambda p: p.encode("utf-8")):
            if len(asked[package]) > 1:
                involved = [i for i, _d in members if any(i in v for v in asked[package].values())]
                conflicts.append(
                    {
                        "runtime": runtime,
                        "environment": name,
                        "package": package,
                        "overlays": involved,
                    }
                )
                blocked.update(involved)
    built = []
    remaining = set()
    for group, members in groups.items():
        runtime, name, _owner = group
        kept = [(i, d) for i, d in members if i not in blocked]
        if not kept:
            continue
        remaining.add(group)
        locks = [d["lock"] for _i, d in kept]
        if runtime == "node":
            # npm installs one lock file; several overlays' locks cannot be combined.
            locked = len(kept) == 1 and locks[0] is not None
        else:
            locked = all(lock is not None for lock in locks)
        built.append(
            {
                "runtime": runtime,
                "environment": name,
                "overlays": [i for i, _d in kept],
                "files": [[i, d["file"]] for i, d in kept],
                "locked": locked,
            }
        )
    left = []
    for identity in removed:
        for dependency in dependencies_of(overlays[identity], files.get(identity, []), os_name):
            then = "rebuilt" if key(dependency, identity) in remaining else "deleted"
            left.append(
                {
                    "overlay": identity,
                    "runtime": dependency["runtime"],
                    "environment": dependency["environment"],
                    "then": then,
                }
            )
    return {
        "environments": built,
        "conflicts": conflicts,
        "blocked": [i for i in active if i in blocked],
        "left": left,
    }


def _skill_origin(entry: "dict[str, Any]", identity: str) -> Any:
    """What two overlays must share to name one skill without colliding: a bundled skill is its
    overlay's own, one from elsewhere is its source in full, as fetched, and its pin."""
    if entry["origin"] == "bundled":
        return ("bundled", identity)
    return (entry.get("key"), entry.get("pin"))


def _deliver(
    winners: "dict[str, tuple[str, str, Any]]",
    collisions: "set[str]",
    entry: "dict[str, Any]",
    identity: str,
) -> bool:
    """Records one skill offered for delivery. A skill from elsewhere never takes a name another
    overlay's skill holds: it is reported, and only the user's configuration could choose it."""
    folded = entry["name"].lower()
    origin = _skill_origin(entry, identity)
    if folded in winners and winners[folded][2] != origin:
        collisions.add(folded)
        if entry["origin"] != "bundled":
            return False
    winners[folded] = (entry["name"], identity, origin)
    return True


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
    winners: "dict[str, tuple[str, str, Any]]" = {}
    collisions: "set[str]" = set()
    for identity in active:
        for entry in skill_entries(overlays[identity], files.get(identity, [])):
            _deliver(winners, collisions, entry, identity)
    result["skills"] = {name: identity for name, identity, _origin in winners.values()}
    result["skill_collisions"] = sorted(collisions)
    if facts is not None:
        try:
            installed = environments(overlays, active, files, facts["os"], facts.get("removed", []))
        except Refused as refused:
            result["env_error"] = {"error": refused.code, "subject": refused.subject}
            return result
        result.update(installed)
        # An overlay in a conflict is not activated, so it contributes nothing.
        active = [identity for identity in active if identity not in installed["blocked"]]
        result["active"] = active
        env = Environment(facts.get("base_env", {}), facts["os"] == "windows")
        roots = facts["roots"]
        for identity in active:
            env.set(root_variable(identity), roots[identity])
        non_defaults: "list[list[str]]" = []
        packages = facts.get("packages", {})
        try:
            if "pre_env" in facts:
                result["hook_reports"] = []
                result["hook_non_defaults"] = []
                _apply_pre_env(env, active, facts["pre_env"], facts.get("hook_limits", {}), result)
            for identity in active:
                tree = files.get(identity, [])
                # A mapping of path to text gives the text of the files read as env files.
                texts = tree if isinstance(tree, dict) else {}
                apply_overlay(
                    env,
                    overlays[identity],
                    dict(facts, files=texts, packages=packages.get(identity, {})),
                    roots[identity],
                    non_defaults,
                    files.get(identity, []),
                    identity,
                )
        except Refused as refused:
            result["env_error"] = {"error": refused.code, "subject": refused.subject}
        else:
            result["env"] = env.values
    return result


def _apply_pre_env(
    env: Environment,
    active: "list[str]",
    runs: "dict[str, dict[str, Any]]",
    limits: "dict[str, int]",
    result: "dict[str, Any]",
) -> None:
    """The ``pre-env`` hooks' output, every overlay's in composition order, after the root
    variables and before any overlay's declarations; reports and non_defaults go to ``result``."""
    for identity in active:
        if identity not in runs:
            continue
        fired = fire_event(
            "pre-env", [dict(runs[identity], source=identity)], None, limits, env.windows
        )
        result["hook_reports"] += fired["reports"]
        result["hook_non_defaults"] += fired["non_defaults"]
        if fired["decision"] == "refuse":
            raise Refused("hook-refused", identity)
        for name, value in fired["env"].items():
            if value is None:
                key = env._key(name)
                if key is not None:
                    del env.values[key]
            else:
                env.set(name, value)


# --------------------------------------------------------------------------------------------
# Hooks: what runs at a session's events, what it is told, and what of its output applies.
# --------------------------------------------------------------------------------------------

#: Each event: its class, whether ``hook.<ext>`` gets it by default, the outputs it takes, what a
#: refusal is for it (``None``: it cannot be refused), and what ``match`` selects.
HOOK_EVENTS: "dict[str, tuple[str, bool, tuple[str, ...], Optional[str], Optional[str]]]" = {
    "pre-env": ("core", True, ("env",), "refuse", None),
    "session-start": ("core", True, ("context", "env"), "refuse", "reason"),
    "session-end": ("core", True, (), None, None),
    "prompt": ("core", False, ("context", "block", "env"), "block", None),
    "turn-end": ("core", True, (), None, None),
    "cd": ("extended", True, ("env",), None, None),
    "pre-compact": ("extended", True, ("context", "block"), "block", None),
    "pre-tool": (
        "extended",
        False,
        ("context", "deny", "ask", "allow", "input", "env"),
        "deny",
        "kind",
    ),
    "post-tool": ("extended", False, ("context",), None, "kind"),
}
SESSION_REASONS = ("new", "resume", "clear", "compact", "fork")
TOOL_KINDS = (
    "read",
    "edit",
    "delete",
    "move",
    "search",
    "execute",
    "think",
    "fetch",
    "switch_mode",
    "other",
)
#: The payload's keys: these three for every event, then each event's own.
PAYLOAD_COMMON = ("event", "harness", "cwd")
PAYLOAD_KEYS = {
    "pre-env": (),
    "session-start": ("session", "reason"),
    "session-end": ("session",),
    "prompt": ("session", "prompt"),
    "turn-end": ("session",),
    "cd": ("session", "previous"),
    "pre-compact": ("session", "trigger"),
    "pre-tool": ("session", "tool"),
    "post-tool": ("session", "tool", "status"),
}
TOOL_KEYS = ("kind", "name", "input")
HOOK_OUTPUT_KEYS = ("context", "decision", "reason", "input", "env")
DEFAULT_HOOK_TIMEOUT = 30
DEFAULT_HOOK_LIMITS = {
    "context_bytes": 1024 * 1024,
    "timeout": 60,
    "event_timeout": 120,
    "max_output": 64 * 1024,
    "max_payload": 1024 * 1024,
}
#: The longest ``reason``, in code points: it is shown beside what it is about.
MAX_HOOK_REASON = 1024
#: Characters a hook's text may not hold: controls other than tab, line feed and carriage return,
#: and the bidirectional overrides and isolates, which change how the text around them reads.
_HOOK_TEXT_REFUSED = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f‪-‮⁦-⁩]")
#: Combined decisions, loosest first.
_UNSET: Any = object()
_DECISION_RANK = {None: 0, "allow": 1, "ask": 2, "deny": 3, "block": 3, "refuse": 3}


class HookFailure(Exception):
    """A run of a hook that failed; ``cause`` is the vectors' class."""

    def __init__(self, cause: str):
        super().__init__(cause)
        self.cause = cause


def default_hook(
    files: "Iterable[str]", os_name: str, interpreters: "Iterable[str]"
) -> "tuple[Optional[dict[str, str]], list[str]]":
    """The ``hook.<ext>`` chosen by runtime, and every one present."""
    members = set(_members(files))
    present = [("hook" + ext) for ext, _i, _o in DEFAULT_SCRIPTS if "hook" + ext in members]
    for ext, interpreter, names in DEFAULT_SCRIPTS:
        path = "hook" + ext
        entry = {"interpreter": interpreter, "path": path, "os": names}
        if path in present and os_matches(entry, os_name) and interpreter in interpreters:
            return {"path": path, "interpreter": interpreter}, present
    return None, present


def hooks_of(
    manifest: "dict[str, Any]",
    files: "Iterable[str]",
    os_name: str,
    interpreters: "Iterable[str]" = INTERPRETERS,
) -> "tuple[list[dict[str, Any]], list[str]]":
    """Every hook the overlay has, in event order, and the ``hook.<ext>`` files reported as
    ``script-not-run`` because an entry needs one and none can run here.

    An entry whose script cannot run here keeps ``path`` (``None`` for a ``hook.<ext>`` none of
    which can) so that firing it fails, and an ``on_failure = "refuse"`` guard fails closed.
    """
    interpreters = list(interpreters)
    declared = manifest.get("hooks")
    declared = declared if isinstance(declared, dict) else {}
    chosen, present = default_hook(files, os_name, interpreters)
    entries: "list[dict[str, Any]]" = []
    needs_default = False
    for event, (_class, by_default, _outputs, _refusal, _match) in HOOK_EVENTS.items():
        if event in declared:
            value = declared[event]
            if value is False:
                continue
            table = value if isinstance(value, dict) else {"run": value}
        elif by_default and default_on(manifest, "hooks") and present:
            table = {}
        else:
            continue
        if "run" in table:
            path: "Optional[str]" = table["run"]
            interpreter: "Optional[str]" = SCRIPT_EXTENSIONS[
                table["run"][table["run"].rindex(".") :]
            ]
        elif chosen is not None:
            path, interpreter = chosen["path"], chosen["interpreter"]
        else:
            needs_default = True
            if event not in declared:
                # A default entry that cannot run: nothing runs, the files are reported.
                continue
            path = interpreter = None
        entries.append(
            {
                "event": event,
                "path": path,
                "interpreter": interpreter,
                "runs": interpreter is not None and interpreter in interpreters,
                "match": table.get("match"),
                "sets": table.get("sets", []),
                "timeout": table.get("timeout", DEFAULT_HOOK_TIMEOUT),
                "on_failure": table.get("on_failure", "report"),
                "payload": list(PAYLOAD_COMMON + PAYLOAD_KEYS[event]),
            }
        )
    return entries, (present if needs_default else [])


def hook_plan(manifest: "dict[str, Any]", facts: "dict[str, Any]") -> "dict[str, Any]":
    """What a consumer would do with an overlay's hooks, or a scope's own, on one harness.

    ``facts``: ``os``, ``interpreters``, ``files``, ``identity``, ``scope`` (``overlay``,
    ``user`` or ``project``), ``digest`` and ``allowed`` (the one digest at which the user
    allowed them); for a project, ``tree``, every file of the directory that holds its
    configuration, whose digest is the one allowed; ``fires`` (the events the consumer can fire
    on this harness; absent, every one), ``partial`` (those it fires for only some occurrences)
    and ``limits`` (``timeout``, the consumer's bound on one run).
    """
    entries, not_run = hooks_of(
        manifest,
        facts.get("files", []),
        facts["os"],
        facts.get("interpreters", INTERPRETERS),
    )
    bound = dict(DEFAULT_HOOK_LIMITS, **facts.get("limits", {}))["timeout"]
    for entry in entries:
        entry["timeout"] = min(entry["timeout"], bound)
    scope = facts.get("scope", "overlay")
    digest = facts.get("digest")
    if "tree" in facts:
        # Every file of the directory, not only those the hooks name: a module beside a script
        # is loaded by it.
        tree = facts["tree"]
        digest = digest_entries(
            [
                (tuple(p.encode("utf-8") for p in path.split("/")), "file", text.encode("utf-8"))
                for path, text in tree.items()
            ]
        )[0]
    allowed = facts.get("allowed")
    on = scope == "user" or (
        digest is not None and allowed is not None and same_digest(digest, allowed)
    )
    fires = facts.get("fires", list(HOOK_EVENTS))
    partial = facts.get("partial", [])
    non_defaults = [["script-not-run", path] for path in not_run]
    reports: "list[list[str]]" = []
    if entries and not on:
        reports.append(["hook-not-allowed", facts.get("identity", "")])
    elif on:
        for entry in entries:
            if entry["event"] not in fires:
                reports.append(["hook-unsupported", entry["event"]])
                continue
            non_defaults.append(["hook", entry["event"]])
            if entry["event"] in partial:
                reports.append(["hook-partial", entry["event"]])
    guarded = any(entry["on_failure"] == "refuse" for entry in entries)
    return {
        "hooks": entries,
        "on": on and bool(entries),
        # A guard that is off would fail open: the overlay waits for the user's yes.
        "activates": on or not guarded,
        "needs": sorted({entry["interpreter"] for entry in entries if entry["interpreter"]}),
        "reports": sorted(reports),
        "non_defaults": sorted(non_defaults),
    }


def hook_matches(event: str, match: "Optional[list[str]]", value: str) -> bool:
    """Whether a hook whose ``match`` is ``match`` runs for this reason or tool kind.

    A tool the consumer could not place (``other``) runs every ``pre-tool`` and ``post-tool``
    hook, so a tool of an unknown kind never slips past a guard.
    """
    if match is None:
        return True
    if HOOK_EVENTS[event][4] == "kind" and value == "other":
        return True
    return value in match


def hook_payload(event: str, facts: "dict[str, Any]") -> "dict[str, Any]":
    """The payload a hook of ``event`` receives: the event's own keys and nothing else of what
    the consumer knows."""
    payload: "dict[str, Any]" = {"event": event}
    for key in PAYLOAD_COMMON[1:] + PAYLOAD_KEYS[event]:
        if key not in facts:
            continue
        value = facts[key]
        if key == "tool" and isinstance(value, dict):
            value = {field: value[field] for field in TOOL_KEYS if field in value}
        payload[key] = value
    return payload


def _hook_text(value: Any) -> bool:
    """Text a hook may give the agent or the user: no control but tab, line feed and carriage
    return, and no bidirectional override."""
    return isinstance(value, str) and not _HOOK_TEXT_REFUSED.search(value)


def read_hook_output(event: str, data: bytes, sets: "Iterable[str]" = ()) -> "dict[str, Any]":
    """A successful run's standard output: what it asks for, or ``HookFailure``.

    ``pre-env`` reads as an env script's output. Every other event reads one JSON object, whose
    keys are those the event takes; a ``decision`` that is not one of the event's own is an
    ``output`` failure, and ``env`` may name only the variables the entry ``sets``.
    """
    _class, _default, outputs, _refusal, _match = HOOK_EVENTS[event]
    if event == "pre-env":
        try:
            return {"env": read_env_script_output(data)}
        except ReadError:
            raise HookFailure("output")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise HookFailure("output")
    whole = text.strip(" \t\r\n")
    if not whole:
        return {}
    try:
        value = _read_json(whole)
    except ReadError:
        raise HookFailure("output")
    if not isinstance(value, dict):
        raise HookFailure("output")
    if "decision" in value:
        decisions = [kind for kind in outputs if kind in ("block", "deny", "ask", "allow")]
        if value["decision"] not in decisions:
            raise HookFailure("output")
    for key in value:
        if key not in HOOK_OUTPUT_KEYS:
            raise HookFailure("output")
    out: "dict[str, Any]" = {}
    if "decision" in value:
        out["decision"] = value["decision"]
    if "reason" in value:
        reason = value["reason"]
        if "decision" not in value or not _hook_text(reason) or len(reason) > MAX_HOOK_REASON:
            raise HookFailure("output")
        out["reason"] = reason
    if "input" in value:
        # A rewritten call: an object, and only an allow carries it.
        if (
            "input" not in outputs
            or value.get("decision") != "allow"
            or not isinstance(value["input"], dict)
        ):
            raise HookFailure("output")
        out["input"] = value["input"]
    if "context" in value:
        if "context" not in outputs or not _hook_text(value["context"]):
            raise HookFailure("output")
        out["context"] = value["context"]
    if "env" in value:
        env = value["env"]
        if "env" not in outputs or not isinstance(env, dict):
            raise HookFailure("output")
        declared = set(sets)
        folded: "set[str]" = set()
        for name, item in env.items():
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name) or is_reserved_variable(name):
                raise HookFailure("output")
            if name not in declared or name.upper() in folded:
                raise HookFailure("output")
            folded.add(name.upper())
            if item is not None and not (isinstance(item, str) and "\0" not in item):
                raise HookFailure("output")
        out["env"] = dict(env)
    return out


def _run_bytes(run: "dict[str, Any]") -> bytes:
    if "stdout_base64" in run:
        return base64.b64decode(run["stdout_base64"])
    if "stdout_parts" in run:
        return "".join(text * times for text, times in run["stdout_parts"]).encode("utf-8")
    return run.get("stdout", "").encode("utf-8")


def hook_result(event: str, run: "dict[str, Any]", limits: "dict[str, int]") -> "dict[str, Any]":
    """One run, as the consumer saw it, checked in a fixed order: started, payload, time, size,
    exit status, then the output itself."""
    limits = dict(DEFAULT_HOOK_LIMITS, **limits)
    if run.get("not_run"):
        raise HookFailure("not-run")
    if run.get("payload_size", 0) > limits["max_payload"]:
        raise HookFailure("payload-too-large")
    if run.get("timed_out"):
        raise HookFailure("timeout")
    data = _run_bytes(run)
    if len(data) > limits["max_output"]:
        raise HookFailure("too-large")
    if run.get("exit", 0) != 0:
        raise HookFailure("exit")
    return read_hook_output(event, data, run.get("sets", ()))


def fire_event(
    event: str,
    runs: "list[dict[str, Any]]",
    applies: "Optional[Iterable[str]]" = None,
    limits: "Optional[dict[str, int]]" = None,
    windows: bool = False,
    context_used: int = 0,
    tool_input: Any = _UNSET,
    kind: "Optional[str]" = None,
) -> "dict[str, Any]":
    """Every hook of one event, in the order given, combined to the tightest result.

    ``runs`` are what each hook did (``source``, ``on_failure``, the ``seconds`` it took, and the
    run as :func:`hook_result` reads it); ``applies`` the outputs the consumer can apply on this
    harness (``context``, ``env``, ``block``, ``deny``, ``ask``, ``refuse``; absent, every one).
    A hook that would start after the event's own bound has passed fails as ``event-timeout``.
    ``context_used`` is what the session's context already holds, in bytes; a part of a hook's
    context that would take the total past ``limits["context_bytes"]`` is not added.
    ``tool_input`` is the call's input as the harness gave it (a ``pre-tool`` case that tests
    rewriting): the result then says what each hook ``seen`` and the ``input`` the call runs with,
    ``None`` for the one it was given. A hook's ``input`` replaces it for the hooks after; it
    applies only when the combined decision is an allow. ``kind`` is the call's tool kind: on
    ``other`` a run whose ``match`` is given and does not name ``other`` still runs, but its allow
    (and its input) does not count.
    """
    _class, _default, outputs, refusal, _match = HOOK_EVENTS[event]
    current = tool_input
    rewriter: "Optional[str]" = None
    can = set(applies) if applies is not None else set(outputs) | {"refuse"}
    bounds = dict(DEFAULT_HOOK_LIMITS, **(limits or {}))
    bound = bounds["event_timeout"]
    spent = 0
    result: "dict[str, Any]" = {
        "ran": [],
        "decision": None,
        "by": None,
        "reason": None,
        "context": [],
        "env": {},
        "reports": [],
        "non_defaults": [],
    }
    if tool_input is not _UNSET:
        result["seen"] = []
    for run in runs:
        source = run["source"]
        try:
            if spent >= bound:
                raise HookFailure("event-timeout")
            result["ran"].append(source)
            if tool_input is not _UNSET:
                result["seen"].append([source, current])
            spent += run.get("seconds", 0)
            out = hook_result(event, run, limits or {})
        except HookFailure as failure:
            result["reports"].append(["hook-failed", source, event, failure.cause])
            if run.get("on_failure", "report") != "refuse" or refusal is None:
                continue
            out = {"decision": refusal}
        decision = out.get("decision")
        if decision == "ask" and "ask" not in can:
            result["reports"].append(["hook-ask-denied", source, event])
            decision = "deny"
        if decision is not None and decision not in can:
            result["reports"].append(["hook-not-applied", source, event, decision])
            decision = None
        if (
            decision == "allow"
            and kind == "other"
            and run.get("match") is not None
            and "other" not in run["match"]
        ):
            result["reports"].append(["hook-not-applied", source, event, "allow"])
            decision = None
            out = {key: value for key, value in out.items() if key != "input"}
        if "input" in out and decision == "allow":
            if "input" in can:
                current, rewriter = out["input"], source
            else:
                # An allow that cannot be applied as asked, the rewrite, is not applied at all.
                result["reports"].append(["hook-not-applied", source, event, "input"])
                decision = None
        if _DECISION_RANK[decision] > _DECISION_RANK[result["decision"]]:
            result.update(decision=decision, by=source, reason=out.get("reason"))
        if _DECISION_RANK[decision] == 3:
            # The prompt, compaction, call or session does not happen: nothing else applies.
            result["context"] = []
            result["env"] = {}
            break
        if out.get("context"):
            size = len(out["context"].encode("utf-8"))
            if "context" in can and context_used + size > bounds["context_bytes"]:
                result["reports"].append(["hook-not-applied", source, event, "context"])
            elif "context" in can:
                context_used += size
                result["context"].append([source, out["context"]])
            else:
                result["reports"].append(["hook-not-applied", source, event, "context"])
        if "env" in out and out["env"]:
            if "env" not in can:
                result["reports"].append(["hook-not-applied", source, event, "env"])
                continue
            for name, value in out["env"].items():
                # On Windows a name set under another case keeps the spelling it has.
                key = next(
                    (k for k in result["env"] if windows and k.upper() == name.upper()), name
                )
                result["env"][key] = value
    result["non_defaults"] = sorted(["env-sensitive", n] for n in result["env"] if is_sensitive(n))
    if tool_input is not _UNSET:
        if rewriter is not None and result["decision"] == "allow":
            result["input"] = current
        else:
            result["input"] = None
            if rewriter is not None and result["decision"] == "ask":
                result["reports"].append(["hook-not-applied", rewriter, event, "input"])
    return result


def hook_order(
    overlays: "dict[str, dict[str, Any]]",
    requested: "list[str]",
    has: "Iterable[str]",
    scopes: "Iterable[str]" = (),
) -> "list[list[str]]":
    """The order the hooks of one event run in, as ``[scope, source]`` pairs.

    Every active overlay that has a hook (``has``) in composition order, then the user's own, then
    the project's, whichever order ``scopes`` (the scopes that have one) names them in.
    """
    visited, _missing = resolve(overlays, requested)
    present = set(has)
    order = [["overlay", i] for i in composition_order(overlays, visited) if i in present]
    return order + [[scope, ""] for scope in ("user", "project") if scope in set(scopes)]


def _state_variable(identity: str) -> str:
    return root_variable(identity)[: -len("ROOT")] + "STATE"


def _base_environment(active: "list[str]", facts: "dict[str, Any]") -> Environment:
    """The base environment, every overlay's root variable and the state variable of each that has
    a state directory: the first step of the order of application."""
    env = Environment(facts.get("base_env", {}), facts["os"] == "windows")
    for identity in active:
        env.set(root_variable(identity), facts["roots"][identity])
        if identity in facts.get("states", {}):
            env.set(_state_variable(identity), facts["states"][identity])
    return env


def _set_or_unset(env: Environment, name: str, value: "Optional[str]") -> None:
    if value is None:
        key = env._key(name)
        if key is not None:
            del env.values[key]
    else:
        env.set(name, value)


def _session_environment(
    event: str,
    overlays: "dict[str, dict[str, Any]]",
    requested: "list[str]",
    files: "dict[str, Any]",
    facts: "dict[str, Any]",
    until: "Optional[str]" = None,
    through: "Optional[str]" = None,
) -> "tuple[Environment, list[str]]":
    """The session's environment as it stands at one point of the order of application.

    The base environment, every overlay's root and state variable, then the ``pre-env`` output of
    the overlays before ``until`` (every one when ``until`` is None), then, unless ``event`` is
    ``pre-env``, every overlay's declarations in composition order up to and including
    ``through`` (every one when None), then what earlier hooks of the event set.
    """
    windows = facts["os"] == "windows"
    visited, _missing = resolve(overlays, requested)
    active = composition_order(overlays, visited)
    env = _base_environment(active, facts)
    limits = facts.get("hook_limits", {})
    for name in active:
        if name == until:
            break
        if name in facts.get("pre_env", {}):
            fired = fire_event(
                "pre-env", [dict(facts["pre_env"][name], source=name)], None, limits, windows
            )
            for variable, value in fired["env"].items():
                _set_or_unset(env, variable, value)
    if event != "pre-env":
        for name in active:
            env.writes.clear()
            tree = files.get(name, [])
            texts = tree if isinstance(tree, dict) else {}
            apply_overlay(
                env,
                overlays[name],
                dict(facts, files=texts, packages={}),
                facts["roots"][name],
                [],
                tree,
                name,
                facts.get("states", {}).get(name),
            )
            if name == through:
                break
        for earlier in facts.get("earlier", []):
            for variable, value in earlier.items():
                _set_or_unset(env, variable, value)
    return env, active


def _own_variables(env: Environment, identity: str, facts: "dict[str, Any]") -> None:
    env.set("AOS_OVERLAY_ROOT", facts["roots"][identity])
    env.set("AOS_OVERLAY_NAME", normalize_name(identity))
    if identity in facts.get("states", {}):
        env.set("AOS_OVERLAY_STATE", facts["states"][identity])


def hook_environment(
    event: str,
    overlays: "dict[str, dict[str, Any]]",
    requested: "list[str]",
    files: "dict[str, Any]",
    facts: "dict[str, Any]",
    scope: str = "overlay",
    identity: "Optional[str]" = None,
) -> "dict[str, str]":
    """The environment a hook of ``event`` runs with.

    A hook gets the session's environment: the base environment, every overlay's root variable
    (and state variable), what every overlay's ``pre-env`` hook set, every overlay's declarations
    in the order of application, and what earlier hooks of the event set (``facts["earlier"]``,
    in run order). An overlay's hook also gets that overlay's ``AOS_OVERLAY_ROOT``,
    ``AOS_OVERLAY_NAME`` and ``AOS_OVERLAY_STATE`` (when it has a state directory); every hook
    gets ``AOS_HOOK_EVENT``. A ``pre-env`` hook runs before any declaration: it gets the base
    environment, the root and state variables, and the output of the ``pre-env`` hooks before it
    in composition order (a user's or a project's, of every overlay's). ``facts`` are compose's
    (``os``, ``base_env``, ``roots``, ``states``, ``pre_env``, grants and secrets).
    """
    env, active = _session_environment(
        event, overlays, requested, files, facts, until=identity if event == "pre-env" else None
    )
    if scope == "overlay":
        assert identity in active
        _own_variables(env, identity, facts)
    env.set("AOS_HOOK_EVENT", event)
    return env.values


def process_environment(
    process: str,
    overlays: "dict[str, dict[str, Any]]",
    requested: "list[str]",
    files: "dict[str, Any]",
    facts: "dict[str, Any]",
    identity: str,
) -> "dict[str, str]":
    """The environment a process of one overlay runs with: ``setup``, ``server`` or ``command``
    get the session's, whole; ``env-script`` gets it as it stands when the script runs, which is
    every earlier overlay's declarations and this overlay's own. Each also gets the overlay's
    ``AOS_OVERLAY_*`` variables."""
    assert process in ("setup", "server", "command", "env-script")
    env, _active = _session_environment(
        "session-start",
        overlays,
        requested,
        files,
        facts,
        through=identity if process == "env-script" else None,
    )
    _own_variables(env, identity, facts)
    return env.values


# --------------------------------------------------------------------------------------------
# Store metadata and catalogs: informational, never applied.
# --------------------------------------------------------------------------------------------

#: The informational fields of ``about``, in the manifest and in a catalog entry.
ABOUT_FIELDS = ("summary", "icon", "homepage", "repository", "license", "authors", "tags")


def _subschema(pointer_to: str) -> Draft202012Validator:
    return _Validator(
        {"$defs": SCHEMA["$defs"], "$ref": pointer_to}, format_checker=FormatChecker()
    )


_ABOUT_FIELD = {field: _subschema("#/$defs/about/properties/" + field) for field in ABOUT_FIELDS}
_CATALOG_FIELD = {
    field: _subschema("#/$defs/catalog/properties/" + field)
    for field in ("name", "description", "homepage")
}
CATALOG_VALIDATOR = _subschema("#/$defs/catalog")


def applies(issues: "list[tuple[str, str]]") -> bool:
    """Whether a manifest with these issues is applied: a problem under ``/about`` never blocks."""
    return not [at for _code, at in issues if not (at == "/about" or at.startswith("/about/"))]


_LICENSE_ID = re.compile(r"^[A-Za-z0-9.-]+\+?$")
_LICENSE_REF = re.compile(r"^(?:DocumentRef-[A-Za-z0-9.-]+:)?LicenseRef-[A-Za-z0-9.-]+$")
_EXCEPTION_ID = re.compile(
    r"^(?:[A-Za-z0-9.-]+|(?:DocumentRef-[A-Za-z0-9.-]+:)?AdditionRef-[A-Za-z0-9.-]+)$"
)
_OPERATORS = ("AND", "OR", "WITH")


def valid_license(expression: str) -> bool:
    """An SPDX license expression: ids, ``LicenseRef-``, ``+``, ``WITH``, ``AND``, ``OR`` and
    parentheses, operators in upper case, ``AND`` binding tighter than ``OR``."""
    if not re.match(r"^[A-Za-z0-9.+:() -]+$", expression):
        return False
    tokens = re.findall(r"\(|\)|[^ ()]+", expression)
    position = 0

    def peek() -> "Optional[str]":
        return tokens[position] if position < len(tokens) else None

    def take() -> "Optional[str]":
        nonlocal position
        token = peek()
        position += 1
        return token

    def license_or_group() -> bool:
        token = take()
        if token == "(":
            return compound() and take() == ")"
        if token is None or token in _OPERATORS or token == ")":
            return False
        if not (_LICENSE_REF.match(token) or _LICENSE_ID.match(token)):
            return False
        if peek() == "WITH":
            take()
            exception = take()
            return exception is not None and bool(_EXCEPTION_ID.match(exception))
        return True

    def term() -> bool:
        if not license_or_group():
            return False
        while peek() == "AND":
            take()
            if not license_or_group():
                return False
        return True

    def compound() -> bool:
        if not term():
            return False
        while peek() == "OR":
            take()
            if not term():
                return False
        return True

    try:
        return compound() and position == len(tokens)
    except RecursionError:
        # Parentheses nested past what the grammar can follow make no license expression.
        return False


def about_field_valid(field: str, value: Any) -> bool:
    """Whether one informational field is valid; an unknown field is not."""
    if field not in _ABOUT_FIELD or not _ABOUT_FIELD[field].is_valid(value):
        return False
    return field != "license" or valid_license(value)


def store_about(about: Any, at: str, ignored: "list[str]") -> "Optional[dict[str, Any]]":
    """What a store shows of an ``about`` table: each invalid or unknown field left out, by pointer."""
    if not isinstance(about, dict):
        ignored.append(at)
        return None
    shown: "dict[str, Any]" = {}
    for field, value in about.items():
        if about_field_valid(field, value):
            shown[field] = value
        else:
            ignored.append(at + "/" + _escape(field))
    return shown or None


def _escape(token: str) -> str:
    """One JSON Pointer reference token."""
    return token.replace("~", "~0").replace("/", "~1")


# ---------------------------------------------------------------------------------- catalogs

#: Catalog file extensions that name a format; any other name is read as an AOS document.
CATALOG_EXTENSIONS = {".toml": "toml", ".json": "json", ".yaml": "yaml", ".yml": "yaml"}
DEFAULT_CATALOG_MAX_BYTES = 4 * 1024 * 1024
CATALOG_ENTRY_KEYS = frozenset(("source", "ref", "pin", "description", "about"))
_REF = re.compile(r"^[^-/:\\@#\x00-\x20\x7f][^/:\\@#\x00-\x20\x7f]*$")
_DRIVE = re.compile(r"^[A-Za-z]:")
#: A scheme before the location, which no relative path has: ``file:``, ``zip:``, ``ext:``.
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]+:")


def catalog_format(name: str) -> "Optional[str]":
    """The format a catalog's file name selects, or None for the AOS document rule."""
    last = name.replace("\\", "/").rsplit("/", 1)[-1]
    if "." not in last:
        return None
    extension = "." + "".join(c.lower() if "A" <= c <= "Z" else c for c in last.rsplit(".", 1)[1])
    return CATALOG_EXTENSIONS.get(extension)


def read_catalog_document(
    data: bytes,
    name: str,
    *,
    max_bytes: int = DEFAULT_CATALOG_MAX_BYTES,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> "dict[str, Any]":
    """A catalog's data model value: its extension names the format, else the AOS rule."""
    kind = catalog_format(name)
    if kind is None:
        return read_document(data, max_bytes=max_bytes, max_depth=max_depth)
    if len(data) > max_bytes:
        raise ReadError("too-large")
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return _parse(kind, data, max_depth)


class CatalogRefusal(Exception):
    """An entry a store does not list. ``code`` is the vectors' class."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _absolute_directory(location: str) -> bool:
    return location.startswith(("/", "\\")) or bool(_DRIVE.match(location))


def _local_git(location: str) -> bool:
    """A Git location on this machine: a path or ``file:``, not a URL or ``host:path``."""
    if "://" in location:
        return location.split("://", 1)[0].lower() == "file"
    return bool(_DRIVE.match(location)) or not re.match(r"^[^/\\:]+:", location)


def _join(*parts: str) -> str:
    import posixpath

    return posixpath.normpath(posixpath.join(*[part for part in parts if part] or ["."]))


def local_source(parsed: "dict[str, Optional[str]]") -> bool:
    """A source on the consumer's machine: a directory, a local Git path, any ``file:``
    location, or a host that is this machine."""
    location = parsed["location"] or ""
    if location.lower().startswith("file:") or parsed["kind"] == "directory":
        return True
    if parsed["kind"] == "git" and _local_git(location):
        return True
    return host_scope(source_host(location)) == "local"


def resolve_entry_source(
    entry: "dict[str, Optional[str]]", origin: "Optional[dict[str, Optional[str]]]"
) -> "dict[str, Optional[str]]":
    """A parsed entry source made absolute against the parsed source of the catalog file."""
    import posixpath

    location = entry["location"] or ""
    relative = (
        entry["kind"] == "directory"
        and not _absolute_directory(location)
        and not _SCHEME.match(location)
    )
    local = (not relative) and local_source(entry)
    if origin is None or origin["kind"] == "directory":
        if relative and origin is not None:
            folder = posixpath.dirname((origin["location"] or "").replace("\\", "/"))
            return dict(entry, location=_join(folder, location))
        return dict(entry)
    if local:
        raise CatalogRefusal("local-source")
    if not relative:
        if entry["kind"] != "git" and not _WEB_URL.match(location):
            raise CatalogRefusal("invalid-source")
        if _holds_credentials(location):
            raise CatalogRefusal("source-credentials")
        return dict(entry)
    if origin["kind"] == "git":
        folder = posixpath.dirname(origin["path"] or "")
        path = _join(folder, location, entry["path"] or "")
        if path == ".." or path.startswith("../"):
            raise CatalogRefusal("leaves-repository")
        if path != "." and not valid_relpath(path):
            raise CatalogRefusal("invalid-source")
        return {
            "kind": "git",
            "location": origin["location"],
            "ref": origin["ref"],
            "path": None if path == "." else path,
        }
    from urllib.parse import urljoin

    return {
        "kind": "url",
        "location": urljoin(origin["location"] or "", location),
        "ref": None,
        "path": entry["path"],
    }


def _catalog_entry(
    value: Any, at: str, origin: "Optional[dict[str, Optional[str]]]", ignored: "list[str]"
) -> "dict[str, Any]":
    if isinstance(value, str):
        fields: "dict[str, Any]" = {"source": value}
    elif isinstance(value, dict):
        if set(value) - CATALOG_ENTRY_KEYS:
            raise CatalogRefusal("invalid-entry")
        fields = value
    else:
        raise CatalogRefusal("invalid-entry")
    if not isinstance(fields.get("source"), str):
        raise CatalogRefusal("invalid-entry")
    try:
        parsed = parse_source(fields["source"])
    except ValueError:
        raise CatalogRefusal("invalid-source")
    source = resolve_entry_source(parsed, origin)
    if "ref" in fields:
        ref = fields["ref"]
        if not isinstance(ref, str) or not _REF.match(ref):
            raise CatalogRefusal("invalid-entry")
        if parsed["kind"] != "git" or parsed["ref"] is not None:
            raise CatalogRefusal("ref-not-allowed")
        source["ref"] = ref
    entry: "dict[str, Any]" = {"source": source}
    if "pin" in fields:
        if not isinstance(fields["pin"], str) or not DIGEST_FORM.match(fields["pin"]):
            raise CatalogRefusal("invalid-pin")
        entry["pin"] = fields["pin"]
    if "description" in fields:
        if isinstance(fields["description"], str):
            entry["description"] = fields["description"]
        else:
            ignored.append(at + "/description")
    if "about" in fields:
        about = store_about(fields["about"], at + "/about", ignored)
        if about is not None:
            entry["about"] = about
    return entry


def read_catalog(
    data: bytes, name: str, base: "Optional[str]" = None, **limits: int
) -> "dict[str, Any]":
    """What a store reads from one catalog: its form, its informational fields, the entries it
    lists with their sources made absolute, the entries it refuses and the fields it ignores.

    ``name`` is the catalog's file name, ``base`` the source the catalog file itself came from.
    """
    document = read_catalog_document(data, name, **limits)
    overlays = document.get("overlays")
    skills = document.get("skills")
    if not isinstance(overlays, dict) and not isinstance(skills, dict):
        raise ReadError("not-a-catalog")
    origin = parse_source(base) if base else None
    ignored: "list[str]" = []
    if not isinstance(overlays, dict):
        if "overlays" in document:
            ignored.append("/overlays")
        overlays = {}
    listed = list(overlays.values()) + (list(skills.values()) if isinstance(skills, dict) else [])
    result: "dict[str, Any]" = {
        "form": "minimal" if all(isinstance(v, str) for v in listed) else "full"
    }
    for field, check in _CATALOG_FIELD.items():
        if field in document:
            if check.is_valid(document[field]):
                result[field] = document[field]
            else:
                ignored.append("/" + field)
    holders: "dict[str, int]" = {}
    for key in overlays:
        if valid_overlay_name(key):
            holders[normalize_name(key)] = holders.get(normalize_name(key), 0) + 1
    entries: "dict[str, Any]" = {}
    refused: "list[list[str]]" = []
    for key in sorted(overlays):
        at = "/overlays/" + _escape(key)
        if not valid_overlay_name(key):
            refused.append([key, "invalid-name"])
        elif holders[normalize_name(key)] > 1:
            refused.append([key, "duplicate-name"])
        else:
            try:
                entries[key] = _catalog_entry(overlays[key], at, origin, ignored)
            except CatalogRefusal as refusal:
                refused.append([key, refusal.code])
    result.update(entries=entries, refused=refused)
    if isinstance(skills, dict):
        result["skills"] = _catalog_skills(skills, origin, ignored)
    elif "skills" in document:
        ignored.append("/skills")
    result["ignored"] = sorted(ignored)
    return result


def valid_skill_name(name: str) -> bool:
    """A skill name is also one path component, since a consumer makes a directory of it."""
    return bool(_SKILL_NAME.match(name)) and valid_relpath(name)


def _catalog_skills(
    skills: "dict[str, Any]", origin: "Optional[dict[str, Optional[str]]]", ignored: "list[str]"
) -> "dict[str, Any]":
    """A catalog's ``skills``: entries as ``overlays`` holds them, names compared by ASCII case."""
    holders: "dict[str, int]" = {}
    for key in skills:
        holders[key.lower()] = holders.get(key.lower(), 0) + 1
    entries: "dict[str, Any]" = {}
    refused: "list[list[str]]" = []
    for key in sorted(skills):
        if not valid_skill_name(key):
            refused.append([key, "invalid-name"])
        elif holders[key.lower()] > 1:
            refused.append([key, "duplicate-name"])
        else:
            try:
                entries[key] = _catalog_entry(
                    skills[key], "/skills/" + _escape(key), origin, ignored
                )
            except CatalogRefusal as refusal:
                refused.append([key, refusal.code])
    return {"entries": entries, "refused": refused}


def resolve_skills(
    overlays: "dict[str, dict[str, Any]]",
    requested: "list[str]",
    files: "dict[str, Any]",
    catalogs: "Iterable[tuple[str, dict[str, Any]]]" = (),
    order: "Iterable[str]" = (),
    fetches: bool = True,
) -> "dict[str, Any]":
    """What a consumer shows before installing and reports after: every skill of the active
    overlays with where it comes from, each name no catalog offers or more than one does, the
    non_defaults, the collisions and what each would do. ``catalogs`` are ``(label, read_catalog
    result)``; ``order`` is the order of labels the user configured, if any; a consumer that does
    not ``fetches`` delivers only bundled skills and says so for the rest. Where ``files`` gives an
    overlay's texts, a bundled ``SKILL.md`` naming another skill is not delivered."""
    visited, _missing = resolve(overlays, requested)
    active = composition_order(overlays, visited)
    catalogs = list(catalogs)
    list_catalogs(catalogs)
    rank = [normalize_name(label) for label in order]
    out: "dict[str, list[Any]]" = {
        "skills": [],
        "missing": [],
        "ambiguous": [],
        "unpinned": [],
        "non_defaults": [],
        "not_fetched": [],
        "name_mismatch": [],
        "shadowing": [],
    }
    winners: "dict[str, tuple[str, str, Any]]" = {}
    collisions: "set[str]" = set()
    for identity in active:
        tree = files.get(identity, [])
        for entry in skill_entries(overlays[identity], tree):
            item = dict(entry, overlay=identity)
            name = entry["name"]
            if entry["origin"] == "catalog":
                offers = []
                for label, catalog in catalogs:
                    listed = catalog.get("skills", {}).get("entries", {})
                    for key in listed:
                        if key.lower() == name.lower():
                            offers.append((label, listed[key]))
                offers = _ranked(offers, rank)
                if not offers:
                    item["origin"] = "missing"
                    out["missing"].append([name, identity])
                elif len(offers) > 1:
                    labels = sorted(label for label, _entry in offers)
                    item.update(origin="ambiguous", catalogs=labels)
                    out["ambiguous"].append([name, identity, labels])
                else:
                    item["catalog"], offer = offers[0]
                    item["source"] = shown_source(offer["source"])
                    item["key"] = source_key(offer["source"])
                    if "pin" in offer:
                        item["pin"] = offer["pin"]
            out["skills"].append({key: value for key, value in item.items() if key != "key"})
            if item["origin"] in ("missing", "ambiguous"):
                continue
            if item["origin"] == "bundled" and isinstance(tree, dict):
                text = tree.get("skills/%s/SKILL.md" % name)
                if text is not None and bundled_name(_as_bytes(text)) not in (None, name):
                    out["name_mismatch"].append([name, identity])
                    continue
            if item["origin"] != "bundled":
                if not fetches:
                    out["not_fetched"].append([name, identity])
                    continue
                if "pin" not in item:
                    out["unpinned"].append([name, identity])
                location = item["key"].split("#", 1)[0]
                if re.match(r"^(?:git\+)?(?:http|git)://", location, re.IGNORECASE):
                    out["non_defaults"].append(["insecure-transport", name, identity])
                if host_scope(source_host(location)) == "private":
                    out["non_defaults"].append(["private-source", name, identity])
            if not _deliver(winners, collisions, item, identity):
                out["shadowing"].append([name, identity])
    out["delivered"] = {name: identity for name, identity, _origin in winners.values()}
    out["collisions"] = sorted(collisions)
    return out


def bundled_name(data: bytes) -> "Optional[str]":
    """The ``name`` a bundled ``SKILL.md`` gives, when its front matter reads; None otherwise."""
    found = read_front_matter(data)
    name = found.get("data", {}).get("name")
    return name if isinstance(name, str) or name is None else str(name)


def _ranked(offers: "list[Any]", rank: "list[str]") -> "list[Any]":
    """The first catalog in the user's order that offers the name; without one, all of them."""
    for label in rank:
        for offer in offers:
            if normalize_name(offer[0]) == label:
                return [offer]
    return offers


#: The Agent Skills front matter keys that grant nothing; any other is reported.
SKILL_INERT_KEYS = ("name", "description", "license", "compatibility", "metadata")


def read_fetched_skill(
    name: str,
    files: "dict[str, Any]",
    pin: "Optional[str]" = None,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> "dict[str, Any]":
    """Checks a skill fetched under ``name``, by relative path to content, before it is delivered:
    its tree digest, and the front matter keys a consumer reports. The pin comes first, so nothing
    unverified is parsed."""
    entries = [
        (tuple(part.encode("utf-8") for part in path.split("/")), "file", _as_bytes(value))
        for path, value in files.items()
    ]
    try:
        digest, lines = digest_entries(entries)
    except DigestError as error:
        raise ReadError(error.code, error.path)
    if pin is not None and not same_digest(pin, digest):
        raise ReadError("pin-mismatch", name)
    if "SKILL.md" not in files:
        raise ReadError("not-a-skill", name)
    found = read_front_matter(
        _as_bytes(files["SKILL.md"]), max_bytes=max_bytes, max_depth=max_depth
    )
    if "error" in found:
        raise ReadError("skill-unreadable", found["error"], found["line"])
    if (
        found["case"] != "mapping"
        or found.get("format") != "yaml"
        or "#!" in found["metadata"][:2].decode("utf-8", "replace")
    ):
        raise ReadError("skill-unreadable", "front matter in YAML is required")
    if found["data"].get("name") != name:
        raise ReadError("skill-name-mismatch", name)
    reported = sorted(key for key in found["data"] if key not in SKILL_INERT_KEYS)
    return {
        "digest": digest,
        "reported": reported,
        "files": [line.split(b"\0", 1)[0].decode("utf-8") for line in lines],
    }


def list_catalogs(catalogs: "list[tuple[str, dict[str, Any]]]") -> "dict[str, Any]":
    """A store's listing of several catalogs, each ``(label, read_catalog result)``.

    An identity two catalogs offer is shown once per catalog, qualified ``<label>/<name>``;
    entries are never merged.
    """
    labels = [label for label, _catalog in catalogs]
    normalized = [normalize_name(label) for label in labels]
    if len(set(normalized)) != len(labels) or not all(map(valid_overlay_name, labels)):
        raise ReadError("invalid-label")
    offered: "dict[str, list[tuple[str, str]]]" = {}
    for label, catalog in catalogs:
        for name in catalog["entries"]:
            offered.setdefault(normalize_name(name), []).append((label, name))
    entries: "list[dict[str, str]]" = []
    collisions: "dict[str, list[str]]" = {}
    for identity in sorted(offered):
        holders = sorted(offered[identity])
        qualified = len(holders) > 1
        if qualified:
            collisions[identity] = [label for label, _name in holders]
        for label, name in holders:
            shown = "%s/%s" % (label, name) if qualified else name
            entries.append({"catalog": label, "name": name, "identity": identity, "shown": shown})
    return {"entries": entries, "collisions": collisions}


def choose(listing: "dict[str, Any]", requested: str) -> "dict[str, str]":
    """The entry a requested name picks: ``<label>/<name>``, or a name one catalog alone offers."""
    label, slash, name = requested.rpartition("/")
    if not valid_overlay_name(name) or (slash and not valid_overlay_name(label)):
        return {"error": "not-found"}
    found = [
        entry
        for entry in listing["entries"]
        if entry["identity"] == normalize_name(name)
        and (not slash or normalize_name(entry["catalog"]) == normalize_name(label))
    ]
    if not found:
        return {"error": "not-found"}
    if len(found) > 1:
        return {"error": "ambiguous"}
    return {"catalog": found[0]["catalog"], "name": found[0]["name"]}


# ------------------------------------------------------------------------------------- icons

ICON_FORMATS = ("png", "webp")
DEFAULT_ICON_MAX_BYTES = 512 * 1024
DEFAULT_ICON_MAX_SIDE = 1024
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class IconError(Exception):
    """An icon a store refuses. ``code`` is the vectors' class."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _png_size(data: bytes) -> "tuple[int, int]":
    if len(data) < 24 or data[8:16] != b"\x00\x00\x00\x0dIHDR":
        raise IconError("icon-unreadable")
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def _webp_size(data: bytes) -> "tuple[int, int]":
    if len(data) < 20 or int.from_bytes(data[4:8], "little") + 8 > len(data):
        raise IconError("icon-unreadable")
    chunk = data[12:16]
    if chunk == b"VP8 " and len(data) >= 30 and data[23:26] == b"\x9d\x01\x2a":
        width = int.from_bytes(data[26:28], "little") & 0x3FFF
        height = int.from_bytes(data[28:30], "little") & 0x3FFF
        return width, height
    if chunk == b"VP8L" and len(data) >= 25 and data[20] == 0x2F:
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if chunk == b"VP8X" and len(data) >= 30:
        return int.from_bytes(data[24:27], "little") + 1, int.from_bytes(data[27:30], "little") + 1
    raise IconError("icon-unreadable")


def read_icon(
    data: bytes,
    name: str,
    *,
    max_bytes: int = DEFAULT_ICON_MAX_BYTES,
    max_width: int = DEFAULT_ICON_MAX_SIDE,
    max_height: int = DEFAULT_ICON_MAX_SIDE,
) -> "dict[str, Any]":
    """An icon's format and dimensions from its header, or the reason a store refuses it.

    The checks run in order: the name's extension, the size in bytes, the signature against the
    extension, the header, the dimensions. Nothing past the header is decoded.
    """
    last = name.rsplit("/", 1)[-1]
    extension = last.rsplit(".", 1)[1].lower() if "." in last else ""
    if extension not in ICON_FORMATS:
        raise IconError("icon-format")
    if len(data) > max_bytes:
        raise IconError("icon-too-large")
    if data.startswith(_PNG_SIGNATURE):
        found = "png"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        found = "webp"
    else:
        raise IconError("icon-format")
    if found != extension:
        raise IconError("icon-mismatch")
    width, height = _png_size(data) if found == "png" else _webp_size(data)
    if not width or not height:
        raise IconError("icon-unreadable")
    if width > max_width or height > max_height:
        raise IconError("icon-dimensions")
    return {"format": found, "width": width, "height": height}


# --------------------------------------------------------------------------------------------
# Knowledge served through MCP: the handlers of kb_list, kb_read and kb_search, and the checks
# on what kb_search answers. Nothing here reads a filesystem: an overlay is a list of entries.
# --------------------------------------------------------------------------------------------

KB_DIRS = ("kb", "flows", "references", "rules", "context")
KB_MODES = ("words", "meaning", "llm")
KB_ENGINES = ("envsubst", "mustache")
KB_MARKDOWN_SUFFIXES = (".md", ".markdown")
KB_EXPANDED = ("aos", "agentic")  # the names of the expanded format, the default
KB_AS_WRITTEN = ("raw", "markdown", "md")
KB_LIMITS = {
    "max_file_bytes": 1048576,
    "max_read_bytes": 65536,
    "max_rendered_bytes": 1048576,
    "max_query_characters": 1000,
    "max_top": 100,
    "max_context_bytes": 16384,
    "max_context_depth": 8,
    "max_include_depth": 5,
}
KB_MAX_INTEGER = 9007199254740991
KB_DEFAULT_TOP = 5


class KnowledgeError(Exception):
    """A refused call. ``code`` is the vectors' error class."""

    def __init__(self, code: str, message: str = ""):
        super().__init__("%s: %s" % (code, message) if message else code)
        self.code = code
        self.message = message or code


def kb_limits(given: "Optional[dict[str, Optional[int]]]") -> "dict[str, Optional[int]]":
    """The settings: the defaults, then the given ones. A setting given as ``None`` is lifted."""
    return dict(KB_LIMITS, **(given or {}))


def _kb_over(value: int, bound: "Optional[int]") -> bool:
    return bound is not None and value > bound


def _kb_hides(code: int) -> bool:
    return (
        0x202A <= code <= 0x202E
        or 0x2066 <= code <= 0x206F
        or 0x200B <= code <= 0x200F
        or 0x2060 <= code <= 0x2064
        or code in (0x2028, 0x2029, 0x061C, 0xFEFF, 0x00AD, 0x180E)
        or 0xFE00 <= code <= 0xFE0F
        or 0xE0000 <= code <= 0xE007F
        or 0xE0100 <= code <= 0xE01EF
        or code in (0x115F, 0x1160, 0x3164, 0xFFA0, 0x034F)
        or 0x17B4 <= code <= 0x17B5
        or 0x1D173 <= code <= 0x1D17A
        or 0xFFF9 <= code <= 0xFFFB
    )


def kb_inert(text: str) -> str:
    """Text as an agent may receive it: each control character but TAB and LF, and each
    character that hides or reorders text, is written ``<U+XXXX>``."""
    out = []
    for char in text:
        code = ord(char)
        if char in "\n\t":
            out.append(char)
        elif code < 0x20 or 0x7F <= code <= 0x9F or _kb_hides(code):
            out.append("<U+%04X>" % code)
        else:
            out.append(char)
    return "".join(out)


def kb_lines(text: str) -> "list[str]":
    """A file's lines: split at LF, a CR before the LF dropped, no line after a final LF."""
    parts = text.split("\n")
    last = parts.pop()
    lines = [part[:-1] if part.endswith("\r") else part for part in parts]
    if last != "":
        lines.append(last)
    return lines


def _kb_bound(key: str, value: "Optional[int]") -> "dict[str, int]":
    return {} if value is None else {key: value}


def kb_tools(modes: "Iterable[str]", limits: "Optional[dict[str, int]]" = None) -> "list[dict]":
    """The tools ``tools/list`` names, with their input schemas and no descriptions."""
    limit = kb_limits(limits)
    modes = [mode for mode in KB_MODES if mode in set(modes)]
    line = {"type": "integer", "minimum": 1, "maximum": KB_MAX_INTEGER}
    tools = [
        {
            "name": "kb_list",
            "inputSchema": {
                "type": "object",
                "properties": {"overlay": {"type": "string"}},
                "additionalProperties": False,
            },
        },
        {
            "name": "kb_read",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "from": dict(line),
                    "to": dict(line),
                    "overlay": {"type": "string"},
                    "context": {"type": "object"},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    ]
    if modes:
        tools.append(
            {
                "name": "kb_search",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": dict(
                            {"type": "string", "minLength": 1},
                            **_kb_bound("maxLength", limit["max_query_characters"]),
                        ),
                        "top": dict(
                            {"type": "integer", "minimum": 1},
                            **_kb_bound("maximum", limit["max_top"]),
                            default=KB_DEFAULT_TOP,
                        ),
                        "overlay": {"type": "string"},
                        "mode": {"type": "string", "enum": ["auto"] + modes, "default": "auto"},
                        "path": {"type": "string"},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
            }
        )
    return tools


_KB_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


def _kb_context_ok(value: Any, depth: int, budget: "list[int]", limit: "dict[str, int]") -> bool:
    if _kb_over(depth, limit["max_context_depth"]):
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, int):
        return abs(value) <= KB_MAX_INTEGER
    if isinstance(value, str):
        budget[0] += len(value.encode("utf-8"))
        return not _kb_over(budget[0], limit["max_context_bytes"])
    if isinstance(value, list):
        return all(_kb_context_ok(item, depth + 1, budget, limit) for item in value)
    if isinstance(value, dict):
        for key, item in value.items():
            if not _KB_IDENT.match(key):
                return False
            budget[0] += len(key.encode("utf-8"))
            if _kb_over(budget[0], limit["max_context_bytes"]):
                return False
            if not _kb_context_ok(item, depth + 1, budget, limit):
                return False
        return True
    return False


def kb_arguments(
    tool: str,
    arguments: Any,
    modes: "Iterable[str]",
    limits: "Optional[dict[str, int]]" = None,
) -> "dict[str, Any]":
    """A call's arguments with the defaults applied, or ``invalid-arguments``. A ``null`` is the
    argument absent."""
    limit = kb_limits(limits)
    schemas = {tool_["name"]: tool_["inputSchema"] for tool_ in kb_tools(modes, limit)}
    if tool not in schemas:
        raise KnowledgeError("invalid-arguments", "no tool is named " + tool)
    schema = schemas[tool]
    if not isinstance(arguments, dict):
        raise KnowledgeError("invalid-arguments", "the arguments are an object")
    out: "dict[str, Any]" = {}
    for key, value in arguments.items():
        if key not in schema["properties"]:
            raise KnowledgeError("invalid-arguments", "no argument is named " + key)
        if value is None:
            continue
        spec = schema["properties"][key]
        if spec["type"] == "string":
            if not isinstance(value, str):
                raise KnowledgeError("invalid-arguments", key + " is text")
            if "enum" in spec and value not in spec["enum"]:
                raise KnowledgeError("invalid-arguments", key + " is not one of its values")
            if key == "query":
                if _kb_over(len(value), spec.get("maxLength")) or not value.strip(" \t\n\v\f\r"):
                    raise KnowledgeError("invalid-arguments", "the query is empty or too long")
        elif spec["type"] == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                raise KnowledgeError("invalid-arguments", key + " is a whole number")
            if value < spec["minimum"] or _kb_over(value, spec.get("maximum")):
                raise KnowledgeError("invalid-arguments", key + " is out of range")
        else:
            if not isinstance(value, dict) or not _kb_context_ok(value, 1, [0], limit):
                raise KnowledgeError("invalid-arguments", key + " is not a usable context")
        out[key] = value
    for key in schema.get("required", ()):
        if key not in out:
            raise KnowledgeError("invalid-arguments", key + " is required")
    if tool == "kb_search":
        out.setdefault("top", KB_DEFAULT_TOP)
        out.setdefault("mode", "auto")
    return out


def _kb_entries(tree: "list[dict]") -> "dict[str, tuple[str, bytes]]":
    out = {}
    for item in tree:
        kind = item.get("type", "file")
        data = base64.b64decode(item["base64"]) if "base64" in item else item.get("text", "")
        out[item["path"]] = (kind, data if isinstance(data, bytes) else data.encode("utf-8"))
    return out


def _kb_selected(path: str, manifest: "dict[str, Any]") -> bool:
    if path in MANIFEST_FILES or not valid_relpath(path):
        return False
    parts = path.split("/")
    named = {
        _named(entry) for field in ("rules", "context") for entry in _declared(manifest, field)
    }
    return (len(parts) > 1 and parts[0] in KB_DIRS) or path == "CONTEXT.md" or path in named


def _kb_hidden_name(path: str) -> bool:
    return any(_kb_hides(ord(char)) for char in path)


_KB_OPTION = re.compile(r"([a-z][a-z_]*)=(\S+)\Z")


def kb_format_line(data: bytes) -> "Optional[tuple[str, dict[str, str]]]":
    """The name and the options a file's first line gives its format, or ``None`` when it gives no
    name. The line is a format line as a manifest's is, with ``name=value`` words besides: the
    name is the last word that is not one, after any slash or backslash, lower-cased in ASCII,
    leading dots dropped."""
    if not data.startswith(b"#!"):
        return None
    end = data.find(b"\n")
    line = data[2:] if end < 0 else data[2:end]
    try:
        text = line.decode("utf-8")
    except UnicodeDecodeError:
        return None
    options: "dict[str, str]" = {}
    names = []
    for word in re.split(r"[ \t\x0c\r]+", text):
        if not word:
            continue
        found = _KB_OPTION.match(word)
        if found:
            options[found.group(1)] = found.group(2)
        else:
            names.append(word)
    if not names:
        return None
    name = re.split(r"[/\\]", names[-1])[-1].lstrip(".")
    name = "".join(c.lower() if "A" <= c <= "Z" else c for c in name)
    return (name, options) if name else None


def kb_shebang(data: bytes) -> "Optional[str]":
    """The name a file's first line gives its format, or ``None`` when it gives none."""
    found = kb_format_line(data)
    return found[0] if found else None


def _kb_ascii_lower(text: str) -> str:
    return "".join(c.lower() if "A" <= c <= "Z" else c for c in text)


def kb_after_shebang(text: str) -> str:
    """A text after its first line, the line end (LF, or CR LF) with it."""
    end = text.find("\n")
    return "" if end < 0 else text[end + 1 :]


def kb_set(
    overlay: "dict[str, Any]", limits: "Optional[dict[str, int]]" = None
) -> "dict[str, Any]":
    """An overlay's knowledge: ``files`` (path -> {text, engine, bytes, rest}) and ``skipped``
    ((path, reason) pairs), both in path-byte order, and the raw ``entries``."""
    limit = kb_limits(limits)
    entries = _kb_entries(overlay.get("tree", []))
    manifest = overlay.get("manifest", {})
    files: "dict[str, dict[str, Any]]" = {}
    skipped: "list[tuple[str, str]]" = []
    for path in _by_bytes(entries):
        kind, data = entries[path]
        if kind != "file" or not _kb_selected(path, manifest):
            continue
        if _kb_hidden_name(path):
            skipped.append((path, "name"))
        elif _kb_over(len(data), limit["max_file_bytes"]):
            skipped.append((path, "too-large"))
        else:
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                skipped.append((path, "not-text"))
                continue
            markdown = _kb_ascii_lower(path).endswith(KB_MARKDOWN_SUFFIXES)
            line = kb_format_line(data) if markdown else None
            name = line[0] if line else None
            engine = None if name in (None,) + KB_AS_WRITTEN + KB_EXPANDED else name
            files[path] = {
                "text": text,
                "engine": engine,
                "raw": not markdown or name in KB_AS_WRITTEN,
                "options": line[1] if line else {},
                "bytes": len(data),
                "rest": kb_after_shebang(text) if name else text,
            }
    return {"files": files, "skipped": skipped, "entries": entries}


def _kb_choose(overlays: "list[dict]", wanted: Optional[str]) -> "list[dict]":
    if wanted is None:
        return overlays
    chosen = [o for o in overlays if normalize_name(o["identity"]) == normalize_name(wanted)]
    if not chosen:
        raise KnowledgeError("unknown-overlay", wanted)
    return chosen


def _kb_error(error: KnowledgeError) -> "dict[str, Any]":
    return {"error": {"class": error.code, "message": error.message}}


def kb_call(
    tool: str,
    overlays: "list[dict]",
    arguments: Any,
    modes: "Iterable[str]" = (),
    limits: "Optional[dict[str, int]]" = None,
    facts: "Optional[dict[str, Any]]" = None,
    engines: "Iterable[str]" = KB_ENGINES,
) -> "dict[str, Any]":
    """What a server answers a call of ``kb_list`` or ``kb_read``: ``{"result": ...}`` or
    ``{"error": {"class", "message"}}``. ``overlays`` are the session's active overlays in
    composition order, each with ``identity``, ``manifest``, ``tree``, ``served`` and its
    template ``facts``; ``facts`` holds the caller's: ``caller``, ``env`` and ``env_allow``;
    ``engines`` are the template engines this server renders with."""
    modes = list(modes)
    # "-engine:option=value" entries say which option values this server cannot honour
    lacks = [entry for entry in engines if entry.startswith("-")]
    engines = [engine for engine in KB_ENGINES if engine in set(engines)] + lacks
    try:
        args = kb_arguments(tool, arguments, modes, limits)
        if tool == "kb_list":
            return {"result": _kb_list(overlays, args, modes, limits, engines, facts or {})}
        if tool == "kb_read":
            return {"result": _kb_read(overlays, args, limits, facts or {}, engines)}
        raise KnowledgeError("invalid-arguments", "no tool is named " + tool)
    except KnowledgeError as error:
        return _kb_error(error)


def _kb_list(overlays, args, modes, limits, engines, facts) -> "dict[str, Any]":
    listed = []
    for overlay in _kb_choose(overlays, args.get("overlay")):
        found = kb_set(overlay, limits)
        files = []
        skipped = list(found["skipped"])
        for path, item in found["files"].items():
            try:
                text = _kb_serve(overlay, found, path, {}, facts, kb_limits(limits), engines)
            except KnowledgeError:
                skipped.append((path, "render"))
                continue
            entry = {"path": path, "lines": len(kb_lines(text)), "bytes": len(text.encode("utf-8"))}
            if item["engine"]:
                entry["template"] = item["engine"]
                entry["rendered"] = _kb_here(item, engines)
            files.append(entry)
        skipped.sort(key=lambda pair: pair[0].encode("utf-8"))
        listed.append(
            {
                "overlay": overlay["identity"],
                "served": bool(overlay.get("served", False)),
                "files": files,
                "skipped": [{"path": kb_inert(path), "reason": reason} for path, reason in skipped],
            }
        )
    result: "dict[str, Any]" = {
        "overlays": listed,
        "engines": [engine for engine in engines if not engine.startswith("-")],
    }
    if modes:
        result["search"] = {"modes": [mode for mode in KB_MODES if mode in set(modes)]}
    return result


def _kb_path_problem(path: str) -> bool:
    return not valid_relpath(path) or _kb_hidden_name(path)


_KB_SKIP_CLASS = {
    "name": "invalid-path",
    "too-large": "too-large",
    "not-text": "not-text",
}
_KB_PRIORITY = ("link", "not-text", "too-large", "not-found")


def _kb_read(overlays, args, limits, facts, engines) -> "dict[str, Any]":
    limit = kb_limits(limits)
    path = args["path"]
    if _kb_path_problem(path):
        raise KnowledgeError("invalid-path", kb_inert(path))
    found_in = []
    problems = []
    for overlay in _kb_choose(overlays, args.get("overlay")):
        held = kb_set(overlay, limit)
        parts = path.split("/")
        linked = any(
            held["entries"].get("/".join(parts[: n + 1]), ("file", b""))[0] == "symlink"
            for n in range(len(parts))
        )
        if linked:
            problems.append("link")
        elif path in held["files"]:
            found_in.append((overlay, held))
        else:
            reason = dict(held["skipped"]).get(path)
            problems.append(_KB_SKIP_CLASS[reason] if reason else "not-found")
    if len(found_in) > 1:
        raise KnowledgeError("ambiguous", "more than one overlay has that path")
    if not found_in:
        raise KnowledgeError(
            min(problems, key=_KB_PRIORITY.index) if problems else "not-found", kb_inert(path)
        )
    overlay, held = found_in[0]
    engine = held["files"][path]["engine"]
    text = _kb_serve(overlay, held, path, args.get("context", {}), facts, limit, engines)
    lines = kb_lines(text)
    total = len(lines)
    start = args.get("from", 1)
    stop = args.get("to")
    if (stop is not None and stop < start) or start > max(total, 1):
        raise KnowledgeError("line-range", "the file has %d lines" % total)
    last = total if stop is None else min(stop, total)
    chosen: "list[str]" = []
    size = 0
    truncated = False
    for line in lines[start - 1 : last]:
        add = len(line.encode("utf-8")) + (1 if chosen else 0)
        if chosen and _kb_over(size + add, limit["max_read_bytes"]):
            truncated = True
            break
        chosen.append(line)
        size += add
    result = {
        "overlay": overlay["identity"],
        "path": path,
        "from_line": start,
        "to_line": start - 1 + len(chosen),
        "total_lines": total,
        "truncated": truncated,
        "text": kb_inert("\n".join(chosen)),
    }
    if engine:
        result["template"] = engine
        result["rendered"] = _kb_here(held["files"][path], engines)
    return result


def _kb_facts(overlay: "dict[str, Any]") -> "dict[str, Any]":
    facts = dict(overlay.get("facts", {}))
    facts.setdefault("name", normalize_name(overlay["identity"]))
    return facts


def _kb_allowed_env(facts: "dict[str, Any]") -> "dict[str, str]":
    env = facts.get("env", {})
    return {
        name: env[name]
        for name in facts.get("env_allow", [])
        if name in env and not is_sensitive(name) and isinstance(env[name], str)
    }


KB_DIALECTS = {
    "gnu": ("all", frozenset()),
    "a8m": ("all", frozenset({"escape", "default"})),
    "drone": ("braced", frozenset({"escape", "default"})),
}
KB_SHELL_FEATURES = (
    "escape",
    "default",
    "assign",
    "alternate",
    "nested",
    "unquote",
    "slice",
    "replace",
    "trim",
    "case",
    "length",
)
KB_IMPLEMENTED_FEATURES = frozenset({"escape", "default"})
KB_UNDEFINED = ("strict", "lenient", "debug")


def _kb_envsubst_options(options: "dict[str, str]") -> "tuple[str, frozenset, str]":
    """The pattern, features and undefined mode an ``envsubst`` line asks for, or ``template-error``."""
    dialect = options.get("dialect", "gnu")
    if dialect not in KB_DIALECTS:
        raise KnowledgeError("template-error", "dialect is gnu, a8m or drone")
    pattern, features = KB_DIALECTS[dialect]
    if "pattern" in options:
        if options["pattern"] not in ("braced", "unbraced", "all"):
            raise KnowledgeError("template-error", "pattern is braced, unbraced or all")
        pattern = options["pattern"]
    if "features" in options:
        asked = frozenset(options["features"].split(","))
        if not asked <= set(KB_SHELL_FEATURES):
            raise KnowledgeError("template-error", "a feature that is not defined")
        features = asked
    undefined = options.get("undefined", "debug")
    if undefined not in KB_UNDEFINED:
        raise KnowledgeError("template-error", "undefined is strict, lenient or debug")
    return pattern, features, undefined


def _kb_here(item, engines) -> bool:
    """Whether this server renders the file's engine with the options it asks for."""
    if item["engine"] not in engines:
        return False
    for key, value in item["options"].items():
        if "-%s:%s=%s" % (item["engine"], key, value) in engines:
            return False
    if item["engine"] == "envsubst":
        try:
            return _kb_envsubst_options(item["options"])[1] <= KB_IMPLEMENTED_FEATURES
        except KnowledgeError:
            return True
    return True


def _kb_serve(overlay, held, path, context, call, limit, engines) -> str:
    """The text ``kb_read`` serves for a file of the knowledge, before it is cut into lines."""
    item = held["files"][path]
    if item["raw"]:
        return item["rest"]
    if item["engine"]:
        return _kb_render(overlay, item, context, call, limit, _kb_here(item, engines), held, path)
    ctx = {
        "overlay": overlay,
        "held": held,
        "context": context,
        "call": call,
        "limit": limit,
        "engines": engines,
        "values": None,
        "added": [0],
    }
    out = _kb_markdown(item["rest"], path, ctx, (path,))
    if _kb_over(len(out.encode("utf-8")), limit["max_rendered_bytes"]):
        raise KnowledgeError("too-large", "the served text")
    return out


def _kb_values(ctx) -> "dict[str, str]":
    """The names ``${NAME}`` replaces, made the first time one is met."""
    if ctx["values"] is None:
        data = _kb_data(ctx["overlay"], ctx["context"], ctx["call"])
        ctx["values"] = _kb_envsubst_values(ctx["overlay"], data, ctx["context"])
    return ctx["values"]


_KB_FENCE = re.compile(r"( {0,3})(`{3,}|~{3,})")


def _kb_opens_fence(line: str) -> "Optional[tuple[str, int]]":
    found = _KB_FENCE.match(line)
    return (found.group(2)[0], len(found.group(2))) if found else None


def _kb_closes_fence(line: str, fence: "tuple[str, int]") -> bool:
    found = _KB_FENCE.match(line)
    return bool(
        found
        and found.group(2)[0] == fence[0]
        and len(found.group(2)) >= fence[1]
        and line[found.end() :].strip(" \t\r\n") == ""
    )


def _kb_code_mask(line: str) -> "list[bool]":
    """Which characters of a line are in a code span: a run of backticks, to the next run of as
    many on the same line; a run with none is itself."""
    mask = [False] * len(line)
    i = 0
    while i < len(line):
        if line[i] != "`":
            i += 1
            continue
        j = i
        while j < len(line) and line[j] == "`":
            j += 1
        k = j
        end = None
        while k < len(line):
            if line[k] == "`":
                m = k
                while m < len(line) and line[m] == "`":
                    m += 1
                if m - k == j - i:
                    end = m
                    break
                k = m
            else:
                k += 1
        if end is None:
            i = j
        else:
            for n in range(i, end):
                mask[n] = True
            i = end
    return mask


def _kb_markdown(text: str, path: str, ctx, chain) -> str:
    out = []
    fence = None
    for line in re.findall(r"[^\n]*\n|[^\n]+", text):
        if fence is not None:
            out.append(_kb_line(line, [True] * len(line), path, ctx, chain))
            if _kb_closes_fence(line, fence):
                fence = None
            continue
        fence = _kb_opens_fence(line)
        if fence:
            out.append(_kb_line(line, [True] * len(line), path, ctx, chain))
        else:
            out.append(_kb_line(line, _kb_code_mask(line), path, ctx, chain))
    return "".join(out)


_KB_TRAILING = ".,;:!?)]}'\""


def _kb_line(line: str, in_code: "list[bool]", path: str, ctx, chain) -> str:
    out = []
    i = 0
    while i < len(line):
        if not in_code[i] and line.startswith("$$", i):
            out.append("$")
            i += 2
            continue
        found = None if in_code[i] else _TEMPLATE_PLACEHOLDER.match(line, i)
        if found:
            values = _kb_values(ctx)
            if found.group(1) in values:
                out.append(values[found.group(1)])
                i = found.end()
                continue
        if line[i] == "@" and not in_code[i] and (i == 0 or line[i - 1] in " \t\r\f\v"):
            token = re.match(r"[^ \t\r\n\f\v]+", line[i + 1 :])
            name = token.group() if token else ""
            while name and name[-1] in _KB_TRAILING:
                name = name[:-1]
            target = _kb_resolve(path, name, ctx["held"]) if name else None
            included = _kb_include(target, ctx, chain) if target else None
            if included is not None:
                out.append(included)
                i += 1 + len(name)
                continue
        out.append(line[i])
        i += 1
    return "".join(out)


def _kb_resolve(path: str, name: str, held) -> "Optional[str]":
    """The file of the knowledge an include names, or ``None``: the name is resolved from the
    including file's folder, ``..`` may rise only to the root, and what is not a served file of the
    overlay is not an include."""
    if name[0] in "/~" or "\\" in name or re.match(r"[A-Za-z]:", name):
        return None
    parts = path.split("/")[:-1]
    for part in name.split("/"):
        if part == "":
            return None
        if part == ".":
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
        else:
            parts.append(part)
    target = "/".join(parts)
    return target if valid_relpath(target) and target in held["files"] else None


def _kb_include(target: str, ctx, chain) -> "Optional[str]":
    item = ctx["held"]["files"][target]
    limit = ctx["limit"]
    if item["raw"]:
        text = item["rest"]
    elif item["engine"]:
        if not _kb_here(item, ctx["engines"]):
            return None
        text = _kb_render(
            ctx["overlay"], item, ctx["context"], ctx["call"], limit, True, ctx["held"], target
        )
    else:
        if target in chain:
            raise KnowledgeError("include-error", "an include comes back to " + target)
        if _kb_over(len(chain), limit["max_include_depth"]):
            raise KnowledgeError("include-error", "includes are nested too deep")
        body = item["rest"]
        found = split_front_matter(body.encode("utf-8"))
        if found["case"] in ("present", "empty"):
            body = body.encode("utf-8")[found["body_offset"] :].decode("utf-8")
        text = _kb_markdown(body, target, ctx, chain + (target,))
    ctx["added"][0] += len(text.encode("utf-8"))
    if _kb_over(ctx["added"][0], limit["max_rendered_bytes"]):
        raise KnowledgeError("too-large", "the included text")
    if text.endswith("\r\n"):
        return text[:-2]
    return text[:-1] if text.endswith("\n") else text


def _kb_envsubst_values(overlay, data, context) -> "dict[str, str]":
    values = template_values(overlay.get("manifest", {}), _kb_facts(overlay))
    for key, name in (("role", "AOS_CALLER_ROLE"), ("profile", "AOS_CALLER_PROFILE")):
        if key in data["caller"]:
            values[name] = data["caller"][key]
    for name, value in data["env"].items():
        values["AOS_ENV_" + name] = value
    for key, value in context.items():
        if isinstance(value, bool):
            values["AOS_ARG_" + key] = "true" if value else "false"
        elif isinstance(value, (int, str)):
            values["AOS_ARG_" + key] = str(value)
    return values


def _kb_data(overlay, context, call) -> "dict[str, Any]":
    """What a template reads: the roots ``overlay``, ``project``, ``caller``, ``env``, ``options``
    and ``context``, each only with what it holds. A sensitive option or variable is never in it."""
    manifest = overlay.get("manifest", {})
    facts = _kb_facts(overlay)
    options: "dict[str, Any]" = {}
    configured = facts.get("options", {})
    for name, declared in (manifest.get("options") or {}).items():
        if declared.get("sensitive") is True:
            continue
        if name in configured:
            try:
                _option_text(declared, name, configured[name])
            except ReadError:
                raise KnowledgeError("invalid-option", name) from None
            options[name] = configured[name]
        elif "default" in declared:
            try:
                _option_text(declared, name, declared["default"])
            except ReadError:
                raise KnowledgeError("invalid-option", name) from None
            options[name] = declared["default"]
    data: "dict[str, Any]" = {
        "overlay": {
            key: facts[source]
            for key, source in (
                ("root", "root"),
                ("state", "state"),
                ("name", "name"),
                ("scope", "scope"),
            )
            if facts.get(source) is not None
        },
        "project": ({"root": facts["project"]} if facts.get("project") is not None else {}),
        "caller": {k: v for k, v in call.get("caller", {}).items() if isinstance(v, str)},
        "env": _kb_allowed_env(call),
        "options": options,
        "context": context,
    }
    return data


def _kb_flow(value: Any) -> str:
    """A value as one line of flow YAML (JSON's shapes): keys in UTF-8 byte order, ``, `` and
    ``: `` between, and in a string only the quotation mark, the backslash and U+0000-U+001F
    escaped, those as ``\\u00xx`` in lower case."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        out = []
        for char in value:
            if char in '"\\':
                out.append("\\" + char)
            elif ord(char) < 0x20:
                out.append("\\u%04x" % ord(char))
            else:
                out.append(char)
        return '"' + "".join(out) + '"'
    if isinstance(value, list):
        return "[" + ", ".join(_kb_flow(item) for item in value) + "]"
    keys = sorted(value, key=lambda key: key.encode("utf-8"))
    return "{" + ", ".join("%s: %s" % (_kb_flow(key), _kb_flow(value[key])) for key in keys) + "}"


def _kb_context_block(engine: str, data: "dict[str, Any]") -> str:
    """The front matter a file gets when its engine is not here: one key holding the engine's
    name and the roots, which are left out when empty."""
    parts = ['"engine": ' + _kb_flow(engine)]
    for root_name in ("overlay", "project", "caller", "env", "options", "context"):
        if data[root_name]:
            parts.append('"%s": %s' % (root_name, _kb_flow(data[root_name])))
    return "---\naos_template_context: {" + ", ".join(parts) + "}\n---\n"


def _kb_partial(held, path, name) -> "Optional[str]":
    """A partial: a served file of the same overlay, found as an include is, its text after its
    first line when that line names a format."""
    target = _kb_resolve(path, name, held) if name else None
    return held["files"][target]["rest"] if target else None


def _kb_render(overlay, item, context, call, limit, here, held, path) -> str:
    manifest = overlay.get("manifest", {})
    data = _kb_data(overlay, context, call)
    engine = item["engine"]
    if not here:
        text = item["text"]
        end = text.find("\n")
        first, rest = (text + "\n", "") if end < 0 else (text[: end + 1], text[end + 1 :])
        out = first + _kb_context_block(engine, data) + rest
    elif engine == "envsubst":
        values = _kb_envsubst_values(overlay, data, context)
        pattern, features, undefined = _kb_envsubst_options(item["options"])
        out = kb_envsubst(item["rest"], values, pattern, features, undefined)
    else:
        escape = item["options"].get("escape", "html")
        if escape not in ("html", "none"):
            raise KnowledgeError("template-error", "escape is html or none")
        out = mustache(
            item["rest"], data, limit, lambda name: _kb_partial(held, path, name), escape
        )
    if _kb_over(len(out.encode("utf-8")), limit["max_rendered_bytes"]):
        raise KnowledgeError("too-large", "the rendered text")
    return out


_KB_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def kb_envsubst(
    text: str,
    values: "dict[str, str]",
    pattern: str = "all",
    features: "frozenset[str]" = frozenset(),
    undefined: str = "debug",
) -> str:
    """``envsubst``: ``$NAME`` and ``${NAME}`` (as ``pattern`` allows) replaced by the value of
    NAME; a name with no value follows ``undefined``; with the ``escape`` feature ``$$`` is ``$``,
    with ``default`` ``${NAME:-word}`` and ``${NAME-word}`` give the word where the name has no
    value (``:-`` also where it is empty). Anything else is text."""
    out = []
    i = 0
    while i < len(text):
        if text[i] != "$":
            out.append(text[i])
            i += 1
            continue
        if "escape" in features and text.startswith("$$", i):
            out.append("$")
            i += 2
            continue
        found = None
        if pattern in ("braced", "all") and text.startswith("${", i):
            name = _KB_NAME.match(text, i + 2)
            if name:
                j = name.end()
                if text.startswith("}", j):
                    found = (name.group(), None, j + 1)
                elif "default" in features and (
                    text.startswith(":-", j) or text.startswith("-", j)
                ):
                    colon = text.startswith(":-", j)
                    close = text.find("}", j)
                    if close >= 0:
                        word = text[j + (2 if colon else 1) : close]
                        found = (name.group(), (colon, word), close + 1)
        if found is None and pattern in ("unbraced", "all"):
            name = _KB_NAME.match(text, i + 1)
            if name:
                found = (name.group(), None, name.end())
        if found is None:
            out.append("$")
            i += 1
            continue
        name, default, end = found
        value = values.get(name)
        if default is not None and (value is None or (default[0] and value == "")):
            out.append(default[1])
        elif value is not None:
            out.append(value)
        elif undefined == "strict":
            raise KnowledgeError("template-error", "a name has no value: " + name)
        elif undefined == "debug":
            out.append(text[i:end])
        i = end
    return "".join(out)


_MISSING = object()
_M_WS = " \t\r\n"
_M_STANDALONE = ("comment", "sec", "inv", "end", "partial", "delim")
_M_TAIL = re.compile(r"[ \t]*(?:\r?\n|\Z)")


def _m_tokens(text: str) -> "list[tuple]":
    tokens: "list[tuple]" = []
    opening, closing = "{{", "}}"
    i = 0
    while i < len(text):
        j = text.find(opening, i)
        if j < 0:
            tokens.append(("text", i, len(text)))
            break
        if j > i:
            tokens.append(("text", i, j))
        k = j + len(opening)
        if opening == "{{" and text.startswith("{", k):
            end = text.find("}}}", k + 1)
            if end < 0:
                raise KnowledgeError("template-error", "a tag is not closed")
            tokens.append(("tag", "raw", text[k + 1 : end].strip(_M_WS), j, end + 3))
            i = end + 3
            continue
        sigil = text[k : k + 1]
        if sigil == "=":
            end = text.find("=" + closing, k + 1)
            parts = text[k + 1 : end].split() if end >= 0 else []
            if len(parts) != 2:
                raise KnowledgeError("template-error", "a delimiter tag is not usable")
            tokens.append(("tag", "delim", "", j, end + 1 + len(closing)))
            i = end + 1 + len(closing)
            opening, closing = parts
            continue
        if sigil and sigil in "!#^/>&":
            end = text.find(closing, k + 1)
            if end < 0:
                raise KnowledgeError("template-error", "a tag is not closed")
            kind = {"!": "comment", "#": "sec", "^": "inv", "/": "end", ">": "partial", "&": "raw"}[
                sigil
            ]
            tokens.append(("tag", kind, text[k + 1 : end].strip(_M_WS), j, end + len(closing)))
            i = end + len(closing)
            continue
        end = text.find(closing, k)
        if end < 0:
            raise KnowledgeError("template-error", "a tag is not closed")
        tokens.append(("tag", "var", text[k:end].strip(_M_WS), j, end + len(closing)))
        i = end + len(closing)
    return tokens


def _m_parse(text: str) -> "list":
    tokens = _m_tokens(text)
    removed: "list[tuple[int, int]]" = []
    indents: "dict[int, str]" = {}
    for index, token in enumerate(tokens):
        if token[0] != "tag" or token[1] not in _M_STANDALONE:
            continue
        start, end = token[3], token[4]
        line = text.rfind("\n", 0, start) + 1
        tail = _M_TAIL.match(text, end)
        if text[line:start].strip(" \t") == "" and tail:
            removed.append((line, tail.end()))
            indents[index] = text[line:start]

    def cut(low: int, high: int) -> str:
        out, at = [], low
        for a, b in removed:
            if b <= low or a >= high:
                continue
            out.append(text[at : max(a, low)])
            at = min(b, high)
        out.append(text[at:high])
        return "".join(out)

    root: "list" = []
    stack = [("", root)]
    for index, token in enumerate(tokens):
        children = stack[-1][1]
        if token[0] == "text":
            piece = cut(token[1], token[2])
            if piece:
                children.append(("text", piece))
            continue
        kind, name = token[1], token[2]
        if kind in ("var", "raw"):
            children.append(("var", name, kind == "var"))
        elif kind in ("sec", "inv"):
            node = ("sec", name, kind == "inv", [])
            children.append(node)
            stack.append((name, node[3]))
        elif kind == "end":
            if len(stack) == 1 or stack[-1][0] != name:
                raise KnowledgeError("template-error", "a section is closed wrongly")
            stack.pop()
        elif kind == "partial":
            children.append(("partial", name, indents.get(index, "")))
    if len(stack) != 1:
        raise KnowledgeError("template-error", "a section is not closed")
    return root


def _m_lookup(name: str, stack: "list") -> Any:
    if name == ".":
        return stack[-1]
    first, *rest = name.split(".")
    value: Any = _MISSING
    for context in reversed(stack):
        if isinstance(context, dict) and first in context:
            value = context[first]
            break
    for key in rest:
        if value is _MISSING:
            break
        value = value[key] if isinstance(value, dict) and key in value else _MISSING
    return value


def _m_text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, str)):
        return str(value)
    return ""


def _m_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def mustache(
    text: str,
    data: "dict[str, Any]",
    limits: "Optional[dict[str, int]]" = None,
    partial: "Optional[Any]" = None,
    escape: str = "html",
) -> str:
    """Mustache as its specification defines it (interpolation, sections, inverted sections,
    comments, delimiters, partials), over ``data``; ``partial(name)`` gives a partial's text or
    ``None``, which renders as nothing. ``escape`` is ``html`` (``& < > "``) or ``none``."""
    limit = kb_limits(limits)
    out: "list[str]" = []
    size = [0]
    parsed: "dict[str, list]" = {}

    def emit(piece: str) -> None:
        size[0] += len(piece.encode("utf-8"))
        if _kb_over(size[0], limit["max_rendered_bytes"]):
            raise KnowledgeError("too-large", "the rendered text")
        out.append(piece)

    def tree(source: str) -> "list":
        if source not in parsed:
            parsed[source] = _m_parse(source)
        return parsed[source]

    def walk(nodes: "list", stack: "list", depth: int) -> None:
        for node in nodes:
            if node[0] == "text":
                emit(node[1])
            elif node[0] == "var":
                piece = _m_text(_m_lookup(node[1], stack))
                emit(_m_escape(piece) if node[2] and escape == "html" else piece)
            elif node[0] == "partial":
                source = partial(node[1]) if partial and node[1] else None
                if source is None:
                    continue
                if node[2]:
                    source = "".join(
                        node[2] + part for part in re.findall(r"[^\n]*\n|[^\n]+", source)
                    )
                if _kb_over(depth + 1, limit["max_include_depth"]):
                    raise KnowledgeError("include-error", "partials are nested too deep")
                walk(tree(source), stack, depth + 1)
            else:
                value = _m_lookup(node[1], stack)
                falsy = value is _MISSING or value is None or value is False or value == []
                if node[2]:
                    if falsy:
                        walk(node[3], stack, depth)
                elif not falsy:
                    for item in value if isinstance(value, list) else [value]:
                        walk(node[3], stack + [item], depth)

    walk(tree(text), [data], 0)
    return "".join(out)


def kb_search_order(passages: "list[dict]") -> "list[dict]":
    """Passages by score, highest first, then path bytes, then first line, then last line; ones
    equal in all four keep the order given."""
    return sorted(
        passages,
        key=lambda p: (-p["score"], p["path"].encode("utf-8"), p["from_line"], p["to_line"]),
    )


def kb_search_check(
    overlays: "list[dict]",
    arguments: "dict[str, Any]",
    response: Any,
    modes: "Iterable[str]",
    limits: "Optional[dict[str, int]]" = None,
    facts: "Optional[dict[str, Any]]" = None,
    engines: "Iterable[str]" = KB_ENGINES,
) -> "list[str]":
    """The rules a ``kb_search`` answer breaks, as sorted ids; empty when it conforms. The ranking
    itself is not checked, only the shape and the order the scores imply."""
    modes = list(modes)
    limit = kb_limits(limits)
    args = kb_arguments("kb_search", arguments, modes, limit)
    broken: "set[str]" = set()
    if not isinstance(response, dict) or set(response) != {"results"}:
        return ["shape"]
    chosen = _kb_choose(overlays, args.get("overlay"))
    results = response["results"]
    if not isinstance(results, list):
        return ["shape"]
    if [r.get("overlay") if isinstance(r, dict) else None for r in results] != [
        o["identity"] for o in chosen
    ]:
        broken.add("overlays")
    prefix = args.get("path")
    for entry, overlay in zip(results, chosen):
        if not isinstance(entry, dict):
            broken.add("shape")
            continue
        if "error" in entry:
            error = entry["error"]
            if (
                set(entry) != {"overlay", "error"}
                or not isinstance(error, dict)
                or set(error) != {"class", "message"}
                or error["class"] not in ("unavailable", "mode-unavailable")
            ):
                broken.add("shape")
            elif error["class"] == "mode-unavailable" and args["mode"] == "auto":
                broken.add("mode")
            continue
        if (
            not {"overlay", "mode", "passages"}
            <= set(entry)
            <= {"overlay", "mode", "passages", "note"}
        ):
            broken.add("shape")
            continue
        if entry["mode"] not in modes or (args["mode"] != "auto" and entry["mode"] != args["mode"]):
            broken.add("mode")
        if "note" in entry and (
            not isinstance(entry["note"], str) or entry["note"] != kb_inert(entry["note"])
        ):
            broken.add("inert")
        passages = entry["passages"]
        if not isinstance(passages, list):
            broken.add("shape")
            continue
        if len(passages) > args["top"]:
            broken.add("top")
        held = kb_set(overlay, limit)
        for passage in passages:
            if not isinstance(passage, dict) or set(passage) != {
                "path",
                "heading",
                "from_line",
                "to_line",
                "score",
                "text",
            }:
                broken.add("shape")
                continue
            score = passage["score"]
            if isinstance(score, bool) or not isinstance(score, (int, float)) or score != score:
                broken.add("shape")
                continue
            path = passage["path"]
            if prefix is not None and not (path == prefix or path.startswith(prefix + "/")):
                broken.add("path-limit")
            try:
                lines = kb_lines(_kb_serve(overlay, held, path, {}, facts or {}, limit, engines))
            except (KeyError, KnowledgeError):
                broken.add("not-knowledge")
                continue
            first, last = passage["from_line"], passage["to_line"]
            if not (
                isinstance(first, int)
                and isinstance(last, int)
                and 1 <= first <= last <= len(lines)
            ):
                broken.add("range")
                continue
            span = kb_inert("\n".join(lines[first - 1 : last]))
            if (
                not isinstance(passage["text"], str)
                or passage["text"] == ""
                or passage["text"] not in span
            ):
                broken.add("text")
            for field in ("heading", "text"):
                if not isinstance(passage[field], str) or passage[field] != kb_inert(
                    passage[field]
                ):
                    broken.add("inert")
        keyed = [
            p
            for p in passages
            if isinstance(p, dict)
            and isinstance(p.get("score"), (int, float))
            and not isinstance(p.get("score"), bool)
            and isinstance(p.get("path"), str)
            and isinstance(p.get("from_line"), int)
            and isinstance(p.get("to_line"), int)
        ]
        if len(keyed) == len(passages) and kb_search_order(passages) != passages:
            broken.add("order")
    return sorted(broken)


def kb_call_result(outcome: "dict[str, Any]") -> "dict[str, Any]":
    """A handler's outcome as MCP's ``tools/call`` result: the same JSON as ``structuredContent``
    and as one text block, and ``isError``."""
    failed = "error" in outcome
    body = {"error": outcome["error"]} if failed else outcome["result"]
    return {
        "content": [{"type": "text", "text": json.dumps(body, ensure_ascii=False)}],
        "structuredContent": body,
        "isError": failed,
    }


def knowledge_plan(
    manifest: "dict[str, Any]", files: "dict[str, Any]", user: "Optional[bool]" = None
) -> "dict[str, Any]":
    """Whether an overlay's rules and context files are left out of the context because they are
    served, and which. The user's choice wins over the overlay's hint; the body of ``OVERLAY.md``
    is never left out, since it is no file the tools serve."""
    hint = manifest.get("knowledge", {}).get("serve") is True
    served = hint if user is None else user
    left = []
    if served:
        for path in rules_of(manifest, files) + context_of(manifest, files):
            if path != "OVERLAY.md" and path not in left:
                left.append(path)
    return {"served": served, "left_out": left}
