# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

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
import salt.modules.moosefs as moosefs


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MoosefsTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.moosefs
    '''

    def setup_loader_modules(self):
        return {moosefs: {}}

    # 'dirinfo' function tests: 1i

    def test_dirinfo(self):
        '''
        Test if it return information on a directory located on the Moose
        '''
        mock = MagicMock(return_value={'stdout': 'Salt:salt'})
        with patch.dict(moosefs.__salt__, {'cmd.run_all': mock}):
            self.assertDictEqual(moosefs.dirinfo('/tmp/salt'), {'Salt': 'salt'})

    # 'fileinfo' function tests: 1

    def test_fileinfo(self):
        '''
        Test if it returns information on a file located on the Moose
        '''
        mock = MagicMock(return_value={'stdout': ''})
        with patch.dict(moosefs.__salt__, {'cmd.run_all': mock}):
            self.assertDictEqual(moosefs.fileinfo('/tmp/salt'), {})

    # 'mounts' function tests: 1

    def test_mounts(self):
        '''
        Test if it returns a list of current MooseFS mounts
        '''
        mock = MagicMock(return_value={'stdout': ''})
        with patch.dict(moosefs.__salt__, {'cmd.run_all': mock}):
            self.assertDictEqual(moosefs.mounts(), {})

    # 'getgoal' function tests: 1

    def test_getgoal(self):
        '''
        Test if it returns goal(s) for a file or directory
        '''
        mock = MagicMock(return_value={'stdout': 'Salt: salt'})
        with patch.dict(moosefs.__salt__, {'cmd.run_all': mock}):
            self.assertDictEqual(moosefs.getgoal('/tmp/salt'), {'goal': 'salt'})
