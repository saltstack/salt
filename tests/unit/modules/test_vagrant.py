import os

import salt.exceptions
import salt.modules.vagrant as vagrant
import salt.utils.platform
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

TEMP_DATABASE_FILE = "/tmp/salt-tests-tmpdir/test_vagrant.sqlite"


class VagrantTestCase(TestCase, LoaderModuleMockMixin):
    """
    Unit TestCase for the salt.modules.vagrant module.
    """

    LOCAL_OPTS = {
        "extension_modules": "",
        "vagrant_sdb_data": {
            "driver": "sqlite3",
            "database": TEMP_DATABASE_FILE,
            "table": "sdb",
            "create_table": True,
        },
    }

    def setup_loader_modules(self):
        vagrant_globals = {
            "__opts__": self.LOCAL_OPTS,
        }
        return {vagrant: vagrant_globals}

    def test_vagrant_get_vm_info_not_found(self):
        mock_sdb = MagicMock(return_value=None)
        with patch.dict(vagrant.__utils__, {"sdb.sdb_get": mock_sdb}):
            with self.assertRaises(salt.exceptions.SaltInvocationError):
                vagrant.get_vm_info("thisNameDoesNotExist")

    def test_vagrant_init_positional(self):
        path_nowhere = os.path.join(os.sep, "tmp", "nowhere")
        if salt.utils.platform.is_windows():
            path_nowhere = "c:{}".format(path_nowhere)
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
            self.assertTrue(resp.startswith("Name test1 defined"))
            expected = dict(
                name="test1",
                cwd=path_nowhere,
                machine="onetest",
                runas="nobody",
                vagrant_provider="french",
                different="very",
            )
            mock_sdb.assert_called_with(
                "sdb://vagrant_sdb_data/onetest?{}".format(path_nowhere),
                "test1",
                self.LOCAL_OPTS,
            )
            mock_sdb.assert_any_call(
                "sdb://vagrant_sdb_data/test1", expected, self.LOCAL_OPTS
            )

    def test_vagrant_get_vm_info(self):
        testdict = {"testone": "one", "machine": "two"}
        mock_sdb = MagicMock(return_value=testdict)
        with patch.dict(vagrant.__utils__, {"sdb.sdb_get": mock_sdb}):
            resp = vagrant.get_vm_info("test1")
            self.assertEqual(resp, testdict)

    def test_vagrant_init_dict(self):
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
            mock_sdb.assert_any_call(
                "sdb://vagrant_sdb_data/test2", expected, self.LOCAL_OPTS
            )

    def test_vagrant_init_arg_override(self):
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
            mock_sdb.assert_any_call(
                "sdb://vagrant_sdb_data/test3", expected, self.LOCAL_OPTS
            )

    def test_vagrant_get_ssh_config_fails(self):
        mock_sdb = MagicMock(return_value=None)
        with patch.dict(vagrant.__utils__, {"sdb.sdb_set": mock_sdb}):
            mock_sdb = MagicMock(return_value={})
            with patch.dict(vagrant.__utils__, {"sdb.sdb_get": mock_sdb}):
                vagrant.init("test3", cwd="/tmp")
                with self.assertRaises(salt.exceptions.SaltInvocationError):
                    vagrant.get_ssh_config("test3")  # has not been started

    def test_vagrant_destroy(self):
        path_mydir = os.path.join(os.sep, "my", "dir")
        if salt.utils.platform.is_windows():
            path_mydir = "c:{}".format(path_mydir)
        mock_cmd = MagicMock(return_value={"retcode": 0})
        with patch.dict(vagrant.__salt__, {"cmd.run_all": mock_cmd}):
            mock_sdb = MagicMock(return_value=None)
            with patch.dict(vagrant.__utils__, {"sdb.sdb_delete": mock_sdb}):
                mock_sdb_get = MagicMock(
                    return_value={"machine": "macfour", "cwd": path_mydir}
                )
                with patch.dict(vagrant.__utils__, {"sdb.sdb_get": mock_sdb_get}):
                    self.assertTrue(vagrant.destroy("test4"))
                    mock_sdb.assert_any_call(
                        "sdb://vagrant_sdb_data/macfour?{}".format(path_mydir),
                        self.LOCAL_OPTS,
                    )
                    mock_sdb.assert_any_call(
                        "sdb://vagrant_sdb_data/test4", self.LOCAL_OPTS
                    )
                    cmd = "vagrant destroy -f macfour"
                    mock_cmd.assert_called_with(
                        cmd, runas=None, cwd=path_mydir, output_loglevel="info"
                    )

    def test_vagrant_start(self):
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
                self.assertTrue(vagrant.start("test5"))
                cmd = "vagrant up five --provider=him"
                mock_cmd.assert_called_with(
                    cmd, runas="me", cwd="/the/dir", output_loglevel="info"
                )
