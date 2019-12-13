# -*- coding: utf-8 -*-
'''
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os.path

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

from salt.exceptions import CommandExecutionError

# Import Salt Libs
import salt.states.cmd as cmd


@skipIf(NO_MOCK, NO_MOCK_REASON)
class CmdTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.cmd
    '''
    def setup_loader_modules(self):
        return {cmd: {'__env__': 'base'}}

    # 'mod_run_check' function tests: 1

    def test_mod_run_check(self):
        '''
        Test to execute the onlyif and unless logic.
        '''
        cmd_kwargs = {}
        creates = '/tmp'

        mock = MagicMock(return_value=1)
        with patch.dict(cmd.__salt__, {'cmd.retcode': mock}):
            with patch.dict(cmd.__opts__, {'test': True}):
                ret = {'comment': 'onlyif condition is false', 'result': True,
                       'skip_watch': True}
                self.assertDictEqual(cmd.mod_run_check(cmd_kwargs, '', '', creates), ret)

                self.assertDictEqual(cmd.mod_run_check(cmd_kwargs, {}, '', creates), ret)

        mock = MagicMock(return_value=1)
        with patch.dict(cmd.__salt__, {'cmd.retcode': mock}):
            with patch.dict(cmd.__opts__, {'test': True}):
                ret = {'comment': 'onlyif condition is false: ', 'result': True,
                       'skip_watch': True}
                self.assertDictEqual(cmd.mod_run_check(cmd_kwargs, [''], '', creates), ret)

        mock = MagicMock(return_value=0)
        with patch.dict(cmd.__salt__, {'cmd.retcode': mock}):
            ret = {'comment': 'unless condition is true', 'result': True,
                   'skip_watch': True}
            self.assertDictEqual(cmd.mod_run_check(cmd_kwargs, None, '', creates), ret)

            self.assertDictEqual(cmd.mod_run_check(cmd_kwargs, None, [''], creates), ret)

            self.assertDictEqual(cmd.mod_run_check(cmd_kwargs, None, True, creates), ret)

        with patch.object(os.path, 'exists',
                          MagicMock(sid_effect=[True, True, False])):
            ret = {'comment': '/tmp exists', 'result': True}
            self.assertDictEqual(cmd.mod_run_check(cmd_kwargs, None, None, creates), ret)

            ret = {'comment': 'All files in creates exist', 'result': True}
            self.assertDictEqual(cmd.mod_run_check(cmd_kwargs, None, None, [creates]), ret)

            self.assertTrue(cmd.mod_run_check(cmd_kwargs, None, None, {}))

    # 'wait' function tests: 1

    def test_wait(self):
        '''
        Test to run the given command only if the watch statement calls it.
        '''
        name = 'cmd.script'

        ret = {'name': name,
               'result': True,
               'changes': {},
               'comment': ''}

        self.assertDictEqual(cmd.wait(name), ret)

    # 'wait_script' function tests: 1

    def test_wait_script(self):
        '''
        Test to download a script from a remote source and execute it
        only if a watch statement calls it.
        '''
        name = 'cmd.script'

        ret = {'name': name,
               'result': True,
               'changes': {},
               'comment': ''}

        self.assertDictEqual(cmd.wait_script(name), ret)

    # 'run' function tests: 1

    def test_run(self):
        '''
        Test to run a command if certain circumstances are met.
        '''
        name = 'cmd.script'

        ret = {'name': name,
               'result': False,
               'changes': {},
               'comment': ''}

        with patch.dict(cmd.__opts__, {'test': False}):
            comt = ("Invalidly-formatted 'env' parameter. See documentation.")
            ret.update({'comment': comt})
            self.assertDictEqual(cmd.run(name, env='salt'), ret)

        with patch.dict(cmd.__grains__, {'shell': 'shell'}):
            with patch.dict(cmd.__opts__, {'test': False}):
                mock = MagicMock(side_effect=[CommandExecutionError,
                                              {'retcode': 1}])
                with patch.dict(cmd.__salt__, {'cmd.run_all': mock}):
                    ret.update({'comment': '', 'result': False})
                    self.assertDictEqual(cmd.run(name), ret)

                    ret.update({'comment': 'Command "cmd.script" run',
                                'result': False, 'changes': {'retcode': 1}})
                    self.assertDictEqual(cmd.run(name), ret)

            with patch.dict(cmd.__opts__, {'test': True}):
                comt = ('Command "cmd.script" would have been executed')
                ret.update({'comment': comt, 'result': None, 'changes': {}})
                self.assertDictEqual(cmd.run(name), ret)

            mock = MagicMock(return_value=1)
            with patch.dict(cmd.__salt__, {'cmd.retcode': mock}):
                with patch.dict(cmd.__opts__, {'test': False}):
                    comt = ('onlyif condition is false')
                    ret.update({'comment': comt, 'result': True,
                                'skip_watch': True})
                    self.assertDictEqual(cmd.run(name, onlyif=''), ret)

    def test_run_root(self):
        '''
        Test to run a command with a different root
        '''
        name = 'cmd.script'

        ret = {'name': name,
               'result': False,
               'changes': {},
               'comment': ''}

        with patch.dict(cmd.__grains__, {'shell': 'shell'}):
            with patch.dict(cmd.__opts__, {'test': False}):
                mock = MagicMock(side_effect=[CommandExecutionError,
                                              {'retcode': 1}])
                with patch.dict(cmd.__salt__, {'cmd.run_chroot': mock}):
                    ret.update({'comment': '', 'result': False})
                    self.assertDictEqual(cmd.run(name, root='/mnt'), ret)

                    ret.update({'comment': 'Command "cmd.script" run',
                                'result': False, 'changes': {'retcode': 1}})
                    self.assertDictEqual(cmd.run(name, root='/mnt'), ret)

    # 'script' function tests: 1

    def test_script(self):
        '''
        Test to download a script and execute it with specified arguments.
        '''
        name = 'cmd.script'

        ret = {'name': name,
               'result': False,
               'changes': {},
               'comment': ''}

        with patch.dict(cmd.__opts__, {'test': False}):
            comt = ("Invalidly-formatted 'env' parameter. See documentation.")
            ret.update({'comment': comt})
            self.assertDictEqual(cmd.script(name, env='salt'), ret)

        with patch.dict(cmd.__grains__, {'shell': 'shell'}):
            with patch.dict(cmd.__opts__, {'test': True}):
                comt = ("Command 'cmd.script' would have been executed")
                ret.update({'comment': comt, 'result': None, 'changes': {}})
                self.assertDictEqual(cmd.script(name), ret)

            with patch.dict(cmd.__opts__, {'test': False}):
                mock = MagicMock(side_effect=[CommandExecutionError,
                                              {'retcode': 1}])
                with patch.dict(cmd.__salt__, {'cmd.script': mock}):
                    ret.update({'comment': '', 'result': False})
                    self.assertDictEqual(cmd.script(name), ret)

                    ret.update({'comment': "Command 'cmd.script' run",
                                'result': False, 'changes': {'retcode': 1}})
                    self.assertDictEqual(cmd.script(name), ret)

            mock = MagicMock(return_value=1)
            with patch.dict(cmd.__salt__, {'cmd.retcode': mock}):
                with patch.dict(cmd.__opts__, {'test': False}):
                    comt = ('onlyif condition is false')
                    ret.update({'comment': comt, 'result': True,
                                'skip_watch': True, 'changes': {}})
                    self.assertDictEqual(cmd.script(name, onlyif=''), ret)

    # 'call' function tests: 1

    def test_call(self):
        '''
        Test to invoke a pre-defined Python function with arguments
        specified in the state declaration.
        '''
        name = 'cmd.script'
