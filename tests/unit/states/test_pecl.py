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
from salt.states import pecl

pecl.__salt__ = {}
pecl.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PeclTestCase(TestCase):
    '''
    Test cases for salt.states.pecl
    '''
    # 'installed' function tests: 1

    def test_installed(self):
        '''
        Test to make sure that a pecl extension is installed.
        '''
        name = 'mongo'
        ver = '1.0.1'

        ret = {'name': name,
               'result': None,
               'comment': '',
               'changes': {}}

        mock_lst = MagicMock(return_value={name: 'stable'})
        mock_t = MagicMock(return_value=True)
        with patch.dict(pecl.__salt__, {'pecl.list': mock_lst,
                                        'pecl.install': mock_t}):
            comt = ('Pecl extension {0} is already installed.'.format(name))
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(pecl.installed(name), ret)

            with patch.dict(pecl.__opts__, {'test': True}):
                comt = ('Pecl extension mongo-1.0.1 would have been installed')
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(pecl.installed(name, version=ver), ret)

            with patch.dict(pecl.__opts__, {'test': False}):
                comt = ('Pecl extension mongo-1.0.1 was successfully installed')
                ret.update({'comment': comt, 'result': True,
                            'changes': {'mongo-1.0.1': 'Installed'}})
                self.assertDictEqual(pecl.installed(name, version=ver), ret)

    # 'removed' function tests: 1

    def test_removed(self):
        '''
        Test to make sure that a pecl extension is not installed.
        '''
        name = 'mongo'

        ret = {'name': name,
               'result': None,
               'comment': '',
               'changes': {}}

        mock_lst = MagicMock(side_effect=[{}, {name: 'stable'},
                                          {name: 'stable'}])
        mock_t = MagicMock(return_value=True)
        with patch.dict(pecl.__salt__, {'pecl.list': mock_lst,
                                        'pecl.uninstall': mock_t}):
            comt = ('Pecl extension {0} is not installed.'.format(name))
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(pecl.removed(name), ret)

            with patch.dict(pecl.__opts__, {'test': True}):
                comt = ('Pecl extension mongo would have been removed')
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(pecl.removed(name), ret)

            with patch.dict(pecl.__opts__, {'test': False}):
                comt = ('Pecl extension mongo was successfully removed.')
                ret.update({'comment': comt, 'result': True,
                            'changes': {name: 'Removed'}})
                self.assertDictEqual(pecl.removed(name), ret)
