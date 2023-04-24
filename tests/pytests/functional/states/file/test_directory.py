import os

import pytest

import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.win_functions

pytestmark = [
    pytest.mark.windows_whitelisted,
]

IS_WINDOWS = salt.utils.platform.is_windows()


@pytest.mark.parametrize("test", [False, True])
def test_directory(file, tmp_path, test):
    """
    file.directory
    """
    name = tmp_path / "a_new_dir"
    ret = file.directory(name=str(name), test=test)
    if test is True:
        assert ret.result is None
        assert not name.is_dir()
    else:
        assert ret.result is True
        assert name.is_dir()


def test_directory_symlink_dry_run(file, tmp_path):
    """
    Ensure that symlinks are followed when file.directory is run with
    test=True
    """
    if IS_WINDOWS and not os.environ.get("GITHUB_ACTIONS_PIPELINE"):
        pytest.xfail(
            "This test fails when running from Jenkins but not on the GitHub "
            "Actions Pipeline"
        )
    tmp_dir = tmp_path / "pgdata"
    sym_dir = tmp_path / "pg_data"

    tmp_dir.mkdir(0o0700)
    sym_dir.symlink_to(tmp_dir, target_is_directory=IS_WINDOWS)

    if IS_WINDOWS:
        extra_kwds = {
            "win_owner": salt.utils.win_functions.get_current_user(with_domain=False),
        }
    else:
        extra_kwds = {
            "mode": 700,
        }

    ret = file.directory(
        test=True, name=str(sym_dir), follow_symlinks=True, **extra_kwds
    )
    assert ret.result is True


@pytest.mark.skip_if_not_root
@pytest.mark.skip_on_windows(reason="Windows does not report any file modes. Skipping.")
def test_directory_max_depth(file, tmp_path):
    """
    file.directory
    Test the max_depth option by iteratively increasing the depth and
    checking that no changes deeper than max_depth have been attempted
    """

    def _get_oct_mode(name):
        """
        Return a string octal representation of the permissions for name
        """
        return salt.utils.files.normalize_mode(oct(name.stat().st_mode & 0o777))

    top = tmp_path / "top_dir"
    sub = top / "sub_dir"
    subsub = sub / "sub_sub_dir"
    dirs = [top, sub, subsub]

    initial_mode = "0111"
    changed_mode = "0555"

    if salt.utils.platform.is_photonos():
        initial_modes = {
            0: {sub: "0750", subsub: "0110"},
            1: {sub: "0110", subsub: "0110"},
            2: {sub: "0110", subsub: "0110"},
        }
    else:
        initial_modes = {
            0: {sub: "0755", subsub: "0111"},
            1: {sub: "0111", subsub: "0111"},
            2: {sub: "0111", subsub: "0111"},
        }

    subsub.mkdir(mode=int(initial_mode, 8), exist_ok=True, parents=True)

    for depth in range(3):
        ret = file.directory(
            name=str(top),
            max_depth=depth,
            dir_mode=changed_mode,
            recurse=["mode"],
        )
        assert ret.result is True
        for changed_dir in dirs[0 : depth + 1]:
            assert changed_mode == _get_oct_mode(changed_dir)
        for untouched_dir in dirs[depth + 1 :]:
            _mode = initial_modes[depth][untouched_dir]
            assert _mode == _get_oct_mode(untouched_dir)


def test_directory_clean(file, tmp_path):
    """
    file.directory with clean=True
    """
    name = tmp_path / "directory_clean_dir"
    name.mkdir()

    strayfile = name / "strayfile"
    strayfile.touch()

    straydir = name / "straydir"
    straydir.mkdir()

    straydir.joinpath("strayfile2").touch()

    ret = file.directory(name=str(name), clean=True)
    assert ret.result is True
    assert strayfile.exists() is False
    assert straydir.is_dir() is False
    assert name.is_dir()


