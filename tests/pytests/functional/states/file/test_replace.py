import os

import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_utf16(path, text):
    """Write *text* to *path* as UTF-16 (with BOM)."""
    path.write_text(text, encoding="utf-16")


def _read_utf16(path):
    return path.read_text(encoding="utf-16")


def test_replace(file, tmp_path):
    """
    file.replace
    """
    name = tmp_path / "testfile"
    name.write_text("change_me")

    ret = file.replace(name=str(name), pattern="change", repl="salt", backup=False)
    assert ret.result is True
    assert name.read_text() == "salt_me"


def test_replace_issue_18612(file, tmp_path):
    """
    Test the (mis-)behaviour of file.replace as described in #18612:

    Using 'prepend_if_not_found' or 'append_if_not_found' resulted in
    an infinitely growing file as 'file.replace' didn't check beforehand
    whether the changes had already been done to the file

    # Case description:

    The tested file contains one commented line
    The commented line should be uncommented in the end, nothing else should change
    """
    test_name = "test_replace_issue_18612"
    path_test = tmp_path / test_name
    path_test.write_text("# en_US.UTF-8")

    ret = []
    for _ in range(3):
        ret.append(
            file.replace(
                name=str(path_test),
                pattern="^# en_US.UTF-8$",
                repl="en_US.UTF-8",
                append_if_not_found=True,
            )
        )

    # ensure, the number of lines didn't change, even after invoking 'file.replace' 3 times
    # and that the replacement succeeded
    assert path_test.read_text() == "en_US.UTF-8"

    # ensure, all runs of 'file.replace' reported success
    for item in ret:
        assert item.result is True


def test_replace_issue_18612_prepend(file, tmp_path):
    """
    Test the (mis-)behaviour of file.replace as described in #18612:

    Using 'prepend_if_not_found' or 'append_if_not_found' resulted in
    an infinitely growing file as 'file.replace' didn't check beforehand
    whether the changes had already been done to the file

    # Case description:

    The tested file contains multiple lines not matching the pattern or replacement in any way
    The replacement pattern should be prepended to the file
    """
    test_name = "test_replace_issue_18612_prepend"
    path_test = tmp_path / test_name
    contents = "#john=doe\n#foo = bar\n#foo=bar\n#blah=blub\n#some=thing"
    path_test.write_text(contents)

    ret = []
    for _ in range(3):
        ret.append(
            file.replace(
                name=str(path_test),
                pattern="^# en_US.UTF-8$",
                repl="en_US.UTF-8",
                prepend_if_not_found=True,
            )
        )

    # ensure, the resulting file contains the expected lines
    assert path_test.read_text() == f"en_US.UTF-8\n{contents}"

    backup_file = path_test.with_name(f"{path_test.name}.bak")
    assert backup_file.is_file()
    assert backup_file.read_text() == contents

    # ensure, all runs of 'file.replace' reported success
    for item in ret:
        assert item.result is True


def test_replace_issue_18612_append(file, tmp_path):
    """
    Test the (mis-)behaviour of file.replace as described in #18612:

    Using 'prepend_if_not_found' or 'append_if_not_found' resulted in
    an infinitely growing file as 'file.replace' didn't check beforehand
    whether the changes had already been done to the file

    # Case description:

    The tested file contains multiple lines not matching the pattern or replacement in any way
    The replacement pattern should be appended to the file
    """
    test_name = "test_replace_issue_18612_append"
    path_test = tmp_path / test_name
    contents = "#john=doe\n#foo = bar\n#foo=bar\n#blah=blub\n#some=thing"
    path_test.write_text(contents)

    ret = []
    for _ in range(3):
        ret.append(
            file.replace(
                name=str(path_test),
                pattern="^# en_US.UTF-8$",
                repl="en_US.UTF-8",
                append_if_not_found=True,
            )
        )

    # ensure, the resulting file contains the expected lines
    assert path_test.read_text() == f"{contents}\nen_US.UTF-8\n"

    backup_file = path_test.with_name(f"{path_test.name}.bak")
    assert backup_file.is_file()
    assert backup_file.read_text() == contents

    # ensure, all runs of 'file.replace' reported success
    for item in ret:
        assert item.result is True


