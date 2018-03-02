# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Daniel Wallace <dwallace@saltstack.com`
'''

# Import python libs
from __future__ import absolute_import, unicode_literals
import os

# Import Salt Testing libs
from tests.support.unit import skipIf
from tests.support.case import ShellCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock

# Import Salt libs
import salt.config
from salt.client import ssh


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SSHPasswordTests(ShellCase):
    def test_password_failure(self):
        '''
        Check password failures when trying to deploy keys
        '''
        opts = salt.config.client_config(self.get_config_file_path('master'))
        opts['list_hosts'] = False
        opts['argv'] = ['test.ping']
        opts['selected_target_option'] = 'glob'
        opts['tgt'] = 'localhost'
        opts['arg'] = []
        roster = os.path.join(self.get_config_dir(), 'roster')
        handle_ssh_ret = [
            {'localhost': {'retcode': 255, 'stderr': u'Permission denied (publickey).\r\n', 'stdout': ''}},
        ]
        expected = {'localhost': 'Permission denied (publickey)'}
        display_output = MagicMock()
        with patch('salt.roster.get_roster_file', MagicMock(return_value=roster)), \
                patch('salt.client.ssh.SSH.handle_ssh', MagicMock(return_value=handle_ssh_ret)), \
                patch('salt.client.ssh.SSH.key_deploy', MagicMock(return_value=expected)), \
                patch('salt.output.display_output', display_output):
            client = ssh.SSH(opts)
            ret = next(client.run_iter())
            with self.assertRaises(SystemExit):
                client.run()
        display_output.assert_called_once_with(expected, 'nested', opts)
        self.assertIs(ret, handle_ssh_ret[0])
