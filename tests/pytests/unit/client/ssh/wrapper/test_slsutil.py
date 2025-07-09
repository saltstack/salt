import contextlib
import logging

import pytest

import salt.client.ssh.wrapper.slsutil as slsutil
from salt.exceptions import CommandExecutionError, SaltInvocationError
from tests.support.mock import MagicMock

log = logging.getLogger(__name__)


# --- These tests are adapted from tests.pytests.unit.utils.slsutil


@pytest.fixture
def configure_loader_modules(master_dirs, master_files):
    return {
        slsutil: {
            "__salt__": {
                "cp.list_master": MagicMock(return_value=master_files),
                "cp.list_master_dirs": MagicMock(return_value=master_dirs),
            },
            "__opts__": {
                "renderer": "jinja|yaml",
                "renderer_blacklist": [],
                "renderer_whitelist": [],
            },
        }
    }


@pytest.fixture
def master_dirs():
    return ["red", "red/files", "blue", "blue/files"]


@pytest.fixture
def master_files():
    return [
        "top.sls",
        "red/init.sls",
        "red/files/default.conf",
        "blue/init.sls",
        "blue/files/default.conf",
    ]


@pytest.mark.parametrize("inpt,expected", ((True, "yes"), (False, "no")))
def test_boolstr(inpt, expected):
    assert slsutil.boolstr(inpt, true="yes", false="no") == expected


@pytest.mark.parametrize(
    "inpt,expected", (("red/init.sls", True), ("green/init.sls", False))
)
def test_file_exists(inpt, expected):
    assert slsutil.file_exists(inpt) is expected


@pytest.mark.parametrize("inpt,expected", (("red", True), ("green", False)))
def test_dir_exists(inpt, expected):
    assert slsutil.dir_exists(inpt) is expected


@pytest.mark.parametrize(
    "inpt,expected",
    (
        ("red", True),
        ("green", False),
        ("red/init.sls", True),
        ("green/init.sls", False),
    ),
)
def test_path_exists(inpt, expected):
    assert slsutil.path_exists(inpt) is expected


@pytest.mark.parametrize(
    "inpt,expected,raises",
    [
        (("red/files", "init.sls"), "red/init.sls", None),
        (("red/files", ["top.sls"]), "top.sls", None),
        (("", "top.sls"), "top.sls", None),
        ((None, "top.sls"), "top.sls", None),
        (("red/files", ["top.sls", "init.sls"]), "red/init.sls", None),
        (
            ("red/files", "notfound"),
            None,
            pytest.raises(
                CommandExecutionError, match=r"File pattern\(s\) not found.*"
            ),
        ),
        (
            ("red", "default.conf"),
            None,
            pytest.raises(
                CommandExecutionError, match=r"File pattern\(s\) not found.*"
            ),
        ),
        (
            ("green", "notfound"),
            None,
            pytest.raises(SaltInvocationError, match="Starting path not found.*"),
        ),
        (
            ("red", 1234),
            None,
            pytest.raises(
                SaltInvocationError, match=".*must be a string or list of strings.*"
            ),
        ),
    ],
)
def test_findup(inpt, expected, raises):
    if raises is None:
        raises = contextlib.nullcontext()
    with raises:
        res = slsutil.findup(*inpt)
        assert res == expected


@pytest.mark.parametrize(
    "a,b,merge_lists,expected",
    [
        (
            {"foo": {"bar": "baz", "hi": "there", "some": ["list"]}},
            {"foo": {"baz": "quux", "bar": "hi", "some": ["other_list"]}},
            False,
            {
                "foo": {
                    "baz": "quux",
                    "bar": "hi",
                    "hi": "there",
                    "some": ["other_list"],
                }
            },
        ),
        (
            {"foo": {"bar": "baz", "hi": "there", "some": ["list"]}},
            {"foo": {"baz": "quux", "bar": "hi", "some": ["other_list"]}},
            True,
            {
                "foo": {
                    "baz": "quux",
                    "bar": "hi",
                    "hi": "there",
                    "some": ["list", "other_list"],
                }
            },
        ),
    ],
)
@pytest.mark.parametrize("func", ("update", "merge", "merge_all"))
def test_update_merge(a, b, merge_lists, expected, func):
    arg = (a, b)
    if func == "merge_all":
        arg = ([a, b],)
    res = getattr(slsutil, func)(*arg, merge_lists=merge_lists)
    assert res == expected
    assert (a is res) is (func == "update")


def test_renderer_requires_either_path_or_string():
    with pytest.raises(SaltInvocationError, match=".*either path or string.*"):
        slsutil.renderer()
