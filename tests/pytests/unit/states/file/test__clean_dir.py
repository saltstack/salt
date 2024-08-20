"""
Tests for _clean_dir function
"""

import pytest

import salt.states.file as file

pytestmark = [
    pytest.mark.windows_whitelisted,
]


def test_normal():
    expected = []
    result = file._clean_dir(
        root=r"/tmp/parent",
        keep=[r"/tmp/parent/meh-1.txt", r"/tmp/parent/meh-2.txt"],
        exclude_pat=None,
    )
    assert result == expected


def test_win_forward_slash():
    expected = []
    result = file._clean_dir(
        root=r"C:/test/parent",
        keep=[r"C:/test/parent/meh-1.txt", r"C:/test/parent/meh-2.txt"],
        exclude_pat=None,
    )
    assert result == expected


def test_win_forward_slash_mixed_case():
    expected = []
    result = file._clean_dir(
        root=r"C:/test/parent",
        keep=[r"C:/test/parent/meh-1.txt", r"C:/test/Parent/Meh-2.txt"],
        exclude_pat=None,
    )
    assert result == expected


def test_win_back_slash():
    expected = []
    result = file._clean_dir(
        root=r"C:\test\parent",
        keep=[r"C:\test\parent\meh-1.txt", r"C:\test\parent\meh-2.txt"],
        exclude_pat=None,
    )
    assert result == expected


def test_win_back_slash_mixed_cased():
    expected = []
    result = file._clean_dir(
        root=r"C:\test\parent",
        keep=[r"C:\test\parent\meh-1.txt", r"C:\test\Parent\Meh-2.txt"],
        exclude_pat=None,
    )
    assert result == expected
