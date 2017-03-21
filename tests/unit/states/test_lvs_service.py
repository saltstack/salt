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
import salt.states.lvs_service as lvs_service

lvs_service.__salt__ = {}
lvs_service.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LvsServiceTestCase(TestCase):
    '''
    Test cases for salt.states.lvs_service
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure that the named service is present.
        '''
        name = 'lvsrs'

        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        mock_check = MagicMock(side_effect=[True, True, True, False, True,
                                            False, True, False, False, False,
                                            False])
        mock_edit = MagicMock(side_effect=[True, False])
        mock_add = MagicMock(side_effect=[True, False])
        with patch.dict(lvs_service.__salt__, {'lvs.check_service': mock_check,
                                               'lvs.edit_service': mock_edit,
                                               'lvs.add_service': mock_add}):
            with patch.dict(lvs_service.__opts__, {'test': True}):
                comt = ('LVS Service lvsrs is present')
                ret.update({'comment': comt})
                self.assertDictEqual(lvs_service.present(name), ret)

                comt = ('LVS Service lvsrs is present but some '
                        'options should update')
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(lvs_service.present(name), ret)

            with patch.dict(lvs_service.__opts__, {'test': False}):
                comt = ('LVS Service lvsrs has been updated')
                ret.update({'comment': comt, 'result': True,
                            'changes': {'lvsrs': 'Update'}})
                self.assertDictEqual(lvs_service.present(name), ret)

                comt = ('LVS Service lvsrs update failed')
                ret.update({'comment': comt, 'result': False, 'changes': {}})
                self.assertDictEqual(lvs_service.present(name), ret)

            with patch.dict(lvs_service.__opts__, {'test': True}):
                comt = ('LVS Service lvsrs is not present and needs'
                        ' to be created')
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(lvs_service.present(name), ret)

            with patch.dict(lvs_service.__opts__, {'test': False}):
                comt = ('LVS Service lvsrs has been created')
                ret.update({'comment': comt, 'result': True,
                            'changes': {'lvsrs': 'Present'}})
                self.assertDictEqual(lvs_service.present(name), ret)

                comt = ('LVS Service lvsrs create failed(False)')
                ret.update({'comment': comt, 'result': False, 'changes': {}})
                self.assertDictEqual(lvs_service.present(name), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure the LVS Real Server in specified service is absent.
        '''
        name = 'lvsrs'

        ret = {'name': name,
               'result': None,
               'comment': '',
               'changes': {}}

        mock_check = MagicMock(side_effect=[True, True, True, False])
        mock_delete = MagicMock(side_effect=[True, False])
        with patch.dict(lvs_service.__salt__,
                        {'lvs.check_service': mock_check,
                         'lvs.delete_service': mock_delete}):
            with patch.dict(lvs_service.__opts__, {'test': True}):
                comt = ('LVS Service lvsrs is present and needs to be removed')
                ret.update({'comment': comt})
                self.assertDictEqual(lvs_service.absent(name), ret)

            with patch.dict(lvs_service.__opts__, {'test': False}):
                comt = ('LVS Service lvsrs has been removed')
                ret.update({'comment': comt, 'result': True,
                            'changes': {'lvsrs': 'Absent'}})
                self.assertDictEqual(lvs_service.absent(name), ret)

                comt = ('LVS Service lvsrs removed failed(False)')
                ret.update({'comment': comt, 'result': False, 'changes': {}})
                self.assertDictEqual(lvs_service.absent(name), ret)

            comt = ('LVS Service lvsrs is not present, so it cannot be removed')
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(lvs_service.absent(name), ret)
