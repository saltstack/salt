# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    tests.unit.utils.format_call_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test `salt.utils.format_call`
'''

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.unit import TestCase

# Import salt libs
from salt.utils import format_call
from salt.exceptions import SaltInvocationError


class TestFormatCall(TestCase):
    def test_simple_args_passing(self):
        def foo(one, two=2, three=3):
            pass

        self.assertEqual(
            format_call(foo, dict(one=10, two=20, three=30)),
            {'args': [10], 'kwargs': dict(two=20, three=30)}
        )
        self.assertEqual(
            format_call(foo, dict(one=10, two=20)),
            {'args': [10], 'kwargs': dict(two=20, three=3)}
        )
        self.assertEqual(
            format_call(foo, dict(one=2)),
            {'args': [2], 'kwargs': dict(two=2, three=3)}
        )

    def test_mimic_typeerror_exceptions(self):
        def foo(one, two=2, three=3):
            pass

        def foo2(one, two, three=3):
            pass

        with self.assertRaisesRegex(
                SaltInvocationError,
                r'foo takes at least 1 argument \(0 given\)'):
            format_call(foo, dict(two=3))

        with self.assertRaisesRegex(
                TypeError,
                r'foo2 takes at least 2 arguments \(1 given\)'):
            format_call(foo2, dict(one=1))
