# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.unit import TestCase

# Import salt libs
import salt.returners.sentry_return as sentry


class SentryReturnerTestCase(TestCase):
    '''
    Test Sentry Returner
    '''
    ret = {'id': '12345',
           'fun': 'mytest.func',
           'fun_args': ['arg1', 'arg2', {'foo': 'bar'}],
           'jid': '54321',
           'return': 'Long Return containing a Traceback'}

    def test_get_message(self):
        self.assertEqual(sentry._get_message(self.ret), 'salt func: mytest.func arg1 arg2 foo=bar')
        self.assertEqual(sentry._get_message({'fun': 'test.func', 'fun_args': []}), 'salt func: test.func')
        self.assertEqual(sentry._get_message({'fun': 'test.func'}), 'salt func: test.func')
