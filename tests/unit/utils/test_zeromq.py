"""
Test salt.utils.zeromq
"""


import salt.utils.zeromq
import zmq
from salt._compat import ipaddress
from salt.exceptions import SaltSystemExit
from tests.support.mock import patch
from tests.support.unit import TestCase, skipIf


class UtilsTestCase(TestCase):
    def test_ip_bracket(self):
        test_ipv4 = "127.0.0.1"
        test_ipv6 = "::1"
        test_ipv6_uri = "[::1]"
        self.assertEqual(test_ipv4, salt.utils.zeromq.ip_bracket(test_ipv4))
        self.assertEqual(
            "[{}]".format(test_ipv6), salt.utils.zeromq.ip_bracket(test_ipv6)
        )
        self.assertEqual(
            "[{}]".format(test_ipv6), salt.utils.zeromq.ip_bracket(test_ipv6_uri)
        )

        ip_addr_obj = ipaddress.ip_address(test_ipv4)
        self.assertEqual(test_ipv4, salt.utils.zeromq.ip_bracket(ip_addr_obj))

    @skipIf(
        not hasattr(zmq, "IPC_PATH_MAX_LEN"), "ZMQ does not have max length support."
    )
    def test_check_ipc_length(self):
        """
        Ensure we throw an exception if we have a too-long IPC URI
        """
        with patch("zmq.IPC_PATH_MAX_LEN", 1):
            self.assertRaises(
                SaltSystemExit, salt.utils.zeromq.check_ipc_path_max_len, "1" * 1024
            )
