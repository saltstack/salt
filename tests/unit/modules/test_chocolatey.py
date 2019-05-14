# -*- coding: utf-8 -*-
'''
Test for the chocolatey module
'''

# Import Python libs
from __future__ import absolute_import
import os

# Import Salt Libs
import salt.modules.chocolatey as chocolatey

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import (
    MagicMock,
    patch
)

CHOCO_PATH = 'C:\\path\\to\\chocolatey.exe'
CHOCO_PATH_PD = os.path.join(
    os.environ.get('ProgramData'), 'Chocolatey', 'bin', 'chocolatey.exe')
CHOCO_PATH_SD = os.path.join(
    os.environ.get('SystemDrive'), 'Chocolatey', 'bin', 'chocolatey.bat')

MOCK_FALSE = MagicMock(return_value=False)


class ChocolateyTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        return {chocolatey: {
            '__context__': {},
            '__salt__': {}
        }}

    def test__clear_context(self):
        context = {'chocolatey._yes': ['--yes'],
                   'chocolatey._path': CHOCO_PATH,
                   'chocolatey._version': '0.9.9'}
        with patch.dict(chocolatey.__context__, context):
            chocolatey._clear_context()
            # Did it clear all chocolatey items?
            self.assertEqual(chocolatey.__context__, {})

    def test__yes_context(self):
        with patch.dict(chocolatey.__context__, {'chocolatey._yes': ['--yes']}):
            result = chocolatey._yes()
            expected = ['--yes']
            # Did it return correctly
            self.assertListEqual(result, expected)
            # Did it populate __context__
            self.assertEqual(chocolatey.__context__['chocolatey._yes'],
                             expected)

    def test__yes_version_greater(self):
        mock_version = MagicMock(return_value='10.0.0')
        with patch('salt.modules.chocolatey.chocolatey_version', mock_version):
            result = chocolatey._yes()
            expected = ['--yes']
            # Did it return correctly
            self.assertListEqual(result, expected)
            # Did it populate __context__
            self.assertEqual(chocolatey.__context__['chocolatey._yes'],
                             expected)

    def test__yes_version_less_than(self):
        mock_version = MagicMock(return_value='0.9.0')
        with patch('salt.modules.chocolatey.chocolatey_version', mock_version):
            result = chocolatey._yes()
            expected = []
            # Did it return correctly
            self.assertListEqual(result, expected)
            # Did it populate __context__
            self.assertEqual(chocolatey.__context__['chocolatey._yes'],
                             expected)

    def test__find_chocolatey_context(self):
        with patch.dict(chocolatey.__context__,
                        {'chocolatey._path': CHOCO_PATH}):
            result = chocolatey._find_chocolatey()
            expected = CHOCO_PATH
            self.assertEqual(result, expected)

    def test__find_chocolatey_which(self):
        mock_which = MagicMock(return_value=CHOCO_PATH)
        with patch.dict(chocolatey.__salt__, {'cmd.which': mock_which}):
            result = chocolatey._find_chocolatey()
            expected = CHOCO_PATH
            # Does it return the correct path
            self.assertEqual(result, expected)
            # Does it populate __context__
            self.assertEqual(chocolatey.__context__['chocolatey._path'],
                             expected)

    def test__find_chocolatey_programdata(self):
        with patch.dict(chocolatey.__salt__, {'cmd.which': MOCK_FALSE}),\
                patch('os.path.isfile', MagicMock(return_value=True)):
            result = chocolatey._find_chocolatey()
            expected = CHOCO_PATH_PD
            # Does it return the correct path
            self.assertEqual(result, expected)
            # Does it populate __context__
            self.assertEqual(chocolatey.__context__['chocolatey._path'],
                             expected)

    def test__find_chocolatey_systemdrive(self):
        with patch.dict(chocolatey.__salt__, {'cmd.which': MOCK_FALSE}),\
                patch('os.path.isfile', MagicMock(side_effect=[False, True])):
            result = chocolatey._find_chocolatey()
            expected = CHOCO_PATH_SD
            # Does it return the correct path
            self.assertEqual(result, expected)
            # Does it populate __context__
            self.assertEqual(chocolatey.__context__['chocolatey._path'],
                             expected)

