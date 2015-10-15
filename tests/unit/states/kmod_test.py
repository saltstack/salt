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
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure that the specified kernel module is loaded.
        '''
        name = 'kvm_amd'

        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=[[name], [], [], [], [], [name], [],
                                      [name]])
        mock_t = MagicMock(side_effect=[[name], name])
        with patch.dict(kmod.__salt__, {'kmod.mod_list': mock,
                                        'kmod.available': mock,
                                        'kmod.load': mock_t}):
            comt = ('Kernel module {0} is already present'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(kmod.present(name), ret)

            with patch.dict(kmod.__opts__, {'test': True}):
                comt = ('Module {0} is set to be loaded'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(kmod.present(name), ret)

            with patch.dict(kmod.__opts__, {'test': False}):
                comt = ('Kernel module {0} is unavailable'.format(name))
                ret.update({'comment': comt, 'result': False})
                self.assertDictEqual(kmod.present(name), ret)

                comt = ('Loaded kernel module {0}'.format(name))
                ret.update({'comment': comt, 'result': True,
                            'changes': {'kvm_amd': 'loaded'}})
                self.assertDictEqual(kmod.present(name), ret)

                comt = ('Loaded kernel module {0}'.format(name))
                ret.update({'comment': name, 'changes': {}, 'result': False})
                self.assertDictEqual(kmod.present(name), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to verify that the named kernel module is not loaded.
        '''
        name = 'kvm_amd'

        ret = {'name': name,
               'result': None,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=[[name], [name], [name], []])
        mock_t = MagicMock(side_effect=[[name], ['A']])
        with patch.dict(kmod.__salt__, {'kmod.mod_list': mock,
                                        'kmod.remove': mock_t}):
            with patch.dict(kmod.__opts__, {'test': True}):
                comt = ('Module {0} is set to be unloaded'.format(name))
                ret.update({'comment': comt})
                self.assertDictEqual(kmod.absent(name), ret)

            with patch.dict(kmod.__opts__, {'test': False}):
                comt = ('Removed kernel module {0}'.format(name))
                ret.update({'comment': comt, 'result': True,
                            'changes': {name: 'removed'}})
                self.assertDictEqual(kmod.absent(name), ret)

                comt = ('Module {0} is present but failed to remove'
                        .format(name))
                ret.update({'comment': comt, 'result': False,
                            'changes': {'A': 'removed'}})
                self.assertDictEqual(kmod.absent(name), ret)

            comt = ('Kernel module {0} is already absent'.format(name))
            ret.update({'comment': comt, 'result': True, 'changes': {}})
            self.assertDictEqual(kmod.absent(name), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(KmodTestCase, needs_daemon=False)
