"""
Unit tests for ``salt.cluster.file_sync``.

These functions back the bulk file_roots / pillar_roots ship-on-join logic
in ``salt.channel.server`` (when ``cluster_isolated_filesystem=True``) and
will also back a future ``cluster.sync_roots`` runner.  The sync wire
format is just whatever ``collect_root_tree`` returns, so the unit tests
here pin its shape end-to-end.
"""

import os

import pytest

from salt.cluster.file_sync import _SKIP_DIR_NAMES, apply_root_tree, collect_root_tree

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def src_root(tmp_path):
    """Source roots dir to feed ``collect_root_tree``."""
    p = tmp_path / "src"
    p.mkdir()
    return p


@pytest.fixture
def dst_root(tmp_path):
    """Destination roots dir to feed ``apply_root_tree``."""
    p = tmp_path / "dst"
    p.mkdir()
    return p


# ---------------------------------------------------------------------------
# collect_root_tree
# ---------------------------------------------------------------------------


def test_collect_empty_roots():
    """``None`` and empty roots maps produce an empty dump."""
    assert collect_root_tree(None) == {}
    assert collect_root_tree({}) == {}
    assert collect_root_tree({"base": []}) == {}


def test_collect_missing_directory(tmp_path):
    """Roots pointing at a non-existent path are silently skipped."""
    missing = tmp_path / "does-not-exist"
    assert collect_root_tree({"base": [str(missing)]}) == {}


def test_collect_single_file(src_root):
    """A single regular file is captured with its relative path, mode, data."""
    f = src_root / "init.sls"
    f.write_text("test-id: test.nop\n")
    f.chmod(0o644)

    dump = collect_root_tree({"base": [str(src_root)]})

    assert "base" in dump
    assert len(dump["base"]) == 1
    entry = dump["base"][0]
    assert entry["path"] == "init.sls"
    assert entry["mode"] == 0o644
    assert entry["data"] == b"test-id: test.nop\n"


def test_collect_nested_directory(src_root):
    """Files in subdirectories keep their relative path with forward slashes."""
    sub = src_root / "demo" / "config"
    sub.mkdir(parents=True)
    (sub / "init.sls").write_text("a: b\n")

    dump = collect_root_tree({"base": [str(src_root)]})

    paths = [e["path"] for e in dump["base"]]
    assert paths == ["demo/config/init.sls"]


def test_collect_skips_vcs_dirs(src_root):
    """``.git`` / ``.hg`` / ``.svn`` / ``__pycache__`` / ``.tox`` are skipped."""
    (src_root / "ok.sls").write_text("ok\n")
    for name in _SKIP_DIR_NAMES:
        d = src_root / name
        d.mkdir()
        (d / "should-skip.txt").write_text("nope\n")
        (d / "nested" / "deep.txt").parent.mkdir(parents=True, exist_ok=True)
        (d / "nested" / "deep.txt").write_text("nope\n")

    dump = collect_root_tree({"base": [str(src_root)]})

    paths = [e["path"] for e in dump["base"]]
    assert paths == ["ok.sls"]


def test_collect_skips_symlinks(src_root, tmp_path):
    """Symlinks (file or directory) are not followed."""
    (src_root / "real.sls").write_text("real\n")
    target = tmp_path / "outside.txt"
    target.write_text("outside\n")
    try:
        (src_root / "link.sls").symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("Filesystem does not support symlinks")

    dump = collect_root_tree({"base": [str(src_root)]})

    paths = [e["path"] for e in dump["base"]]
    assert paths == ["real.sls"]


def test_collect_multiple_roots_per_env_first_wins(tmp_path):
    """When two root dirs share a relative path, the earlier root wins."""
    a = tmp_path / "a"
    a.mkdir()
    b = tmp_path / "b"
    b.mkdir()
    (a / "shared.sls").write_bytes(b"from-a\n")
    (b / "shared.sls").write_bytes(b"from-b\n")
    (b / "only-b.sls").write_bytes(b"only-b\n")

    dump = collect_root_tree({"base": [str(a), str(b)]})

    by_path = {e["path"]: e["data"] for e in dump["base"]}
    assert by_path["shared.sls"] == b"from-a\n"
    assert by_path["only-b.sls"] == b"only-b\n"


def test_collect_preserves_binary_content(src_root):
    """Non-UTF-8 bytes round-trip identity-equal as ``bytes``."""
    payload = bytes(range(256))
    (src_root / "blob.bin").write_bytes(payload)

    dump = collect_root_tree({"base": [str(src_root)]})

    entry = next(e for e in dump["base"] if e["path"] == "blob.bin")
    assert entry["data"] == payload
    assert isinstance(entry["data"], bytes)


