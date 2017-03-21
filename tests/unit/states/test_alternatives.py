# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

# Import Salt Libs
import salt.states.alternatives as alternatives


@skipIf(NO_MOCK, NO_MOCK_REASON)
class AlternativesTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.alternatives
    '''
    loader_module = alternatives
    # 'install' function tests: 1

    def test_install(self):
        '''
        Test to install new alternative for defined <name>
        '''
        name = 'pager'
        link = '/usr/bin/pager'
        path = '/usr/bin/less'
        priority = 5

        ret = {'name': name,
               'link': link,
               'path': path,
               'priority': priority,
               'result': None,
               'changes': {},
               'comment': ''}

        bad_link = '/bin/pager'
        err = 'the primary link for {0} must be {1}'.format(name, link)

        mock = MagicMock(side_effect=[True, False, False, False])
        mock_out = MagicMock(side_effect=['', err])
        mock_path = MagicMock(return_value=path)
        mock_link = MagicMock(return_value=link)
        with patch.dict(alternatives.__salt__,
                        {'alternatives.check_installed': mock,
                         'alternatives.install': mock_out,
                         'alternatives.show_current': mock_path,
                         'alternatives.show_link': mock_link}):
            comt = ('Alternatives for {0} is already set to {1}'
                   ).format(name, path)
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(alternatives.install(name, link, path,
                                                      priority), ret)

            comt = (('Alternative will be set for {0} to {1} with priority {2}'
                    ).format(name, path, priority))
            ret.update({'comment': comt, 'result': None})
            with patch.dict(alternatives.__opts__, {'test': True}):
                self.assertDictEqual(alternatives.install(name, link, path,
                                                          priority), ret)

            comt = ('Alternative for {0} set to path {1} with priority {2}'
                   ).format(name, path, priority)
            ret.update({'comment': comt, 'result': True,
                        'changes': {'name': name, 'link': link, 'path': path,
                                    'priority': priority}})
            with patch.dict(alternatives.__opts__, {'test': False}):
                self.assertDictEqual(alternatives.install(name, link, path,
                                                          priority), ret)

            comt = ('Alternative for {0} not installed: {1}'
                   ).format(name, err)
            ret.update({'comment': comt, 'result': False,
                        'changes': {}, 'link': bad_link})
            with patch.dict(alternatives.__opts__, {'test': False}):
                self.assertDictEqual(alternatives.install(name, bad_link, path,
                                                          priority), ret)

    # 'remove' function tests: 1

    def test_remove(self):
        '''
        Test to removes installed alternative for defined <name> and <path>
        or fallback to default alternative, if some defined before.
        '''
        name = 'pager'
        path = '/usr/bin/less'

        ret = {'name': name,
               'path': path,
               'result': None,
               'changes': {},
               'comment': ''}

        mock = MagicMock(side_effect=[True, True, True, False, False])
        mock_bool = MagicMock(return_value=True)
        mock_show = MagicMock(side_effect=[False, True, True, False])
        with patch.dict(alternatives.__salt__,
                        {'alternatives.check_exists': mock,
                         'alternatives.show_current': mock_show,
                         'alternatives.remove': mock_bool}):
            comt = ('Alternative for {0} will be removed'.format(name))
            ret.update({'comment': comt})
            with patch.dict(alternatives.__opts__, {'test': True}):
                self.assertDictEqual(alternatives.remove(name, path), ret)

            comt = ('Alternative for {0} removed'.format(name))
            ret.update({'comment': comt, 'result': True})
            with patch.dict(alternatives.__opts__, {'test': False}):
                self.assertDictEqual(alternatives.remove(name, path), ret)

            comt = ('Alternative for pager removed. Falling back to path True')
            ret.update({'comment': comt, 'result': True,
                        'changes': {'path': True}})
            with patch.dict(alternatives.__opts__, {'test': False}):
                self.assertDictEqual(alternatives.remove(name, path), ret)

            comt = ('Alternative for {0} is set to it\'s default path True'
                   ).format(name)
            ret.update({'comment': comt, 'result': True, 'changes': {}})
            self.assertDictEqual(alternatives.remove(name, path), ret)

            comt = ('Alternative for {0} doesn\'t exist').format(name)
            ret.update({'comment': comt, 'result': False})
            self.assertDictEqual(alternatives.remove(name, path), ret)

    # 'auto' function tests: 1

    def test_auto(self):
        '''
        Test to instruct alternatives to use the highest priority
        path for <name>
        '''
        name = 'pager'

        ret = {'name': name,
               'result': True,
               'changes': {},
               'comment': ''}

        mock = MagicMock(side_effect=[' auto mode', ' ', ' '])
        mock_auto = MagicMock(return_value=True)
        with patch.dict(alternatives.__salt__,
                        {'alternatives.display': mock,
                         'alternatives.auto': mock_auto}):
            comt = ('{0} already in auto mode'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(alternatives.auto(name), ret)

            comt = ('{0} will be put in auto mode'.format(name))
            ret.update({'comment': comt, 'result': None})
            with patch.dict(alternatives.__opts__, {'test': True}):
                self.assertDictEqual(alternatives.auto(name), ret)

            ret.update({'comment': '', 'result': True,
                        'changes': {'result': True}})
            with patch.dict(alternatives.__opts__, {'test': False}):
                self.assertDictEqual(alternatives.auto(name), ret)

    # 'set_' function tests: 1

    def test_set(self):
        '''
        Test to sets alternative for <name> to <path>, if <path> is defined
        as an alternative for <name>.
        '''
        name = 'pager'
        path = '/usr/bin/less'

        ret = {'name': name,
               'path': path,
               'result': True,
               'changes': {},
               'comment': ''}

        mock = MagicMock(side_effect=[path, path, ''])
        mock_bool = MagicMock(return_value=True)
        mock_show = MagicMock(side_effect=[path, False, False, False, False])
        with patch.dict(alternatives.__salt__,
                        {'alternatives.display': mock,
                         'alternatives.show_current': mock_show,
                         'alternatives.set': mock_bool}):
            comt = ('Alternative for {0} already set to {1}'.format(name, path))
            ret.update({'comment': comt})
            self.assertDictEqual(alternatives.set_(name, path), ret)

            comt = ('Alternative for {0} will be set to path False'
                   ).format(name)
            ret.update({'comment': comt, 'result': None})
            with patch.dict(alternatives.__opts__, {'test': True}):
                self.assertDictEqual(alternatives.set_(name, path), ret)

            comt = 'Alternative for {0} not updated'.format(name)
            ret.update({'comment': comt, 'result': True})
            with patch.dict(alternatives.__opts__, {'test': False}):
                self.assertDictEqual(alternatives.set_(name, path), ret)

            comt = ('Alternative {0} for {1} doesn\'t exist').format(path, name)
            ret.update({'comment': comt, 'result': False})
            self.assertDictEqual(alternatives.set_(name, path), ret)
