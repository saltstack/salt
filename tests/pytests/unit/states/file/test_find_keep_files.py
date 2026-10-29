import logging

import pytest

import salt.states.file as filestate
from tests.support.mock import patch

log = logging.getLogger(__name__)


@pytest.mark.skip_on_windows(reason="Do not run on Windows")
def test__find_keep_files_unix():
    keep = filestate._find_keep_files(
        "/test/parent_folder", ["/test/parent_folder/meh.txt"]
    )
    expected = [
        "/",
        "/test",
        "/test/parent_folder",
        "/test/parent_folder/meh.txt",
    ]
    actual = sorted(list(keep))
    assert actual == expected, actual


@pytest.mark.skip_unless_on_windows(reason="Do not run except on Windows")
def test__find_keep_files_win32():
    """
    Test _find_keep_files. The `_find_keep_files` function is only called by
    _clean_dir.
    """
    keep = filestate._find_keep_files(
        "c:\\test\\parent_folder",
        ["C:\\test\\parent_folder\\meh-1.txt", "C:\\Test\\Parent_folder\\Meh-2.txt"],
    )
    expected = [
        "c:\\",
        "c:\\test",
        "c:\\test\\parent_folder",
        "c:\\test\\parent_folder\\meh-1.txt",
        "c:\\test\\parent_folder\\meh-2.txt",
    ]
    actual = sorted(list(keep))
    assert actual == expected


@pytest.mark.skip_unless_on_windows(reason="Do not run except on Windows")
def test__clean_dir_win32():
    """
    Test _clean_dir to ensure that regardless of case, we keep all files
    requested and do not delete any. Therefore, the expected list should
    be empty for this test.
    """
    keep = filestate._clean_dir(
        "c:\\test\\parent_folder",
        [
            "C:\\test\\parent_folder\\meh-1.txt",
            "C:\\Test\\Parent_folder\\Meh-2.txt",
        ],
        exclude_pat=None,
    )
    actual = sorted(list(keep))
    expected = []
    assert actual == expected


@pytest.mark.skip_unless_on_darwin(reason="Do not run except on OS X")
def test__find_keep_files_darwin():
    """
    Test _clean_dir to ensure that regardless of case, we keep all files
    requested and do not delete any. Therefore, the expected list should
    be empty for this test.
    """
    keep = filestate._clean_dir(
        "/test/parent_folder",
        [
            "/test/folder/parent_folder/meh-1.txt",
            "/Test/folder/Parent_Folder/Meh-2.txt",
        ],
        exclude_pat=None,
    )
    actual = sorted(list(keep))
    expected = []
    assert actual == expected


def test__gen_keep_files_bare_string_requisite_53692():
    """
    A bare-string requisite ID that happens to contain the substring "file"
    must not crash _gen_keep_files. This is the file.recurse(clean=True)
    reproducer from #53692: the require list holds a plain state ID string
    (written as ``- p_files_recurse_test_recurse_one``) instead of the dict
    form ``- file: <id>``. Before the fix the "file" in comp membership test
    degraded to a substring match, then comp["file"] indexed a str with a str
    and raised ``TypeError: string indices must be integers``.
    """
    # require here mirrors a state's ``require`` requisite list as passed from
    # the file.recurse / file.directory clean handlers; the bare string is the
    # requisite ID form ``- p_files_recurse_test_recurse_one``.
    lowstate = [
        {
            "name": "/test1",
            "__id__": "p_files_recurse_test_recurse_one",
            "fun": "recurse",
        }
    ]
    with patch.object(filestate, "__lowstate__", lowstate, create=True):
        keep = filestate._gen_keep_files("/test2", ["p_files_recurse_test_recurse_one"])
    assert keep == []


def test__gen_keep_files_bare_string_requisite_61042():
    """
    Same crash as #53692 via the #61042 MCVE: a bare-string requisite ID
    ``aaa_file`` (contains "file") passed to file.recurse(clean=True) must be
    ignored, not raise TypeError.
    """
    # Bare requisite ID form ``- aaa_file`` from the #61042 reproducer.
    lowstate = [{"name": "/srv/aaa", "__id__": "aaa_file", "fun": "managed"}]
    with patch.object(filestate, "__lowstate__", lowstate, create=True):
        keep = filestate._gen_keep_files("/srv/target", ["aaa_file"])
    assert keep == []


def test__gen_keep_files_dict_requisite_not_regressed_53692():
    """
    Inverse / must-not-regress for #53692: a normal dict requisite
    ``{"file": <id>}`` that matches a low state must still contribute its file
    to the keep list. Passes with and without the fix, proving the isinstance
    guard does not disturb the supported dict requisite path.
    """
    lowstate = [{"name": "/nonexistent/kept", "__id__": "kept_id", "fun": "managed"}]
    with patch.object(filestate, "__lowstate__", lowstate, create=True):
        with patch("os.path.isdir", return_value=False):
            keep = filestate._gen_keep_files("/parent", [{"file": "kept_id"}])
    assert keep == ["/nonexistent/kept"]


def test__gen_keep_files_dict_requisite_not_regressed_61042():
    """
    Inverse / must-not-regress for #61042: the dict requisite form
    ``{"file": "bbb"}`` still retains the required file. Passes before and
    after the fix.
    """
    lowstate = [{"name": "/nonexistent/bbb", "__id__": "bbb", "fun": "managed"}]
    with patch.object(filestate, "__lowstate__", lowstate, create=True):
        with patch("os.path.isdir", return_value=False):
            keep = filestate._gen_keep_files("/parent", [{"file": "bbb"}])
    assert keep == ["/nonexistent/bbb"]


def test__gen_keep_files_bare_string_without_file_ignored():
    """
    Peripheral coverage: a bare-string requisite that does NOT contain the
    substring "file" was, and remains, silently ignored by _gen_keep_files
    (it never matches the dict-key check). This documents that the fix only
    changes the crashing substring-match case and preserves the pre-existing
    drop of bare-string requisites. Passes with and without the fix.
    """
    lowstate = [{"name": "/test1", "__id__": "aaa", "fun": "managed"}]
    with patch.object(filestate, "__lowstate__", lowstate, create=True):
        keep = filestate._gen_keep_files("/test2", ["aaa"])
    assert keep == []
