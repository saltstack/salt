# -*- encoding: utf-8 -*-
'''
    :codeauthor: :email: `Justin Anderson <janderson@saltstack.com>`

    tests.integration.states.network
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''
# Python libs

# Salt libs
import integration

# Salttesting libs
from salttesting import skipIf
from salttesting.helpers import destructiveTest, ensure_in_syspath

ensure_in_syspath('../../')

def _check_arch_linux():
    with open('/etc/os-release', 'r') as f:
        release = f.readline()
        r = release.split('=')[1].strip().strip('"')
        return r


@destructiveTest
@skipIf(_check_arch_linux() == 'Arch Linux', 'Network state not support on Arch')
class NetworkTest(integration.ModuleCase):
    '''
    Validate network state module
    '''
    def setUp(self):
        self.run_function('cmd.run', ['ip link add name dummy0 type dummy'])

    def tearDown(self):
        self.run_function('cmd.run', ['ip link delete dev dummy0'])

    def test_managed(self):
        '''
        network.managed
        '''
        if_name = 'dummy0'
        enabled = True
        _type = 'eth'
        ipaddr = '10.1.0.1'
        netmask = '255.255.255.0'
        broadcast = '10.1.0.255'

        expected_if_ret = [{
                    "broadcast": broadcast,
                    "netmask": netmask,
                    "label": if_name,
                    "address": ipaddr
                }]
        interface = self.run_function('network.interface', [if_name])
        self.assertEqual(interface, '')

        ret = self.run_state('network.managed',
                            name=if_name, enabled=enabled, type=_type,
                            ipaddr=ipaddr, netmask=netmask)

        interface = self.run_function('network.interface', [if_name])
        self.assertEqual(interface, expected_if_ret)

    def test_routes(self):
        '''
        network.routes
        '''
        if_name = 'dummy0'
        routes = [{'name': 'secure_network',
                   'ipaddr': '10.2.0.0',
                   'netmask': '255.255.255.0',
                   'gateway': '10.1.0.3'}]

        ret = self.run_state('network.routes', name=if_name, routes=routes)

        self.assertTrue(ret['network_|-dummy0_|-dummy0_|-routes']['result'])

    def test_system(self):
        '''
        network.system
        '''
        conf_name = 'dummy_system'
        enabled = True
        hostname = 'server1.example.com'
        gateway = '10.1.0.1'
        gatewaydev = 'dummy0'

        ret = self.run_state('network.system',
                    name=conf_name, enabled=enabled, hostname=hostname,
                    gateway=gateway, gatewaydev=gatewaydev)

        self.assertTrue(ret['network_|-dummy_system_|-dummy_system_|-system']['result'])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(NetworkTest)
