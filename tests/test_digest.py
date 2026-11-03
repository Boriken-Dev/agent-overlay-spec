"""The tree digest against tests/vectors/digest.json, abstractly and on the filesystem."""

from __future__ import annotations

import base64
import json
import os

import pytest

import aos_reference as aos

VECTORS = json.loads((aos.ROOT / "tests" / "vectors" / "digest.json").read_text(encoding="utf-8"))
CASES = {case["id"]: case for case in VECTORS["cases"]}


def entries(tree: "list[dict]") -> list:
    out = []
    for item in tree:
        raw = (
            base64.b64decode(item["path_base64"])
            if "path_base64" in item
            else item["path"].encode()
        )
        kind = item.get("type", "file")
        data = b""
        if kind == "file":
            data = base64.b64decode(item["base64"]) if "base64" in item else item["text"].encode()
        out.append((tuple(raw.split(b"/")), kind, data))
    return out


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_digest_vector(case_id):
    case = CASES[case_id]
    expect = case["expect"]
    if "error" in expect:
        with pytest.raises(aos.DigestError) as raised:
            aos.digest_entries(entries(case["tree"]))
        assert raised.value.code == expect["error"]
    else:
        digest, lines = aos.digest_entries(entries(case["tree"]))
        assert [line.decode("utf-8") for line in lines] == expect["lines"]
        assert digest == expect["digest"]


def materialize(case: dict, root) -> bool:
    """Builds the case's tree under ``root``; False when this platform cannot hold it."""
    for item in case["tree"]:
        if "path_base64" in item or "\\" in item.get("path", ""):
            return False
        path = root / item["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        kind = item.get("type", "file")
        if kind == "dir":
            path.mkdir(parents=True, exist_ok=True)
        elif kind == "symlink":
            try:
                os.symlink(item["target"], path, target_is_directory=item["path"] == "docs")
            except (OSError, NotImplementedError):
                return False
        elif kind == "special":
            if not hasattr(os, "mkfifo"):
                return False
            os.mkfifo(path)
        else:
            data = base64.b64decode(item["base64"]) if "base64" in item else item["text"].encode()
            path.write_bytes(data)
    return True


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_digest_vector_on_this_filesystem(case_id, tmp_path):
    case = CASES[case_id]
    if not materialize(case, tmp_path):
        pytest.skip("this platform cannot hold the tree")
    expect = case["expect"]
    if case_id == "case-pair" and len(list(tmp_path.iterdir())) < 2:
        pytest.skip("a case-insensitive filesystem holds one of the two names")
    if "error" in expect:
        with pytest.raises(aos.DigestError) as raised:
            aos.tree_digest(tmp_path)
        assert raised.value.code == expect["error"]
    else:
        assert aos.tree_digest(tmp_path) == expect["digest"]


def test_digests_compare_without_case():
    digest = CASES["one-file"]["expect"]["digest"]
    assert aos.same_digest(digest, digest.upper().replace("SHA256:", "sha256:"))
    with pytest.raises(ValueError):
        aos.same_digest(digest, "sha1:" + "0" * 40)


def test_examples_have_a_digest():
    for root in (aos.ROOT / "examples").iterdir():
        if root.is_dir():
            assert aos.DIGEST_FORM.match(aos.tree_digest(root))
