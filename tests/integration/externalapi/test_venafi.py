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
from tests.support.helpers import destructiveTest, expensiveTest
from salt.ext.six.moves import range


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
        return func(self, _random_name(prefix='salt_test_'), *args, **kwargs)
    return wrapper


@destructiveTest
@expensiveTest
class VenafiTest(ShellCase):
    '''
    Test the venafi runner
    '''

    @with_random_name
    def test_gen_key_password(self, name):
        '''
        venafi.gen_key
        '''
        ret = self.run_run_plus(fun='venafi.gen_key',
                                minion_id='{0}.test.saltstack.com'.format(name),
                                dns_name='{0}.test.saltstack.com'.format(name),
                                zone='Internet',
                                password='SecretSauce')
        self.assertEqual(ret['out'][0], '-----BEGIN RSA PRIVATE KEY-----')
        self.assertEqual(ret['out'][1], 'Proc-Type: 4,ENCRYPTED')
        self.assertEqual(ret['out'][-1], '-----END RSA PRIVATE KEY-----')

    @with_random_name
    def test_gen_key_without_password(self, name):
        '''
        venafi.gen_key
        '''
        ret = self.run_run_plus(fun='venafi.gen_key',
                                minion_id='{0}.test.saltstack.com'.format(name),
                                dns_name='{0}.test.saltstack.com'.format(name),
                                zone='Internet')
        self.assertEqual(ret['out'][0], '-----BEGIN RSA PRIVATE KEY-----')
        self.assertNotEqual(ret['out'][1], 'Proc-Type: 4,ENCRYPTED')
        self.assertEqual(ret['out'][-1], '-----END RSA PRIVATE KEY-----')

    @with_random_name
    def test_gen_csr(self, name):
        '''
        venafi.gen_csr
        '''
        ret = self.run_run_plus(fun='venafi.gen_csr',
                                minion_id='{0}.test.saltstack.com'.format(name),
                                dns_name='{0}.test.saltstack.com'.format(name),
                                country='US', state='Utah', loc='Salt Lake City',
                                org='Salt Stack Inc.', org_unit='Testing',
                                zone='Internet', password='SecretSauce')
        self.assertEqual(ret['out'][0], '-----BEGIN CERTIFICATE REQUEST-----')
        self.assertEqual(ret['out'][-1], '-----END CERTIFICATE REQUEST-----')

    @with_random_name
    def test_request(self, name):
        '''
        venafi.request
        '''
        ret = self.run_run_plus(fun='venafi.request',
                                minion_id='{0}.example.com'.format(name),
                                dns_name='{0}.example.com'.format(name),
                                country='US', state='Utah', loc='Salt Lake City',
                                org='Salt Stack Inc.', org_unit='Testing',
                                zone='Internet', password='SecretSauce')
        self.assertTrue('request_id' in ret['return'])
