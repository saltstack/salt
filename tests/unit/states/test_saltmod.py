# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import
import os
import time
import tempfile

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.paths import TMP
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

# Import Salt Libs
import salt.utils.jid
import salt.utils.event
import salt.states.saltmod as saltmod


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltmodTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.saltmod
    '''
    def setup_loader_modules(self):
        return {
            saltmod: {
                '__env__': 'base',
                '__opts__': {
                    '__role': 'master',
                    'file_client': 'remote',
                    'sock_dir': tempfile.mkdtemp(dir=TMP),
                    'transport': 'tcp'
                },
                '__salt__': {'saltutil.cmd': MagicMock()},
                '__orchestration_jid__': salt.utils.jid.gen_jid()
            }
        }

    # 'state' function tests: 1

    def test_state(self):
        '''
        Test to invoke a state run on a given target
        '''
        name = 'state'
        tgt = 'minion1'

        comt = ('Passed invalid value for \'allow_fail\', must be an int')

        ret = {'name': name,
               'changes': {},
               'result': False,
               'comment': comt}

        test_ret = {'name': name,
                    'changes': {},
                    'result': True,
                    'comment': 'States ran successfully.'
                    }

        self.assertDictEqual(saltmod.state(name, tgt, allow_fail='a'), ret)

        comt = ('No highstate or sls specified, no execution made')
        ret.update({'comment': comt})
        self.assertDictEqual(saltmod.state(name, tgt), ret)

        comt = ("Must pass in boolean for value of 'concurrent'")
        ret.update({'comment': comt})
        self.assertDictEqual(saltmod.state(name, tgt, highstate=True,
                                           concurrent='a'), ret)

        ret.update({'comment': comt, 'result': None})
        with patch.dict(saltmod.__opts__, {'test': True}):
            self.assertDictEqual(saltmod.state(name, tgt, highstate=True), test_ret)

        ret.update({'comment': 'States ran successfully. No changes made to silver.', 'result': True, '__jid__': '20170406104341210934'})
        with patch.dict(saltmod.__opts__, {'test': False}):
            mock = MagicMock(return_value={'silver': {'jid': '20170406104341210934', 'retcode': 0, 'ret': {'test_|-notify_me_|-this is a name_|-show_notification': {'comment': 'Notify me', 'name': 'this is a name', 'start_time': '10:43:41.487565', 'result': True, 'duration': 0.35, '__run_num__': 0, '__sls__': 'demo', 'changes': {}, '__id__': 'notify_me'}}, 'out': 'highstate'}})
            with patch.dict(saltmod.__salt__, {'saltutil.cmd': mock}):
                self.assertDictEqual(saltmod.state(name, tgt, highstate=True),
                                     ret)

    # 'function' function tests: 1

    def test_function(self):
        '''
        Test to execute a single module function on a remote
        minion via salt or salt-ssh
        '''
        name = 'state'
        tgt = 'larry'

        comt = ('Function state will be executed'
                ' on target {0} as test=False'.format(tgt))

        ret = {'name': name,
               'changes': {},
               'result': None,
               'comment': comt}

        with patch.dict(saltmod.__opts__, {'test': True}):
            self.assertDictEqual(saltmod.function(name, tgt), ret)

        ret.update({'result': True,
                    'changes': {'out': 'highstate', 'ret': {tgt: ''}},
                    'comment': 'Function ran successfully.'
                              ' Function state ran on {0}.'.format(tgt)})
        with patch.dict(saltmod.__opts__, {'test': False}):
            mock_ret = {'larry': {'ret': '', 'retcode': 0, 'failed': False}}
            mock_cmd = MagicMock(return_value=mock_ret)
            with patch.dict(saltmod.__salt__, {'saltutil.cmd': mock_cmd}):
                self.assertDictEqual(saltmod.function(name, tgt), ret)

    # 'wait_for_event' function tests: 1

    def test_wait_for_event(self):
        '''
        Test to watch Salt's event bus and block until a condition is met
        '''
        name = 'state'
        tgt = 'minion1'

        comt = ('Timeout value reached.')

        ret = {'name': name,
               'changes': {},
               'result': False,
               'comment': comt}

        class Mockevent(object):
            '''
            Mock event class
            '''
            flag = None

            def __init__(self):
                self.full = None

            def get_event(self, full):
                '''
                Mock get_event method
                '''
                self.full = full
                if self.flag:
                    return {'tag': name, 'data': {}}
                return None

        with patch.object(salt.utils.event, 'get_event',
                          MagicMock(return_value=Mockevent())):
            with patch.dict(saltmod.__opts__, {'sock_dir': True,
                                               'transport': True}):
                with patch.object(time, 'time', MagicMock(return_value=1.0)):
                    self.assertDictEqual(saltmod.wait_for_event(name, 'salt',
                                                                timeout=-1.0),
                                         ret)

                    Mockevent.flag = True
                    ret.update({'comment': 'All events seen in 0.0 seconds.',
                                'result': True})
                    self.assertDictEqual(saltmod.wait_for_event(name, ''), ret)

                    ret.update({'comment': 'Timeout value reached.',
                                'result': False})
                    self.assertDictEqual(saltmod.wait_for_event(name, tgt,
                                                                timeout=-1.0),
                                         ret)

    # 'runner' function tests: 1

    def test_runner(self):
        '''
        Test to execute a runner module on the master
        '''
        name = 'state'

        ret = {'changes': True, 'name': 'state', 'result': True,
               'comment': 'Runner function \'state\' executed.',
               '__orchestration__': True}
        runner_mock = MagicMock(return_value={'return': True})

        with patch.dict(saltmod.__salt__, {'saltutil.runner': runner_mock}):
            self.assertDictEqual(saltmod.runner(name), ret)

    # 'wheel' function tests: 1

    def test_wheel(self):
        '''
        Test to execute a wheel module on the master
        '''
        name = 'state'

        ret = {'changes': True, 'name': 'state', 'result': True,
               'comment': 'Wheel function \'state\' executed.',
               '__orchestration__': True}
        wheel_mock = MagicMock(return_value={'return': True})

        with patch.dict(saltmod.__salt__, {'saltutil.wheel': wheel_mock}):
            self.assertDictEqual(saltmod.wheel(name), ret)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class StatemodTests(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        self.tmp_cachedir = tempfile.mkdtemp(dir=TMP)
        return {
            saltmod: {
                '__env__': 'base',
                '__opts__': {
                    'id': 'webserver2',
                    'argv': [],
                    '__role': 'master',
                    'cachedir': self.tmp_cachedir,
                    'extension_modules': os.path.join(self.tmp_cachedir, 'extmods'),
                },
                '__salt__': {'saltutil.cmd': MagicMock()},
                '__orchestration_jid__': salt.utils.jid.gen_jid()
            }
        }

    def test_statemod_state(self):
        ''' Smoke test for for salt.states.statemod.state().  Ensures that we
            don't take an exception if optional parameters are not specified in
            __opts__ or __env__.
        '''
        args = ('webserver_setup', 'webserver2')
        kwargs = {
            'tgt_type': 'glob',
            'fail_minions': None,
            'pillar': None,
            'top': None,
            'batch': None,
            'orchestration_jid': None,
            'sls': 'vroom',
            'queue': False,
            'concurrent': False,
            'highstate': None,
            'expr_form': None,
            'ret': '',
            'ssh': False,
            'timeout': None, 'test': False,
            'allow_fail': 0,
            'saltenv': None,
            'expect_minions': False
        }
        ret = saltmod.state(*args, **kwargs)
        expected = {
            'comment': 'States ran successfully.',
            'changes': {},
            'name': 'webserver_setup',
            'result': True
        }
        self.assertEqual(ret, expected)
