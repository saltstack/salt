# -*- coding: utf-8 -*-
'''
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import (
    MagicMock,
    patch)

# Import Salt Libs
import salt.modules.sensors as sensors


class SensorTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.sensors
    '''
    def setup_loader_modules(self):
        return {sensors: {}}

    def test_sense(self):
        '''
        Test to gather lm-sensors data from a given chip
        '''
        with patch.dict(sensors.__salt__,
                        {'cmd.run': MagicMock(return_value='A:a B:b C:c D:d')}):
            self.assertDictEqual(sensors.sense('chip'), {'A': 'a B'})
