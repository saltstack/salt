# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(FirewalldTestCase, needs_daemon=False)
