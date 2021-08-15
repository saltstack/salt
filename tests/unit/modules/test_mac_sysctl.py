"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

import salt.modules.mac_sysctl as mac_sysctl
from salt.exceptions import CommandExecutionError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import DEFAULT, MagicMock, mock_open, patch
from tests.support.unit import TestCase


class DarwinSysctlTestCase(TestCase, LoaderModuleMockMixin):
    """
    TestCase for salt.modules.mac_sysctl module
    """

    def setup_loader_modules(self):
        return {mac_sysctl: {}}

    def test_get(self):
        """
        Tests the return of get function
        """
        mock_cmd = MagicMock(return_value="foo")
        with patch.dict(mac_sysctl.__salt__, {"cmd.run": mock_cmd}):
            self.assertEqual(mac_sysctl.get("kern.ostype"), "foo")

    def test_assign_cmd_failed(self):
        """
        Tests if the assignment was successful or not
        """
        cmd = {
            "pid": 3548,
            "retcode": 1,
            "stderr": "",
            "stdout": "net.inet.icmp.icmplim: 250 -> 50",
        }
        mock_cmd = MagicMock(return_value=cmd)
        with patch.dict(mac_sysctl.__salt__, {"cmd.run_all": mock_cmd}):
            self.assertRaises(
                CommandExecutionError, mac_sysctl.assign, "net.inet.icmp.icmplim", 50
            )

    def test_assign(self):
        """
        Tests the return of successful assign function
        """
        cmd = {
            "pid": 3548,
            "retcode": 0,
            "stderr": "",
            "stdout": "net.inet.icmp.icmplim: 250 -> 50",
        }
        ret = {"net.inet.icmp.icmplim": "50"}
        mock_cmd = MagicMock(return_value=cmd)
        with patch.dict(mac_sysctl.__salt__, {"cmd.run_all": mock_cmd}):
            self.assertEqual(mac_sysctl.assign("net.inet.icmp.icmplim", 50), ret)

    def test_persist_no_conf_failure(self):
        """
        Tests adding of config file failure
        """
        read_data = IOError(13, "Permission denied", "/file")
        with patch("salt.utils.files.fopen", mock_open(read_data=read_data)), patch(
            "os.path.isfile", MagicMock(return_value=False)
        ):
            self.assertRaises(
                CommandExecutionError,
                mac_sysctl.persist,
                "net.inet.icmp.icmplim",
                50,
                config=None,
            )

    def test_persist_no_conf_success(self):
        """
        Tests successful add of config file when it did not already exist
        """
        config = "/etc/sysctl.conf"
        isfile_mock = MagicMock(side_effect=lambda x: False if x == config else DEFAULT)
        with patch("salt.utils.files.fopen", mock_open()) as m_open, patch(
            "os.path.isfile", isfile_mock
        ):
            mac_sysctl.persist("net.inet.icmp.icmplim", 50, config=config)
            # We only should have opened the one file
            num_handles = len(m_open.filehandles)
            assert num_handles == 1, num_handles
            writes = m_open.write_calls()
            # We should have called .write() only once, with the expected
            # content
            num_writes = len(writes)
            assert num_writes == 1, num_writes
            assert writes[0] == "#\n# Kernel sysctl configuration\n#\n", writes[0]

    def test_persist_success(self):
        """
        Tests successful write to existing sysctl file
        """
        config = "/etc/sysctl.conf"
        to_write = "#\n# Kernel sysctl configuration\n#\n"
        writelines_calls = [
            [
                "#\n",
                "# Kernel sysctl configuration\n",
                "#\n",
                "net.inet.icmp.icmplim=50\n",
            ]
        ]
        isfile_mock = MagicMock(side_effect=lambda x: True if x == config else DEFAULT)
        with patch(
            "salt.utils.files.fopen", mock_open(read_data=to_write)
        ) as m_open, patch("os.path.isfile", isfile_mock):
            mac_sysctl.persist("net.inet.icmp.icmplim", 50, config=config)
            # We only should have opened the one file
            num_handles = len(m_open.filehandles)
            assert num_handles == 1, num_handles
            writes = m_open.writelines_calls()
            assert writes == writelines_calls, writes
