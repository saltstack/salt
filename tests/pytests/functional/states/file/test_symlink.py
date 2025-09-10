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


@pytest.mark.parametrize("typ", ("dir", "file"))
@pytest.mark.parametrize("relation", ("parent", "sibling", "child"))
def test_symlink_relative(file, tmp_path, typ, relation):
    """
    Ensure symlinks with relative targets work as expected.
    This is especiallly important on windows, where symlinks
    don't dynamically switch types between file and directory.
    """
    if relation == "parent":
        symlink = tmp_path / "subdirectory" / "symlink"
        target_spec = "../target"
    elif relation == "sibling":
        symlink = tmp_path / "symlink"
        target_spec = "target"
    else:
        symlink = tmp_path / "symlink"
        target_spec = "subdirectory/target"
    target = (symlink.parent / target_spec).resolve()
    if typ == "dir":
        target.mkdir(parents=True)
        check_file = symlink / "file_in_target"
        (target / "file_in_target").write_text("resolved")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("resolved")
        check_file = symlink
    res = file.symlink(str(symlink), target=target_spec, makedirs=True)
    assert res.result is True
    assert symlink.exists()
    assert symlink.is_symlink()
    assert symlink.is_dir() is (typ == "dir")
    assert check_file.read_text() == "resolved"
