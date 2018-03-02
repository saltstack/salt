# coding: utf-8

# python libs
from __future__ import absolute_import
import os

# salt testing libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import patch, call, mock_open, NO_MOCK, NO_MOCK_REASON, MagicMock

# salt libs
from salt.ext import six
import salt.utils.files
from salt import crypt

# third-party libs
try:
    import M2Crypto
    HAS_M2 = True
except ImportError:
    HAS_M2 = False
try:
    from Cryptodome.PublicKey import RSA  # pylint: disable=unused-import
    HAS_PYCRYPTO_RSA = True
except ImportError:
    HAS_PYCRYPTO_RSA = False
if not HAS_PYCRYPTO_RSA:
    try:
        from Crypto.PublicKey import RSA
        HAS_PYCRYPTO_RSA = True
    except ImportError:
        HAS_PYCRYPTO_RSA = False


PRIVKEY_DATA = (
    '-----BEGIN RSA PRIVATE KEY-----\n'
    'MIIEpAIBAAKCAQEA75GR6ZTv5JOv90Vq8tKhKC7YQnhDIo2hM0HVziTEk5R4UQBW\n'
    'a0CKytFMbTONY2msEDwX9iA0x7F5Lgj0X8eD4ZMsYqLzqjWMekLC8bjhxc+EuPo9\n'
    'Dygu3mJ2VgRC7XhlFpmdo5NN8J2E7B/CNB3R4hOcMMZNZdi0xLtFoTfwU61UPfFX\n'
    '14mV2laqLbvDEfQLJhUTDeFFV8EN5Z4H1ttLP3sMXJvc3EvM0JiDVj4l1TWFUHHz\n'
    'eFgCA1Im0lv8i7PFrgW7nyMfK9uDSsUmIp7k6ai4tVzwkTmV5PsriP1ju88Lo3MB\n'
    '4/sUmDv/JmlZ9YyzTO3Po8Uz3Aeq9HJWyBWHAQIDAQABAoIBAGOzBzBYZUWRGOgl\n'
    'IY8QjTT12dY/ymC05GM6gMobjxuD7FZ5d32HDLu/QrknfS3kKlFPUQGDAbQhbbb0\n'
    'zw6VL5NO9mfOPO2W/3FaG1sRgBQcerWonoSSSn8OJwVBHMFLG3a+U1Zh1UvPoiPK\n'
    'S734swIM+zFpNYivGPvOm/muF/waFf8tF/47t1cwt/JGXYQnkG/P7z0vp47Irpsb\n'
    'Yjw7vPe4BnbY6SppSxscW3KoV7GtJLFKIxAXbxsuJMF/rYe3O3w2VKJ1Sug1VDJl\n'
    '/GytwAkSUer84WwP2b07Wn4c5pCnmLslMgXCLkENgi1NnJMhYVOnckxGDZk54hqP\n'
    '9RbLnkkCgYEA/yKuWEvgdzYRYkqpzB0l9ka7Y00CV4Dha9Of6GjQi9i4VCJ/UFVr\n'
    'UlhTo5y0ZzpcDAPcoZf5CFZsD90a/BpQ3YTtdln2MMCL/Kr3QFmetkmDrt+3wYnX\n'
    'sKESfsa2nZdOATRpl1antpwyD4RzsAeOPwBiACj4fkq5iZJBSI0bxrMCgYEA8GFi\n'
    'qAjgKh81/Uai6KWTOW2kX02LEMVRrnZLQ9VPPLGid4KZDDk1/dEfxjjkcyOxX1Ux\n'
    'Klu4W8ZEdZyzPcJrfk7PdopfGOfrhWzkREK9C40H7ou/1jUecq/STPfSOmxh3Y+D\n'
    'ifMNO6z4sQAHx8VaHaxVsJ7SGR/spr0pkZL+NXsCgYEA84rIgBKWB1W+TGRXJzdf\n'
    'yHIGaCjXpm2pQMN3LmP3RrcuZWm0vBt94dHcrR5l+u/zc6iwEDTAjJvqdU4rdyEr\n'
    'tfkwr7v6TNlQB3WvpWanIPyVzfVSNFX/ZWSsAgZvxYjr9ixw6vzWBXOeOb/Gqu7b\n'
    'cvpLkjmJ0wxDhbXtyXKhZA8CgYBZyvcQb+hUs732M4mtQBSD0kohc5TsGdlOQ1AQ\n'
    'McFcmbpnzDghkclyW8jzwdLMk9uxEeDAwuxWE/UEvhlSi6qdzxC+Zifp5NBc0fVe\n'
    '7lMx2mfJGxj5CnSqQLVdHQHB4zSXkAGB6XHbBd0MOUeuvzDPfs2voVQ4IG3FR0oc\n'
    '3/znuwKBgQChZGH3McQcxmLA28aUwOVbWssfXKdDCsiJO+PEXXlL0maO3SbnFn+Q\n'
    'Tyf8oHI5cdP7AbwDSx9bUfRPjg9dKKmATBFr2bn216pjGxK0OjYOCntFTVr0psRB\n'
    'CrKg52Qrq71/2l4V2NLQZU40Dr1bN9V+Ftd9L0pvpCAEAWpIbLXGDw==\n'
    '-----END RSA PRIVATE KEY-----')

