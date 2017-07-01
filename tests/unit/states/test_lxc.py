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
    patch)

# Import Salt Libs
import salt.states.lxc as lxc
import salt.utils


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LxcTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.lxc
    '''
    def setup_loader_modules(self):
        return {lxc: {}}

    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to verify the named container if it exist.
        '''
        name = 'web01'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=[False, True, True, True, True, True,
                                      True])
        mock_t = MagicMock(side_effect=[None, True, 'frozen', 'frozen',
                                        'stopped', 'running', 'running'])
        with patch.dict(lxc.__salt__, {'lxc.exists': mock,
                                       'lxc.state': mock_t}):
            comt = ("Clone source 'True' does not exist")
            ret.update({'comment': comt})
            self.assertDictEqual(lxc.present(name, clone_from=True), ret)

            with patch.dict(lxc.__opts__, {'test': True}):
                comt = ("Container 'web01' will be cloned from True")
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(lxc.present(name, clone_from=True), ret)

                comt = ("Container 'web01' already exists")
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(lxc.present(name, clone_from=True), ret)

                comt = ("Container 'web01' would be unfrozen")
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(lxc.present(name, running=True,
                                                 clone_from=True), ret)

                comt = ('Container \'{0}\' would be stopped'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(lxc.present(name, running=False,
                                                 clone_from=True), ret)

                comt = ("Container 'web01' already exists and is stopped")
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(lxc.present(name, running=False,
                                                 clone_from=True), ret)

            with patch.dict(lxc.__opts__, {'test': False}):
                comt = ("Container 'web01' already exists")
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(lxc.present(name, clone_from=True), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure a container is not present, destroying it if present.
        '''
        name = 'web01'

        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=[False, True, True])
        mock_des = MagicMock(return_value={'state': True})
        with patch.dict(lxc.__salt__, {'lxc.exists': mock,
                                       'lxc.destroy': mock_des}):
            comt = ('Container \'{0}\' does not exist'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(lxc.absent(name), ret)

            with patch.dict(lxc.__opts__, {'test': True}):
                comt = ('Container \'{0}\' would be destroyed'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(lxc.absent(name), ret)

            with patch.dict(lxc.__opts__, {'test': False}):
                comt = ('Container \'{0}\' was destroyed'.format(name))
                ret.update({'comment': comt, 'result': True,
                            'changes': {'state': True}})
                self.assertDictEqual(lxc.absent(name), ret)

    # 'running' function tests: 1

    def test_running(self):
        '''
        Test to ensure that a container is running.
        '''
        name = 'web01'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        mock = MagicMock(return_value={'state': {'new': 'stop'}})
        mock_t = MagicMock(side_effect=[None, 'running', 'stopped', 'start'])
        with patch.dict(lxc.__salt__, {'lxc.exists': mock,
                                       'lxc.state': mock_t,
                                       'lxc.start': mock}):
            comt = ('Container \'{0}\' does not exist'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(lxc.running(name), ret)

            comt = ("Container 'web01' is already running")
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(lxc.running(name), ret)

            with patch.dict(lxc.__opts__, {'test': True}):
                comt = ("Container 'web01' would be started")
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(lxc.running(name), ret)

            with patch.dict(lxc.__opts__, {'test': False}):
                comt = ("Unable to start container 'web01'")
                ret.update({'comment': comt, 'result': False, 'changes':
                            {'state': {'new': 'stop', 'old': 'start'}}})
                self.assertDictEqual(lxc.running(name), ret)

    # 'frozen' function tests: 1

    def test_frozen(self):
        '''
        Test to ensure that a container is frozen.
        '''
        name = 'web01'

        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        mock = MagicMock(return_value={'state': {'new': 'stop'}})
        mock_t = MagicMock(side_effect=['frozen', 'stopped', 'stopped'])
        with patch.dict(lxc.__salt__, {'lxc.freeze': mock,
                                       'lxc.state': mock_t}):
            comt = ('Container \'{0}\' is already frozen'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(lxc.frozen(name), ret)

            with patch.dict(lxc.__opts__, {'test': True}):
                comt = ("Container 'web01' would be started and frozen")
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(lxc.frozen(name), ret)

            with patch.dict(lxc.__opts__, {'test': False}):
                comt = ("Unable to start and freeze container 'web01'")
                ret.update({'comment': comt, 'result': False, 'changes':
                            {'state': {'new': 'stop', 'old': 'stopped'}}})
                self.assertDictEqual(lxc.frozen(name), ret)

    # 'stopped' function tests: 1

    def test_stopped(self):
        '''
        Test to ensure that a container is stopped.
        '''
        name = 'web01'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        mock = MagicMock(return_value={'state': {'new': 'stop'}})
        mock_t = MagicMock(side_effect=[None, 'stopped', 'frozen', 'frozen'])
        with patch.dict(lxc.__salt__, {'lxc.stop': mock,
                                       'lxc.state': mock_t}):
            comt = ('Container \'{0}\' does not exist'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(lxc.stopped(name), ret)

            comt = ('Container \'{0}\' is already stopped'.format(name))
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(lxc.stopped(name), ret)

            with patch.dict(lxc.__opts__, {'test': True}):
                comt = ("Container 'web01' would be stopped")
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(lxc.stopped(name), ret)

            with patch.dict(lxc.__opts__, {'test': False}):
                comt = ("Unable to stop container 'web01'")
                ret.update({'comment': comt, 'result': False, 'changes':
                            {'state': {'new': 'stop', 'old': 'frozen'}}})
                self.assertDictEqual(lxc.stopped(name), ret)

    # 'set_pass' function tests: 1

    def test_set_pass(self):
        '''
        Test to execute set_pass func.
        '''
        comment = ('The lxc.set_pass state is no longer supported. Please see '
                   'the LXC states documentation for further information.')
        ret = {'name': 'web01',
               'comment': comment,
               'result': False,
               'changes': {}}

        self.assertDictEqual(lxc.set_pass('web01'), ret)

    # 'edited_conf' function tests: 1

    def test_edited_conf(self):
        '''
        Test to edit LXC configuration options
        '''
        name = 'web01'

        comment = ('{0} lxc.conf will be edited'.format(name))

        ret = {'name': name,
               'result': True,
               'comment': comment,
               'changes': {}}

        with patch.object(salt.utils, 'warn_until', MagicMock()):
            with patch.dict(lxc.__opts__, {'test': True}):
                self.assertDictEqual(lxc.edited_conf(name), ret)

            with patch.dict(lxc.__opts__, {'test': False}):
                mock = MagicMock(return_value={})
                with patch.dict(lxc.__salt__, {'lxc.update_lxc_conf': mock}):
                    self.assertDictEqual(lxc.edited_conf(name),
                                         {'name': 'web01'})
