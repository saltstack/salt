# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import python libs
from __future__ import absolute_import
import os

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, patch

# Import salt libs
from salt import minion
from salt.utils import event
from salt.exceptions import SaltSystemExit
import salt.syspaths

ensure_in_syspath('../')

__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MinionTestCase(TestCase):
    def test_invalid_master_address(self):
        with patch.dict(__opts__, {'ipv6': False, 'master': float('127.0'), 'master_port': '4555', 'retry_dns': False}):
            self.assertRaises(SaltSystemExit, minion.resolve_dns, __opts__)

    @skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
    def test_sock_path_len(self):
        '''
        This tests whether or not a larger hash causes the sock path to exceed
        the system's max sock path length. See the below link for more
        information.

        https://github.com/saltstack/salt/issues/12172#issuecomment-43903643
        '''
        opts = {
            'id': 'salt-testing',
            'hash_type': 'sha512',
            'sock_dir': os.path.join(salt.syspaths.SOCK_DIR, 'minion'),
            'extension_modules': ''
        }
        with patch.dict(__opts__, opts):
            try:
                event_publisher = event.AsyncEventPublisher(__opts__)
                result = True
            except SaltSystemExit:
                result = False
        self.assertTrue(result)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MinionTestCase, needs_daemon=False)