PUBKEY_DATA = (
    '-----BEGIN PUBLIC KEY-----\n'
    'MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA75GR6ZTv5JOv90Vq8tKh\n'
    'KC7YQnhDIo2hM0HVziTEk5R4UQBWa0CKytFMbTONY2msEDwX9iA0x7F5Lgj0X8eD\n'
    '4ZMsYqLzqjWMekLC8bjhxc+EuPo9Dygu3mJ2VgRC7XhlFpmdo5NN8J2E7B/CNB3R\n'
    '4hOcMMZNZdi0xLtFoTfwU61UPfFX14mV2laqLbvDEfQLJhUTDeFFV8EN5Z4H1ttL\n'
    'P3sMXJvc3EvM0JiDVj4l1TWFUHHzeFgCA1Im0lv8i7PFrgW7nyMfK9uDSsUmIp7k\n'
    '6ai4tVzwkTmV5PsriP1ju88Lo3MB4/sUmDv/JmlZ9YyzTO3Po8Uz3Aeq9HJWyBWH\n'
    'AQIDAQAB\n'
    '-----END PUBLIC KEY-----')

MSG = b'It\'s me, Mario'

SIG = (
        b'\x07\xf3\xb1\xe7\xdb\x06\xf4_\xe2\xdc\xcb!F\xfb\xbex{W\x1d\xe4E'
        b'\xd3\r\xc5\x90\xca(\x05\x1d\x99\x8b\x1aug\x9f\x95>\x94\x7f\xe3+'
        b'\x12\xfa\x9c\xd4\xb8\x02]\x0e\xa5\xa3LL\xc3\xa2\x8f+\x83Z\x1b\x17'
        b'\xbfT\xd3\xc7\xfd\x0b\xf4\xd7J\xfe^\x86q"I\xa3x\xbc\xd3$\xe9M<\xe1'
        b'\x07\xad\xf2_\x9f\xfa\xf7g(~\xd8\xf5\xe7\xda-\xa3Ko\xfc.\x99\xcf'
        b'\x9b\xb9\xc1U\x97\x82\'\xcb\xc6\x08\xaa\xa0\xe4\xd0\xc1+\xfc\x86'
        b'\r\xe4y\xb1#\xd3\x1dS\x96D28\xc4\xd5\r\xd4\x98\x1a44"\xd7\xc2\xb4'
        b']\xa7\x0f\xa7Db\x85G\x8c\xd6\x94!\x8af1O\xf6g\xd7\x03\xfd\xb3\xbc'
        b'\xce\x9f\xe7\x015\xb8\x1d]AHK\xa0\x14m\xda=O\xa7\xde\xf2\xff\x9b'
        b'\x8e\x83\xc8j\x11\x1a\x98\x85\xde\xc5\x91\x07\x84!\x12^4\xcb\xa8'
        b'\x98\x8a\x8a&#\xb9(#?\x80\x15\x9eW\xb5\x12\xd1\x95S\xf2<G\xeb\xf1'
        b'\x14H\xb2\xc4>\xc3A\xed\x86x~\xcfU\xd5Q\xfe~\x10\xd2\x9b')


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYCRYPTO_RSA, 'pycrypto >= 2.6 is not available')
@skipIf(HAS_M2, 'm2crypto is used by salt.crypt if installed')
class CryptTestCase(TestCase):
    def test_gen_keys(self):
        with patch.multiple(os, umask=MagicMock(), chmod=MagicMock(),
                            access=MagicMock(return_value=True)):
            with patch('salt.utils.files.fopen', mock_open()):
                open_priv_wb = call('/keydir{0}keyname.pem'.format(os.sep), 'wb+')
                open_pub_wb = call('/keydir{0}keyname.pub'.format(os.sep), 'wb+')
                with patch('os.path.isfile', return_value=True):
                    self.assertEqual(crypt.gen_keys('/keydir', 'keyname', 2048), '/keydir{0}keyname.pem'.format(os.sep))
                    self.assertNotIn(open_priv_wb, salt.utils.files.fopen.mock_calls)
                    self.assertNotIn(open_pub_wb, salt.utils.files.fopen.mock_calls)
                with patch('os.path.isfile', return_value=False):
                    with patch('salt.utils.files.fopen', mock_open()):
                        crypt.gen_keys('/keydir', 'keyname', 2048)
                        salt.utils.files.fopen.assert_has_calls([open_priv_wb, open_pub_wb], any_order=True)

    @patch('os.umask', MagicMock())
    @patch('os.chmod', MagicMock())
    @patch('os.chown', MagicMock(), create=True)
    @patch('os.access', MagicMock(return_value=True))
    def test_gen_keys_with_passphrase(self):
        key_path = os.path.join(os.sep, 'keydir')
        with patch('salt.utils.files.fopen', mock_open()):
            open_priv_wb = call(os.path.join(key_path, 'keyname.pem'), 'wb+')
            open_pub_wb = call(os.path.join(key_path, 'keyname.pub'), 'wb+')
            with patch('os.path.isfile', return_value=True):
                self.assertEqual(crypt.gen_keys(key_path, 'keyname', 2048, passphrase='password'), os.path.join(key_path, 'keyname.pem'))
                self.assertNotIn(open_priv_wb, salt.utils.files.fopen.mock_calls)
                self.assertNotIn(open_pub_wb, salt.utils.files.fopen.mock_calls)
            with patch('os.path.isfile', return_value=False):
                with patch('salt.utils.files.fopen', mock_open()):
                    crypt.gen_keys(key_path, 'keyname', 2048)
                    salt.utils.files.fopen.assert_has_calls([open_priv_wb, open_pub_wb], any_order=True)

    def test_sign_message(self):
        key = RSA.importKey(PRIVKEY_DATA)
        with patch('salt.crypt.get_rsa_key', return_value=key):
            self.assertEqual(SIG, salt.crypt.sign_message('/keydir/keyname.pem', MSG))

    def test_sign_message_with_passphrase(self):
        key = RSA.importKey(PRIVKEY_DATA)
        with patch('salt.crypt.get_rsa_key', return_value=key):
            self.assertEqual(SIG, crypt.sign_message('/keydir/keyname.pem', MSG, passphrase='password'))

    def test_verify_signature(self):
        with patch('salt.utils.files.fopen', mock_open(read_data=PUBKEY_DATA)):
            self.assertTrue(crypt.verify_signature('/keydir/keyname.pub', MSG, SIG))


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_M2, 'm2crypto is not available')
class M2CryptTestCase(TestCase):
    @patch('os.umask', MagicMock())
    @patch('os.chmod', MagicMock())
    @patch('os.access', MagicMock(return_value=True))
    def test_gen_keys(self):
        with patch('M2Crypto.RSA.RSA.save_pem', MagicMock()) as save_pem:
            with patch('M2Crypto.RSA.RSA.save_pub_key', MagicMock()) as save_pub:
                with patch('os.path.isfile', return_value=True):
                    self.assertEqual(crypt.gen_keys('/keydir', 'keyname', 2048),
                                     '/keydir{0}keyname.pem'.format(os.sep))
                    save_pem.assert_not_called()
                    save_pub.assert_not_called()

                with patch('os.path.isfile', return_value=False):
                    self.assertEqual(crypt.gen_keys('/keydir', 'keyname', 2048),
                                     '/keydir{0}keyname.pem'.format(os.sep))
                    save_pem.assert_called_once_with('/keydir{0}keyname.pem'.format(os.sep), cipher=None)
                    save_pub.assert_called_once_with('/keydir{0}keyname.pub'.format(os.sep))

    @patch('os.umask', MagicMock())
    @patch('os.chmod', MagicMock())
    @patch('os.chown', MagicMock())
    @patch('os.access', MagicMock(return_value=True))
    def test_gen_keys_with_passphrase(self):
        with patch('M2Crypto.RSA.RSA.save_pem', MagicMock()) as save_pem:
            with patch('M2Crypto.RSA.RSA.save_pub_key', MagicMock()) as save_pub:
                with patch('os.path.isfile', return_value=True):
                    self.assertEqual(crypt.gen_keys('/keydir', 'keyname', 2048, passphrase='password'),
                                     '/keydir{0}keyname.pem'.format(os.sep))
                    save_pem.assert_not_called()
                    save_pub.assert_not_called()

                with patch('os.path.isfile', return_value=False):
                    self.assertEqual(crypt.gen_keys('/keydir', 'keyname', 2048, passphrase='password'),
                                     '/keydir{0}keyname.pem'.format(os.sep))
                    callback = save_pem.call_args[1]['callback']
                    save_pem.assert_called_once_with('/keydir{0}keyname.pem'.format(os.sep),
                                                     cipher='des_ede3_cbc',
                                                     callback=callback)
                    self.assertEqual(callback(None), b'password')
                    save_pub.assert_called_once_with('/keydir{0}keyname.pub'.format(os.sep))

    def test_sign_message(self):
        key = M2Crypto.RSA.load_key_string(six.b(PRIVKEY_DATA))
        with patch('salt.crypt.get_rsa_key', return_value=key):
            self.assertEqual(SIG, salt.crypt.sign_message('/keydir/keyname.pem', MSG))

    def test_sign_message_with_passphrase(self):
        key = M2Crypto.RSA.load_key_string(six.b(PRIVKEY_DATA))
        with patch('salt.crypt.get_rsa_key', return_value=key):
            self.assertEqual(SIG, crypt.sign_message('/keydir/keyname.pem', MSG, passphrase='password'))

    def test_verify_signature(self):
        key = M2Crypto.RSA.load_pub_key_bio(M2Crypto.BIO.MemoryBuffer(six.b(PUBKEY_DATA)))
        with patch('M2Crypto.RSA.load_pub_key', return_value=key):
            self.assertTrue(crypt.verify_signature('/keydir/keyname.pub', MSG, SIG))

    def test_encrypt_decrypt_bin(self):
        priv_key = M2Crypto.RSA.load_key_string(six.b(PRIVKEY_DATA))
        pub_key = M2Crypto.RSA.load_pub_key_bio(M2Crypto.BIO.MemoryBuffer(six.b(PUBKEY_DATA)))
        encrypted = salt.crypt.private_encrypt(priv_key, b'salt')
        decrypted = salt.crypt.public_decrypt(pub_key, encrypted)
        self.assertEqual(b'salt', decrypted)
