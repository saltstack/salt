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
    NO_MOCK_REASON,
    MagicMock,
    patch)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import modjk_worker

modjk_worker.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ModjkWorkerTestCase(TestCase):
    '''
    Test cases for salt.states.modjk_worker
    '''
    # 'stop' function tests: 1

    def test_stop(self):
        '''
        Test to stop the named worker from the lbn load balancers
         at the targeted minions.
        '''
        name = "{{ grains['id'] }}"
        lbn = 'application'
        target = 'roles:balancer'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        comt = ('no servers answered the published command modjk.worker_status')
        mock = MagicMock(return_value=False)
        with patch.dict(modjk_worker.__salt__, {'publish.publish': mock}):
            ret.update({'comment': comt})
            self.assertDictEqual(modjk_worker.stop(name, lbn, target), ret)

    # 'activate' function tests: 1

    def test_activate(self):
        '''
        Test to activate the named worker from the lbn load balancers
         at the targeted minions.
        '''
        name = "{{ grains['id'] }}"
        lbn = 'application'
        target = 'roles:balancer'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        comt = ('no servers answered the published command modjk.worker_status')
        mock = MagicMock(return_value=False)
        with patch.dict(modjk_worker.__salt__, {'publish.publish': mock}):
            ret.update({'comment': comt})
            self.assertDictEqual(modjk_worker.activate(name, lbn, target), ret)

    # 'disable' function tests: 1

    def test_disable(self):
        '''
        Test to disable the named worker from the lbn load balancers
         at the targeted minions.
        '''
        name = "{{ grains['id'] }}"
        lbn = 'application'
        target = 'roles:balancer'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        comt = ('no servers answered the published command modjk.worker_status')
        mock = MagicMock(return_value=False)
        with patch.dict(modjk_worker.__salt__, {'publish.publish': mock}):
            ret.update({'comment': comt})
            self.assertDictEqual(modjk_worker.disable(name, lbn, target), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ModjkWorkerTestCase, needs_daemon=False)
