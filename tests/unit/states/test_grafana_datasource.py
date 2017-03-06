# -*- coding: utf-8 -*-
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    Mock,
    MagicMock,
    patch
)

# Import Salt Libs
from salt.states import grafana_datasource

grafana_datasource.__opts__ = {}
grafana_datasource.__salt__ = {}

profile = {
    'grafana_url': 'http://grafana',
    'grafana_token': 'token',
}


def mock_json_response(data):
    response = MagicMock()
    response.json = MagicMock(return_value=data)
    return Mock(return_value=response)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class GrafanaDatasourceTestCase(TestCase):
    def test_present(self):
        with patch('requests.get', mock_json_response([])):
            with patch('requests.post') as rpost:
                ret = grafana_datasource.present('test', 'type', 'url', profile=profile)
                rpost.assert_called_once_with(
                    'http://grafana/api/datasources',
                    grafana_datasource._get_json_data('test', 'type', 'url'),
                    headers={'Authorization': 'Bearer token', 'Accept': 'application/json'},
                    timeout=3
                )
                self.assertTrue(ret['result'])
                self.assertEqual(ret['comment'], 'New data source test added')

        data = grafana_datasource._get_json_data('test', 'type', 'url')
        data.update({'id': 1, 'orgId': 1})
        with patch('requests.get', mock_json_response([data])):
            with patch('requests.put') as rput:
                ret = grafana_datasource.present('test', 'type', 'url', profile=profile)
                rput.assert_called_once_with(
                    'http://grafana/api/datasources/1',
                    grafana_datasource._get_json_data('test', 'type', 'url'),
                    headers={'Authorization': 'Bearer token', 'Accept': 'application/json'},
                    timeout=3
                )
                self.assertTrue(ret['result'])
                self.assertEqual(ret['comment'], 'Data source test already up-to-date')
                self.assertEqual(ret['changes'], None)

            with patch('requests.put') as rput:
                ret = grafana_datasource.present('test', 'type', 'newurl', profile=profile)
                rput.assert_called_once_with(
                    'http://grafana/api/datasources/1',
                    grafana_datasource._get_json_data('test', 'type', 'newurl'),
                    headers={'Authorization': 'Bearer token', 'Accept': 'application/json'},
                    timeout=3
                )
                self.assertTrue(ret['result'])
                self.assertEqual(ret['comment'], 'Data source test updated')
                self.assertEqual(ret['changes'], {'old': {'url': 'url'}, 'new': {'url': 'newurl'}})

    def test_absent(self):
        with patch('requests.get', mock_json_response([])):
            with patch('requests.delete') as rdelete:
                ret = grafana_datasource.absent('test', profile=profile)
                self.assertTrue(rdelete.call_count == 0)
                self.assertTrue(ret['result'])
                self.assertEqual(ret['comment'], 'Data source test already absent')

        with patch('requests.get', mock_json_response([{'name': 'test', 'id': 1}])):
            with patch('requests.delete') as rdelete:
                ret = grafana_datasource.absent('test', profile=profile)
                rdelete.assert_called_once_with(
                    'http://grafana/api/datasources/1',
                    headers={'Authorization': 'Bearer token', 'Accept': 'application/json'},
                    timeout=3
                )
                self.assertTrue(ret['result'])
                self.assertEqual(ret['comment'], 'Data source test was deleted')
