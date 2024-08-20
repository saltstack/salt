"""
    TestCase for the salt.modules.vagrant module.
"""

import pytest

import salt.exceptions
import salt.modules.vagrant as vagrant
import salt.utils.platform
from tests.support.mock import MagicMock, patch


@pytest.fixture
def local_opts(tmp_path):
    return {
        "extension_modules": "",
        "vagrant_sdb_data": {
            "driver": "sqlite3",
            "database": str(tmp_path / "test_vagrant.sqlite"),
            "table": "sdb",
            "create_table": True,
        },
    }


@pytest.fixture
def configure_loader_modules(local_opts):
    return {vagrant: {"__opts__": local_opts}}


def test_vagrant_get_vm_info_not_found():
    mock_sdb = MagicMock(return_value=None)
    with patch.dict(vagrant.__utils__, {"sdb.sdb_get": mock_sdb}):
        with pytest.raises(salt.exceptions.SaltInvocationError):
            vagrant.get_vm_info("thisNameDoesNotExist")


def test_vagrant_init_positional(local_opts, tmp_path):
    path_nowhere = str(tmp_path / "tmp" / "nowhere")
    mock_sdb = MagicMock(return_value=None)
    with patch.dict(vagrant.__utils__, {"sdb.sdb_set": mock_sdb}):
        resp = vagrant.init(
            "test1",
            path_nowhere,
            "onetest",
            "nobody",
            False,
            "french",
            {"different": "very"},
        )
        assert resp.startswith("Name test1 defined")
        expected = dict(
            name="test1",
            cwd=path_nowhere,
            machine="onetest",
            runas="nobody",
            vagrant_provider="french",
            different="very",
        )
        mock_sdb.assert_called_with(
            f"sdb://vagrant_sdb_data/onetest?{path_nowhere}",
            "test1",
            local_opts,
        )
        mock_sdb.assert_any_call("sdb://vagrant_sdb_data/test1", expected, local_opts)


def test_vagrant_get_vm_info():
    testdict = {"testone": "one", "machine": "two"}
    mock_sdb = MagicMock(return_value=testdict)
    with patch.dict(vagrant.__utils__, {"sdb.sdb_get": mock_sdb}):
        resp = vagrant.get_vm_info("test1")
        assert resp == testdict


def test_vagrant_init_dict(local_opts):
    testdict = dict(
        cwd="/tmp/anywhere",
        machine="twotest",
        runas="somebody",
        vagrant_provider="english",
    )
    expected = testdict.copy()
    expected["name"] = "test2"
    mock_sdb = MagicMock(return_value=None)
    with patch.dict(vagrant.__utils__, {"sdb.sdb_set": mock_sdb}):
        vagrant.init("test2", vm=testdict)
        mock_sdb.assert_any_call("sdb://vagrant_sdb_data/test2", expected, local_opts)


def test_vagrant_init_arg_override(local_opts):
    testdict = dict(
        cwd="/tmp/there",
        machine="treetest",
        runas="anybody",
        vagrant_provider="spansh",
    )
    mock_sdb = MagicMock(return_value=None)
    with patch.dict(vagrant.__utils__, {"sdb.sdb_set": mock_sdb}):
        vagrant.init(
            "test3",
            cwd="/tmp",
            machine="threetest",
            runas="him",
            vagrant_provider="polish",
            vm=testdict,
        )
        expected = dict(
            name="test3",
            cwd="/tmp",
            machine="threetest",
            runas="him",
            vagrant_provider="polish",
        )
        mock_sdb.assert_any_call("sdb://vagrant_sdb_data/test3", expected, local_opts)


def test_vagrant_get_ssh_config_fails():
    mock_sdb = MagicMock(return_value=None)
    with patch.dict(vagrant.__utils__, {"sdb.sdb_set": mock_sdb}):
        mock_sdb = MagicMock(return_value={})
        with patch.dict(vagrant.__utils__, {"sdb.sdb_get": mock_sdb}):
            vagrant.init("test3", cwd="/tmp")
            with pytest.raises(salt.exceptions.SaltInvocationError):
                vagrant.get_ssh_config("test3")  # has not been started


def test_vagrant_destroy(local_opts, tmp_path):
    path_mydir = str(tmp_path / "my" / "dir")
    mock_cmd = MagicMock(return_value={"retcode": 0})
    with patch.dict(vagrant.__salt__, {"cmd.run_all": mock_cmd}):
        mock_sdb = MagicMock(return_value=None)
        with patch.dict(vagrant.__utils__, {"sdb.sdb_delete": mock_sdb}):
            mock_sdb_get = MagicMock(
                return_value={"machine": "macfour", "cwd": path_mydir}
            )
            with patch.dict(vagrant.__utils__, {"sdb.sdb_get": mock_sdb_get}):
                assert vagrant.destroy("test4")
                mock_sdb.assert_any_call(
                    f"sdb://vagrant_sdb_data/macfour?{path_mydir}",
                    local_opts,
                )
                mock_sdb.assert_any_call("sdb://vagrant_sdb_data/test4", local_opts)
                cmd = "vagrant destroy -f macfour"
                mock_cmd.assert_called_with(
                    cmd, runas=None, cwd=path_mydir, output_loglevel="info"
                )


def test_vagrant_start():
    mock_cmd = MagicMock(return_value={"retcode": 0})
    with patch.dict(vagrant.__salt__, {"cmd.run_all": mock_cmd}):
        mock_sdb_get = MagicMock(
            return_value={
                "machine": "five",
                "cwd": "/the/dir",
                "runas": "me",
                "vagrant_provider": "him",
            }
        )
        with patch.dict(vagrant.__utils__, {"sdb.sdb_get": mock_sdb_get}):
            assert vagrant.start("test5")
            cmd = "vagrant up five --provider=him"
            mock_cmd.assert_called_with(
                cmd, runas="me", cwd="/the/dir", output_loglevel="info"
            )
