# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
from collections import namedtuple

# Import Salt Libs
from salt.exceptions import SaltInvocationError
import salt.utils.args

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    create_autospec,
    DEFAULT,
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)


class ArgsTestCase(TestCase):
    '''
    TestCase for salt.utils.args module
    '''

    def test_condition_input_string(self):
        '''
        Test passing a jid on the command line
        '''
        cmd = salt.utils.args.condition_input(['*', 'foo.bar', 20141020201325675584], None)
        self.assertIsInstance(cmd[2], str)

    def test_clean_kwargs(self):
        self.assertDictEqual(salt.utils.args.clean_kwargs(foo='bar'), {'foo': 'bar'})
        self.assertDictEqual(salt.utils.args.clean_kwargs(__pub_foo='bar'), {})
        self.assertDictEqual(salt.utils.args.clean_kwargs(__foo_bar='gwar'), {})
        self.assertDictEqual(salt.utils.args.clean_kwargs(foo_bar='gwar'), {'foo_bar': 'gwar'})

    def test_get_function_argspec(self):
        def dummy_func(first, second, third, fourth='fifth'):
            pass

        expected_argspec = namedtuple('ArgSpec', 'args varargs keywords defaults')(
            args=['first', 'second', 'third', 'fourth'], varargs=None, keywords=None, defaults=('fifth',))
        ret = salt.utils.args.get_function_argspec(dummy_func)

        self.assertEqual(ret, expected_argspec)

    def test_parse_kwarg(self):
        ret = salt.utils.args.parse_kwarg('foo=bar')
        self.assertEqual(ret, ('foo', 'bar'))

        ret = salt.utils.args.parse_kwarg('foobar')
        self.assertEqual(ret, (None, None))

    def test_arg_lookup(self):
        def dummy_func(first, second, third, fourth='fifth'):
            pass

        expected_dict = {'args': ['first', 'second', 'third'], 'kwargs': {'fourth': 'fifth'}}
        ret = salt.utils.args.arg_lookup(dummy_func)
        self.assertEqual(expected_dict, ret)

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_format_call(self):
        with patch('salt.utils.args.arg_lookup') as arg_lookup:
            def dummy_func(first=None, second=None, third=None):
                pass

            arg_lookup.return_value = {'args': ['first', 'second', 'third'], 'kwargs': {}}
            get_function_argspec = DEFAULT
            get_function_argspec.return_value = namedtuple('ArgSpec', 'args varargs keywords defaults')(
                args=['first', 'second', 'third', 'fourth'], varargs=None, keywords=None, defaults=('fifth',))

            # Make sure we raise an error if we don't pass in the requisite number of arguments
            self.assertRaises(SaltInvocationError, salt.utils.format_call, dummy_func, {'1': 2})

            # Make sure we warn on invalid kwargs
            ret = salt.utils.format_call(dummy_func, {'first': 2, 'second': 2, 'third': 3})
            self.assertGreaterEqual(len(ret['warnings']), 1)

            ret = salt.utils.format_call(dummy_func, {'first': 2, 'second': 2, 'third': 3},
                                         expected_extra_kws=('first', 'second', 'third'))
            self.assertDictEqual(ret, {'args': [], 'kwargs': {}})

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_argspec_report(self):
        def _test_spec(arg1, arg2, kwarg1=None):
            pass

        sys_mock = create_autospec(_test_spec)
        test_functions = {'test_module.test_spec': sys_mock}
        ret = salt.utils.args.argspec_report(test_functions, 'test_module.test_spec')
        self.assertDictEqual(ret, {'test_module.test_spec':
                                       {'kwargs': True, 'args': None, 'defaults': None, 'varargs': True}})
