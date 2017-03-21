# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

# Import Salt libs
import salt.renderers.gpg as gpg
from salt.exceptions import SaltRenderError

gpg.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class GPGTestCase(TestCase):
    '''
    unit test GPG renderer
    '''
    def test__get_gpg_exec(self):
        '''
        test _get_gpg_exec
        '''
        gpg_exec = '/bin/gpg'

        with patch('salt.utils.which', MagicMock(return_value=gpg_exec)):
            self.assertEqual(gpg._get_gpg_exec(), gpg_exec)

        with patch('salt.utils.which', MagicMock(return_value=False)):
            self.assertRaises(SaltRenderError, gpg._get_gpg_exec)

    @patch('salt.utils.which', MagicMock())
    def test__decrypt_ciphertext(self):
        '''
        test _decrypt_ciphertext
        '''
        key_dir = '/etc/salt/gpgkeys'
        secret = 'Use more salt.'
        crypted = '!@#$%^&*()_+'

        class GPGDecrypt(object):
            def communicate(self, *args, **kwargs):
                return [secret, None]

        class GPGNotDecrypt(object):
            def communicate(self, *args, **kwargs):
                return [None, 'decrypt error']

        with patch('salt.renderers.gpg._get_key_dir', MagicMock(return_value=key_dir)):
            with patch('salt.renderers.gpg.Popen', MagicMock(return_value=GPGDecrypt())):
                self.assertEqual(gpg._decrypt_ciphertext(crypted), secret)
            with patch('salt.renderers.gpg.Popen', MagicMock(return_value=GPGNotDecrypt())):
                self.assertEqual(gpg._decrypt_ciphertext(crypted), crypted)

    def test__decrypt_object(self):
        '''
        test _decrypt_object
        '''

        secret = 'Use more salt.'
        crypted = '-----BEGIN PGP MESSAGE-----!@#$%^&*()_+'

        secret_map = {'secret': secret}
        crypted_map = {'secret': crypted}

        secret_list = [secret]
        crypted_list = [crypted]

        with patch('salt.renderers.gpg._decrypt_ciphertext', MagicMock(return_value=secret)):
            self.assertEqual(gpg._decrypt_object(secret), secret)
            self.assertEqual(gpg._decrypt_object(crypted), secret)
            self.assertEqual(gpg._decrypt_object(crypted_map), secret_map)
            self.assertEqual(gpg._decrypt_object(crypted_list), secret_list)
            self.assertEqual(gpg._decrypt_object(None), None)

    def test_render(self):
        '''
        test render
        '''

        key_dir = '/etc/salt/gpgkeys'
        secret = 'Use more salt.'
        crypted = '-----BEGIN PGP MESSAGE-----!@#$%^&*()_+'

        with patch('salt.renderers.gpg._get_gpg_exec', MagicMock(return_value=True)):
            with patch('salt.renderers.gpg._get_key_dir', MagicMock(return_value=key_dir)):
                with patch('salt.renderers.gpg._decrypt_object', MagicMock(return_value=secret)):
                    self.assertEqual(gpg.render(crypted), secret)
