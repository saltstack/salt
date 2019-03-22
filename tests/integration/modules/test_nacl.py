# -*- coding: utf-8 -*-
'''
Tests for the nacl execution module
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import salt.utils.stringutils

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf

try:
    import libnacl.secret  # pylint: disable=unused-import
    import libnacl.sealed  # pylint: disable=unused-import
    HAS_LIBNACL = True
except ImportError:
    HAS_LIBNACL = False


@skipIf(not HAS_LIBNACL, 'skipping test_nacl, libnacl is unavailable')
class NaclTest(ModuleCase):
    '''
    Test the nacl runner
    '''
    def test_keygen(self):
        '''
        Test keygen
        '''
        # Store the data
        ret = self.run_function(
            'nacl.keygen',
        )
        self.assertIn('pk', ret)
        self.assertIn('sk', ret)

    def test_enc_dec(self):
        '''
        Generate keys, encrypt, then decrypt.
        '''
        # Store the data
        ret = self.run_function(
            'nacl.keygen',
        )
        self.assertIn('pk', ret)
        self.assertIn('sk', ret)
        pk = ret['pk']
        sk = ret['sk']

        unencrypted_data = salt.utils.stringutils.to_str('hello')

        # Encrypt with pk
        ret = self.run_function(
            'nacl.enc',
            data=unencrypted_data,
            pk=pk,
        )
        encrypted_data = ret

        # Decrypt with sk
        ret = self.run_function(
            'nacl.dec',
            data=encrypted_data,
            sk=sk,
        )
        self.assertEqual(unencrypted_data, ret)
