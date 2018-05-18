# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import collections

# Import Salt Testing Libs
from tests.support import mock
from tests.support import mixins
from tests.support.unit import skipIf, TestCase

# Import Salt Libs
import salt.roster.sshconfig as sshconfig

_SAMPLE_SSH_CONFIG = """
Host *
    User user.mcuserface

Host abc*
    IdentityFile ~/.ssh/id_rsa_abc

Host def*
    IdentityFile ~/.ssh/id_rsa_def

Host abc.asdfgfdhgjkl.com
    HostName 123.123.123.123

Host abc123.asdfgfdhgjkl.com
    HostName 123.123.123.124

Host def.asdfgfdhgjkl.com
    HostName 234.234.234.234
"""

_TARGET_ABC = collections.OrderedDict([
    ('user', 'user.mcuserface'),
    ('priv', '~/.ssh/id_rsa_abc'),
    ('host', 'abc.asdfgfdhgjkl.com')
])

_TARGET_ABC123 = collections.OrderedDict([
    ('user', 'user.mcuserface'),
    ('priv', '~/.ssh/id_rsa_abc'),
    ('host', 'abc123.asdfgfdhgjkl.com')
])

_TARGET_DEF = collections.OrderedDict([
    ('user', 'user.mcuserface'),
    ('priv', '~/.ssh/id_rsa_def'),
    ('host', 'def.asdfgfdhgjkl.com')
])

_ALL = {
    'abc.asdfgfdhgjkl.com': _TARGET_ABC,
    'abc123.asdfgfdhgjkl.com': _TARGET_ABC123,
    'def.asdfgfdhgjkl.com': _TARGET_DEF
}

_ABC_GLOB = {
    'abc.asdfgfdhgjkl.com': _TARGET_ABC,
    'abc123.asdfgfdhgjkl.com': _TARGET_ABC123
}


@skipIf(mock.NO_MOCK, mock.NO_MOCK_REASON)
class SSHConfigRosterTestCase(TestCase, mixins.LoaderModuleMockMixin):

    @classmethod
    def setUpClass(cls):
        cls.mock_fp = mock_fp = mock.mock_open(read_data=_SAMPLE_SSH_CONFIG)

    def setup_loader_modules(self):
        return {sshconfig: {}}

    def test_all(self):
        with mock.patch('salt.utils.files.fopen', self.mock_fp):
            with mock.patch('salt.roster.sshconfig._get_ssh_config_file'):
                self.mock_fp.return_value.__iter__.return_value = _SAMPLE_SSH_CONFIG.splitlines()
                targets = sshconfig.targets('*')
        self.assertEqual(targets, _ALL)

    def test_abc_glob(self):
        with mock.patch('salt.utils.files.fopen', self.mock_fp):
            with mock.patch('salt.roster.sshconfig._get_ssh_config_file'):
                self.mock_fp.return_value.__iter__.return_value = _SAMPLE_SSH_CONFIG.splitlines()
                targets = sshconfig.targets('abc*')
        self.assertEqual(targets, _ABC_GLOB)
