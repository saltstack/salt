# coding: utf-8

# Python Libs
from __future__ import absolute_import

# Salt Libs
from salt.modules import beacons
import integration
from salttesting import skipIf
from salttesting.mock import NO_MOCK, NO_MOCK_REASON
from salttesting.helpers import destructiveTest, ensure_in_syspath

ensure_in_syspath('../../')

beacons.__opts__ = {}


class BeaconsTest(integration.ModuleCase):
    '''
    Tests the beacons execution module
    '''
    @destructiveTest
    def test_add(self):
        ret = self.run_function('beacons.add', ['ps', "{'apache2': 'stopped'}"])
        self.assertEqual(ret, {'comment': 'Added beacons: ps.', 'result': True})

    def test_list(self):
        ret = self.run_function('beacons.list')
        self.assertEqual({'beacons': {}}, ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(BeaconsTest)
