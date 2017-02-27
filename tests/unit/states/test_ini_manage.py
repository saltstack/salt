# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON,
    patch)

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

        original = {'mysection': {'first': 'who is on',
                                  'second': 'what is on',
                                  'third': "I don't know"}}
        desired = {'mysection': {'first': 'who is on',
                                 'second': 'what is on'}}
        changes = {'mysection': {'first': 'who is on',
                                 'second': 'what is on',
                                 'third': {'after': None, 'before': "I don't know"}}}
        with patch.dict(ini_manage.__salt__, {'ini.get_section': MagicMock(return_value=original['mysection'])}):
            with patch.dict(ini_manage.__salt__, {'ini.remove_option': MagicMock(return_value='third')}):
                with patch.dict(ini_manage.__salt__, {'ini.get_option': MagicMock(return_value="I don't know")}):
                    with patch.dict(ini_manage.__salt__, {'ini.set_option': MagicMock(return_value=desired)}):
                        with patch.dict(ini_manage.__opts__, {'test': False}):
                            comt = ('Changes take effect')
                            ret.update({'comment': comt, 'result': True, 'changes': changes})
                            self.assertDictEqual(ini_manage.options_present(name, desired, strict=True), ret)

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
