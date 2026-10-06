import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]


def test_prepend_issue_27401_makedirs(file, tmp_path):
    """
    file.prepend but create directories if needed as an option, and create
    the file if it doesn't exist
    """
    fname = "prepend_issue_27401"
    name = tmp_path / fname

    # Non existing file get's touched
    ret = file.prepend(name=str(name), text="cheese", makedirs=True)
    assert ret.result is True
    assert name.is_file()
    assert name.read_text() == "cheese\n"

    # Nested directory and file get's touched
    name = tmp_path / "issue_27401" / fname
    ret = file.prepend(name=str(name), text="cheese", makedirs=True)
    assert ret.result is True
    assert name.is_file()
    assert name.read_text() == "cheese\n"
    assert name.parent.is_dir()

    # Parent directory exists but file does not and makedirs is False
    name = name.with_name(fname + "2")
    ret = file.prepend(name=str(name), text="cheese", makedirs=False)
    assert ret.result is True
    assert name.is_file()
    assert name.read_text() == "cheese\n"
    assert name.parent.is_dir()


@pytest.mark.parametrize("show_changes", (None, True, False))
def test_prepend_show_changes(file, show_changes, tmp_path):
    """
    Test show_changes argument for file.prepend
    """

    name = tmp_path / "testfile-prepend-show_changes"
    name.write_text("#salty!")
    if show_changes is None:
        ret = file.prepend(name=str(name), text="cheese")
    else:
        ret = file.prepend(name=str(name), text="cheese", show_changes=show_changes)

    assert ret.result is True
    assert name.exists()

    if show_changes in [True, None]:
        assert "diff" in ret.changes
        assert "cheese" in ret.changes["diff"]
    else:
        assert ret.changes["diff"] == "<show_changes=False>"
