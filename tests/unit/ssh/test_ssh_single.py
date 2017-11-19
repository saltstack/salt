# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Eric Radman <ericshane@eradman.com`
'''

# Import python libs
from __future__ import absolute_import
import tempfile
import os.path

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON

# Import Salt libs
import tests.integration as integration
import salt.utils.thin as thin
from salt.client import ssh


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