#         func = 'myfunc'

        ret = {'name': name,
               'result': False,
               'changes': {},
               'comment': ''}

        flag = None

        def func():
            '''
            Mock func method
            '''
            if flag:
                return {}
            else:
                return []

        with patch.dict(cmd.__grains__, {'shell': 'shell'}):
            flag = True
            self.assertDictEqual(cmd.call(name, func), ret)

            flag = False
            comt = ('onlyif condition is false')
            ret.update({'comment': '', 'result': False,
                        'changes': {'retval': []}})
            self.assertDictEqual(cmd.call(name, func), ret)

            mock = MagicMock(return_value=1)
            with patch.dict(cmd.__salt__, {'cmd.retcode': mock}):
                with patch.dict(cmd.__opts__, {'test': True}):
                    comt = ('onlyif condition is false')
                    ret.update({'comment': comt, 'skip_watch': True,
                                'result': True, 'changes': {}})
                    self.assertDictEqual(cmd.call(name, func, onlyif=''), ret)

    # 'wait_call' function tests: 1

    def test_wait_call(self):
        '''
        Test to run wait_call.
        '''
        name = 'cmd.script'
        func = 'myfunc'

        ret = {'name': name,
               'result': True,
               'changes': {},
               'comment': ''}

        self.assertDictEqual(cmd.wait_call(name, func), ret)

    # 'mod_watch' function tests: 1

    def test_mod_watch(self):
        '''
        Test to execute a cmd function based on a watch call
        '''
        name = 'cmd.script'

        ret = {'name': name,
               'result': False,
               'changes': {},
               'comment': ''}

        def func():
            '''
            Mock func method
            '''
            return {}

        with patch.dict(cmd.__grains__, {'shell': 'shell'}):
            with patch.dict(cmd.__opts__, {'test': False}):
                mock = MagicMock(return_value={'retcode': 1})
                with patch.dict(cmd.__salt__, {'cmd.run_all': mock}):
                    self.assertDictEqual(cmd.mod_watch(name, sfun='wait',
                                                       stateful=True), ret)

                    comt = ('Command "cmd.script" run')
                    ret.update({'comment': comt, 'changes': {'retcode': 1}})
                    self.assertDictEqual(cmd.mod_watch(name, sfun='wait',
                                                       stateful=False), ret)

                with patch.dict(cmd.__salt__, {'cmd.script': mock}):
                    ret.update({'comment': '', 'changes': {}})
                    self.assertDictEqual(cmd.mod_watch(name, sfun='script',
                                                       stateful=True), ret)

                    comt = ("Command 'cmd.script' run")
                    ret.update({'comment': comt, 'changes': {'retcode': 1}})
                    self.assertDictEqual(cmd.mod_watch(name, sfun='script',
                                                       stateful=False), ret)

                with patch.dict(cmd.__salt__, {'cmd.script': mock}):
                    ret.update({'comment': '', 'changes': {}})
                    self.assertDictEqual(cmd.mod_watch(name, sfun='call',
                                                       func=func), ret)

                    comt = ('cmd.call needs a named parameter func')
                    ret.update({'comment': comt})
                    self.assertDictEqual(cmd.mod_watch(name, sfun='call'), ret)

                comt = ('cmd.salt does not work with the watch requisite,'
                        ' please use cmd.wait or cmd.wait_script')
                ret.update({'comment': comt})
                self.assertDictEqual(cmd.mod_watch(name, sfun='salt'), ret)
