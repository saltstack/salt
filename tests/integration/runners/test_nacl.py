# -*- coding: utf-8 -*-
'''
Tests for the salt-run command
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.case import ShellCase
from tests.support.unit import skipIf

try:
    import libnacl.secret  # pylint: disable=unused-import
    import libnacl.sealed  # pylint: disable=unused-import
    HAS_LIBNACL = True
except ImportError:
    HAS_LIBNACL = False


@skipIf(not HAS_LIBNACL, 'skipping test_nacl, libnacl is unavailable')
class NaclTest(ShellCase):
    '''
    Test the nacl runner
    '''
    def test_keygen(self):
        '''
        Test keygen
        '''
        # Store the data
        ret = self.run_run_plus(
            'nacl.keygen',
        )
        self.assertIn('pk', ret['return'])
        self.assertIn('sk', ret['return'])

    def test_enc(self):
        '''
        Test keygen
        '''
        # Store the data
        ret = self.run_run_plus(
            'nacl.keygen',
        )
        self.assertIn('pk', ret['return'])
        self.assertIn('sk', ret['return'])
        pk = ret['return']['pk']
        sk = ret['return']['sk']

        unencrypted_data = 'hello'

        # Encrypt with pk
        ret = self.run_run_plus(
            'nacl.enc',
            data=unencrypted_data,
            pk=pk,
        )
        self.assertIn('return', ret)

    def test_enc_dec(self):
        '''
        Store, list, fetch, then flush data
        '''
        # Store the data
        ret = self.run_run_plus(
            'nacl.keygen',
        )
        self.assertIn('pk', ret['return'])
        self.assertIn('sk', ret['return'])
        pk = ret['return']['pk']
        sk = ret['return']['sk']

        unencrypted_data = b'hello'

        # Encrypt with pk
        ret = self.run_run_plus(
            'nacl.enc',
            data=unencrypted_data,
            pk=pk,
        )
        self.assertIn('return', ret)
        encrypted_data = ret['return']

        # Decrypt with sk
        ret = self.run_run_plus(
            'nacl.dec',
            data=encrypted_data,
            sk=sk,
        )
        self.assertIn('return', ret)
        self.assertEqual(unencrypted_data, ret['return'])
