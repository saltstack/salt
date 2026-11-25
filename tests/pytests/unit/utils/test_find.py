"""
Tests for salt.utils.find.
"""

import os

import salt.utils.files
import salt.utils.find


def _make_tree(root):
    for parts in (
        ("match", "level2", "level3"),
        ("unrelated", "level2", "level3"),
    ):
        os.makedirs(os.path.join(root, *parts))
    with salt.utils.files.fopen(os.path.join(root, "top.txt"), "w", encoding="utf-8"):
        pass
    with salt.utils.files.fopen(
        os.path.join(root, "match", "level2", "level3", "deep.txt"),
        "w",
        encoding="utf-8",
    ):
        pass


def _child_depth(root, dirpath):
    relpath = os.path.relpath(dirpath, root)
    return salt.utils.find.path_depth(relpath) + 1


def test_maxdepth_does_not_list_deeper_directories(tmp_path, monkeypatch):
    """
    maxdepth filters matches and must also stop os.walk from descending.
    """
    root = str(tmp_path)
    _make_tree(root)
    walked = []
    real_walk = os.walk

    def spy_walk(top, *args, **kwargs):
        for dirpath, dirs, files in real_walk(top, *args, **kwargs):
            walked.append(dirpath)
            yield dirpath, dirs, files

    monkeypatch.setattr(os, "walk", spy_walk)

    found = list(salt.utils.find.Finder({"maxdepth": 1, "name": "match*"}).find(root))

    assert found == [os.path.join(root, "match")]
    assert walked, "os.walk should still list the search root"
    assert all(_child_depth(root, dirpath) <= 1 for dirpath in walked)
    assert not any("level2" in dirpath or "level3" in dirpath for dirpath in walked)


def test_maxdepth_still_returns_entries_at_the_limit(tmp_path, monkeypatch):
    root = str(tmp_path)
    _make_tree(root)
    walked = []
    real_walk = os.walk

    def spy_walk(top, *args, **kwargs):
        for dirpath, dirs, files in real_walk(top, *args, **kwargs):
            walked.append(dirpath)
            yield dirpath, dirs, files

    monkeypatch.setattr(os, "walk", spy_walk)

    found = set(salt.utils.find.Finder({"maxdepth": 1}).find(root))

    assert root in found
    assert os.path.join(root, "match") in found
    assert os.path.join(root, "unrelated") in found
    assert os.path.join(root, "top.txt") in found
    assert os.path.join(root, "match", "level2") not in found
    assert all(_child_depth(root, dirpath) <= 1 for dirpath in walked)


def test_maxdepth_zero_does_not_descend(tmp_path, monkeypatch):
    root = str(tmp_path)
    _make_tree(root)
    walked = []
    real_walk = os.walk

    def spy_walk(top, *args, **kwargs):
        for dirpath, dirs, files in real_walk(top, *args, **kwargs):
            walked.append(dirpath)
            yield dirpath, dirs, files

    monkeypatch.setattr(os, "walk", spy_walk)

    found = list(salt.utils.find.Finder({"maxdepth": 0}).find(root))

    assert found == [root]
    assert all(_child_depth(root, dirpath) <= 1 for dirpath in walked)


def test_find_yields_the_paths_that_match(tmp_path):
    (tmp_path / "a.txt").write_text("")
    (tmp_path / "b.log").write_text("")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.txt").write_text("")

    found = sorted(salt.utils.find.find(str(tmp_path), {"name": "*.txt"}))

    assert found == sorted([str(tmp_path / "a.txt"), str(sub / "c.txt")])


def test_find_is_a_generator(tmp_path):
    found = salt.utils.find.find(str(tmp_path), {})
    assert iter(found) is found