def test_replace_issue_18612_append_not_found_content(file, tmp_path):
    """
    Test the (mis-)behaviour of file.replace as described in #18612:

    Using 'prepend_if_not_found' or 'append_if_not_found' resulted in
    an infinitely growing file as 'file.replace' didn't check beforehand
    whether the changes had already been done to the file

    # Case description:

    The tested file contains multiple lines not matching the pattern or replacement in any way
    The 'not_found_content' value should be appended to the file
    """
    test_name = "test_replace_issue_18612_append_not_found_content"
    path_test = tmp_path / test_name
    contents = "#john=doe\n#foo = bar\n#foo=bar\n#blah=blub\n#some=thing"
    path_test.write_text(contents)

    not_found_content = "THIS LINE WASN'T FOUND! SO WE'RE APPENDING IT HERE!"

    ret = []
    for _ in range(3):
        ret.append(
            file.replace(
                name=str(path_test),
                pattern="^# en_US.UTF-8$",
                repl="en_US.UTF-8",
                append_if_not_found=True,
                not_found_content=not_found_content,
            )
        )

    # ensure, the resulting file contains the expected lines
    assert path_test.read_text() == f"{contents}\n{not_found_content}\n"

    backup_file = path_test.with_name(f"{path_test.name}.bak")
    assert backup_file.is_file()
    assert backup_file.read_text() == contents

    # ensure, all runs of 'file.replace' reported success
    for item in ret:
        assert item.result is True


def test_replace_issue_18612_change_mid_line_with_comment(file, tmp_path):
    """
    Test the (mis-)behaviour of file.replace as described in #18612:

    Using 'prepend_if_not_found' or 'append_if_not_found' resulted in
    an infinitely growing file as 'file.replace' didn't check beforehand
    whether the changes had already been done to the file

    # Case description:

    The tested file contains 5 key=value pairs
    The commented key=value pair #foo=bar should be changed to foo=salt
    The comment char (#) in front of foo=bar should be removed
    """
    test_name = "test_replace_issue_18612_change_mid_line_with_comment"
    path_test = tmp_path / test_name
    contents = "#john=doe\n#foo = bar\n#foo=bar\n#blah=blub\n#some=thing"
    path_test.write_text(contents)

    ret = []
    for _ in range(3):
        ret.append(
            file.replace(
                name=str(path_test),
                pattern="^#foo=bar($|(?=\r\n))",
                repl="foo=salt",
                append_if_not_found=True,
            )
        )

    # ensure, the resulting file contains the expected lines
    assert path_test.read_text() == contents.replace("#foo=bar", "foo=salt")

    backup_file = path_test.with_name(f"{path_test.name}.bak")
    assert backup_file.is_file()
    assert backup_file.read_text() == contents

    # ensure, all runs of 'file.replace' reported success
    for item in ret:
        assert item.result is True


def test_replace_issue_18841_no_changes(file, tmp_path):
    """
    Test the (mis-)behaviour of file.replace as described in #18841:

    Using file.replace in a way which shouldn't modify the file at all
    results in changed mtime of the original file and a backup file being created.

    # Case description

    The tested file contains multiple lines
    The tested file contains a line already matching the replacement (no change needed)
    The tested file's content shouldn't change at all
    The tested file's mtime shouldn't change at all
    No backup file should be created
    """
    test_name = "test_replace_issue_18841_no_changes"
    path_test = tmp_path / test_name
    contents = "#john=doe\n#foo = bar\ngoodbye world\n#foo=bar\n#blah=blub\n#some=thing"
    path_test.write_text(contents)

    # get (m|a)time of file
    fstats_orig = path_test.stat()

    # define how far we predate the file
    age = 5 * 24 * 60 * 60

    # set (m|a)time of file 5 days into the past
    os.utime(str(path_test), (fstats_orig.st_mtime - age, fstats_orig.st_atime - age))

    # Get stat again after we modified it
    fstats_orig = path_test.stat()

    ret = file.replace(
        name=str(path_test),
        pattern="^hello world$",
        repl="goodbye world",
        show_changes=True,
        flags=["IGNORECASE"],
        backup=False,
    )
    assert ret.result is True

    # get (m|a)time of file
    fstats_post = path_test.stat()

    # ensure, the file content didn't change
    assert path_test.read_text() == contents

    # ensure no backup file was created
    backup_file = path_test.with_name(f"{path_test.name}.bak")
    assert backup_file.is_file() is False

    # ensure the file's mtime didn't change
    assert fstats_post.st_mtime == fstats_orig.st_mtime


