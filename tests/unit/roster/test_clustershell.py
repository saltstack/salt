"""
unit tests for clustershell roster
"""

from tests.support.mock import MagicMock, patch

# Import Salt Testing libraries
from tests.support.unit import TestCase, skipIf

try:
    from ClusterShell.NodeSet import NodeSet  # pylint: disable=unused-import

    HAS_CLUSTERSHELL = True
except (ImportError, OSError) as e:
    HAS_CLUSTERSHELL = False


@skipIf(
    HAS_CLUSTERSHELL is False,
    "Install Python Clustershell bindings before running these tests.",
)
class ClusterShellTestCase(TestCase):
    """
    Test cases for clustershell roster
    """

    def test_targets(self):
        mock_socket = MagicMock()
        mock_nodeset = MagicMock()
        mock_nodeset.NodeSet.return_value = ["foo"]
        with patch.dict(
            "sys.modules",
            **{"socket": mock_socket, "ClusterShell.NodeSet": mock_nodeset}
        ):
            import salt.roster.clustershell

            salt.roster.clustershell.__opts__ = {}
            with patch.dict(
                salt.roster.clustershell.__opts__,
                {"ssh_scan_ports": [1, 2, 3], "ssh_scan_timeout": 30},
            ):
                # Reimports are necessary to re-init the namespace.
                # pylint: disable=unused-import
                import socket
                from ClusterShell.NodeSet import NodeSet

                # pylint: enable=unused-import
                ret = salt.roster.clustershell.targets("foo")
                mock_socket.gethostbyname.assert_any_call("foo")
                self.assertTrue("foo" in ret)
                self.assertTrue(ret["foo"]["port"] == 3)
