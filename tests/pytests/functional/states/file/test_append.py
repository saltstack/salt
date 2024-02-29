import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]


FIRST_IF_CONTENTS = """\
# set variable identifying the chroot you work in (used in the prompt below)
if [ -z "$debian_chroot" ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi

"""
SECOND_IF_CONTENTS = """\
# enable bash completion in interactive shells
if [ -f /etc/bash_completion ] && ! shopt -oq posix; then
    . /etc/bash_completion
fi
"""


@pytest.mark.parametrize("test", (True, False))
def test_append(file, tmp_path, test):
    """
    file.append
    """
    name = tmp_path / "testfile"
    name.write_text("#salty!")
    ret = file.append(name=str(name), text="cheese", test=test)
    if test is True:
        assert ret.result is None
        assert name.read_text() == "#salty!"
    else:
        assert ret.result is True
        assert name.read_text() == "#salty!\ncheese\n"


def test_append_issue_1864_makedirs(file, tmp_path):
    """
    file.append but create directories if needed as an option, and create
    the file if it doesn't exist
    """
    fname = "append_issue_1864_makedirs"
    name = tmp_path / fname

    # Non existing file get's touched
    ret = file.append(name=str(name), text="cheese", makedirs=True)
    assert ret.result is True
    assert name.is_file()

    # Nested directory and file get's touched
    name = tmp_path / "issue_1864" / fname
    ret = file.append(name=str(name), text="cheese", makedirs=True)
    assert ret.result is True
    assert name.is_file()
    assert name.parent.is_dir()

    # Parent directory exists but file does not and makedirs is False
    name = name.with_name(name.name + "2")
    ret = file.append(name=str(name), text="cheese", makedirs=False)
    assert ret.result is True
    assert name.is_file()


def test_issue_2227_file_append(file, tmp_path):
    """
    Text to append includes a percent symbol
    """
    # let's make use of existing state to create a file with contents to
    # test against
    tmp_file_append = tmp_path / "test.append"
    tmp_file_append.write_text(FIRST_IF_CONTENTS + SECOND_IF_CONTENTS)
    ret = file.append(name=str(tmp_file_append), text="HISTTIMEFORMAT='%F %T '")
    assert ret.result is True
    contents_pre = tmp_file_append.read_text()

    # It should not append text again
    ret = file.append(name=str(tmp_file_append), text="HISTTIMEFORMAT='%F %T '")
    assert ret.result is True
    contents_post = tmp_file_append.read_text()

    assert contents_pre == contents_post


def test_issue_2379_file_append(modules, tmp_path):
    # Get a path to the temporary file
    tmp_file = tmp_path / "issue-2379-file-append.txt"
    # Write some data to it
    tmp_file.write_text(
        "hello\nworld\n"  # Some junk
        "#PermitRootLogin yes\n"  # Commented text
        "# PermitRootLogin yes\n"  # Commented text with space
    )
    # create the sls template
    template_lines = [
        f"{tmp_file}:",
        "  file.append:",
        "    - text: PermitRootLogin yes",
    ]
    template = "\n".join(template_lines)
    ret = modules.state.template_str(template)
    for state_run in ret:
        assert state_run.result is True
        assert "Appended 1 lines" in state_run.comment


@pytest.mark.slow_test
def test_issue_1896_file_append_source(file, tmp_path, state_tree):
    """
    Verify that we can append a file's contents
    """
    testfile = tmp_path / "test.append"
    testfile.touch()

    firstif_file = pytest.helpers.temp_file(
        "firstif", directory=state_tree / "testappend", contents=FIRST_IF_CONTENTS
    )
    secondif_file = pytest.helpers.temp_file(
        "secondif", directory=state_tree / "testappend", contents=SECOND_IF_CONTENTS
    )
    with firstif_file, secondif_file:
        ret = file.append(name=str(testfile), source="salt://testappend/firstif")
        assert ret.result is True
        ret = file.append(name=str(testfile), source="salt://testappend/secondif")
        assert ret.result is True

        testfile_contents = testfile.read_text()

        assert testfile_contents == FIRST_IF_CONTENTS + SECOND_IF_CONTENTS

        # Run it again
        ret = file.append(name=str(testfile), source="salt://testappend/firstif")
        assert ret.result is True
        ret = file.append(name=str(testfile), source="salt://testappend/secondif")
        assert ret.result is True

        testfile_contents = testfile.read_text()

        assert testfile_contents == FIRST_IF_CONTENTS + SECOND_IF_CONTENTS


def test_file_append_check_cmd(modules, state_tree, tmp_path):
    """
    Test that check_cmd works for file.append
    and those states do not run.
    """
    sls_contents = """
    append_in_file:
      file.append:
        - name: /tmp/test
        - text: "appended text"
        - check_cmd:
          - "djasjahj"
    """
    with pytest.helpers.temp_file(
        "file-append-check-cmd.sls", sls_contents, state_tree
    ):
        ret = modules.state.sls("file-append-check-cmd")
        for state_run in ret:
            assert state_run.result is False
            assert state_run.comment == "check_cmd determined the state failed"
