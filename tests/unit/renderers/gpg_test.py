# -*- coding: utf-8 -*-

# Import Python libs
import os
from imp import find_module

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import patch, Mock, NO_MOCK, NO_MOCK_REASON

ensure_in_syspath('../../')

# Import Salt libs
import salt.loader
import salt.config
import salt.utils
from salt.utils.odict import OrderedDict
from salt.state import HighState
from integration import TMP

GPG_KEYDIR = os.path.join(TMP, 'gpg-keydir')

# The keyring library uses `getcwd()`, let's make sure we in a good directory
# before importing keyring
if not os.path.isdir(GPG_KEYDIR):
    os.makedirs(GPG_KEYDIR)

os.chdir(GPG_KEYDIR)


OPTS = salt.config.minion_config(None)
OPTS['state_events'] = False
OPTS['id'] = 'whatever'
OPTS['file_client'] = 'local'
OPTS['file_roots'] = dict(base=['/tmp'])
OPTS['cachedir'] = 'cachedir'
OPTS['test'] = False
OPTS['grains'] = salt.loader.grains(OPTS)
OPTS['gpg_keydir'] = GPG_KEYDIR

ENCRYPTED_STRING = '''
-----BEGIN PGP MESSAGE-----
I AM SO SECRET!
-----END PGP MESSAGE-----
'''
DECRYPTED_STRING = 'I am not a secret anymore'
SKIP = False

try:
    find_module('gnupg')
except ImportError:
    SKIP = True

if salt.utils.which('gpg') is None:
    SKIP = True


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(SKIP, "GPG must be installed")
class GPGTestCase(TestCase):

    def setUp(self):
        self.HIGHSTATE = HighState(OPTS)
        self.HIGHSTATE.push_active()

    def tearDown(self):
        self.HIGHSTATE.pop_active()

    def render_sls(self, data, sls='', env='base', **kws):
        return self.HIGHSTATE.state.rend['gpg'](
            data, env=env, sls=sls, **kws
        )

    def make_decryption_mock(self):
        decrypted_data_mock = Mock()
        decrypted_data_mock.ok = True
        decrypted_data_mock.__str__ = lambda x: DECRYPTED_STRING
        return decrypted_data_mock

    def make_nested_object(self, s):
        return OrderedDict([
            ('array_key', [1, False, s]),
            ('string_key', 'A Normal String'),
            ('dict_key', {1: None}),
        ])

    @patch('gnupg.GPG')
    def test_homedir_is_passed_to_gpg(self, gpg_mock):
        self.render_sls({})
        gpg_mock.assert_called_with(gnupghome=OPTS['gpg_keydir'])

    def test_normal_string_is_unchanged(self):
        s = 'I am just another string'
        new_s = self.render_sls(s)
        self.assertEqual(s, new_s)

    def test_encrypted_string_is_decrypted(self):
        with patch('gnupg.GPG.decrypt', return_value=self.make_decryption_mock()):
            new_s = self.render_sls(ENCRYPTED_STRING)
        self.assertEqual(new_s, DECRYPTED_STRING)

    def test_encrypted_string_is_unchanged_when_gpg_fails(self):
        d_mock = self.make_decryption_mock()
        d_mock.ok = False
        with patch('gnupg.GPG.decrypt', return_value=d_mock):
            new_s = self.render_sls(ENCRYPTED_STRING)
        self.assertEqual(new_s, ENCRYPTED_STRING)

    def test_nested_object_is_decrypted(self):
        encrypted_o = self.make_nested_object(ENCRYPTED_STRING)
        decrypted_o = self.make_nested_object(DECRYPTED_STRING)
        with patch('gnupg.GPG.decrypt', return_value=self.make_decryption_mock()):
            new_o = self.render_sls(encrypted_o)
        self.assertEqual(new_o, decrypted_o)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(GPGTestCase, needs_daemon=False)
