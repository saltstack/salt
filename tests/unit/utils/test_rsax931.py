# coding: utf-8
'''
Test the RSA ANSI X9.31 signer and verifier
'''

# python libs
from __future__ import absolute_import, print_function, unicode_literals

# salt testing libs
from tests.support.unit import TestCase

# salt libs
from salt.utils.rsax931 import RSAX931Signer, RSAX931Verifier


class RSAX931Test(TestCase):

    privkey_data = (
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

    pubkey_data = (
        '-----BEGIN PUBLIC KEY-----\n'
        'MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA75GR6ZTv5JOv90Vq8tKh\n'
        'KC7YQnhDIo2hM0HVziTEk5R4UQBWa0CKytFMbTONY2msEDwX9iA0x7F5Lgj0X8eD\n'
        '4ZMsYqLzqjWMekLC8bjhxc+EuPo9Dygu3mJ2VgRC7XhlFpmdo5NN8J2E7B/CNB3R\n'
        '4hOcMMZNZdi0xLtFoTfwU61UPfFX14mV2laqLbvDEfQLJhUTDeFFV8EN5Z4H1ttL\n'
        'P3sMXJvc3EvM0JiDVj4l1TWFUHHzeFgCA1Im0lv8i7PFrgW7nyMfK9uDSsUmIp7k\n'
        '6ai4tVzwkTmV5PsriP1ju88Lo3MB4/sUmDv/JmlZ9YyzTO3Po8Uz3Aeq9HJWyBWH\n'
        'AQIDAQAB\n'
        '-----END PUBLIC KEY-----')

    hello_world = b'hello, world'

    hello_world_sig = (
        b'\x63\xa0\x70\xd2\xe4\xd4\x6b\x8a\xa2\x59\x27\x5f\x00\x69'
        b'\x1e\x3c\x50\xed\x50\x13\x09\x80\xe3\x47\x4e\x14\xb5\x7c'
        b'\x07\x26\x4e\x20\x74\xea\x0e\xf8\xda\xff\x1e\x57\x8c\x67'
        b'\x76\x73\xaa\xea\x0f\x0a\xe7\xa2\xe3\x88\xfc\x09\x87\x36'
        b'\x01\x3a\xb7\x4c\x40\xe0\xf4\x54\xc5\xf1\xaa\xb2\x1d\x7f'
        b'\xb6\xd3\xa8\xdd\x28\x69\x8b\x88\xe4\x42\x1e\x48\x3e\x1f'
        b'\xe2\x2b\x3c\x7c\x85\x11\xe9\x59\xd7\xf3\xc2\x21\xd3\x55'
        b'\xcb\x9c\x3c\x93\xcc\x20\xdf\x64\x81\xd0\x0d\xbf\x8e\x8d'
        b'\x47\xec\x1d\x9e\x27\xec\x12\xed\x8b\x5f\xd6\x1d\xec\x8d'
        b'\x77\x5a\x58\x8a\x24\xb6\x0f\x12\xb7\x51\xef\x7d\x85\x0f'
        b'\x49\x39\x02\x81\x15\x08\x70\xd6\xe0\x0b\x31\xff\x5f\xf9'
        b'\xd1\x92\x38\x59\x8c\x22\x9c\xbb\xbf\xcf\x85\x34\xe2\x47'
        b'\xf5\xe2\xaa\xb4\x62\x33\x3c\x13\x78\x33\x87\x08\x9e\xb5'
        b'\xbc\x5d\xc1\xbf\x79\x7c\xfa\x5f\x06\x6a\x3b\x17\x40\x09'
        b'\xb9\x09\xbf\x32\xc3\x00\xe2\xbc\x91\x77\x14\xa5\x23\xf5'
        b'\xf5\xf1\x09\x12\x38\xda\x3b\x6a\x82\x81\x7b\x5e\x1c\xcb'
        b'\xaa\x36\x9b\x08\x36\x03\x14\x96\xa3\x31\x39\x59\x16\x75'
        b'\xc9\xb6\x66\x94\x1b\x97\xff\xc8\xa1\xe3\x21\x35\x23\x06'
        b'\x4c\x9b\xf4\xee')

    def test_signer(self):
        with self.assertRaises(ValueError):
            signer = RSAX931Signer('bogus key data')
        with self.assertRaises(ValueError):
            signer = RSAX931Signer(RSAX931Test.pubkey_data)

        signer = RSAX931Signer(RSAX931Test.privkey_data)
        with self.assertRaises(ValueError):
            signer.sign('x'*255)  # message too long

        sig = signer.sign(RSAX931Test.hello_world)
        self.assertEqual(RSAX931Test.hello_world_sig, sig)

    def test_verifier(self):
        with self.assertRaises(ValueError):
            verifier = RSAX931Verifier('bogus key data')
        with self.assertRaises(ValueError):
            verifier = RSAX931Verifier(RSAX931Test.privkey_data)

        verifier = RSAX931Verifier(RSAX931Test.pubkey_data)
        with self.assertRaises(ValueError):
            verifier.verify('')
        with self.assertRaises(ValueError):
            verifier.verify(RSAX931Test.hello_world_sig + b'junk')

        msg = verifier.verify(RSAX931Test.hello_world_sig)
        self.assertEqual(RSAX931Test.hello_world, msg)
