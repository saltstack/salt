# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.power_dns as power_dns
from salt.exceptions import CommandExecutionError

# Import Salt Testing Libs
from tests.support.unit import TestCase

import mock


class PowerDnsTestCase(TestCase):
    """
    Test cases for salt.states.power_dns
    """

    def _mock_response(
        self,
        status=200,
        content="CONTENT",
        json_data=None,
        raise_for_status=None):
        mock_resp = mock.Mock()
        mock_resp.raise_for_status = mock.Mock()
        if raise_for_status:
            mock_resp.raise_for_status.side_effect = raise_for_status
        mock_resp.status_code = status
        mock_resp.content = content
        if json_data:
            mock_resp.json = mock.Mock(
                return_value=json_data
            )
        return mock_resp

    @mock.patch('requests.get')
    def test__get_zone_return_correct_json(self, mock_get):
        mock_resp = self._mock_response(json_data="test_data")
        mock_get.return_value = mock_resp
        response = power_dns._get_zone("zone", "key", "server")
        self.assertEqual(response, "test_data")
        self.assertTrue(mock_resp.json.called)

    @mock.patch('requests.get')
    def test__get_zone_unprocessable_entity_return_none(self, mock_get):
        mock_resp = self._mock_response(status=422)
        mock_get.return_value = mock_resp
        response = power_dns._get_zone("zone", "key", "server")
        self.assertEqual(response, None)

    def test__check_records_equality_returns_true(self):
        old_record = {"name": "test_name_1", "type": "A"}
        new_record = {"name": "test_name_1", "type": "A"}
        result = power_dns._check_records_equality(old_record, new_record)
        self.assertTrue(result)

    def test__check_records_equality_returns_false(self):
        old_record = {"name": "test_name_1"}
        new_record = {"name": "test_name_2"}
        result = power_dns._check_records_equality(old_record, new_record)
        self.assertFalse(result)

    def test__check_is_zone_changed_rerurns_changes(self):
        old_zone = {"dnssec": False}
        new_zone = {"dnssec": True}
        result = power_dns._check_is_zone_changed(old_zone, new_zone)
        self.assertEqual(len(result), 1)
        self.assertEqual(result, [{"dnssec": {"old": False, "new": True}}])

    def test__check_is_zone_changed_rerurns_empty_list(self):
        old_zone = {"dnssec": False}
        new_zone = {"dnssec": False}
        result = power_dns._check_is_zone_changed(old_zone, new_zone)
        self.assertEqual(len(result), 0)
        self.assertEqual(result, [])

    def test__check_are_records_changed_returns_true(self):
        old_records = [{"content": "test_1"}, {"content": "test_2"}]
        new_records = [{"content": "test_3"}]
        result = power_dns._check_are_records_changed(old_records, new_records)
        self.assertTrue(result)

    def test__check_are_records_changed_returns_false(self):
        old_records = [{"content": "test_1"}]
        new_records = [{"content": "test_1"}]
        result = power_dns._check_are_records_changed(old_records, new_records)
        self.assertFalse(result)

    def test__check_are_rrsets_changed_return_list_of_changes(self):
        old_rrset = [
            {"name": "test_name.com", "type": "A", "records": [
                {"content": "123.45.67.89"}], "ttl": 30}
        ]
        new_rrset = [
            {"name": "test_name.com", "type": "A", "records": [
                {"content": "123.45.67.89"}], "ttl": 30},
            {"name": "www.test_name.com", "type": "CNAME",
             "records": [{"content": "test_name.com"}], "ttl": 30}
        ]
        result = power_dns._check_are_rrsets_changed(old_rrset, new_rrset)
        self.assertEqual(result, [{'www.test_name.com': {
            'new': {'content': ['test_name.com'], 'ttl': 30}, 'type': 'CNAME'}}])

    def test__check_are_rrsets_changed_return_empty_list(self):
        old_rrset = [
            {"name": "test_name.com", "type": "A", "records": [
                {"content": "123.45.67.89"}], "ttl": 30}
        ]
        new_rrset = [
            {"name": "test_name.com", "type": "A", "records": [
                {"content": "123.45.67.89"}], "ttl": 30}
        ]
        result = power_dns._check_are_rrsets_changed(old_rrset, new_rrset)
        self.assertEqual(len(result), 0)
        self.assertEqual(result, [])

    def test__check_are_rrsets_deleted(self):
        rrsets = [
            {"changetype": "DELETE", "name": "zone1.com", "records": [
                {"content": "123.45.67.89"}], "type": "A", "ttl": 30},
            {"changetype": "REPLACE", "name": "zone1.com", "records": [
                {"content": "123.45.67.89"}], "type": "A", "ttl": 30}
        ]
        result = power_dns._check_are_rrsets_deleted(rrsets)
        self.assertEqual(len(result), 1)
        self.assertEqual(
            result, [{'zone1.com': {'content': ['123.45.67.89'], 'ttl': 30, 'type': 'A'}}])

    def test__check_are_rrsets_have_ns_returns_true(self):
        rrsets = [
            {"changetype": "DELETE", "name": "zone1.com", "records": [
                {"content": "123.45.67.89"}], "type": "NS", "ttl": 30},
            {"changetype": "REPLACE", "name": "zone1.com", "records": [
                {"content": "123.45.67.89"}], "type": "A", "ttl": 30}
        ]
        result = power_dns._check_are_rrsets_have_ns(rrsets)
        self.assertTrue(result)

    def test__check_are_rrsets_have_ns_returns_false(self):
        rrsets = [
            {"changetype": "DELETE", "name": "zone1.com", "records": [
                {"content": "123.45.67.89"}], "type": "A", "ttl": 30},
            {"changetype": "REPLACE", "name": "zone1.com", "records": [
                {"content": "123.45.67.89"}], "type": "A", "ttl": 30}
        ]
        result = power_dns._check_are_rrsets_have_ns(rrsets)
        self.assertFalse(result)

    def test__filter_incorrect_soa_records_returns_records_wo_soa(self):
        rrsets = [
            {"changetype": "DELETE", "name": "zone1.com", "records": [
                {"content": "123.45.67.89"}], "type": "SOA", "ttl": 30},
            {"changetype": "REPLACE", "name": "zone1.com", "records": [
                {"content": "123.45.67.89"}], "type": "A", "ttl": 30}
        ]
        result = power_dns._filter_incorrect_soa_records(rrsets)
        self.assertEqual(len(result), 1)
        self.assertEqual(result, [{"changetype": "REPLACE", "name": "zone1.com", "records": [
            {"content": "123.45.67.89"}], "type": "A", "ttl": 30}])

    def test__prepare_nameservers_rrsets_return_rrsets(self):
        name = "zone1.com"
        nameservers = ["ns.zone.org", "ns.zone.org"]

        result = power_dns._prepare_nameservers_rrsets(name, nameservers)
        self.assertEqual(result, [
            {'changetype': 'REPLACE',
             'name': 'zone1.com.',
             'records': [{'content': 'ns.zone.org.', 'disabled': False},
                         {'content': 'ns.zone.org.', 'disabled': False}],
             'ttl': 3600,
             'type': 'NS'}])

    def test__prepare_rrset_return_rrsets(self):
        rrset_1 = {"name": "zone1.com", "records": [
            {"content": "123.45.67.89"}], "type": "a", "ttl": 3600}
        rrset_2 = {"name": "zone2.com", "content": [
            "mx.test.com", "mx2.test.com"], "type": "mx"}
        rrset_3 = {"name": "zone3.com",
                   "content": "test_content", "type": "txt"}
        result_1 = power_dns._prepare_rrset(rrset_1)
        result_2 = power_dns._prepare_rrset(rrset_2)
        result_3 = power_dns._prepare_rrset(rrset_3)
        self.assertEqual(
            result_1,
            {
                'name': 'zone1.com.',
                'records': [{'content': '123.45.67.89', 'disabled': False}],
                'type': 'A',
                'ttl': 3600,
                'changetype': 'REPLACE'
            }
        )
        self.assertEqual(
            result_2,
            {
                'changetype': 'REPLACE',
                'name': 'zone2.com.',
                'records': [{'content': 'mx.test.com.', 'disabled': False},
                            {'content': 'mx2.test.com.', 'disabled': False}],
                'ttl': 300,
                'type': 'MX'
            }
        )
        self.assertEqual(
            result_3,
            {
                'changetype': 'REPLACE',
                'name': 'zone3.com.',
                'records': [{'content': '"test_content"', 'disabled': False}],
                'ttl': 300,
                'type': 'TXT'
            }
        )

    def test__prepare_rrsets_new_rrsets(self):
        name = "zone1.com"
        drop_existing = False
        nameservers = ["ns1.zone.org", "ns2.zone.org"]
        new_rrsets = [
            {"name": "zone1.com", "records": [
                {"content": "123.45.67.89"}], "type": "a", "ttl": 3600},
            {"name": "mx.zone1.com", "content": [
                "mx.test.com", "mx2.test.com"], "type": "mx"},
            {"name": "txt.zone1.com", "content": "test_content", "type": "txt"}
        ]

        result = power_dns._prepare_rrsets(
            name, drop_existing, nameservers, new_rrsets)
        self.assertEqual(len(result), 4)
        self.assertEqual(
            result,
            [
                {
                    'name': 'zone1.com.',
                    'records': [{'content': '123.45.67.89', 'disabled': False}],
                    'type': 'A',
                    'ttl': 3600,
                    'changetype': 'REPLACE'
                },
                {
                    'changetype': 'REPLACE',
                    'name': 'mx.zone1.com.',
                    'records': [{'content': 'mx.test.com.', 'disabled': False},
                                {'content': 'mx2.test.com.', 'disabled': False}],
                    'ttl': 300,
                    'type': 'MX'
                },
                {
                    'changetype': 'REPLACE',
                    'name': 'txt.zone1.com.',
                    'records': [{'content': '"test_content"', 'disabled': False}],
                    'ttl': 300,
                    'type': 'TXT'
                },
                {
                    'changetype': 'REPLACE',
                    'name': 'zone1.com.',
                    'records': [{'content': 'ns1.zone.org.', 'disabled': False},
                                {'content': 'ns2.zone.org.', 'disabled': False}],
                    'ttl': 3600,
                    'type': 'NS'
                }
            ]
        )

    def test__prepare_rrsets_new_rrsets_and_old_rrsets(self):
        name = "zone1.com"
        drop_existing = False
        nameservers = ["ns1.zone.org", "ns2.zone.org"]
        new_rrsets = [
            {"name": "zone1.com", "records": [
                {"content": "123.45.67.89"}], "type": "a", "ttl": 7200}
        ]
        old_rrsets = [
            {'name': 'zone1.com.', 'records': [
                {'content': '23.45.67.1', 'disabled': False}], 'type': 'A', 'ttl': 3600}
        ]

        result = power_dns._prepare_rrsets(
            name, drop_existing, nameservers, new_rrsets, old_rrsets)
        self.assertEqual(len(result), 2)
        self.assertEqual(
            result,
            [
                {
                    'name': 'zone1.com.',
                    'records': [{'content': '123.45.67.89', 'disabled': False}],
                    'type': 'A',
                    'ttl': 7200,
                    'changetype': 'REPLACE'
                },
                {
                    'changetype': 'REPLACE',
                    'name': 'zone1.com.',
                    'records': [{'content': 'ns1.zone.org.', 'disabled': False},
                                {'content': 'ns2.zone.org.', 'disabled': False}],
                    'ttl': 3600,
                    'type': 'NS'
                }
            ]
        )

    def test__prepare_rrsets_new_rrsets_and_old_rrsets_drop_existing(self):
        name = "zone1.com"
        drop_existing = True
        nameservers = ["ns1.zone.org", "ns2.zone.org"]
        new_rrsets = [
            {"name": "www.zone1.com", "records": [
                {"content": "zone1.com"}], "type": "cname", "ttl": 7200}
        ]
        old_rrsets = [
            {'name': 'zone1.com.', 'records': [
                {'content': '23.45.67.1', 'disabled': False}], 'type': 'A', 'ttl': 3600}
        ]

        result = power_dns._prepare_rrsets(
            name, drop_existing, nameservers, new_rrsets, old_rrsets)
        self.assertEqual(len(result), 3)
        self.assertEqual(
            result,
            [
                {
                    'changetype': 'DELETE',
                    'name': 'zone1.com.',
                    'records': [{'content': '23.45.67.1', 'disabled': False}],
                    'ttl': 3600,
                    'type': 'A'
                },
                {
                    'name': 'www.zone1.com.',
                    'records': [{'content': 'zone1.com.', 'disabled': False}],
                    'type': 'CNAME',
                    'ttl': 7200,
                    'changetype': 'REPLACE'
                },
                {
                    'changetype': 'REPLACE',
                    'name': 'zone1.com.',
                    'records': [{'content': 'ns1.zone.org.', 'disabled': False},
                                {'content': 'ns2.zone.org.', 'disabled': False}],
                    'ttl': 3600,
                    'type': 'NS'
                }
            ]
        )

    def test__prepare_new_zone_result_object(self):
        request = {
            "dnssec": False,
            "name": "zone1.com",
            "nameservers": ["ns1.zone.org", "ns2.zone.org"],
            "rrsets": [
                {"name": "www.zone1.com", "records": [
                    {"content": "zone1.com"}], "type": "CNAME", "ttl": 7200},
                {"name": "zone1.com", "records": [
                    {"content": "123.45.67.89"}], "type": "A", "ttl": 3600}
            ]
        }
        result = power_dns._prepare_new_zone_result_object(request)
        self.assertEqual(result, {
            'dnssec': False,
            'name': 'zone1.com',
            'nameservers': ['ns1.zone.org', 'ns2.zone.org'],
            'records': [
                {'www.zone1.com': {'content': [
                    'zone1.com'], 'ttl': 7200, 'type': 'CNAME'}},
                {'zone1.com': {'content': [
                    '123.45.67.89'], 'ttl': 3600, 'type': 'A'}}
            ]
        })

    def test__validate_rrsets_raise_error(self):
        rrsets = [
            {"name": "zone.com", "content": {}}
        ]
        nameservers = ['ns1.zone.org', 'ns2.zone.org']

        self.assertRaises(CommandExecutionError,
                          power_dns._validate_rrsets, rrsets, nameservers)

    def test__check_is_valid_ip_address_correct_ip(self):
        ip = "123.45.67.89"
        result = power_dns._check_is_valid_ip_address(ip)
        self.assertTrue(result)

    def test__check_is_valid_ip_address_incorrect_ip(self):
        ip = "1123.45.67.8139"
        result = power_dns._check_is_valid_ip_address(ip)
        self.assertFalse(result)

    def test__add_trailing_dot_add_dot(self):
        content = "zone1.com"
        result = power_dns._add_trailing_dot(content)
        self.assertEqual(result, "zone1.com.")

    def test__add_trailing_dot_skip_dot(self):
        content = "zone1.com."
        result = power_dns._add_trailing_dot(content)
        self.assertEqual(result, "zone1.com.")

    def test__extract_content_from_records(self):
        records = [
            {"content": "test_content1"},
            {"content": "test_content2"}
        ]
        result = power_dns._extract_content_from_records(records)
        self.assertEqual(len(result), 2)
        self.assertEqual(result, ["test_content1", "test_content2"])

    @mock.patch('requests.post')
    def test_manage_zone_creates_new_zone(self, mock_post):

        method_get_zone = mock.patch(
            'salt.modules.power_dns._get_zone', return_value=None)
        method_get_zone.start()
        mock_post_resp = self._mock_response(status=201)
        mock_post.return_value = mock_post_resp

        name = "zone1.com"
        key = "TEST_KEY"
        server = "pdns.test.com"
        rrsets = [
            {"name": "zone1.com", "records": [
                {"content": "12.34.56.78"}], "type": "A", "ttl": 30},
            {"name": "www.zone1.com", "records": [
                {"content": "zone1.com"}], "type": "cname", "ttl": 7200}
        ]
        nameservers = [
            "ns1.zone1.com",
            "ns2.zone2.com"
        ]
        drop_existing = False
        dnssec = True

        result = power_dns.manage_zone(
            name, key, server, rrsets, nameservers, drop_existing, dnssec)

        method_get_zone.stop()

        self.assertEqual(
            result,
            {'changes':
                {'created': {
                    'dnssec': True,
                    'name': 'zone1.com.',
                    'nameservers': [],
                    'records': [
                        {'zone1.com.': {'content': ['12.34.56.78'], 'ttl': 30, 'type': 'A'}},
                        {'www.zone1.com.': {'content': ['zone1.com.'], 'ttl': 7200, 'type': 'CNAME'}},
                        {'zone1.com.': {'content': ['ns1.zone1.com.', 'ns2.zone2.com.'], 'ttl': 3600, 'type': 'NS'}}]}},
                'name': 'zone1.com',
                'result': True})

    @mock.patch('requests.post')
    def test_manage_zone_fail_creates_new_zone(self, mock_post):

        method_get_zone = mock.patch(
            'salt.modules.power_dns._get_zone', return_value=None)
        method_get_zone.start()
        mock_post_resp = self._mock_response(status=400)
        mock_post.return_value = mock_post_resp

        name = "zone1.com"
        key = "TEST_KEY"
        server = "pdns.test.com"
        rrsets = [
            {"name": "zone1.com", "records": [
                {"content": "12.34.56.78"}], "type": "A", "ttl": 30},
            {"name": "www.zone1.com", "records": [
                {"content": "zone1.com"}], "type": "cname", "ttl": 7200}
        ]
        nameservers = [
            "ns1.zone1.com",
            "ns2.zone2.com"
        ]
        drop_existing = False
        dnssec = True

        self.assertRaises(CommandExecutionError, power_dns.manage_zone, name, key, server, rrsets, nameservers,
                          drop_existing, dnssec)
        method_get_zone.stop()

    @mock.patch('requests.put')
    def test_manage_zone_updates_dnssec(self, mock_put):

        old_zone = {'dnssec': False,
                    'rrsets': [{"name": "zone1.com", "records": [{"content": "12.34.56.78"}], "type": "A", "ttl": 30}]}

        method_get_zone = mock.patch(
            'salt.modules.power_dns._get_zone', return_value=old_zone)
        method_check_are_rrsets_changed = mock.patch(
            'salt.modules.power_dns._check_are_rrsets_changed', return_value=False
        )
        method_check_are_rrsets_deleted = mock.patch(
            'salt.modules.power_dns._check_are_rrsets_deleted', return_value=False
        )
        method_get_zone.start()
        method_check_are_rrsets_changed.start()
        method_check_are_rrsets_deleted.start()
        mock_put_resp = self._mock_response(status=204)
        mock_put.return_value = mock_put_resp

        name = "zone1.com"
        key = "TEST_KEY"
        server = "pdns.test.com"
        rrsets = [
            {"name": "zone1.com", "records": [
                {"content": "12.34.56.78"}], "type": "A", "ttl": 30}
        ]
        nameservers = [
            "ns1.zone1.com",
            "ns2.zone2.com"
        ]
        drop_existing = False
        dnssec = True

        result = power_dns.manage_zone(
            name, key, server, rrsets, nameservers, drop_existing, dnssec)

        method_get_zone.stop()
        method_check_are_rrsets_changed.stop()
        method_check_are_rrsets_deleted.stop()

        self.assertEqual(
            result,
            {'changes': {'zone': [{'dnssec': {'new': True, 'old': False}}]}, 'name': 'zone1.com', 'result': True})

    @mock.patch('requests.put')
    def test_manage_zone_fails_update_dnssec(self, mock_put):

        old_zone = {'dnssec': False,
                    'rrsets': [{"name": "zone1.com", "records": [{"content": "12.34.56.78"}], "type": "A", "ttl": 30}]}

        method_get_zone = mock.patch(
            'salt.modules.power_dns._get_zone', return_value=old_zone)
        method_get_zone.start()
        mock_put_resp = self._mock_response(status=400)
        mock_put.return_value = mock_put_resp

        name = "zone1.com"
        key = "TEST_KEY"
        server = "pdns.test.com"
        rrsets = [
            {"name": "zone1.com", "records": [
                {"content": "12.34.56.78"}], "type": "A", "ttl": 30},
            {"name": "www.zone1.com", "records": [
                {"content": "zone1.com"}], "type": "cname", "ttl": 7200}
        ]
        nameservers = [
            "ns1.zone1.com",
            "ns2.zone2.com"
        ]
        drop_existing = False
        dnssec = True

        self.assertRaises(CommandExecutionError, power_dns.manage_zone, name, key, server, rrsets, nameservers,
                          drop_existing, dnssec)
        method_get_zone.stop()

    @mock.patch('requests.patch')
    def test_manage_zone_updates_rrsets(self, mock_patch):

        old_zone = {'dnssec': False,
                    'rrsets': [{"name": "zone1.com", "records": [{"content": "12.34.56.87"}], "type": "A", "ttl": 30}]}

        method_get_zone = mock.patch(
            'salt.modules.power_dns._get_zone', return_value=old_zone)

        method_get_zone.start()
        mock_patch_resp = self._mock_response(status=204)
        mock_patch.return_value = mock_patch_resp

        name = "zone1.com"
        key = "TEST_KEY"
        server = "pdns.test.com"
        rrsets = [
            {"name": "zone1.com", "records": [
                {"content": "12.34.56.78"}], "type": "A", "ttl": 30}
        ]
        nameservers = [
            "ns1.zone1.com",
            "ns2.zone2.com"
        ]
        drop_existing = False
        dnssec = False

        result = power_dns.manage_zone(
            name, key, server, rrsets, nameservers, drop_existing, dnssec)

        method_get_zone.stop()

        self.assertEqual(
            result,
            {'changes': {'records':
                {
                    'deleted': [],
                    'modified':
                        [
                            {'zone1.com.': {'new': {'content': ['12.34.56.78'], 'ttl': 30}, 'type': 'A'}},
                            {'zone1.com.': {'new': {'content': ['ns1.zone1.com.', 'ns2.zone2.com.'], 'ttl': 3600},
                                            'type': 'NS'}}
                        ]
                }},
                'name': 'zone1.com',
                'result': True})

    @mock.patch('requests.patch')
    def test_manage_zone_fails_update_rrsets(self, mock_patch):

        old_zone = {'dnssec': False,
                    'rrsets': [{"name": "zone1.com", "records": [{"content": "12.34.56.87"}], "type": "A", "ttl": 30}]}

        method_get_zone = mock.patch(
            'salt.modules.power_dns._get_zone', return_value=old_zone)

        method_get_zone.start()
        mock_patch_resp = self._mock_response(status=400, json_data="Test data")
        mock_patch.return_value = mock_patch_resp

        name = "zone1.com"
        key = "TEST_KEY"
        server = "pdns.test.com"
        rrsets = [
            {"name": "zone1.com", "records": [
                {"content": "12.34.56.78"}], "type": "A", "ttl": 30}
        ]
        nameservers = [
            "ns1.zone1.com",
            "ns2.zone2.com"
        ]
        drop_existing = False
        dnssec = False

        self.assertRaises(CommandExecutionError, power_dns.manage_zone, name, key, server, rrsets, nameservers,
                          drop_existing, dnssec)

        method_get_zone.stop()

    def test_delete_zone_no_zone(self):

        name = "zone1.com"
        key = "TEST_KEY"
        server = "pdns.test.com"

        method_get_zone = mock.patch(
            'salt.modules.power_dns._get_zone', return_value=None)
        method_get_zone.start()

        result = power_dns.delete_zone(name, key, server)

        method_get_zone.stop()

        self.assertEqual(result, {'changes': {}, 'name': 'zone1.com', 'result': True})

    @mock.patch('requests.delete')
    def test_delete_zone_sucess(self, mock_delete):

        name = "zone1.com"
        key = "TEST_KEY"
        server = "pdns.test.com"

        mock_delete_resp = self._mock_response(status=204, json_data="Test data")
        mock_delete.return_value = mock_delete_resp

        method_get_zone = mock.patch(
            'salt.modules.power_dns._get_zone', return_value={"name": "zone1.com"})
        method_get_zone.start()

        result = power_dns.delete_zone(name, key, server)

        method_get_zone.stop()

        self.assertEqual(result, {'changes': {'deleted': 'zone1.com'}, 'name': 'zone1.com', 'result': True})

    @mock.patch('requests.delete')
    def test_delete_zone_fails(self, mock_delete):

        name = "zone1.com"
        key = "TEST_KEY"
        server = "pdns.test.com"

        mock_delete_resp = self._mock_response(status=400, json_data="Test data")
        mock_delete.return_value = mock_delete_resp

        method_get_zone = mock.patch(
            'salt.modules.power_dns._get_zone', return_value={"name": "zone1.com"})
        method_get_zone.start()

        self.assertRaises(CommandExecutionError, power_dns.delete_zone, name, key, server)

        method_get_zone.stop()
