# coding: utf-8

# Python libs
from __future__ import absolute_import
from collections import namedtuple

# Salt testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock
from tests.support.mixins import LoaderModuleMockMixin

# Salt libs
import salt.beacons.service as service_beacon

PATCH_OPTS = dict(autospec=True, spec_set=True)

FakeProcess = namedtuple('Process', 'cmdline pid')


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ServiceBeaconTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test case for salt.beacons.service
    '''

    def setup_loader_modules(self):
        return {
            service_beacon: {
                '__context__': {},
                '__salt__': {},
            }
        }

    def test_non_list_config(self):
        config = {}

        ret = service_beacon.validate(config)

        self.assertEqual(ret, (False, 'Configuration for service beacon must'
                                      ' be a list.'))

    def test_empty_config(self):
        config = [{}]

        ret = service_beacon.validate(config)

        self.assertEqual(ret, (False, 'Configuration for service '
                                      'beacon requires services.'))

    def test_service_running(self):
        with patch.dict(service_beacon.__salt__,
                        {'service.status': MagicMock(return_value=True)}):
            config = [{'services': {'salt-master': {}}}]

            ret = service_beacon.validate(config)

            self.assertEqual(ret, (True, 'Valid beacon configuration'))

            ret = service_beacon.beacon(config)
            self.assertEqual(ret, [{'service_name': 'salt-master',
                                    'tag': 'salt-master',
                                    'salt-master': {'running': True}}])

    def test_service_not_running(self):
        with patch.dict(service_beacon.__salt__,
                        {'service.status': MagicMock(return_value=False)}):
            config = [{'services': {'salt-master': {}}}]

            ret = service_beacon.validate(config)

            self.assertEqual(ret, (True, 'Valid beacon configuration'))

            ret = service_beacon.beacon(config)
            self.assertEqual(ret, [{'service_name': 'salt-master',
                                    'tag': 'salt-master',
                                    'salt-master': {'running': False}}])
