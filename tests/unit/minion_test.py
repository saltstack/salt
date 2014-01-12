# -*- coding: utf-8 -*-
'''
    :codauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, patch

from salt import minion
from salt.exceptions import SaltSystemExit


ensure_in_syspath('../')

__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MinionTestCase(TestCase):
    def test_invalid_master_address(self):
        with patch.dict(__opts__, {'ipv6': False, 'master': float('127.0'), 'master_port': '4555', 'retry_dns': False}):
            self.assertRaises(SaltSystemExit, minion.resolve_dns, __opts__)
