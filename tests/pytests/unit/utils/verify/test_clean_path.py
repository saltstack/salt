"""
salt.utils.clean_path works as expected
"""

import salt.utils.verify


def test_clean_path_valid(tmp_path):
    path_a = str(tmp_path / "foo")
    path_b = str(tmp_path / "foo" / "bar")
    assert salt.utils.verify.clean_path(path_a, path_b) == path_b


def test_clean_path_invalid(tmp_path):
    path_a = str(tmp_path / "foo")
    path_b = str(tmp_path / "baz" / "bar")
    assert salt.utils.verify.clean_path(path_a, path_b) == ""
