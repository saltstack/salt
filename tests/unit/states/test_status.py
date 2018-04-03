# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

# Import Salt Libs
import salt.states.status as status


@skipIf(NO_MOCK, NO_MOCK_REASON)
class StatusTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.status
    '''
    def setup_loader_modules(self):
        return {status: {}}

    # 'loadavg' function tests: 1
    def test_loadavg(self):
        '''
        Test to return the current load average for the specified minion.
        '''
        name = 'mymonitor'

        ret = {'name': name,
               'changes': {},
               'result': True,
               'data': {},
               'comment': ''}

        mock = MagicMock(return_value=[])
        with patch.dict(status.__salt__, {'status.loadavg': mock}):
            comt = ('Requested load average mymonitor not available ')
            ret.update({'comment': comt, 'result': False})
            self.assertDictEqual(status.loadavg(name), ret)

        mock = MagicMock(return_value={name: 3})
        with patch.dict(status.__salt__, {'status.loadavg': mock}):
            comt = ('Min must be less than max')
            ret.update({'comment': comt, 'result': False})
            self.assertDictEqual(status.loadavg(name, 1, 5), ret)

            comt = ('Load avg is below minimum of 4 at 3.0')
            ret.update({'comment': comt, 'data': 3})
            self.assertDictEqual(status.loadavg(name, 5, 4), ret)

            comt = ('Load avg above maximum of 2 at 3.0')
            ret.update({'comment': comt, 'data': 3})
            self.assertDictEqual(status.loadavg(name, 2, 1), ret)

            comt = ('Load avg in acceptable range')
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(status.loadavg(name, 3, 1), ret)

    # 'process' function tests: 1

    def test_process(self):
        '''
        Test to return whether the specified signature
        is found in the process tree.
        '''
        name = 'mymonitor'

        ret = {'name': name,
               'changes': {},
               'result': True,
               'data': {},
               'comment': ''}

        mock = MagicMock(side_effect=[{}, {name: 1}])
        with patch.dict(status.__salt__, {'status.pid': mock}):
            comt = ('Process signature "mymonitor" not found ')
            ret.update({'comment': comt, 'result': False})
            self.assertDictEqual(status.process(name), ret)

            comt = ('Process signature "mymonitor" was found ')
            ret.update({'comment': comt, 'result': True,
                        'data': {name: 1}})
            self.assertDictEqual(status.process(name), ret)