def test_collect_multiple_envs(tmp_path):
    """Each env in the roots map produces an independent sub-dict."""
    base = tmp_path / "base"
    base.mkdir()
    (base / "b.sls").write_text("b\n")
    prod = tmp_path / "prod"
    prod.mkdir()
    (prod / "p.sls").write_text("p\n")

    dump = collect_root_tree({"base": [str(base)], "prod": [str(prod)]})

    assert set(dump.keys()) == {"base", "prod"}
    assert dump["base"][0]["path"] == "b.sls"
    assert dump["prod"][0]["path"] == "p.sls"


# ---------------------------------------------------------------------------
# apply_root_tree
# ---------------------------------------------------------------------------


def test_apply_empty_dump(dst_root):
    """``None`` and ``{}`` dumps are no-ops, return 0."""
    assert apply_root_tree({"base": [str(dst_root)]}, None) == 0
    assert apply_root_tree({"base": [str(dst_root)]}, {}) == 0
    assert list(dst_root.iterdir()) == []


def test_apply_missing_local_env(dst_root):
    """Envs in the dump that are absent from the local roots map are skipped."""
    dump = {"unknown-env": [{"path": "x.sls", "mode": 0o644, "data": b"x\n"}]}
    assert apply_root_tree({"base": [str(dst_root)]}, dump) == 0


def test_apply_writes_into_first_root(tmp_path):
    """Files are written under ``roots[env][0]``, even if multiple roots exist."""
    a = tmp_path / "a"
    a.mkdir()
    b = tmp_path / "b"
    b.mkdir()
    dump = {"base": [{"path": "demo/init.sls", "mode": 0o644, "data": b"yes\n"}]}

    written = apply_root_tree({"base": [str(a), str(b)]}, dump)

    assert written == 1
    assert (a / "demo" / "init.sls").read_bytes() == b"yes\n"
    assert not (b / "demo").exists()


def test_apply_creates_parents(dst_root):
    """Intermediate directories are created on demand."""
    dump = {"base": [{"path": "deep/nested/dir/file.sls", "data": b"x\n"}]}

    written = apply_root_tree({"base": [str(dst_root)]}, dump)

    assert written == 1
    assert (dst_root / "deep" / "nested" / "dir" / "file.sls").read_bytes() == b"x\n"


def test_apply_preserves_mode(dst_root):
    """The stored mode is applied via ``os.chmod`` after write."""
    dump = {"base": [{"path": "exec.sh", "mode": 0o750, "data": b"#!/bin/sh\n"}]}

    written = apply_root_tree({"base": [str(dst_root)]}, dump)

    assert written == 1
    mode = os.stat(dst_root / "exec.sh").st_mode & 0o777
    assert mode == 0o750


def test_apply_coerces_str_data_to_bytes(dst_root):
    """``salt.payload`` round-trips bytes back as str on some backends; coerce."""
    dump = {"base": [{"path": "init.sls", "mode": 0o644, "data": "as-string\n"}]}

    written = apply_root_tree({"base": [str(dst_root)]}, dump)

    assert written == 1
    assert (dst_root / "init.sls").read_bytes() == b"as-string\n"


def test_apply_skips_entries_missing_required_fields(dst_root):
    """Entries without ``path`` or ``data`` are silently skipped."""
    dump = {
        "base": [
            {"mode": 0o644, "data": b"orphan\n"},  # no path
            {"path": "no-data.sls", "mode": 0o644},  # no data
            {"path": "ok.sls", "mode": 0o644, "data": b"ok\n"},
        ]
    }

    written = apply_root_tree({"base": [str(dst_root)]}, dump)

    assert written == 1
    assert (dst_root / "ok.sls").read_bytes() == b"ok\n"
    assert not (dst_root / "no-data.sls").exists()


def test_apply_overwrites_existing_file(dst_root):
    """Re-applying a tree replaces existing files."""
    target = dst_root / "init.sls"
    target.write_text("old\n")

    dump = {"base": [{"path": "init.sls", "mode": 0o644, "data": b"new\n"}]}
    written = apply_root_tree({"base": [str(dst_root)]}, dump)

    assert written == 1
    assert target.read_bytes() == b"new\n"


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_round_trip_collect_then_apply(src_root, dst_root):
    """``apply_root_tree(collect_root_tree(...))`` reproduces the source tree."""
    (src_root / "top.sls").write_text("top\n")
    sub = src_root / "demo"
    sub.mkdir()
    (sub / "init.sls").write_text("demo\n")
    (src_root / "blob.bin").write_bytes(bytes(range(64)))

    dump = collect_root_tree({"base": [str(src_root)]})
    written = apply_root_tree({"base": [str(dst_root)]}, dump)

    assert written == 3
    assert (dst_root / "top.sls").read_bytes() == b"top\n"
    assert (dst_root / "demo" / "init.sls").read_bytes() == b"demo\n"
    assert (dst_root / "blob.bin").read_bytes() == bytes(range(64))
