# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

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

try:
    import dns.query
    import dns.update
    import dns.tsigkeyring
    dns_support = True
except ImportError as e:
    dns_support = False

# Import salt libs
import salt.utils
import json
# Globals
ddns.__grains__ = {}
ddns.__salt__ = {}


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
        file_data = json.dumps({'A': 'B'})
        with patch('dns.message.make_query', return_value=True):
            with patch('dns.rdatatype.from_text', return_value=True):
                with patch('dns.rdata.from_text', return_value=True):
                    mock = MagicMock(return_value=True)
                    with patch.dict(ddns.__salt__, {'config.option': mock}):
                        mock = MagicMock(return_value=True)
                        with patch.dict(ddns.__salt__, {'file.file_exists': mock}):
                            with patch('salt.utils.fopen',
                                       mock_open(read_data=file_data),
                                       create=True):
                                with patch.object(dns.tsigkeyring, 'from_text', return_value=True):
                                    with patch.object(dns.query, 'udp') as mock:
                                        mock.answer = [{'address': 'localhost'}]
                                        self.assertFalse(ddns.update(zone='A',
                                                                     name='B',
                                                                     ttl=1,
                                                                     rdtype='C',
                                                                     data='D'))

    def test_delete(self):
        '''
        Test to delete a DNS record.
        '''
        file_data = json.dumps({'A': 'B'})
        with patch.object(dns.query, 'udp') as mock:
            mock.answer = [{'address': 'localhost'}]
            mock = MagicMock(return_value=True)
            with patch.dict(ddns.__salt__, {'config.option': mock}):
                mock = MagicMock(return_value=True)
                with patch.dict(ddns.__salt__, {'file.file_exists': mock}):
                    with patch('salt.utils.fopen',
                               mock_open(read_data=file_data),
                               create=True):
                        with patch.object(dns.tsigkeyring, 'from_text', return_value=True):
                            self.assertFalse(ddns.delete(zone='A', name='B'))

if __name__ == '__main__':
    from integration import run_tests
    run_tests(DDNSTestCase, needs_daemon=False)