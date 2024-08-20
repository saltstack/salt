import logging
import os
import shutil
import textwrap

import pytest

import salt.config
import salt.loader
import salt.modules.cmdmod as cmdmod
import salt.modules.config as configmod
import salt.modules.file as filemod
import salt.utils.data
import salt.utils.files
import salt.utils.platform
import salt.utils.stringutils
from salt.exceptions import SaltInvocationError
from tests.support.mock import MagicMock

log = logging.getLogger(__name__)

pytestmark = pytest.mark.skipif(
    salt.utils.platform.is_windows(), reason="grep not supported on Windows"
)


@pytest.fixture
def configure_loader_modules():
    return {
        filemod: {
            "__salt__": {
                "config.manage_mode": configmod.manage_mode,
                "cmd.run": cmdmod.run,
                "cmd.run_all": cmdmod.run_all,
            },
            "__opts__": {
                "test": False,
                "file_roots": {"base": "tmp"},
                "pillar_roots": {"base": "tmp"},
                "cachedir": "tmp",
                "grains": {},
            },
            "__grains__": {"kernel": "Linux"},
            "__utils__": {
                "files.is_text": MagicMock(return_value=True),
                "stringutils.get_diff": salt.utils.stringutils.get_diff,
            },
        }
    }


@pytest.fixture
def multiline_string():
    multiline_string = textwrap.dedent(
        """\
        Lorem ipsum dolor sit amet, consectetur
        adipiscing elit. Nam rhoncus enim ac
        bibendum vulputate.
        """
    )

    multiline_string = os.linesep.join(multiline_string.splitlines())

    return multiline_string


@pytest.fixture
def multiline_file(tmp_path, multiline_string):
    multiline_file = str(tmp_path / "multiline-file.txt")

    with salt.utils.files.fopen(multiline_file, "w+") as file_handle:
        file_handle.write(multiline_string)

    yield multiline_file
    shutil.rmtree(str(tmp_path))


def test_grep_query_exists(multiline_file):
    result = filemod.grep(multiline_file, "Lorem ipsum")

    assert result, None
    assert result["retcode"] == 0
    assert result["stdout"] == "Lorem ipsum dolor sit amet, consectetur"
    assert result["stderr"] == ""


def test_grep_query_not_exists(multiline_file):
    result = filemod.grep(multiline_file, "Lorem Lorem")

    assert result["retcode"] == 1
    assert result["stdout"] == ""
    assert result["stderr"] == ""


def test_grep_query_exists_with_opt(multiline_file):
    result = filemod.grep(multiline_file, "Lorem ipsum", "-i")

    assert result, None
    assert result["retcode"] == 0
    assert result["stdout"] == "Lorem ipsum dolor sit amet, consectetur"
    assert result["stderr"] == ""


def test_grep_query_not_exists_opt(multiline_file, multiline_string):
    result = filemod.grep(multiline_file, "Lorem Lorem", "-v")

    assert result["retcode"] == 0
    assert result["stdout"] == multiline_string
    assert result["stderr"] == ""


def test_grep_query_too_many_opts(multiline_file):
    with pytest.raises(
        SaltInvocationError, match="^Passing multiple command line arg"
    ) as cm:
        result = filemod.grep(multiline_file, "Lorem Lorem", "-i -b2")


def test_grep_query_exists_wildcard(multiline_file):
    _file = f"{multiline_file}*"
    result = filemod.grep(_file, "Lorem ipsum")

    assert result, None
    assert result["retcode"] == 0
    assert result["stdout"] == "Lorem ipsum dolor sit amet, consectetur"
    assert result["stderr"] == ""


def test_grep_file_not_exists_wildcard(multiline_file):
    _file = f"{multiline_file}-junk*"
    result = filemod.grep(_file, "Lorem ipsum")

    assert result, None
    assert not result["retcode"] == 0
    assert not result["stdout"] == "Lorem ipsum dolor sit amet, consectetur"
    _expected_stderr = "grep: {}-junk*: No such file or directory".format(
        multiline_file
    )
    assert result["stderr"] == _expected_stderr
