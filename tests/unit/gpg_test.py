# -*- coding: utf-8 -*-

# Import Python libs
import os
from collections import OrderedDict

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import patch, Mock

ensure_in_syspath('../')

# Import Salt libs
import salt.loader
import salt.config
from salt.state import HighState

OPTS = salt.config.minion_config(None)
OPTS['state_events'] = False
OPTS['id'] = 'whatever'
OPTS['file_client'] = 'local'
OPTS['file_roots'] = dict(base=['/tmp'])
OPTS['test'] = False
OPTS['grains'] = salt.loader.grains(OPTS)
OPTS['gpg_keydir'] = os.getcwd()

ENCRYPTED_STRING = """
-----BEGIN PGP MESSAGE-----
I AM SO SECRET!
-----END PGP MESSAGE-----
"""
DECRYPTED_STRING = "I am not a secret anymore"


class PyDSLRendererTestCase(TestCase):

    def setUp(self):
        self.HIGHSTATE = HighState(OPTS)
        self.HIGHSTATE.push_active()

    def tearDown(self):
        self.HIGHSTATE.pop_active()

    def render_sls(self, data, sls='', env='base', **kws):
        return self.HIGHSTATE.state.rend['gpg'](
            data, env=env, sls=sls, **kws
        )

    def make_decryption_mock(self, gpg_mock, decrypted_string):
        decrypted_data_mock = Mock()
        decrypted_data_mock.ok = True
        decrypted_data_mock.__str__ = lambda x: DECRYPTED_STRING

        decrypt_mock = Mock(return_value=decrypted_data_mock)
        gpg_mock.decrypt = decrypt_mock

        return gpg_mock

    def make_nested_object(self, s):
        return OrderedDict([
            ('array_key', [1, False, s])
            ('string_key', "A Normal String"),
            ('dict_key', {1: None}),
            ('obj_key', object()),
        ])

    @patch('gnupg.GPG')
    def test_homedir_is_passed_to_gpg(self, gpg_mock):
        self.render_sls({})
        gpg_mock.assert_called_with(OPTS['gpg_keydir'])

    def test_normal_string_is_unchanged(self):
        s = 'I am just another string'
        new_s = self.render_sls(s)
        self.assertEqual(s, new_s)

    @patch('gnupg.GPG')
    def test_encrypted_string_is_decrypted(self, gpg_mock):
        gpg_mock = self.make_decryption_mock(gpg_mock)

        new_s = self.render_sls(ENCRYPTED_STRING)
        self.assertEqual(new_s, DECRYPTED_STRING)

    @patch('gnupg.GPG')
    def test_encrypted_string_is_unchanged_when_gpg_fails(self, gpg_mock):
        decrypted_data_mock = Mock()
        decrypted_data_mock.ok = False

        decrypt_mock = Mock(return_value=decrypted_data_mock)
        gpg_mock.decrypt = decrypt_mock

        new_s = self.render_sls(ENCRYPTED_STRING)
        self.assertEqual(new_s, ENCRYPTED_STRING)

    @patch('gnupg.GPG')
    def test_nested_object_is_decrypted(self, gpg_mock):
        gpg_mock = self.make_decryption_mock(gpg_mock)

        encrypted_o = self.make_nested_object(ENCRYPTED_STRING)
        decrypted_o = self.make_nested_object(DECRYPTED_STRING)

        new_o = self.render_sls(encrypted_o)
        self.assertEqual(new_o, decrypted_o)
