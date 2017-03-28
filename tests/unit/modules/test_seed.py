# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import
import os
import shutil

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)


# Import Salt Libs
import salt.utils.odict
import salt.modules.seed as seed


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SeedTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.seed
    '''
    def setup_loader_modules(self):
        return {seed: {}}

    def test_mkconfig_odict(self):
        with patch.dict(seed.__opts__,
                        {'master': 'foo'}):
            ddd = salt.utils.odict.OrderedDict()
            ddd['b'] = 'b'
            ddd['a'] = 'b'
            data = seed.mkconfig(ddd, approve_key=False)
            with open(data['config']) as fic:
                fdata = fic.read()
                self.assertEqual(fdata, 'b: b\na: b\nmaster: foo\n')

    def test_prep_bootstrap(self):
        '''
        Test to update and get the random script to a random place
        '''
        with patch.dict(seed.__salt__,
                        {'config.gather_bootstrap_script': MagicMock()}):
            with patch.object(os.path, 'join', return_value='A'):
                with patch.object(os.path, 'exists', return_value=True):
                    with patch.object(os, 'chmod', return_value=None):
                        with patch.object(shutil, 'copy', return_value=None):
                            self.assertEqual(seed.prep_bootstrap('mpt'), ('A', 'A'))

    def test_apply_(self):
        '''
        Test to seed a location (disk image, directory, or block device)
        with the minion config, approve the minion's key, and/or install
        salt-minion.
        '''
        mock = MagicMock(side_effect=[False, {'type': 'type',
                                              'target': 'target'},
                                      {'type': 'type', 'target': 'target'},
                                      {'type': 'type', 'target': 'target'}])
        with patch.dict(seed.__salt__, {'file.stats': mock}):
            self.assertEqual(seed.apply_('path'), 'path does not exist')

            with patch.object(seed, '_mount', return_value=False):
                self.assertEqual(seed.apply_('path'),
                                 'target could not be mounted')

            with patch.object(seed, '_mount', return_value=True):
                with patch.object(os.path, 'join', return_value='A'):
                    with patch.object(os, 'makedirs',
                                      MagicMock(side_effect=OSError('f'))):
                        with patch.object(os.path, 'isdir',
                                          return_value=False):
                            self.assertRaises(OSError, seed.apply_, 'p')

                    with patch.object(os, 'makedirs', MagicMock()):
                        with patch.object(seed, 'mkconfig', return_value='A'):
                            with patch.object(seed, '_check_install',
                                              return_value=False):
                                with patch.object(seed, '_umount',
                                                  return_value=None):
                                    self.assertFalse(seed.apply_('path',
                                                                 install=False))
