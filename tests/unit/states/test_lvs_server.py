# -*- coding: utf-8 -*-
'''
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import (
    MagicMock,
    patch)

# Import Salt Libs
import salt.states.lvs_server as lvs_server


class LvsServerTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.lvs_server
    '''
    def setup_loader_modules(self):
        return {lvs_server: {}}

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
        with patch.dict(lvs_server.__salt__, {'lvs.check_server': mock_check,
                                              'lvs.edit_server': mock_edit,
                                              'lvs.add_server': mock_add}):
            with patch.dict(lvs_server.__opts__, {'test': True}):
                comt = ('LVS Server lvsrs in service None(None) is present')
                ret.update({'comment': comt})
                self.assertDictEqual(lvs_server.present(name), ret)

                comt = ('LVS Server lvsrs in service None(None) is present '
                        'but some options should update')
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(lvs_server.present(name), ret)

            with patch.dict(lvs_server.__opts__, {'test': False}):
                comt = ('LVS Server lvsrs in service None(None) '
                        'has been updated')
                ret.update({'comment': comt, 'result': True,
                            'changes': {'lvsrs': 'Update'}})
                self.assertDictEqual(lvs_server.present(name), ret)

                comt = ('LVS Server lvsrs in service None(None) '
                        'update failed(False)')
                ret.update({'comment': comt, 'result': False, 'changes': {}})
                self.assertDictEqual(lvs_server.present(name), ret)

            with patch.dict(lvs_server.__opts__, {'test': True}):
                comt = ('LVS Server lvsrs in service None(None) is not present '
                        'and needs to be created')
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(lvs_server.present(name), ret)

            with patch.dict(lvs_server.__opts__, {'test': False}):
                comt = ('LVS Server lvsrs in service None(None) '
                        'has been created')
                ret.update({'comment': comt, 'result': True,
                            'changes': {'lvsrs': 'Present'}})
                self.assertDictEqual(lvs_server.present(name), ret)

                comt = ('LVS Service lvsrs in service None(None) '
                        'create failed(False)')
                ret.update({'comment': comt, 'result': False, 'changes': {}})
                self.assertDictEqual(lvs_server.present(name), ret)

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
        with patch.dict(lvs_server.__salt__, {'lvs.check_server': mock_check,
                                              'lvs.delete_server': mock_delete}):
            with patch.dict(lvs_server.__opts__, {'test': True}):
                comt = ('LVS Server lvsrs in service None(None) is present'
                        ' and needs to be removed')
                ret.update({'comment': comt})
                self.assertDictEqual(lvs_server.absent(name), ret)

            with patch.dict(lvs_server.__opts__, {'test': False}):
                comt = ('LVS Server lvsrs in service None(None) '
                        'has been removed')
                ret.update({'comment': comt, 'result': True,
                            'changes': {'lvsrs': 'Absent'}})
                self.assertDictEqual(lvs_server.absent(name), ret)

                comt = ('LVS Server lvsrs in service None(None) removed '
                        'failed(False)')
                ret.update({'comment': comt, 'result': False, 'changes': {}})
                self.assertDictEqual(lvs_server.absent(name), ret)

            comt = ('LVS Server lvsrs in service None(None) is not present,'
                    ' so it cannot be removed')
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(lvs_server.absent(name), ret)
