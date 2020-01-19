# -*- coding: utf-8 -*-
'''
unit tests for the beacon_module parameter
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import patch

# Import Salt Libs
import salt.beacons as beacons
import salt.config

import logging
log = logging.getLogger(__name__)


class BeaconsTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt beacon_module parameter
    '''

    def setup_loader_modules(self):
        return {beacons: {}}

    def test_beacon_module(self):
        '''
        Test that beacon_module parameter for beacon configuration
        '''
        mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
        mock_opts['id'] = 'minion'
        mock_opts['__role'] = 'minion'
        mock_opts['beacons'] = {'watch_apache': [{'processes': {'apache2': 'stopped'}},
                                                 {'beacon_module': 'ps'}]}
        with patch.dict(beacons.__opts__, mock_opts):
            ret = salt.beacons.Beacon(mock_opts, []).process(mock_opts['beacons'], mock_opts['grains'])
            _expected = [{'tag': 'salt/beacon/minion/watch_apache/',
                          'data': {'id': u'minion', u'apache2': u'Stopped'},
                          'beacon_name': 'ps'}]
            self.assertEqual(ret, _expected)
