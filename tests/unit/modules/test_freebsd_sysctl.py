"""
    :codeauthor: asomers <asomers@gmail.com>
"""


import salt.modules.freebsd_sysctl as freebsd_sysctl
import salt.modules.systemd_service as systemd
from salt.exceptions import CommandExecutionError
from tests.support.helpers import dedent
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, mock_open, patch
from tests.support.unit import TestCase


class FreeBSDSysctlTestCase(TestCase, LoaderModuleMockMixin):
    """
    TestCase for salt.modules.freebsd_sysctl module
    """

    def setup_loader_modules(self):
        return {freebsd_sysctl: {}, systemd: {}}

    def test_get(self):
        """
        Tests the return of get function
        """
        mock_cmd = MagicMock(return_value="1")
        with patch.dict(freebsd_sysctl.__salt__, {"cmd.run": mock_cmd}):
            self.assertEqual(freebsd_sysctl.get("vfs.usermount"), "1")

    def test_assign_failed(self):
        """
        Tests if the assignment was successful or not
        """
        cmd = {
            "pid": 1337,
            "retcode": 1,
            "stderr": "sysctl: unknown oid 'asef.esrhaseras.easr'",
            "stdout": "",
        }
        mock_cmd = MagicMock(return_value=cmd)
        with patch.dict(freebsd_sysctl.__salt__, {"cmd.run_all": mock_cmd}):
            self.assertRaises(
                CommandExecutionError,
                freebsd_sysctl.assign,
                "asef.esrhaseras.easr",
                "backward",
            )

    def test_assign_success(self):
        """
        Tests the return of successful assign function
        """
        cmd = {
            "pid": 1337,
            "retcode": 0,
            "stderr": "",
            "stdout": "vfs.usermount: 0 -> 1",
        }
        ret = {"vfs.usermount": "1"}
        mock_cmd = MagicMock(return_value=cmd)
        with patch.dict(freebsd_sysctl.__salt__, {"cmd.run_all": mock_cmd}):
            self.assertEqual(freebsd_sysctl.assign("vfs.usermount", 1), ret)

    def test_persist_no_conf_failure(self):
        """
        Tests adding of config file failure
        """
        asn_cmd = {
            "pid": 1337,
            "retcode": 1,
            "stderr": "sysctl: vfs.usermount=1: Operation not permitted",
            "stdout": "vfs.usermount: 1",
        }
        mock_asn_cmd = MagicMock(return_value=asn_cmd)
        cmd = "sysctl vfs.usermount=1"
        mock_cmd = MagicMock(return_value=cmd)
        with patch.dict(
            freebsd_sysctl.__salt__,
            {"cmd.run_stdout": mock_cmd, "cmd.run_all": mock_asn_cmd},
        ):
            with patch("salt.utils.files.fopen", mock_open()) as m_open:
                self.assertRaises(
                    CommandExecutionError,
                    freebsd_sysctl.persist,
                    "net.ipv4.ip_forward",
                    1,
                    config=None,
                )

    def test_persist_updated(self):
        """
        Tests sysctl.conf success
        """
        cmd = {
            "pid": 1337,
            "retcode": 0,
            "stderr": "",
            "stdout": "vfs.usermount: 1 -> 1",
        }
        mock_cmd = MagicMock(return_value=cmd)

        with patch("salt.utils.files.fopen", mock_open()):
            with patch.dict(
                freebsd_sysctl.__salt__,
                {"cmd.run_all": mock_cmd},
            ):
                self.assertEqual(
                    freebsd_sysctl.persist("vfs.usermount", 1),
                    "Updated",
                )

    def test_persist_updated_tunable(self):
        """
        Tests loader.conf success
        """

        with patch("salt.utils.files.fopen", mock_open()):
            self.assertEqual(
                freebsd_sysctl.persist("vfs.usermount", 1, "/boot/loader.conf"),
                "Updated",
            )

    def test_show(self):
        """
        Tests the show function
        """
        # Mock just a small portion of the full "sysctl -ae" output, but be
        # sure to include a multi-line value.
        mock_cmd = MagicMock(
            return_value=dedent(
                """\
            kern.ostype=FreeBSD
            kern.osrelease=13.0-CURRENT
            kern.osrevision=199506
            kern.version=FreeBSD 13.0-CURRENT #246 r365916M: Thu Sep 24 09:17:12 MDT 2020
                user@host.domain:/usr/obj/usr/src/head
            /amd64.amd64/sys/GENERIC

            kern.maxvnodes=213989
            """,
                "\n",
            )
        )
        with patch.dict(freebsd_sysctl.__salt__, {"cmd.run": mock_cmd}):
            ret = freebsd_sysctl.show()
            self.assertEqual("FreeBSD", ret["kern.ostype"])
            self.assertEqual(
                dedent(
                    """\
                FreeBSD 13.0-CURRENT #246 r365916M: Thu Sep 24 09:17:12 MDT 2020
                    user@host.domain:/usr/obj/usr/src/head
                /amd64.amd64/sys/GENERIC
                """,
                    "\n",
                ),
                ret["kern.version"],
            )
