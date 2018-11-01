# -*- coding: utf-8 -*-
'''
Integration tests for the beacon states
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest

import logging
log = logging.getLogger(__name__)


@destructiveTest
class BeaconStateTestCase(ModuleCase):
    '''
    Test beacon states
    '''
    def setUp(self):
        '''
        '''
        pass

    def tearDown(self):
        pass

    def test_present_absent(self):
        kwargs = {'/': '38%', 'interval': 5}
        ret = self.run_state(
            'beacon.present',
            name='diskusage',
            **kwargs
        )
        self.assertSaltTrueReturn(ret)

        ret = self.run_function('beacons.list', return_yaml=False)
        self.assertEqual(ret, {'diskusage': [{'interval': 5}, {'/': u'38%'}]})

        ret = self.run_state(
            'beacon.absent',
            name='diskusage',
        )
        self.assertSaltTrueReturn(ret)

        ret = self.run_function('beacons.list', return_yaml=False)
        self.assertEqual(ret, {'beacons': {}})
