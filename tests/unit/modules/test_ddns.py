# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import
import textwrap
import json
try:
    import dns.query
    import dns.tsigkeyring
    HAS_DNS = True
except ImportError:
    HAS_DNS = False


# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    mock_open,
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.ddns as ddns


@skipIf(HAS_DNS is False, 'dnspython libs not installed')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class DDNSTestCase(TestCase, LoaderModuleMockMixin):
    '''
    TestCase for the salt.modules.ddns module
    '''

    def setup_loader_modules(self):
        return {ddns: {}}

    def test_add_host(self):
        '''
        Test cases for Add, replace, or update the A
        and PTR (reverse) records for a host.
        '''
        with patch('salt.modules.ddns.update') as ddns_update:
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

    def test_delete_host(self):
        '''
        Tests for delete the forward and reverse records for a host.
        '''
        with patch('salt.modules.ddns.delete') as ddns_delete:
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

        with patch.object(dns.message, 'make_query', MagicMock(return_value=mock_request)):
            with patch.object(dns.query, 'udp', mock_udp_query()):
                with patch.object(dns.rdatatype, 'from_text', MagicMock(return_value=mock_rdtype)):
                    with patch.object(ddns, '_get_keyring', return_value=None):
                        with patch.object(ddns, '_config', return_value=None):
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

        with patch.object(dns.query, 'udp', mock_udp_query()):
            with patch('salt.utils.fopen', mock_open(read_data=file_data), create=True):
                with patch.object(dns.tsigkeyring, 'from_text', return_value=True):
                    with patch.object(ddns, '_get_keyring', return_value=None):
                        with patch.object(ddns, '_config', return_value=None):
                            self.assertTrue(ddns.delete(zone='A', name='B'))
