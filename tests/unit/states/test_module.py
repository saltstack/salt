# -*- coding: utf-8 -*-
'''
    :codeauthor: Nicole Thomas (nicole@saltstack.com)
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
from inspect import ArgSpec
import logging

# Import Salt Libs
import salt.states.module as module

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

log = logging.getLogger(__name__)

CMD = 'foo.bar'

STATE_APPLY_RET = {
    'module_|-test2_|-state.apply_|-run': {
        'comment': 'Module function state.apply executed',
        'name': 'state.apply',
        'start_time': '16:11:48.818932',
        'result': False,
        'duration': 179.439,
        '__run_num__': 0,
        'changes': {
            'ret': {
                'module_|-test3_|-state.apply_|-run': {
                    'comment': 'Module function state.apply executed',
                    'name': 'state.apply',
                    'start_time': '16:11:48.904796',
                    'result': True,
                    'duration': 89.522,
                    '__run_num__': 0,
                    'changes': {
                        'ret': {
                            'module_|-test4_|-cmd.run_|-run': {
                                'comment': 'Module function cmd.run executed',
                                'name': 'cmd.run',
                                'start_time': '16:11:48.988574',
                                'result': True,
                                'duration': 4.543,
                                '__run_num__': 0,
                                'changes': {
                                    'ret': 'Wed Mar  7 16:11:48 CET 2018'
                                },
                                '__id__': 'test4'
                            }
                        }
                    },
                    '__id__': 'test3'
                },
                'module_|-test3_fail_|-test3_fail_|-run': {
                    'comment': 'Module function test3_fail is not available',
                    'name': 'test3_fail',
                    'start_time': '16:11:48.994607',
                    'result': False,
                    'duration': 0.466,
                    '__run_num__': 1,
                    'changes': {},
                    '__id__': 'test3_fail'
                }
            }
        },
        '__id__': 'test2'
    }
}


def _mocked_func_named(name, names=('Fred', 'Swen',)):
    '''
    Mocked function with named defaults.

    :param name:
    :param names:
    :return:
    '''
    return {'name': name, 'names': names}


def _mocked_func_args(*args):
    '''
    Mocked function with args.

    :param args:
    :return:
    '''
    assert args == ('foo', 'bar')
    return {'args': args}


def _mocked_none_return(ret=None):
    '''
    Mocked function returns None
    :return:
    '''
    return ret


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ModuleStateTest(TestCase, LoaderModuleMockMixin):
    '''
    Tests module state (salt/states/module.py)
    '''
    def setup_loader_modules(self):
        return {
            module: {
                '__opts__': {'test': False},
                '__salt__': {CMD: MagicMock()}
            }
        }

    @classmethod
    def setUpClass(cls):
        cls.aspec = ArgSpec(args=['hello', 'world'],
                            varargs=None,
                            keywords=None,
                            defaults=False)

        cls.bspec = ArgSpec(args=[],
                            varargs='names',
                            keywords='kwargs',
                            defaults=None)

    @classmethod
    def tearDownClass(cls):
        del cls.aspec
        del cls.bspec

    def test_run_module_not_available(self):
        '''
        Tests the return of module.run state when the module function is not available.
        :return:
        '''
        with patch.dict(module.__salt__, {}, clear=True):
            with patch.dict(module.__opts__, {'use_superseded': ['module.run']}):
                ret = module.run(**{CMD: None})
                if ret['comment'] != "Unavailable function: {0}.".format(CMD) or ret['result']:
                    self.fail('module.run did not fail as expected: {0}'.format(ret))

    def test_module_run_hidden_varargs(self):
        '''
        Tests the return of module.run state when hidden varargs are used with
        wrong type.
        '''
        with patch('salt.utils.args.get_function_argspec', MagicMock(return_value=self.bspec)):
            ret = module._run(CMD, m_names='anyname')
            comment = "'names' must be a list."
            self.assertEqual(ret['comment'], comment)

    def test_run_testmode(self):
        '''
        Tests the return of the module.run state when test=True is passed.
        :return:
        '''
        with patch.dict(module.__opts__, {'test': True, 'use_superseded': ['module.run']}):
            ret = module.run(**{CMD: None})
            if ret['comment'] != "Function {0} to be executed.".format(CMD) or not ret['result']:
                self.fail('module.run failed: {0}'.format(ret))

    def test_run_missing_arg(self):
        '''
        Tests the return of module.run state when arguments are missing
        :return:
        '''
        with patch.dict(module.__salt__, {CMD: _mocked_func_named}):
            with patch.dict(module.__opts__, {'use_superseded': ['module.run']}):
                ret = module.run(**{CMD: None})
                expected_comment = "'{0}' failed: Function expects 1 parameters, got only 0".format(CMD)
                if ret['comment'] != expected_comment:
                    self.fail('module.run did not fail as expected: {0}'.format(ret))

    def test_run_correct_arg(self):
        '''
        Tests the return of module.run state when arguments are correct
        :return:
        '''
        with patch.dict(module.__salt__, {CMD: _mocked_func_named}):
            with patch.dict(module.__opts__, {'use_superseded': ['module.run']}):
                ret = module.run(**{CMD: ['Fred']})
                if ret['comment'] != '{0}: Success'.format(CMD) or not ret['result']:
                    self.fail('module.run failed: {0}'.format(ret))

    def test_run_state_apply_result_false(self):
        '''
        Tests the 'result' of module.run that calls state.apply execution module
        :return:
        '''
        with patch.dict(module.__salt__, {"state.apply": MagicMock(return_value=STATE_APPLY_RET)}):
            with patch.dict(module.__opts__, {'use_deprecated': ['module.run']}):
                ret = module.run(**{"name": "state.apply", 'mods': 'test2'})
                if ret['result']:
                    self.fail('module.run did not report false result: {0}'.format(ret))

    def test_run_unexpected_keywords(self):
        with patch.dict(module.__salt__, {CMD: _mocked_func_args}):
            with patch.dict(module.__opts__, {'use_superseded': ['module.run']}):
                ret = module.run(**{CMD: [{'foo': 'bar'}]})
                expected_comment = "'{0}' failed: {1}() got an unexpected keyword argument " \
                                   "'foo'".format(CMD, module.__salt__[CMD].__name__)
                if ret['comment'] != expected_comment or ret['result']:
                    self.fail('module.run did not fail as expected: {0}'.format(ret))

    def test_run_args(self):
        '''
        Test unnamed args.
        :return:
        '''
        with patch.dict(module.__salt__, {CMD: _mocked_func_args}):
            with patch.dict(module.__opts__, {'use_superseded': ['module.run']}):
                try:
                    ret = module.run(**{CMD: ['foo', 'bar']})
                except Exception as exc:
                    log.exception('test_run_none_return: raised exception')
                    self.fail('module.run raised exception: {0}'.format(exc))
                if not ret['result']:
                    log.exception(
                        'test_run_none_return: test failed, result: %s',
                        ret
                    )
                    self.fail('module.run failed: {0}'.format(ret))

    def test_run_none_return(self):
        '''
        Test handling of a broken function that returns None.
        :return:
        '''
        with patch.dict(module.__salt__, {CMD: _mocked_none_return}):
            with patch.dict(module.__opts__, {'use_superseded': ['module.run']}):
                try:
                    ret = module.run(**{CMD: None})
                except Exception as exc:
                    log.exception('test_run_none_return: raised exception')
                    self.fail('module.run raised exception: {0}'.format(exc))
                if not ret['result']:
                    log.exception(
                        'test_run_none_return: test failed, result: %s',
                        ret
                    )
                    self.fail('module.run failed: {0}'.format(ret))

    def test_run_typed_return(self):
        '''
        Test handling of a broken function that returns any type.
        :return:
        '''
        for val in [1, 0, 'a', '', (1, 2,), (), [1, 2], [], {'a': 'b'}, {}, True, False]:
            with patch.dict(module.__salt__, {CMD: _mocked_none_return}):
                with patch.dict(module.__opts__, {'use_superseded': ['module.run']}):
                    log.debug('test_run_typed_return: trying %s', val)
                    try:
                        ret = module.run(**{CMD: [{'ret': val}]})
                    except Exception as exc:
                        log.exception('test_run_typed_return: raised exception')
                        self.fail('module.run raised exception: {0}'.format(exc))
                    if not ret['result']:
                        log.exception(
                            'test_run_typed_return: test failed, result: %s',
                            ret
                        )
                        self.fail('module.run failed: {0}'.format(ret))

    def test_run_batch_call(self):
        '''
        Test batch call
        :return:
        '''
        with patch.dict(module.__opts__, {'use_superseded': ['module.run']}):
            with patch.dict(module.__salt__,
                            {'first': _mocked_none_return,
                             'second': _mocked_none_return,
                             'third': _mocked_none_return}, clear=True):
                for f_name in module.__salt__:
                    log.debug('test_run_batch_call: trying %s', f_name)
                    try:
                        ret = module.run(**{f_name: None})
                    except Exception as exc:
                        log.exception('test_run_batch_call: raised exception')
                        self.fail('module.run raised exception: {0}'.format(exc))
                    if not ret['result']:
                        log.exception(
                            'test_run_batch_call: test failed, result: %s',
                            ret
                        )
                        self.fail('module.run failed: {0}'.format(ret))

    def test_module_run_module_not_available(self):
        '''
        Tests the return of module.run state when the module function
        name isn't available
        '''
        with patch.dict(module.__salt__, {}, clear=True):
            ret = module._run(CMD)
            comment = 'Module function {0} is not available'.format(CMD)
            self.assertEqual(ret['comment'], comment)
            self.assertFalse(ret['result'])

    def test_module_run_test_true(self):
        '''
        Tests the return of module.run state when test=True is passed in
        '''
        with patch.dict(module.__opts__, {'test': True}):
            ret = module._run(CMD)
            comment = 'Module function {0} is set to execute'.format(CMD)
            self.assertEqual(ret['comment'], comment)

    def test_module_run_missing_arg(self):
        '''
        Tests the return of module.run state when arguments are missing
        '''
        with patch('salt.utils.args.get_function_argspec', MagicMock(return_value=self.aspec)):
            ret = module._run(CMD)
            comment = 'The following arguments are missing:'
            self.assertIn(comment, ret['comment'])
            self.assertIn('world', ret['comment'])
            self.assertIn('hello', ret['comment'])
