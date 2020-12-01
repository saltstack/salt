import pytest
import salt.modules.cp as cp
from tests.support.mock import call, patch

# pylint: disable=comparison-to-True-should-be-if-cond-is-True-or-if-cond,singleton-comparison


@pytest.fixture(autouse=True)
def setup_loader():
    setup_loader_modules = {cp: {}}
    with pytest.helpers.loader_mock(setup_loader_modules) as loader_mock:
        yield loader_mock


@pytest.mark.parametrize(
    # TODO: Are there any other traversal attack strings? -W. Werner, 2020-12-01
    "bad_path",
    [
        "foo/bar/..",
        "/foo/bar/../",
        "/foo/bar/..",
        "/../foo/bar/",
        "../",
        "..",
        "/foo/bar/../bang",
    ],
)
def test_push_dir_should_fail_with_relative_paths(bad_path):
    result = cp.push_dir(bad_path)
    assert result == False


def test_when_path_is_a_file_it_should_get_pushed():
    expected_result = object()
    patch_isfile = patch("os.path.isfile", return_value=True, autospec=True)
    patch_push = patch(
        "salt.modules.cp.push", autospec=True, return_value=expected_result
    )
    with patch_isfile, patch_push as fake_push:
        result = cp.push_dir("/fnord")

        assert result is expected_result
        fake_push.assert_called_with("/fnord", upload_path=None)


def test_when_there_are_no_files_then_push_dir_should_return_False():
    patch_isfile = patch("os.path.isfile", return_value=False, autospec=True)
    patch_salt_walk = patch("salt.utils.path.os_walk", return_value=[], autospec=True)
    with patch_isfile:
        result = cp.push_dir("/fnord")

        assert result == False


@pytest.mark.parametrize(
    "paths", [[("fnordroot", "fnord", ("foo.txt", "bar.txt"))]],
)
def test_when_glob_is_None_and_there_are_paths_then_result_should_be_True(paths):
    patch_isfile = patch("os.path.isfile", return_value=False, autospec=True)
    patch_salt_walk = patch(
        "salt.utils.path.os_walk", return_value=paths, autospec=True
    )
    patch_push = patch("salt.modules.cp.push", autospec=True, return_value=True)
    with patch_isfile, patch_salt_walk, patch_push:
        result = cp.push_dir("/fnord")

        assert result == True


def test_when_glob_is_None_and_there_are_paths_then_all_paths_should_be_pushed():
    paths = [("fnordroot", "fnord", ("foo.txt", "bar.txt"))]
    patch_isfile = patch("os.path.isfile", return_value=False, autospec=True)
    patch_salt_walk = patch(
        "salt.utils.path.os_walk", return_value=paths, autospec=True
    )
    patch_push = patch("salt.modules.cp.push", autospec=True, return_value=42)
    with patch_isfile, patch_salt_walk, patch_push as fake_push:
        cp.push_dir("/fnord")

        fake_push.assert_any_call("fnordroot/foo.txt", upload_path=None)
        fake_push.assert_any_call("fnordroot/bar.txt", upload_path=None)
        assert len(fake_push.mock_calls) == 2


def test_when_upload_path_is_provided_then_the_correct_path_should_be_pushed():
    paths = [
        (
            ("/pretendroot", "fnord", ("foo.txt", "bar.txt")),
            ("/pretendroot/subpath", "fnord", ("foo.txt", "bar.txt")),
        )
    ]
    patch_isfile = patch("os.path.isfile", return_value=False, autospec=True)
    patch_salt_walk = patch("salt.utils.path.os_walk", side_effect=paths, autospec=True)
    patch_push = patch("salt.modules.cp.push", autospec=True, return_value=42)
    with patch_isfile, patch_salt_walk, patch_push as fake_push:
        cp.push_dir("/pretendroot", upload_path="/foo/baz/bang")

        fake_push.assert_has_calls(
            [
                call("/pretendroot/foo.txt", upload_path="/foo/baz/bang/foo.txt"),
                call("/pretendroot/bar.txt", upload_path="/foo/baz/bang/bar.txt"),
                call(
                    "/pretendroot/subpath/foo.txt",
                    upload_path="/foo/baz/bang/subpath/foo.txt",
                ),
                call(
                    "/pretendroot/subpath/bar.txt",
                    upload_path="/foo/baz/bang/subpath/bar.txt",
                ),
            ]
        )