def test_directory_is_idempotent(file, tmp_path):
    """
    Ensure the file.directory state produces no changes when rerun.
    """
    name = tmp_path / "a_dir_twice"

    extra_kwds = {}
    if IS_WINDOWS:
        extra_kwds["win_owner"] = salt.utils.win_functions.get_current_user(
            with_domain=True
        )

    ret = file.directory(name=str(name), **extra_kwds)
    assert ret.result is True
    assert ret.changes

    ret = file.directory(name=str(name), **extra_kwds)
    assert ret.result is True
    assert not ret.changes


@pytest.mark.parametrize("test", [False, True])
def test_directory_clean_exclude(file, tmp_path, test):
    """
    file.directory with clean=True and exclude_pat set

    Skipped on windows when test=True because clean and exclude_pat not supported
    by salt.sates.file._check_directory_win
    """
    if test is True and IS_WINDOWS:
        pytest.skip("Skipped on windows")

    name = tmp_path / "directory_clean_dir"
    name.mkdir()

    strayfile = name / "strayfile"
    strayfile.touch()

    straydir = name / "straydir"
    straydir.mkdir()

    strayfile2 = straydir / "strayfile2"
    strayfile2.touch()

    keepfile = straydir / "keepfile"
    keepfile.touch()

    exclude_pat = "E@^straydir(|/keepfile)$"
    if IS_WINDOWS:
        exclude_pat = r"E@^straydir(|\\keepfile)$"

    ret = file.directory(name=str(name), clean=True, exclude_pat=exclude_pat, test=test)
    if test is True:
        assert ret.result is None
        assert strayfile.exists()
        assert strayfile2.exists()
        assert keepfile.exists()
        assert str(strayfile) in ret.comment
        assert str(strayfile2) in ret.comment
        assert str(keepfile) not in ret.comment
    else:
        assert ret.result is True
        assert strayfile.exists() is False
        assert strayfile2.exists() is False
        assert keepfile.exists()


def test_directory_clean_require_in(modules, tmp_path, state_tree):
    """
    file.directory test with clean=True and require_in file
    """
    name = tmp_path / "a-directory"
    name.mkdir()
    good_file = name / "good-file"
    wrong_file = name / "wrong-file"
    wrong_file.write_text("foo")

    sls_contents = """
    some_dir:
      file.directory:
        - name: {name}
        - clean: true

    {good_file}:
      file.managed:
        - require_in:
          - file: some_dir
    """.format(
        name=name, good_file=good_file
    )

    with pytest.helpers.temp_file("clean-require-in.sls", sls_contents, state_tree):
        ret = modules.state.sls("clean-require-in")
        for state_run in ret:
            assert state_run.result is True

    assert good_file.exists()
    assert wrong_file.exists() is False


def test_directory_clean_require_in_with_id(modules, tmp_path, state_tree):
    """
    file.directory test with clean=True and require_in file with an ID
    different from the file name
    """
    name = tmp_path / "a-directory"
    name.mkdir()
    good_file = name / "good-file"
    wrong_file = name / "wrong-file"
    wrong_file.write_text("foo")

    sls_contents = f"""
    some_dir:
      file.directory:
        - name: {name}
        - clean: true

    some_file:
      file.managed:
        - name: {good_file}
        - require_in:
          - file: some_dir
    """

    with pytest.helpers.temp_file("clean-require-in.sls", sls_contents, state_tree):
        ret = modules.state.sls("clean-require-in")
        for state_run in ret:
            assert state_run.result is True

    assert good_file.exists()
    assert wrong_file.exists() is False


