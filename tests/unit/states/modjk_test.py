# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import modjk
import salt.ext.six as six


if six.PY2:
    LIST_NOT_STR = "workers should be a list not a <type 'str'>"
else:
    LIST_NOT_STR = "workers should be a list not a <class 'str'>"


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ModjkTestCase(TestCase):
    '''
    Test cases for salt.states.modjk
    '''
    # 'worker_stopped' function tests: 1

    def test_worker_stopped(self):
        '''
        Test to stop all the workers in the modjk load balancer
        '''
        name = 'loadbalancer'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        ret.update({'comment': LIST_NOT_STR})
        self.assertDictEqual(modjk.worker_stopped(name, 'app1'), ret)

    # 'worker_activated' function tests: 1

    def test_worker_activated(self):
        '''
        Test to activate all the workers in the modjk load balancer
        '''
        name = 'loadbalancer'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        ret.update({'comment': LIST_NOT_STR})
        self.assertDictEqual(modjk.worker_activated(name, 'app1'), ret)

    # 'worker_disabled' function tests: 1

    def test_worker_disabled(self):
        '''
        Test to disable all the workers in the modjk load balancer
        '''
        name = 'loadbalancer'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        ret.update({'comment': LIST_NOT_STR})
        self.assertDictEqual(modjk.worker_disabled(name, 'app1'), ret)

    # 'worker_recover' function tests: 1

    def test_worker_recover(self):
        '''
        Test to recover all the workers in the modjk load balancer
        '''
        name = 'loadbalancer'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        ret.update({'comment': LIST_NOT_STR})
        self.assertDictEqual(modjk.worker_recover(name, 'app1'), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ModjkTestCase, needs_daemon=False)
