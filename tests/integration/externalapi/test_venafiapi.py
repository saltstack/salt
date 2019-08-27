# -*- coding: utf-8 -*-
'''
Tests for the salt-run command
'''
# Import Python libs
from __future__ import absolute_import
import functools
import random
import string

# Import Salt Testing libs
from tests.support.case import ShellCase
from tests.support.helpers import destructiveTest, expensiveTest
from salt.ext.six.moves import range


def _random_name(prefix=''):
    ret = prefix
    for _ in range(8):
        ret += random.choice(string.ascii_lowercase)
    return ret


def with_random_name(func):
    '''
    generate a randomized name for a container
    '''
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        name = _random_name(prefix='salt_')
        return func(self, _random_name(prefix='salt_test_'), *args, **kwargs)
    return wrapper


# @destructiveTest
# @expensiveTest
class VenafiTest(ShellCase):
    '''
    Test the venafi runner
    '''

    @with_random_name
    def test_request(self, name):
        '''
        venafi.request
        '''
        print(self.master_opts['venafi'])
        ret = self.run_run_plus(fun='venafi.request',
                                minion_id='{0}.example.com'.format(name),
                                dns_name='{0}.example.com'.format(name),
                                zone='Default')
        print("ret is:",ret['return'])
        # self.assertTrue('request_id' in ret['return'])