# @pytest.mark.skip_on_darwin(reaon="WAR ROOM TEMPORARY SKIP, Test is flaky on macosx")
def test_directory_clean_require_with_name(modules, tmp_path, state_tree):
    """
    file.directory test with clean=True and require with a file state
    relatively to the state's name, not its ID.
    """
    name = tmp_path / "a-directory"
    name.mkdir()
    good_file = name / "good-file"
    wrong_file = name / "wrong-file"
    wrong_file.write_text("foo")

    sls_contents = f"""
    some_dir:
      file.directory:
        - name: {name}
        - clean: true
        - require:
            # This requirement refers to the name of the following
            # state, not its ID.
            - file: {good_file}

    some_file:
      file.managed:
        - name: {good_file}
    """

    with pytest.helpers.temp_file("clean-require.sls", sls_contents, state_tree):
        ret = modules.state.sls("clean-require")
        for state_run in ret:
            assert state_run.result is True

    assert good_file.exists()
    assert wrong_file.exists() is False


def test_directory_broken_symlink(file, tmp_path):
    """
    Ensure that file.directory works even if a directory
    contains broken symbolic link
    """
    tmp_dir = tmp_path / "foo"
    tmp_dir.mkdir(0o700)
    null_file = tmp_dir / "null"
    broken_link = tmp_dir / "broken"
    broken_link.symlink_to(null_file)

    if IS_WINDOWS:
        extra_kwds = {
            "follow_symlinks": True,
            "win_owner": salt.utils.win_functions.get_current_user(with_domain=False),
        }
    else:
        extra_kwds = {
            "file_mode": 644,
            "dir_mode": 755,
        }
    ret = file.directory(name=str(tmp_dir), recurse=["mode"], **extra_kwds)
    assert ret.result is True


def _check_skip(grains):
    if grains["os"] == "MacOS":
        return True
    return False


@pytest.mark.skip_initial_gh_actions_failure(skip=_check_skip)
@pytest.mark.skip_if_not_root
@pytest.mark.skip_on_windows(
    reason="Windows fails to enforce group ownership, and test was previously skipped on windows"
)
@pytest.mark.parametrize("follow_symlinks", (True, False))
def test_issue_12209_follow_symlinks(
    file, modules, tmp_path, state_file_account, follow_symlinks
):
    """
    Ensure that symlinks are properly chowned when recursing (following
    symlinks)
    """
    # Make the directories for this test
    onedir = tmp_path / "one"
    onedir.mkdir()
    twodir = tmp_path / "two"
    twodir.symlink_to(onedir, target_is_directory=IS_WINDOWS)

    # Run the state
    ret = file.directory(
        name=str(tmp_path),
        follow_symlinks=follow_symlinks,
        user=state_file_account.username,
        group=state_file_account.group.name,
        recurse=["user", "group"],
    )
    assert ret.result is True

    if follow_symlinks:
        # Double-check, in case state mis-reported a True result. Since we are
        # following symlinks, we expect twodir to still be owned by root, but
        # onedir should be owned by the 'state_file_account.username' user.
        one_user_check = modules.file.get_user(str(onedir))
        assert one_user_check == state_file_account.username
        two_user_check = modules.file.get_user(str(twodir), follow_symlinks=False)
        assert two_user_check == "root"
        one_group_check = modules.file.get_group(str(onedir))
        assert one_group_check == state_file_account.group.name
        if salt.utils.path.which("id"):
            if "user.primary_group" in modules:
                # Which is not the case for our FreeBSD VM on our CI setup
                root_group = modules.user.primary_group("root")
                two_group_check = modules.file.get_group(
                    str(twodir), follow_symlinks=False
                )
                assert two_group_check == root_group
    else:
        # Double-check, in case state mis-reported a True result. Since we
        # are not following symlinks, we expect twodir to now be owned by
        # the 'state_file_account.username' user, just like onedir.
        one_user_check = modules.file.get_user(str(onedir))
        assert one_user_check == state_file_account.username
        two_user_check = modules.file.get_user(str(twodir), follow_symlinks=False)
        assert two_user_check == state_file_account.username
        one_group_check = modules.file.get_group(str(onedir))
        assert one_group_check == state_file_account.group.name
        two_group_check = modules.file.get_group(str(twodir), follow_symlinks=False)
        assert two_group_check == state_file_account.group.name
