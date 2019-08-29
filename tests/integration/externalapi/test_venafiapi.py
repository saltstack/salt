# -*- coding: utf-8 -*-
'''
Tests for the salt-run command
'''
# Import Python libs
from __future__ import absolute_import
import functools
import random
import string

# Import Salt Testing libs
from tests.support.case import ShellCase
from salt.ext.six.moves import range
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import serialization
import pytest

def _random_name(prefix=''):
    ret = prefix
    for _ in range(8):
        ret += random.choice(string.ascii_lowercase)
    return ret


def with_random_name(func):
    '''
    generate a randomized name for a container
    '''

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        name = _random_name(prefix='salt_')
        return func(self, _random_name(prefix='salt-test-'), *args, **kwargs)

    return wrapper


# @destructiveTest
# @expensiveTest
class VenafiTest(ShellCase):
    '''
    Test the venafi runner
    '''

    @with_random_name
    def test_request(self, name):
        '''
        venafi.request
        '''
        print("Using venafi config:", self.master_opts['venafi'])
        cn = '{0}.example.com'.format(name)
        ret = self.run_run_plus(fun='venafi.request',
                                minion_id=cn,
                                dns_name=cn,
                                zone='Default')
        cert_output = ret['return'][0]
        if not cert_output:
            pytest.fail('venafi_certificate not found in output_value')

        print("Testing certificate:\n", cert_output)
        cert = x509.load_pem_x509_certificate(cert_output.encode(), default_backend())
        assert isinstance(cert, x509.Certificate)
        assert cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME) == [
            x509.NameAttribute(
                NameOID.COMMON_NAME, cn
            )
        ]

        pkey_output = ret['return'][1]
        print("Testing pkey:\n", pkey_output)
        if not pkey_output:
            pytest.fail('venafi_private key not found in output_value')

        pkey = serialization.load_pem_private_key(pkey_output.encode(), password=None, backend=default_backend())

        pkey_public_key_pem = pkey.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        cert_public_key_pem = cert.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        assert pkey_public_key_pem == cert_public_key_pem