def test_when_glob_has_trailing_star_then_then_all_matching_paths_should_be_pushed():
    paths = [("fnordroot", "fnord", ("foo.txt", "bar.txt", ".foo.txt", "foo-bang.txt"))]
    patch_isfile = patch("os.path.isfile", return_value=False, autospec=True)
    patch_salt_walk = patch(
        "salt.utils.path.os_walk", return_value=paths, autospec=True
    )
    patch_push = patch("salt.modules.cp.push", autospec=True, return_value=42)
    with patch_isfile, patch_salt_walk, patch_push as fake_push:
        cp.push_dir("/fnord", glob="foo*")

        assert len(fake_push.mock_calls) == 2
        fake_push.assert_any_call("fnordroot/foo.txt", upload_path=None)
        fake_push.assert_any_call("fnordroot/foo-bang.txt", upload_path=None)


def test_when_glob_has_leading_star_then_then_all_matching_paths_should_be_pushed():
    paths = [("fnordroot", "fnord", ("foo.txt", "bar.txt", ".foo.txt", "foo-bang.txt"))]
    patch_isfile = patch("os.path.isfile", return_value=False, autospec=True)
    patch_salt_walk = patch(
        "salt.utils.path.os_walk", return_value=paths, autospec=True
    )
    patch_push = patch("salt.modules.cp.push", autospec=True, return_value=42)
    with patch_isfile, patch_salt_walk, patch_push as fake_push:
        cp.push_dir("/fnord", glob="*foo.txt")

        assert len(fake_push.mock_calls) == 2
        fake_push.assert_any_call("fnordroot/foo.txt", upload_path=None)
        fake_push.assert_any_call("fnordroot/.foo.txt", upload_path=None)


def test_when_push_fails_then_result_should_be_False():
    paths = [("fnordroot", "fnord", ("foo.txt", "bar.txt", ".foo.txt", "foo-bang.txt"))]
    patch_isfile = patch("os.path.isfile", return_value=False, autospec=True)
    patch_salt_walk = patch(
        "salt.utils.path.os_walk", return_value=paths, autospec=True
    )
    patch_push = patch(
        "salt.modules.cp.push", autospec=True, side_effect=[True, False],
    )
    with patch_isfile, patch_salt_walk, patch_push as fake_push:
        result = cp.push_dir("/fnord", glob="*foo.txt")

        assert result == False
        assert len(fake_push.mock_calls) == 2
        fake_push.assert_any_call("fnordroot/foo.txt", upload_path=None)
        fake_push.assert_any_call("fnordroot/.foo.txt", upload_path=None)


## TODO: angeloudy's desired scenario -W. Werner, 2020-12-01
# salt-call cp.push_dir /a/b glob='**/b/*.txt', while still supports the old matching
#
# salt-call cp.push_dir /a/b glob='*.txt'
#
# In my case, I have many exported files(with extension *.groovy)from my application inside FreeBSD Jails.
#
# /jails/jail1/usr/local/myapp/export
# /jails/jail2/usr/local/myapp/export
# /jails/jail3/usr/local/myapp/export
# /jails/jail3/usr/local/myapp/export
# I wanted to do
# salt minion1 cp.push_dir /jails glob='**/export/*.groovy',

# Test that:

# .foo.bar
# foo.bar

# are handled as expected

# foo*
# *.txt
# foo-*-bar.txt
# */foo/bar.*
# */foo/*.bar
