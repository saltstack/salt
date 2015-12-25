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
from salt.states import kmod

kmod.__salt__ = {}
kmod.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class KmodTestCase(TestCase):
    '''
    Test cases for salt.states.kmod
    '''
    # 'present' function tests: 2

    def test_present(self):
        '''
        Test to ensure that the specified kernel module is loaded.
        '''
        name = 'cheese'
        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        mock_mod_list = MagicMock(return_value=[name])
        with patch.dict(kmod.__salt__, {'kmod.mod_list': mock_mod_list}):
            comment = 'Kernel module {0} is already present'.format(name)
            ret.update({'comment': comment})
            self.assertDictEqual(kmod.present(name), ret)

        mock_mod_list = MagicMock(return_value=[])
        with patch.dict(kmod.__salt__, {'kmod.mod_list': mock_mod_list}):
            with patch.dict(kmod.__opts__, {'test': True}):
                comment = 'Kernel module {0} is set to be loaded'.format(name)
                ret.update({'comment': comment, 'result': None})
                self.assertDictEqual(kmod.present(name), ret)

        mock_mod_list = MagicMock(return_value=[])
        mock_available = MagicMock(return_value=[name])
        mock_load = MagicMock(return_value=[name])
        with patch.dict(kmod.__salt__, {'kmod.mod_list': mock_mod_list,
                                        'kmod.available': mock_available,
                                        'kmod.load': mock_load}):
            with patch.dict(kmod.__opts__, {'test': False}):
                comment = 'Loaded kernel module {0}'.format(name)
                ret.update({'comment': comment,
                            'result': True,
                            'changes': {name: 'loaded'}})
                self.assertDictEqual(kmod.present(name), ret)

    def test_present_multi(self):
        '''
        Test to ensure that multiple kernel modules are loaded.
        '''
        name = 'salted kernel'
        mods = ['cheese', 'crackers']
        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        mock_mod_list = MagicMock(return_value=mods)
        with patch.dict(kmod.__salt__, {'kmod.mod_list': mock_mod_list}):
            comment = 'Kernel modules {0} are already present'.format(', '.join(mods))
            ret.update({'comment': comment})
            self.assertDictEqual(kmod.present(name, mods=mods), ret)

        mock_mod_list = MagicMock(return_value=[])
        with patch.dict(kmod.__salt__, {'kmod.mod_list': mock_mod_list}):
            with patch.dict(kmod.__opts__, {'test': True}):
                comment = 'Kernel modules {0} are set to be loaded'.format(', '.join(mods))
                ret.update({'comment': comment, 'result': None})
                self.assertDictEqual(kmod.present(name, mods=mods), ret)

        mock_mod_list = MagicMock(return_value=[])
        mock_available = MagicMock(return_value=mods)
        mock_load = MagicMock(return_value=mods)
        with patch.dict(kmod.__salt__, {'kmod.mod_list': mock_mod_list,
                                        'kmod.available': mock_available,
                                        'kmod.load': mock_load}):
            with patch.dict(kmod.__opts__, {'test': False}):
                comment = 'Loaded kernel modules {0}'.format(', '.join(mods))
                ret.update({'comment': comment,
                            'result': True,
                            'changes': {mods[0]: 'loaded',
                                        mods[1]: 'loaded'}})
                self.assertDictEqual(kmod.present(name, mods=mods), ret)

    # 'absent' function tests: 2

    def test_absent(self):
        '''
        Test to verify that the named kernel module is not loaded.
        '''
        name = 'cheese'
        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        mock_mod_list = MagicMock(return_value=[name])
        with patch.dict(kmod.__salt__, {'kmod.mod_list': mock_mod_list}):
            with patch.dict(kmod.__opts__, {'test': True}):
                comment = 'Kernel module {0} is set to be removed'.format(name)
                ret.update({'comment': comment, 'result': None})
                self.assertDictEqual(kmod.absent(name), ret)

        mock_mod_list = MagicMock(return_value=[name])
        mock_remove = MagicMock(return_value=[name])
        with patch.dict(kmod.__salt__, {'kmod.mod_list': mock_mod_list,
                                        'kmod.remove': mock_remove}):
            with patch.dict(kmod.__opts__, {'test': False}):
                comment = 'Removed kernel module {0}'.format(name)
                ret.update({'comment': comment,
                            'result': True,
                            'changes': {name: 'removed'}})
                self.assertDictEqual(kmod.absent(name), ret)

        mock_mod_list = MagicMock(return_value=[])
        with patch.dict(kmod.__salt__, {'kmod.mod_list': mock_mod_list}):
            with patch.dict(kmod.__opts__, {'test': True}):
                comment = 'Kernel module {0} is already removed'.format(name)
                ret.update({'comment': comment,
                            'result': True,
                            'changes': {}})
                self.assertDictEqual(kmod.absent(name), ret)

    def test_absent_multi(self):
        '''
        Test to verify that multiple kernel modules are not loaded.
        '''
        name = 'salted kernel'
        mods = ['cheese', 'crackers']
        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        mock_mod_list = MagicMock(return_value=mods)
        with patch.dict(kmod.__salt__, {'kmod.mod_list': mock_mod_list}):
            with patch.dict(kmod.__opts__, {'test': True}):
                comment = 'Kernel modules {0} are set to be removed'.format(', '.join(mods))
                ret.update({'comment': comment, 'result': None})
                self.assertDictEqual(kmod.absent(name, mods=mods), ret)

        mock_mod_list = MagicMock(return_value=mods)
        mock_remove = MagicMock(return_value=mods)
        with patch.dict(kmod.__salt__, {'kmod.mod_list': mock_mod_list,
                                        'kmod.remove': mock_remove}):
            with patch.dict(kmod.__opts__, {'test': False}):
                comment = 'Removed kernel modules {0}'.format(', '.join(mods))
                ret.update({'comment': comment,
                            'result': True,
                            'changes': {mods[0]: 'removed',
                                        mods[1]: 'removed'}})
                self.assertDictEqual(kmod.absent(name, mods=mods), ret)

        mock_mod_list = MagicMock(return_value=[])
        with patch.dict(kmod.__salt__, {'kmod.mod_list': mock_mod_list}):
            with patch.dict(kmod.__opts__, {'test': True}):
                comment = 'Kernel modules {0} are already removed'.format(', '.join(mods))
                ret.update({'comment': comment,
                            'result': True,
                            'changes': {}})
                self.assertDictEqual(kmod.absent(name, mods=mods), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(KmodTestCase, needs_daemon=False)