def test_replace_issue_18841_omit_backup(file, tmp_path):
    """
    Test the (mis-)behaviour of file.replace as described in #18841:

    Using file.replace in a way which shouldn't modify the file at all
    results in changed mtime of the original file and a backup file being created.

    # Case description

    The tested file contains multiple lines
    The tested file contains a line already matching the replacement (no change needed)
    The tested file's content shouldn't change at all
    The tested file's mtime shouldn't change at all
    No backup file should be created, although backup=False isn't explicitly defined
    """
    test_name = "test_replace_issue_18841_omit_backup"
    path_test = tmp_path / test_name
    contents = "#john=doe\n#foo = bar\ngoodbye world\n#foo=bar\n#blah=blub\n#some=thing"
    path_test.write_text(contents)

    # get (m|a)time of file
    fstats_orig = path_test.stat()

    # define how far we predate the file
    age = 5 * 24 * 60 * 60

    # set (m|a)time of file 5 days into the past
    os.utime(str(path_test), (fstats_orig.st_mtime - age, fstats_orig.st_atime - age))

    # Grab stat again after changing (m|a)time
    # fstats_orig = path_test.stat()

    ret = file.replace(
        name=str(path_test),
        pattern="^hello world$",
        repl="goodbye world",
        show_changes=True,
        flags=["IGNORECASE"],
    )
    assert ret.result is True

    # get (m|a)time of file
    # fstats_post = path_test.stat()

    # ensure, the file content didn't change
    assert path_test.read_text() == contents

    # ensure no backup file was created
    backup_file = path_test.with_name(f"{path_test.name}.bak")
    assert backup_file.is_file() is False

    # ensure the file's mtime didn't change
    # assert fstats_post.st_mtime == fstats_orig.st_mtime - age
    # This is commented out because before the test was migrated, while it was
    # passing, checking mtime was wrongly being done:
    #
    #    self.assertTrue(fstats_post.st_mtime, fstats_orig.st_mtime - age)
    #
    # The above is ALWAYS true. Anyway, the backup file was not created, so the
    # test is still valid and valuable


def test_file_replace_prerequired_issues_55775(modules, state_tree, tmp_path):
    """
    Test that __prerequired__ is filter from file.replace
    if __prerequired__ is not filter from file.replace an error will be raised
    """
    managed_file = tmp_path / "issue-55775.txt"
    sls_contents = f"""
    {managed_file}:
      file.managed:
        - contents:
          - foo
    file.replace:
      file.replace:
        - name: {managed_file}
        - pattern: 'foo'
        - repl: 'bar'
        - prereq:
          - test no changes
          - test changes
    test no changes:
      test.succeed_without_changes:
        - name: no changes
    test changes:
      test.succeed_with_changes:
        - name: changes
    """
    with pytest.helpers.temp_file("file-replace.sls", sls_contents, state_tree):
        ret = modules.state.sls("file-replace")
        assert not ret.failed
        for state_run in ret:
            assert state_run.result is True

    assert managed_file.exists()


def test_file_replace_check_cmd(modules, state_tree):
    """
    Test that check_cmd works for file.replace
    and those states do not run.
    """
    sls_contents = """
    replace_in_file:
      file.replace:
        - name: /tmp/test
        - pattern: hi
        - repl: "replacement text"
        - append_if_not_found: True
        - check_cmd:
          - "djasjahj"
    """
    with pytest.helpers.temp_file(
        "file-replace-check-cmd.sls", sls_contents, state_tree
    ):
        ret = modules.state.sls("file-replace-check-cmd")
        for state_run in ret:
            assert state_run.result is False
            assert state_run.comment == "check_cmd determined the state failed"


# ---------------------------------------------------------------------------
# UTF-16 encoding tests (issue #52793)
# ---------------------------------------------------------------------------


def test_replace_utf16_state(file, tmp_path):
    """
    file.replace state with encoding='utf-16' should successfully replace a
    pattern in a UTF-16 encoded file and keep the file in UTF-16 encoding.
    """
    name = tmp_path / "PSWindowsUpdate.psd1"
    _write_utf16(name, "PowerShellVersion = '2.0'\r\nModuleVersion = '1.0'\r\n")

    ret = file.replace(
        name=str(name),
        pattern=r"PowerShellVersion\s+=\s+'2\.0'",
        repl="PowerShellVersion = '3.0'",
        encoding="utf-16",
        backup=False,
    )

    assert ret.result is True
    content = _read_utf16(name)
    assert "PowerShellVersion = '3.0'" in content
    assert "PowerShellVersion = '2.0'" not in content
    assert "ModuleVersion = '1.0'" in content

    raw = name.read_bytes()
    assert raw[:2] in (b"\xff\xfe", b"\xfe\xff"), "BOM missing after replace"


