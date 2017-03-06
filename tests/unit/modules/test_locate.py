# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import locate

# Globals
locate.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LocateTestCase(TestCase):
    '''
    Test cases for salt.modules.locate
    '''
    # 'version' function tests: 1

    def test_version(self):
        '''
        Test if it returns the version of locate
        '''
        mock = MagicMock(return_value='mlocate 0.26')
        with patch.dict(locate.__salt__, {'cmd.run': mock}):
            self.assertListEqual(locate.version(), ['mlocate 0.26'])

    # 'stats' function tests: 1

    def test_stats(self):
        '''
        Test if it returns statistics about the locate database
        '''
        ret = {'files': '75,253',
               'directories': '49,252',
               'bytes in file names': '93,214',
               'bytes used to store database': '29,165',
               'database': '/var/lib/mlocate/mlocate.db'}

        mock_ret = '''Database /var/lib/mlocate/mlocate.db:
        49,252 directories 
        75,253 files 
        93,214 bytes in file names 
        29,165 bytes used to store database'''

        with patch.dict(locate.__salt__,
                        {'cmd.run': MagicMock(return_value=mock_ret)}):
            self.assertDictEqual(locate.stats(), ret)

    # 'updatedb' function tests: 1

    def test_updatedb(self):
        '''
        Test if it updates the locate database
        '''
        mock = MagicMock(return_value='')
        with patch.dict(locate.__salt__, {'cmd.run': mock}):
            self.assertListEqual(locate.updatedb(), [])

    # 'locate' function tests: 1

    def test_locate(self):
        '''
        Test if it performs a file lookup.
        '''
        mock = MagicMock(return_value='')
        with patch.dict(locate.__salt__, {'cmd.run': mock}):
            self.assertListEqual(locate.locate('wholename', database='myfile'), [])
