import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]


def test_symlink(file, tmp_path):
    """
    file.symlink
    """
    symlink = tmp_path / "symlink"
    target = tmp_path / "target"

    # Make sure the symlink target exists
    target.mkdir()

    ret = file.symlink(str(symlink), target=str(target))
    expected = {
        "name": str(symlink),
        "changes": {"new": str(symlink)},
        "result": True,
        "comment": f"Created new symlink {symlink} -> {target}",
    }
    assert ret.filtered == expected
    assert symlink.exists()
    assert symlink.is_symlink()


def test_symlink_test(file, tmp_path):
    """
    file.symlink
    """
    symlink = tmp_path / "symlink"
    target = tmp_path / "target"

    # Make sure the symlink target exists
    target.mkdir()

    ret = file.symlink(str(symlink), target=str(target), test=True)
    assert ret.result is None
    assert symlink.exists() is False
