# -*- coding: utf-8 -*-
'''
Test salt.utils.zeromq
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import zmq

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import salt libs
import salt.utils.zeromq
from salt.exceptions import SaltSystemExit


class UtilsTestCase(TestCase):
    def test_ip_bracket(self):
        test_ipv4 = '127.0.0.1'
        test_ipv6 = '::1'
        self.assertEqual(test_ipv4, salt.utils.zeromq.ip_bracket(test_ipv4))
        self.assertEqual('[{0}]'.format(test_ipv6), salt.utils.zeromq.ip_bracket(test_ipv6))

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    @skipIf(not hasattr(zmq, 'IPC_PATH_MAX_LEN'), "ZMQ does not have max length support.")
    def test_check_ipc_length(self):
        '''
        Ensure we throw an exception if we have a too-long IPC URI
        '''
        with patch('zmq.IPC_PATH_MAX_LEN', 1):
            self.assertRaises(SaltSystemExit, salt.utils.zeromq.check_ipc_path_max_len, '1' * 1024)
