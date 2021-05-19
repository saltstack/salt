import logging

import pytest
import salt.exceptions
import salt.modules.slsutil as slsutil
from tests.support.mock import MagicMock

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules(master_dirs, master_files):
    return {
        slsutil: {
            "__salt__": {
                "cp.list_master": MagicMock(return_value=master_files),
                "cp.list_master_dirs": MagicMock(return_value=master_dirs),
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


def test_banner():
    """
    Test banner function
    """
    check_banner()
    check_banner(width=81)
    check_banner(width=20)
    check_banner(commentchar="//", borderchar="-")
    check_banner(title="title here", text="text here")
    check_banner(commentchar=" *")


def check_banner(
    width=72,
    commentchar="#",
    borderchar="#",
    blockstart=None,
    blockend=None,
    title=None,
    text=None,
    newline=True,
):

    result = slsutil.banner(
        width=width,
        commentchar=commentchar,
        borderchar=borderchar,
        blockstart=blockstart,
        blockend=blockend,
        title=title,
        text=text,
        newline=newline,
    ).splitlines()
    for line in result:
        assert len(line) == width
        assert line.startswith(commentchar)
        assert line.endswith(commentchar.strip())


def test_boolstr():
    """
    Test boolstr function
    """
    assert "yes" == slsutil.boolstr(True, true="yes", false="no")
    assert "no" == slsutil.boolstr(False, true="yes", false="no")


def test_file_exists():
    """
    Test file_exists function
    """
    assert slsutil.file_exists("red/init.sls")
    assert not slsutil.file_exists("green/init.sls")


def test_dir_exists():
    """
    Test dir_exists function
    """
    assert slsutil.dir_exists("red")
    assert not slsutil.dir_exists("green")


def test_path_exists():
    """
    Test path_exists function
    """
    assert slsutil.path_exists("red")
    assert not slsutil.path_exists("green")
    assert slsutil.path_exists("red/init.sls")
    assert not slsutil.path_exists("green/init.sls")


def test_findup():
    """
    Test findup function
    """
    assert "red/init.sls" == slsutil.findup("red/files", "init.sls")
    assert "top.sls" == slsutil.findup("red/files", ["top.sls"])
    assert "top.sls" == slsutil.findup("", "top.sls")
    assert "top.sls" == slsutil.findup(None, "top.sls")
    assert "red/init.sls" == slsutil.findup("red/files", ["top.sls", "init.sls"])

    with pytest.raises(salt.exceptions.CommandExecutionError):
        slsutil.findup("red/files", "notfound")

    with pytest.raises(salt.exceptions.CommandExecutionError):
        slsutil.findup("red", "default.conf")
