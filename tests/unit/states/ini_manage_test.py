# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.mock import (
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON,
    patch)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import ini_manage

ini_manage.__salt__ = {}
ini_manage.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class IniManageTestCase(TestCase):
    '''
    Test cases for salt.states.ini_manage
    '''
    # 'options_present' function tests: 1

    def test_options_present(self):
        '''
        Test to verify options present in file.
        '''
        name = 'salt'

        ret = {'name': name,
               'result': None,
               'comment': '',
               'changes': {}}

        with patch.dict(ini_manage.__opts__, {'test': True}):
            comt = 'No changes detected.'
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(ini_manage.options_present(name), ret)

        changes = {'first': 'who is on',
                   'second': 'what is on',
                   'third': "I don't know"}
        with patch.dict(ini_manage.__salt__, {'ini.set_option': MagicMock(return_value=changes)}):
            with patch.dict(ini_manage.__opts__, {'test': False}):
                comt = ('Changes take effect')
                ret.update({'comment': comt, 'result': True, 'changes': changes})
                self.assertDictEqual(ini_manage.options_present(name), ret)

    # 'options_absent' function tests: 1

    def test_options_absent(self):
        '''
        Test to verify options absent in file.
        '''
        name = 'salt'

        ret = {'name': name,
               'result': None,
               'comment': '',
               'changes': {}}

        with patch.dict(ini_manage.__opts__, {'test': True}):
            comt = 'No changes detected.'
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(ini_manage.options_absent(name), ret)

        with patch.dict(ini_manage.__opts__, {'test': False}):
            comt = ('No anomaly detected')
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(ini_manage.options_absent(name), ret)

    # 'sections_present' function tests: 1

    def test_sections_present(self):
        '''
        Test to verify sections present in file.
        '''
        name = 'salt'

        ret = {'name': name,
               'result': None,
               'comment': '',
               'changes': {}}

        with patch.dict(ini_manage.__opts__, {'test': True}):
            comt = 'No changes detected.'
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(ini_manage.sections_present(name), ret)

        changes = {'first': 'who is on',
                   'second': 'what is on',
                   'third': "I don't know"}
        with patch.dict(ini_manage.__salt__, {'ini.set_option': MagicMock(return_value=changes)}):
            with patch.dict(ini_manage.__opts__, {'test': False}):
                comt = ('Changes take effect')
                ret.update({'comment': comt, 'result': True, 'changes': changes})
                self.assertDictEqual(ini_manage.sections_present(name), ret)

    # 'sections_absent' function tests: 1

    def test_sections_absent(self):
        '''
        Test to verify sections absent in file.
        '''
        name = 'salt'

        ret = {'name': name,
               'result': None,
               'comment': '',
               'changes': {}}

        with patch.dict(ini_manage.__opts__, {'test': True}):
            comt = 'No changes detected.'
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(ini_manage.sections_absent(name), ret)

        with patch.dict(ini_manage.__opts__, {'test': False}):
            comt = ('No anomaly detected')
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(ini_manage.sections_absent(name), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(IniManageTestCase, needs_daemon=False)
