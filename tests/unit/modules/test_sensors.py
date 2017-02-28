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
from salt.modules import sensors

# Globals
sensors.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SensorTestCase(TestCase):
    '''
    Test cases for salt.modules.sensors
    '''
    def test_sense(self):
        '''
        Test to gather lm-sensors data from a given chip
        '''
        with patch.dict(sensors.__salt__,
                        {'cmd.run': MagicMock(return_value='A:a B:b C:c D:d')}):
            self.assertDictEqual(sensors.sense('chip'), {'A': 'a B'})


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SensorTestCase, needs_daemon=False)
