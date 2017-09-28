# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
import salt.states.modjk_worker as modjk_worker


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ModjkWorkerTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.modjk_worker
    '''
    def setup_loader_modules(self):
        return {modjk_worker: {}}
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
