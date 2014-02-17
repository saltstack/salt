# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Salt Testing Libs
from salttesting import TestCase
from salttesting.mock import MagicMock, patch, mock_open, call
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

#Import Salt Libs
from salt.modules import dnsutil

mock_hosts_file = '##\n'\
                    '# Host Database\n'\
                    '#\n'\
                    '# localhost is used to configure the loopback interface\n'\
                    '# when the system is booting.  Do not change this entry.\n'\
                    '##\n'\
                    '127.0.0.1	localhost\n'\
                    '255.255.255.255	broadcasthost\n'\
                    '::1             localhost\n'\
                    'fe80::1%lo0	localhost'

mock_hosts_file_rtn = {'::1': ['localhost'], '255.255.255.255': ['broadcasthost'],
                       '127.0.0.1': ['localhost'], 'fe80::1%lo0': ['localhost']}

mock_calls_list = [call.read(), call.write('##\n'),
                   call.write('# Host Database\n'),
                   call.write('#\n'),
                   call.write('# localhost is used to configure the loopback interface\n'),
                   call.write('# when the system is booting.  Do not change this entry.\n'),
                   call.write('##\n'),
                   call.write('127.0.0.1 localhost'),
                   call.write('\n'),
                   call.write('255.255.255.255 broadcasthost'),
                   call.write('\n'),
                   call.write('::1 localhost'),
                   call.write('\n'),
                   call.write('fe80::1%lo0 localhost'),
                   call.write('\n'),
                   call.close()]


class DNSUtilTestCase(TestCase):

    def test_parse_hosts(self):
        with patch('salt.utils.fopen', mock_open(read_data=mock_hosts_file)):
            self.assertEqual(dnsutil.parse_hosts(), {'::1': ['localhost'],
                                                     '255.255.255.255': ['broadcasthost'],
                                                     '127.0.0.1': ['localhost'],
                                                     'fe80::1%lo0': ['localhost']})

    @patch('salt.modules.dnsutil.parse_hosts', MagicMock(return_value=mock_hosts_file_rtn))
    def test_hosts_append(self):
        with patch('salt.utils.fopen', mock_open(read_data=mock_hosts_file)) as m_open:
            dnsutil.hosts_append('/etc/hosts', '127.0.0.1', 'ad1.yuk.co,ad2.yuk.co')
            helper_open = m_open()
            helper_open.write.assert_called_once_with('\n127.0.0.1 ad1.yuk.co ad2.yuk.co')

    def test_hosts_remove(self):
        toRemove = 'ad1.yuk.co'
        new_mock_file = mock_hosts_file + '\n127.0.0.1 ' + toRemove + '\n'
        with patch('salt.utils.fopen', mock_open(read_data=new_mock_file)) as m_open:
            dnsutil.hosts_remove('/etc/hosts', toRemove)
            helper_open = m_open()
            calls_list = helper_open.method_calls
            self.assertEqual(calls_list, mock_calls_list)
