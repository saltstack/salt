import logging
import os
import shutil

import pytest

import salt.config
import salt.loader
import salt.modules.cmdmod as cmdmod
import salt.modules.file as filemod
import salt.utils.data
import salt.utils.files
import salt.utils.platform
import salt.utils.stringutils
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)

pytestmark = pytest.mark.skipif(
    salt.modules.selinux.getenforce() != "Enforcing",
    reason="Skip if selinux not enabled",
)


@pytest.fixture
def configure_loader_modules():
    return {
        filemod: {
            "__salt__": {
                "cmd.run": cmdmod.run,
                "cmd.run_all": cmdmod.run_all,
                "cmd.retcode": cmdmod.retcode,
                "selinux.fcontext_add_policy": MagicMock(
                    return_value={"retcode": 0, "stdout": ""}
                ),
            },
            "__opts__": {"test": False},
        }
    }


@pytest.fixture
def subdir(tmp_path):
    subdir = tmp_path / "file-selinux-test-dir"
    subdir.mkdir()
    yield subdir
    shutil.rmtree(str(subdir))


@pytest.fixture
def tfile1(subdir):
    filename = str(subdir / "tfile1")
    with salt.utils.files.fopen(filename, "w+"):
        pass
    yield filename
    os.remove(filename)


@pytest.fixture
def tfile2(subdir):
    filename = str(subdir / "tfile2")
    with salt.utils.files.fopen(filename, "w+"):
        pass
    yield filename
    os.remove(filename)


@pytest.fixture
def tfile3(subdir):
    filename = str(subdir / "tfile3")
    with salt.utils.files.fopen(filename, "w+"):
        pass
    yield filename
    os.remove(filename)


def test_selinux_getcontext(tfile1):
    """
    Test get selinux context
    Assumes default selinux attributes on temporary files
    """
    result = filemod.get_selinux_context(tfile1)
    assert result == "unconfined_u:object_r:user_tmp_t:s0"


def test_selinux_setcontext(tfile2):
    """
    Test set selinux context
    Assumes default selinux attributes on temporary files
    """
    result = filemod.set_selinux_context(tfile2, user="system_u")
    assert result == "system_u:object_r:user_tmp_t:s0"


def test_selinux_setcontext_persist(tfile2):
    """
    Test set selinux context with persist=True
    Assumes default selinux attributes on temporary files
    """
    result = filemod.set_selinux_context(tfile2, user="system_u", persist=True)
    assert result == "system_u:object_r:user_tmp_t:s0"


def test_selinux_setcontext_persist_change(tfile2):
    """
    Test set selinux context with persist=True
    Assumes default selinux attributes on temporary files
    """
    result = filemod.set_selinux_context(tfile2, user="system_u", persist=True)
    assert result == "system_u:object_r:user_tmp_t:s0"

    result = filemod.set_selinux_context(
        tfile2, user="unconfined_u", type="net_conf_t", persist=True
    )
    assert result == "unconfined_u:object_r:net_conf_t:s0"


def test_file_check_perms(tfile3):
    expected_result = (
        {
            "comment": f"The file {tfile3} is set to be changed",
            "changes": {
                "selinux": {"New": "Type: lost_found_t", "Old": "Type: user_tmp_t"},
                "mode": "0664",
            },
            "name": tfile3,
            "result": True,
        },
        {"cmode": "0664", "luser": "root", "lmode": "0644", "lgroup": "root"},
    )

    # Disable lsattr calls
    with patch("salt.utils.path.which") as m_which:
        m_which.return_value = None
        result = filemod.check_perms(
            tfile3,
            {},
            "root",
            "root",
            664,
            seuser=None,
            serole=None,
            setype="lost_found_t",
            serange=None,
        )
        assert result == expected_result
