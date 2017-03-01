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
from salt.states import layman

layman.__salt__ = {}
layman.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LaymanTestCase(TestCase):
    '''
    Test cases for salt.states.layman
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to verify that the overlay is present.
        '''
        name = 'sunrise'

        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=[[name], []])
        with patch.dict(layman.__salt__, {'layman.list_local': mock}):
            comt = ('Overlay {0} already present'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(layman.present(name), ret)

            with patch.dict(layman.__opts__, {'test': True}):
                comt = ('Overlay {0} is set to be added'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(layman.present(name), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to verify that the overlay is absent.
        '''
        name = 'sunrise'

        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=[[], [name]])
        with patch.dict(layman.__salt__, {'layman.list_local': mock}):
            comt = ('Overlay {0} already absent'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(layman.absent(name), ret)

            with patch.dict(layman.__opts__, {'test': True}):
                comt = ('Overlay {0} is set to be deleted'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(layman.absent(name), ret)
