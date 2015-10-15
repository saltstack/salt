# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import lvs_server

lvs_server.__salt__ = {}
lvs_server.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LvsServerTestCase(TestCase):
    '''
    Test cases for salt.states.lvs_server
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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(LvsServerTestCase, needs_daemon=False)
