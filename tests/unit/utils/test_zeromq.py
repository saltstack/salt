"""
Test salt.utils.zeromq
"""

import pytest
import zmq

import salt.utils.zeromq
from salt.exceptions import SaltSystemExit
from tests.support.mock import patch
from tests.support.unit import TestCase


class UtilsTestCase(TestCase):
    @pytest.mark.skipif(
        not hasattr(zmq, "IPC_PATH_MAX_LEN"),
        reason="ZMQ does not have max length support.",
    )
    def test_check_ipc_length(self):
        """
        Ensure we throw an exception if we have a too-long IPC URI
        """
        with patch("zmq.IPC_PATH_MAX_LEN", 1):
            self.assertRaises(
                SaltSystemExit, salt.utils.zeromq.check_ipc_path_max_len, "1" * 1024
            )
