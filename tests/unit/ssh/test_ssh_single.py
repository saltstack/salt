# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Eric Radman <ericshane@eradman.com`
'''

# Import python libs
from __future__ import absolute_import
import tempfile
import os.path

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON

ensure_in_syspath('../')

# Import Salt libs
import integration
from salt.client import ssh
from salt.utils import thin


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SSHSingleTests(TestCase):
    def setUp(self):
        self.tmp_cachedir = tempfile.mkdtemp(dir=integration.TMP)

    def test_single_opts(self):
        ''' Sanity check for ssh.Single options
        '''
        argv = ['ssh.set_auth_key', 'root', 'hobn+amNAXSBTiOXEqlBjGB...rsa root@master']
        opts = {
            'argv': argv,
            '__role': 'master',
            'cachedir': self.tmp_cachedir,
            'extension_modules': os.path.join(self.tmp_cachedir, 'extmods'),
        }
        target = {
            'passwd': 'abc123',
            'ssh_options': None,
            'sudo': False,
            'identities_only': False,
            'host': 'login1',
            'user': 'root',
            'timeout': 65,
            'remote_port_forwards': None,
            'sudo_user': '',
            'port': '22',
            'priv': '/etc/salt/pki/master/ssh/salt-ssh.rsa'
        }

        single = ssh.Single(
                opts,
                opts['argv'],
                'localhost',
                mods={},
                fsclient=None,
                thin=thin.thin_path(opts['cachedir']),
                mine=False,
                **target)

        self.assertEqual(single.shell._ssh_opts(), '')
        self.assertEqual(single.shell._cmd_str('date +%s'), 'ssh login1 '
                         '-o KbdInteractiveAuthentication=no -o '
                         'PasswordAuthentication=yes -o ConnectTimeout=65 -o Port=22 '
                         '-o IdentityFile=/etc/salt/pki/master/ssh/salt-ssh.rsa '
                         '-o User=root  date +%s')

if __name__ == '__main__':
    from integration import run_tests
    run_tests(SSHSingleTests, needs_daemon=False)
