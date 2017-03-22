# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2017 by the SaltStack Team, see AUTHORS for more details.


    tests.unit.beacons.test_status
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Status beacon test cases
'''

# Python libs
from __future__ import absolute_import

# Salt libs
import salt.config
import salt.loader
from salt.beacons import status
import salt.modules.status as status_module

# Salt testing libs
from tests.support.unit import TestCase
from tests.support.mixins import LoaderModuleMockMixin


class StatusBeaconTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test case for salt.beacons.status
    '''

    def setup_loader_modules(self):
        opts = salt.config.DEFAULT_MINION_OPTS
        module_globals = {
            '__opts__': opts,
            '__salt__': 'autoload',
            '__context__': {},
            '__grains__': {'kernel': 'Linux'}
        }
        return {
            status: module_globals,
            status_module: module_globals
        }

    def test_empty_config(self, *args, **kwargs):
        config = {}
        ret = status.beacon(config)
        self.assertEqual(sorted(list(ret[0]['data'])), sorted(['loadavg', 'meminfo', 'cpustats', 'vmstats', 'time']))

    def test_deprecated_dict_config(self):
        config = {'time': ['all']}
        ret = status.beacon(config)
        self.assertEqual(list(ret[0]['data']), ['time'])

    def test_list_config(self):
        config = [{'time': ['all']}]
        ret = status.beacon(config)
        self.assertEqual(list(ret[0]['data']), ['time'])
