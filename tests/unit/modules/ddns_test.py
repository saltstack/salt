# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import


# Import python libs
import contextlib
import textwrap
import json
try:
    import dns.query
    import dns.tsigkeyring
    HAS_DNS = True
except ImportError:
    HAS_DNS = False


# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    mock_open,
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import ddns

# Globals
ddns.__grains__ = {}
ddns.__salt__ = {}


@skipIf(HAS_DNS is False, 'dnspython libs not installed')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class DDNSTestCase(TestCase):
    '''
    TestCase for the salt.modules.ddns module
    '''
    @patch('salt.modules.ddns.update')
    def test_add_host(self, ddns_update):
        '''
        Test cases for Add, replace, or update the A
        and PTR (reverse) records for a host.
        '''
        ddns_update.return_value = False
        self.assertFalse(ddns.add_host(zone='A',
                                       name='B',
                                       ttl=1,
                                       ip='172.27.0.0'))

        ddns_update.return_value = True
        self.assertTrue(ddns.add_host(zone='A',
                                      name='B',
                                      ttl=1,
                                      ip='172.27.0.0'))

    @patch('salt.modules.ddns.delete')
    def test_delete_host(self, ddns_delete):
        '''
        Tests for delete the forward and reverse records for a host.
        '''
        ddns_delete.return_value = False
        with patch.object(dns.query, 'udp') as mock:
            mock.answer = [{'address': 'localhost'}]
            self.assertFalse(ddns.delete_host(zone='A', name='B'))

    def test_update(self):
        '''
        Test to add, replace, or update a DNS record.
        '''
        mock_request = textwrap.dedent('''\
            id 29380
            opcode QUERY
            rcode NOERROR
            flags RD
            ;QUESTION
            name.zone. IN AAAA
            ;ANSWER
            ;AUTHORITY
            ;ADDITIONAL''')
        mock_rdtype = 28  # rdtype of AAAA record

        class MockRrset(object):
            def __init__(self):
                self.items = [{'address': 'localhost'}]
                self.ttl = 2

        class MockAnswer(object):
            def __init__(self, *args, **kwargs):
                self.answer = [MockRrset()]

            def rcode(self):
                return 0

        def mock_udp_query(*args, **kwargs):
            return MockAnswer

        with contextlib.nested(
                patch.object(dns.message, 'make_query', MagicMock(return_value=mock_request)),
                patch.object(dns.query, 'udp', mock_udp_query()),
                patch.object(dns.rdatatype, 'from_text', MagicMock(return_value=mock_rdtype)),
                patch.object(ddns, '_get_keyring', return_value=None),
                patch.object(ddns, '_config', return_value=None)):
            self.assertTrue(ddns.update('zone', 'name', 1, 'AAAA', '::1'))

    def test_delete(self):
        '''
        Test to delete a DNS record.
        '''
        file_data = json.dumps({'A': 'B'})

        class MockAnswer(object):
            def __init__(self, *args, **kwargs):
                self.answer = [{'address': 'localhost'}]

            def rcode(self):
                return 0

        def mock_udp_query(*args, **kwargs):
            return MockAnswer

        with contextlib.nested(
                patch.object(dns.query, 'udp', mock_udp_query()),
                patch('salt.utils.fopen', mock_open(read_data=file_data), create=True),
                patch.object(dns.tsigkeyring, 'from_text', return_value=True),
                patch.object(ddns, '_get_keyring', return_value=None),
                patch.object(ddns, '_config', return_value=None)):
            self.assertTrue(ddns.delete(zone='A', name='B'))

if __name__ == '__main__':
    from integration import run_tests
    run_tests(DDNSTestCase, needs_daemon=False)
