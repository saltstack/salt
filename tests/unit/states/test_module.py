# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas (nicole@saltstack.com)`
'''

# Import Python Libs
from __future__ import absolute_import
from inspect import ArgSpec

# Import Salt Libs
from salt.states import module

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

CMD = 'foo.bar'


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
    loader_module = module

    def loader_module_globals(self):
        return {
            '__opts__': {'test': False},
            '__salt__': {CMD: MagicMock()}
        }

    aspec = ArgSpec(args=['hello', 'world'],
                    varargs=None,
                    keywords=None,
                    defaults=False)

    def test_run_module_not_available(self):
        '''
        Tests the return of module.run state when the module function is not available.
        :return:
        '''
        with patch.dict(module.__salt__, {}, clear=True):
            with patch.dict(module.__opts__, {'use_superseded': ['module.run']}):
                ret = module.run(**{CMD: None})
                assert ret['comment'] == "Unavailable function: {0}.".format(CMD)
                assert not ret['result']

    def test_run_testmode(self):
        '''
        Tests the return of the module.run state when test=True is passed.
        :return:
        '''
        with patch.dict(module.__opts__, {'test': True, 'use_superseded': ['module.run']}):
            ret = module.run(**{CMD: None})
            assert ret['comment'] == "Function {0} to be executed.".format(CMD)
            assert ret['result']

    def test_run_missing_arg(self):
        '''
        Tests the return of module.run state when arguments are missing
        :return:
        '''
        with patch.dict(module.__salt__, {CMD: _mocked_func_named}):
            with patch.dict(module.__opts__, {'use_superseded': ['module.run']}):
                ret = module.run(**{CMD: None})
                assert ret['comment'] == "'{0}' failed: Missing arguments: name".format(CMD)

    def test_run_correct_arg(self):
        '''
        Tests the return of module.run state when arguments are correct
        :return:
        '''
        with patch.dict(module.__salt__, {CMD: _mocked_func_named}):
            with patch.dict(module.__opts__, {'use_superseded': ['module.run']}):
                ret = module.run(**{CMD: [{'name': 'Fred'}]})
                assert ret['comment'] == '{0}: Success'.format(CMD)
                assert ret['result']

    def test_run_unexpected_keywords(self):
        with patch.dict(module.__salt__, {CMD: _mocked_func_args}):
            with patch.dict(module.__opts__, {'use_superseded': ['module.run']}):
                ret = module.run(**{CMD: [{'foo': 'bar'}]})
                assert ret['comment'] == "'{0}' failed: {1}() got an unexpected keyword argument " \
                                         "'foo'".format(CMD, module.__salt__[CMD].__name__)
                assert not ret['result']

    def test_run_args(self):
        '''
        Test unnamed args.
        :return:
        '''
        with patch.dict(module.__salt__, {CMD: _mocked_func_args}):
            with patch.dict(module.__opts__, {'use_superseded': ['module.run']}):
                assert module.run(**{CMD: ['foo', 'bar']})['result']

    def test_run_none_return(self):
        '''
        Test handling of a broken function that returns None.
        :return:
        '''
        with patch.dict(module.__salt__, {CMD: _mocked_none_return}):
            with patch.dict(module.__opts__, {'use_superseded': ['module.run']}):
                assert module.run(**{CMD: None})['result']

    def test_run_typed_return(self):
        '''
        Test handling of a broken function that returns any type.
        :return:
        '''
        for val in [1, 0, 'a', '', (1, 2,), (), [1, 2], [], {'a': 'b'}, {}, True, False]:
            with patch.dict(module.__salt__, {CMD: _mocked_none_return}):
                with patch.dict(module.__opts__, {'use_superseded': ['module.run']}):
                    assert module.run(**{CMD: [{'ret': val}]})['result']

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
                    assert module.run(**{f_name: None})['result']

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

    @patch('salt.utils.args.get_function_argspec', MagicMock(return_value=aspec))
    def test_module_run_missing_arg(self):
        '''
        Tests the return of module.run state when arguments are missing
        '''
        ret = module._run(CMD)
        comment = 'The following arguments are missing:'
        self.assertIn(comment, ret['comment'])
        self.assertIn('world', ret['comment'])
        self.assertIn('hello', ret['comment'])