def test_replace_utf16_state_idempotent(file, tmp_path):
    """
    Calling file.replace twice on a UTF-16 file should produce no changes on
    the second run (idempotency, similar to issue #18612).
    """
    name = tmp_path / "idempotent.psd1"
    _write_utf16(name, "PowerShellVersion = '2.0'\r\n")

    results = []
    for _ in range(2):
        results.append(
            file.replace(
                name=str(name),
                pattern=r"PowerShellVersion\s+=\s+'2\.0'",
                repl="PowerShellVersion = '3.0'",
                encoding="utf-16",
                backup=False,
            )
        )

    assert results[0].result is True
    assert results[1].result is True
    assert "PowerShellVersion = '3.0'" in _read_utf16(name)
    assert "PowerShellVersion = '2.0'" not in _read_utf16(name)


def test_replace_utf16_state_no_match(file, tmp_path):
    """
    file.replace state with encoding='utf-16' should report no changes when
    the pattern is not found, leaving the file byte-for-byte identical.
    """
    name = tmp_path / "no_match.psd1"
    _write_utf16(name, "PowerShellVersion = '3.0'\n")
    original_bytes = name.read_bytes()

    ret = file.replace(
        name=str(name),
        pattern=r"DoesNotExist",
        repl="something",
        encoding="utf-16",
        backup=False,
    )

    assert ret.result is True
    assert name.read_bytes() == original_bytes


def test_replace_utf16_state_append_if_not_found(file, tmp_path):
    """
    append_if_not_found=True should append content to a UTF-16 file when the
    pattern is absent, and not grow the file on subsequent runs.
    """
    name = tmp_path / "append.psd1"
    _write_utf16(name, "ModuleVersion = '1.0'\r\n")

    results = []
    for _ in range(3):
        results.append(
            file.replace(
                name=str(name),
                pattern=r"^PowerShellVersion\s*=.*$",
                repl="PowerShellVersion = '3.0'",
                append_if_not_found=True,
                encoding="utf-16",
                backup=False,
            )
        )

    for ret in results:
        assert ret.result is True

    content = _read_utf16(name)
    assert content.count("PowerShellVersion") == 1
    assert "ModuleVersion = '1.0'" in content


def test_replace_utf32_state(file, tmp_path):
    """
    file.replace state with encoding='utf-32' should successfully replace a
    pattern in a UTF-32 encoded file and keep the file in UTF-32 encoding.
    """
    name = tmp_path / "test_utf32.txt"
    name.write_text("key = old_value\n", encoding="utf-32")

    ret = file.replace(
        name=str(name),
        pattern=r"key = old_value",
        repl="key = new_value",
        encoding="utf-32",
        backup=False,
    )

    assert ret.result is True
    content = name.read_text(encoding="utf-32")
    assert "key = new_value" in content
    assert "key = old_value" not in content

    raw = name.read_bytes()
    assert raw[:4] in (
        b"\xff\xfe\x00\x00",
        b"\x00\x00\xfe\xff",
    ), "BOM missing after replace: file is no longer UTF-32"


def test_replace_utf16_execution_module(modules, tmp_path):
    """
    The file.replace execution module called directly should handle UTF-16
    files when encoding is specified.
    """
    name = tmp_path / "exec_module.psd1"
    _write_utf16(name, "PowerShellVersion = '2.0'\r\nModuleVersion = '1.0'\r\n")

    result = modules.file.replace(
        path=str(name),
        pattern=r"PowerShellVersion\s+=\s+'2\.0'",
        repl="PowerShellVersion = '3.0'",
        encoding="utf-16",
        show_changes=False,
    )

    assert result is True
    content = _read_utf16(name)
    assert "PowerShellVersion = '3.0'" in content
    assert "PowerShellVersion = '2.0'" not in content

    raw = name.read_bytes()
    assert raw[:2] in (b"\xff\xfe", b"\xfe\xff"), "BOM missing after replace"
