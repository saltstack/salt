"""
Tests for salt.utils.path helpers.
"""

import os

import salt.utils.path


def test_os_walk_prune_prevents_descent(tmp_path):
    """
    In-place edits of the yielded dirs list must be seen by os.walk.
    """
    keep = tmp_path / "keep" / "nested"
    drop = tmp_path / "drop" / "nested"
    keep.mkdir(parents=True)
    drop.mkdir(parents=True)
    (keep / "kept.txt").write_text("kept", encoding="utf-8")
    (drop / "dropped.txt").write_text("dropped", encoding="utf-8")

    seen = []
    for dirpath, dirs, files in salt.utils.path.os_walk(str(tmp_path)):
        seen.append(os.path.relpath(dirpath, str(tmp_path)))
        dirs[:] = [name for name in dirs if name != "drop"]

    assert "." in seen
    assert "keep" in seen
    assert os.path.join("keep", "nested") in seen
    assert "drop" not in seen
    assert os.path.join("drop", "nested") not in seen


def test_os_walk_clearing_dirs_stops_at_root(tmp_path):
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "b" / "c.txt").write_text("c", encoding="utf-8")

    seen = []
    for dirpath, dirs, files in salt.utils.path.os_walk(str(tmp_path)):
        seen.append(dirpath)
        dirs[:] = []

    assert seen == [str(tmp_path)]


def test_os_walk_yields_str_names(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "file.txt").write_text("x", encoding="utf-8")

    saw_root = False
    for root, dirs, files in salt.utils.path.os_walk(str(tmp_path)):
        saw_root = True
        assert isinstance(root, str)
        assert all(isinstance(name, str) for name in dirs)
        assert all(isinstance(name, str) for name in files)
    assert saw_root
