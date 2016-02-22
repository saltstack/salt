# coding: utf-8

# Python Libs
from __future__ import absolute_import

# Salt Libs
from salt.modules import beacons
import integration
from salttesting import skipIf
from salttesting.helpers import destructiveTest, ensure_in_syspath

ensure_in_syspath('../../')

beacons.__opts__ = {}


class BeaconsTest(integration.ModuleCase):
    '''
    Tests the beacons execution module
    '''
    @destructiveTest
    def test_add(self):
        ret = self.run_function('beacons.add', ['ps', {'apache2': 'stopped'}])
        self.assertEqual(ret, {'comment': 'Added beacon: ps.', 'result': True})

    @destructiveTest
    def test_list(self):
        ret = self.run_function('beacons.list')
        self.assertEqual({'beacons': {}}, ret)

    @destructiveTest
    def test_disable(self):
        ret = self.run_function('beacons.disable')
        self.assertEqual(ret, {'comment': 'Disabled beacons on minion.', 'result': True})

    @destructiveTest
    def test_disable_beacon(self):
        self.run_function('beacons.add', ['ps', {'apache2': 'stopped'}])

        ret = self.run_function('beacons.disable_beacon', ['ps'])
        self.assertEqual(ret, {'comment': 'Disabled beacon on minion.', 'result': True})

    @destructiveTest
    def test_enable(self):
        ret = self.run_function('beacons.enable')
        self.assertEqual(ret, {'comment': 'Enabled beacons on minion.', 'result': True})

    @destructiveTest
    def test_enable_beacon(self):
        self.run_function('beacons.add', ['ps', {'apache2': 'stopped'}])

        ret = self.run_function('beacons.enable_beacon', ['ps'])
        self.assertEqual(ret, {'comment': 'Enabled beacon ps on minion.', 'result': True})

    @destructiveTest
    def test_delete(self):
        ret = self.run_function('beacons.delete', ['ps'])
        self.assertEqual(ret, {'comment': 'Deleted beacon: ps.', 'result': True})


if __name__ == '__main__':
    from integration import run_tests
    run_tests(BeaconsTest)
