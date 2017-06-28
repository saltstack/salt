# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.debconfmod as debconfmod
import os


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DebconfmodTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.DebconfmodTestCase
    '''
    def setup_loader_modules(self):
        return {debconfmod: {}}

    def test_get_selections(self):
        '''
        Test for Answers to debconf questions for all packages
        '''
        mock = MagicMock(return_value=[])
        with patch.dict(debconfmod.__salt__, {'cmd.run_stdout': mock}):
            with patch.object(debconfmod, '_unpack_lines', mock):
                self.assertEqual(debconfmod.get_selections(False), {})

    def test_show(self):
        '''
        Test for Answers to debconf questions for a package
        '''
        mock = MagicMock(return_value={})
        with patch.object(debconfmod, 'get_selections', mock):
            self.assertEqual(debconfmod.show('name'), None)

    def test_set_(self):
        '''
        Test for Set answers to debconf questions for a package.
        '''
        mock = MagicMock(return_value=None)
        with patch.object(os, 'write', mock):
            with patch.object(os, 'close', mock):
                with patch.object(debconfmod, '_set_file', mock):
                    with patch.object(os, 'unlink', mock):
                        self.assertTrue(debconfmod.set_('package',
                                                        'question',
                                                        'type', 'value'))

    def test_set_template(self):
        '''
        Test for Set answers to debconf questions from a template.
        '''
        mock = MagicMock(return_value='A')
        with patch.dict(debconfmod.__salt__, {'cp.get_template': mock}):
            with patch.object(debconfmod, 'set_file', mock):
                self.assertEqual(debconfmod.set_template('path',
                                                         'template',
                                                         'context',
                                                         'defaults',
                                                         'saltenv'), 'A')

    def test_set_file(self):
        '''
        Test for Set answers to debconf questions from a file.
        '''
        mock = MagicMock(return_value='A')
        with patch.dict(debconfmod.__salt__, {'cp.cache_file': mock}):
            mock = MagicMock(return_value=None)
            with patch.object(debconfmod, '_set_file', mock):
                self.assertTrue(debconfmod.set_file('path'))

        mock = MagicMock(return_value=False)
        with patch.dict(debconfmod.__salt__, {'cp.cache_file': mock}):
            mock = MagicMock(return_value=None)
            with patch.object(debconfmod, '_set_file', mock):
                self.assertFalse(debconfmod.set_file('path'))
