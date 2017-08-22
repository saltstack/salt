# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
from collections import namedtuple

# Import Salt Libs
import salt.utils.args

# Import Salt Testing Libs
from tests.support.unit import TestCase


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
