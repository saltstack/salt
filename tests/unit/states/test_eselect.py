# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
from salt.states import eselect

eselect.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class EselectTestCase(TestCase):
    '''
    Test cases for salt.states.eselect
    '''
    # 'set_' function tests: 1

    def test_set_(self):
        '''
        Test to verify that the given module is set to the given target
        '''
        name = 'myeselect'
        target = 'hardened/linux/amd64'

        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        mock = MagicMock(return_value=target)
        with patch.dict(eselect.__salt__, {'eselect.get_current_target': mock}):
            comt = ('Target \'{0}\' is already set on \'{1}\' module.'
                    .format(target, name))
            ret.update({'comment': comt})
            self.assertDictEqual(eselect.set_(name, target), ret)
