# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import firewalld


# Globals
firewalld.__grains__ = {}
firewalld.__salt__ = {}
firewalld.__context__ = {}
firewalld.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class FirewalldTestCase(TestCase):
    '''
    Test cases for salt.modules.firewalld
    '''
    def test_version(self):
        '''
        Test for Return version from firewall-cmd
        '''
        with patch.object(firewalld, '__firewall_cmd', return_value=2):
            self.assertEqual(firewalld.version(), 2)

    def test_default_zone(self):
        '''
        Test for Print default zone for connections and interfaces
        '''
        with patch.object(firewalld, '__firewall_cmd', return_value='A'):
            self.assertEqual(firewalld.default_zone(), 'A')

    def test_list_zones(self):
        '''
        Test for List everything added for or enabled in all zones
        '''
        with patch.object(firewalld, '__firewall_cmd', return_value=[]):
            self.assertEqual(firewalld.default_zone(), [])

    def test_get_zones(self):
        '''
        Test for Print predefined zones
        '''
        with patch.object(firewalld, '__firewall_cmd', return_value='A'):
            self.assertEqual(firewalld.get_zones(), ['A'])

    def test_get_services(self):
        '''
        Test for Print predefined services
        '''
        with patch.object(firewalld, '__firewall_cmd', return_value='A'):
            self.assertEqual(firewalld.get_services(), ['A'])

    def test_get_icmp_types(self):
        '''
        Test for Print predefined icmptypes
        '''
        with patch.object(firewalld, '__firewall_cmd', return_value='A'):
            self.assertEqual(firewalld.get_icmp_types(), ['A'])

    def test_new_zone(self):
        '''
        Test for Add a new zone
        '''
        with patch.object(firewalld, '__mgmt', return_value='success'):
            mock = MagicMock(return_value='A')
            with patch.object(firewalld, '__firewall_cmd', mock):
                self.assertEqual(firewalld.new_zone('zone'), 'A')

        with patch.object(firewalld, '__mgmt', return_value='A'):
            self.assertEqual(firewalld.new_zone('zone'), 'A')

        with patch.object(firewalld, '__mgmt', return_value='A'):
            self.assertEqual(firewalld.new_zone('zone', False), 'A')

    def test_delete_zone(self):
        '''
        Test for Delete an existing zone
        '''
        with patch.object(firewalld, '__mgmt', return_value='success'):
            with patch.object(firewalld, '__firewall_cmd', return_value='A'):
                self.assertEqual(firewalld.delete_zone('zone'), 'A')

        with patch.object(firewalld, '__mgmt', return_value='A'):
            self.assertEqual(firewalld.delete_zone('zone'), 'A')

        mock = MagicMock(return_value='A')
        with patch.object(firewalld, '__mgmt', return_value='A'):
            self.assertEqual(firewalld.delete_zone('zone', False), 'A')

    def test_set_default_zone(self):
        '''
        Test for Set default zone
        '''
        with patch.object(firewalld, '__firewall_cmd', return_value='A'):
            self.assertEqual(firewalld.set_default_zone('zone'), 'A')

    def test_new_service(self):
        '''
        Test for Add a new service
        '''
        with patch.object(firewalld, '__mgmt', return_value='success'):
            mock = MagicMock(return_value='A')
            with patch.object(firewalld, '__firewall_cmd', return_value='A'):
                self.assertEqual(firewalld.new_service('zone'), 'A')

        with patch.object(firewalld, '__mgmt', return_value='A'):
            self.assertEqual(firewalld.new_service('zone'), 'A')

        with patch.object(firewalld, '__mgmt', return_value='A'):
            self.assertEqual(firewalld.new_service('zone', False), 'A')

    def test_delete_service(self):
        '''
        Test for Delete an existing service
        '''
        with patch.object(firewalld, '__mgmt', return_value='success'):
            mock = MagicMock(return_value='A')
            with patch.object(firewalld, '__firewall_cmd', return_value='A'):
                self.assertEqual(firewalld.delete_service('name'), 'A')

        with patch.object(firewalld, '__mgmt', return_value='A'):
            self.assertEqual(firewalld.delete_service('name'), 'A')

        with patch.object(firewalld, '__mgmt', return_value='A'):
            self.assertEqual(firewalld.delete_service('name', False), 'A')

    def test_list_all(self):
        '''
        Test for List everything added for or enabled in a zone
        '''
        with patch.object(firewalld, '__firewall_cmd', return_value=''):
            self.assertEqual(firewalld.list_all(), {})

    def test_list_services(self):
        '''
        Test for List services added for zone as a space separated list.
        '''
        with patch.object(firewalld, '__firewall_cmd', return_value=''):
            self.assertEqual(firewalld.list_services(), [])

    def test_add_service(self):
        '''
        Test for Add a service for zone
        '''
        with patch.object(firewalld, '__firewall_cmd', return_value=''):
            self.assertEqual(firewalld.add_service('name'), '')

    def test_remove_service(self):
        '''
        Test for Remove a service from zone
        '''
        with patch.object(firewalld, '__firewall_cmd', return_value=''):
            self.assertEqual(firewalld.remove_service('name'), '')

    def test_add_masquerade(self):
        '''
        Test for adding masquerade
        '''
        with patch.object(firewalld, '__firewall_cmd', return_value='success'):
            self.assertEqual(firewalld.add_masquerade('name'), 'success')

    def test_remove_masquerade(self):
        '''
        Test for removing masquerade
        '''
        with patch.object(firewalld, '__firewall_cmd', return_value='success'):
            self.assertEqual(firewalld.remove_masquerade('name'), 'success')

    def test_add_port(self):
        '''
        Test adding a port to a specific zone
        '''
        with patch.object(firewalld, '__firewall_cmd', return_value='success'):
            self.assertEqual(firewalld.add_port('zone', '80/tcp'), 'success')

    def test_remove_port(self):
        '''
        Test removing a port from a specific zone
        '''
        with patch.object(firewalld, '__firewall_cmd', return_value='success'):
            self.assertEqual(firewalld.remove_port('zone', '80/tcp'), 'success')

    def test_list_ports(self):
        '''
        Test listing ports within a zone
        '''
        ret = '22/tcp 53/udp 53/tcp'
        exp = ['22/tcp', '53/udp', '53/tcp']

        with patch.object(firewalld, '__firewall_cmd', return_value=ret):
            self.assertEqual(firewalld.list_ports('zone'), exp)

    def test_add_port_fwd(self):
        '''
        Test adding port forwarding on a zone
        '''
        with patch.object(firewalld, '__firewall_cmd', return_value='success'):
            self.assertEqual(firewalld.add_port_fwd('zone', '22', '2222', 'tcp'), 'success')

    def test_remove_port_fwd(self):
        '''
        Test removing port forwarding on a zone
        '''
        with patch.object(firewalld, '__firewall_cmd', return_value='success'):
            self.assertEqual(firewalld.remove_port_fwd('zone', '22', '2222', 'tcp'), 'success')

    def test_list_port_fwd(self):
        '''
        Test listing all port forwarding for a zone
        '''
        ret = 'port=23:proto=tcp:toport=8080:toaddr=\nport=80:proto=tcp:toport=443:toaddr='
        exp = [{'Destination address': '',
                'Destination port': '8080',
                'Protocol': 'tcp',
                'Source port': '23'},
               {'Destination address': '',
                'Destination port': '443',
                'Protocol': 'tcp',
                'Source port': '80'}]

        with patch.object(firewalld, '__firewall_cmd', return_value=ret):
            self.assertEqual(firewalld.list_port_fwd('zone'), exp)

    def test_block_icmp(self):
        '''
        Test ICMP block
        '''
        with patch.object(firewalld, '__firewall_cmd', return_value='success'):
            with patch.object(firewalld, 'get_icmp_types', return_value='echo-reply'):
                self.assertEqual(firewalld.block_icmp('zone', 'echo-reply'), 'success')

        with patch.object(firewalld, '__firewall_cmd'):
            self.assertFalse(firewalld.block_icmp('zone', 'echo-reply'))

    def test_allow_icmp(self):
        '''
        Test ICMP allow
        '''
        with patch.object(firewalld, '__firewall_cmd', return_value='success'):
            with patch.object(firewalld, 'get_icmp_types', return_value='echo-reply'):
                self.assertEqual(firewalld.allow_icmp('zone', 'echo-reply'), 'success')

        with patch.object(firewalld, '__firewall_cmd', return_value='success'):
            self.assertFalse(firewalld.allow_icmp('zone', 'echo-reply'))

    def test_list_icmp_block(self):
        '''
        Test ICMP block list
        '''
        ret = 'echo-reply echo-request'
        exp = ['echo-reply', 'echo-request']

        with patch.object(firewalld, '__firewall_cmd', return_value=ret):
            self.assertEqual(firewalld.list_icmp_block('zone'), exp)

    def test_get_rich_rules(self):
        '''
        Test listing rich rules bound to a zone
        '''
        with patch.object(firewalld, '__firewall_cmd', return_value=''):
            self.assertEqual(firewalld.get_rich_rules('zone'), [])

    def test_add_rich_rule(self):
        '''
        Test adding a rich rule to a zone
        '''
        with patch.object(firewalld, '__firewall_cmd', return_value='success'):
            self.assertEqual(firewalld.add_rich_rule('zone', 'rule family="ipv4" source address="1.2.3.4" accept'), 'success')

    def test_remove_rich_rule(self):
        '''
        Test removing a rich rule to a zone
        '''
        with patch.object(firewalld, '__firewall_cmd', return_value='success'):
            self.assertEqual(firewalld.remove_rich_rule('zone', 'rule family="ipv4" source address="1.2.3.4" accept'), 'success')

if __name__ == '__main__':
    from integration import run_tests
    run_tests(FirewalldTestCase, needs_daemon=False)
