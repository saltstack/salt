"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import salt.modules.neutron as neutron
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock
from tests.support.unit import TestCase


class MockNeutron:
    """
    Mock of neutron
    """

    @staticmethod
    def get_quotas_tenant():
        """
        Mock of get_quotas_tenant method
        """
        return True

    @staticmethod
    def list_quotas():
        """
        Mock of list_quotas method
        """
        return True

    @staticmethod
    def show_quota(tenant_id):
        """
        Mock of show_quota method
        """
        return tenant_id

    @staticmethod
    def update_quota(
        tenant_id,
        subnet,
        router,
        network,
        floatingip,
        port,
        security_group,
        security_group_rule,
    ):
        """
        Mock of update_quota method
        """
        return (
            tenant_id,
            subnet,
            router,
            network,
            floatingip,
            port,
            security_group,
            security_group_rule,
        )

    @staticmethod
    def delete_quota(tenant_id):
        """
        Mock of delete_quota method
        """
        return tenant_id

    @staticmethod
    def list_extensions():
        """
        Mock of list_extensions method
        """
        return True

    @staticmethod
    def list_ports():
        """
        Mock of list_ports method
        """
        return True

    @staticmethod
    def show_port(port):
        """
        Mock of show_port method
        """
        return port

    @staticmethod
    def create_port(name, network, device_id, admin_state_up):
        """
        Mock of create_port method
        """
        return (name, network, device_id, admin_state_up)

    @staticmethod
    def update_port(port, name, admin_state_up):
        """
        Mock of update_port method
        """
        return (port, name, admin_state_up)

    @staticmethod
    def delete_port(port):
        """
        Mock of delete_port method
        """
        return port

    @staticmethod
    def list_networks():
        """
        Mock of list_networks method
        """
        return True

    @staticmethod
    def show_network(network):
        """
        Mock of show_network method
        """
        return network

    @staticmethod
    def create_network(
        name,
        admin_state_up,
        router_ext,
        network_type,
        physical_network,
        segmentation_id,
        shared,
    ):
        """
        Mock of create_network method
        """
        return (
            name,
            admin_state_up,
            router_ext,
            network_type,
            physical_network,
            segmentation_id,
            shared,
        )

    @staticmethod
    def update_network(network, name):
        """
        Mock of update_network method
        """
        return (network, name)

    @staticmethod
    def delete_network(network):
        """
        Mock of delete_network method
        """
        return network

    @staticmethod
    def list_subnets():
        """
        Mock of list_subnets method
        """
        return True

    @staticmethod
    def show_subnet(subnet):
        """
        Mock of show_subnet method
        """
        return subnet

    @staticmethod
    def create_subnet(network, cidr, name, ip_version):
        """
        Mock of create_subnet method
        """
        return (network, cidr, name, ip_version)

    @staticmethod
    def update_subnet(subnet, name):
        """
        Mock of update_subnet method
        """
        return (subnet, name)

    @staticmethod
    def delete_subnet(subnet):
        """
        Mock of delete_subnet method
        """
        return subnet

    @staticmethod
    def list_routers():
        """
        Mock of list_routers method
        """
        return True

    @staticmethod
    def show_router(router):
        """
        Mock of show_router method
        """
        return router

    @staticmethod
    def create_router(name, ext_network, admin_state_up):
        """
        Mock of create_router method
        """
        return (name, ext_network, admin_state_up)

    @staticmethod
    def update_router(router, name, admin_state_up, **kwargs):
        """
        Mock of update_router method
        """
        return (router, name, admin_state_up, kwargs)

    @staticmethod
    def delete_router(router):
        """
        Mock of delete_router method
        """
        return router

    @staticmethod
    def add_interface_router(router, subnet):
        """
        Mock of add_interface_router method
        """
        return (router, subnet)

    @staticmethod
    def remove_interface_router(router, subnet):
        """
        Mock of remove_interface_router method
        """
        return (router, subnet)

    @staticmethod
    def add_gateway_router(router, ext_network):
        """
        Mock of add_gateway_router method
        """
        return (router, ext_network)

    @staticmethod
    def remove_gateway_router(router):
        """
        Mock of remove_gateway_router method
        """
        return router

    @staticmethod
    def list_floatingips():
        """
        Mock of list_floatingips method
        """
        return True

    @staticmethod
    def show_floatingip(floatingip_id):
        """
        Mock of show_floatingip method
        """
        return floatingip_id

    @staticmethod
    def create_floatingip(floating_network, port):
        """
        Mock of create_floatingip method
        """
        return (floating_network, port)

    @staticmethod
    def update_floatingip(floating_network, port):
        """
        Mock of create_floatingip method
        """
        return (floating_network, port)

    @staticmethod
    def delete_floatingip(floatingip_id):
        """
        Mock of delete_floatingip method
        """
        return floatingip_id

    @staticmethod
    def list_security_groups():
        """
        Mock of list_security_groups method
        """
        return True

    @staticmethod
    def show_security_group(security_group):
        """
        Mock of show_security_group method
        """
        return security_group

    @staticmethod
    def create_security_group(name, description):
        """
        Mock of create_security_group method
        """
        return (name, description)

    @staticmethod
    def update_security_group(security_group, name, description):
        """
        Mock of update_security_group method
        """
        return (security_group, name, description)

    @staticmethod
    def delete_security_group(security_group):
        """
        Mock of delete_security_group method
        """
        return security_group

    @staticmethod
    def list_security_group_rules():
        """
        Mock of list_security_group_rules method
        """
        return True

    @staticmethod
    def show_security_group_rule(security_group_rule_id):
        """
        Mock of show_security_group_rule method
        """
        return security_group_rule_id

    @staticmethod
    def create_security_group_rule(
        security_group,
        remote_group_id,
        direction,
        protocol,
        port_range_min,
        port_range_max,
        ethertype,
    ):
        """
        Mock of create_security_group_rule method
        """
        return (
            security_group,
            remote_group_id,
            direction,
            protocol,
            port_range_min,
            port_range_max,
            ethertype,
        )

    @staticmethod
    def delete_security_group_rule(security_group_rule_id):
        """
        Mock of delete_security_group_rule method
        """
        return security_group_rule_id

    @staticmethod
    def list_vpnservices(retrieve_all, **kwargs):
        """
        Mock of list_vpnservices method
        """
        return (retrieve_all, kwargs)

    @staticmethod
    def show_vpnservice(vpnservice, **kwargs):
        """
        Mock of show_vpnservice method
        """
        return (vpnservice, kwargs)

    @staticmethod
    def create_vpnservice(subnet, router, name, admin_state_up):
        """
        Mock of create_vpnservice method
        """
        return (subnet, router, name, admin_state_up)

    @staticmethod
    def update_vpnservice(vpnservice, desc):
        """
        Mock of update_vpnservice method
        """
        return (vpnservice, desc)

    @staticmethod
    def delete_vpnservice(vpnservice):
        """
        Mock of delete_vpnservice method
        """
        return vpnservice

    @staticmethod
    def list_ipsec_site_connections():
        """
        Mock of list_ipsec_site_connections method
        """
        return True

    @staticmethod
    def show_ipsec_site_connection(ipsec_site_connection):
        """
        Mock of show_ipsec_site_connection method
        """
        return ipsec_site_connection

    @staticmethod
    def create_ipsec_site_connection(
        name,
        ipsecpolicy,
        ikepolicy,
        vpnservice,
        peer_cidrs,
        peer_address,
        peer_id,
        psk,
        admin_state_up,
        **kwargs
    ):
        """
        Mock of create_ipsec_site_connection method
        """
        return (
            name,
            ipsecpolicy,
            ikepolicy,
            vpnservice,
            peer_cidrs,
            peer_address,
            peer_id,
            psk,
            admin_state_up,
            kwargs,
        )

    @staticmethod
    def delete_ipsec_site_connection(ipsec_site_connection):
        """
        Mock of delete_vpnservice method
        """
        return ipsec_site_connection

    @staticmethod
    def list_ikepolicies():
        """
        Mock of list_ikepolicies method
        """
        return True

    @staticmethod
    def show_ikepolicy(ikepolicy):
        """
        Mock of show_ikepolicy method
        """
        return ikepolicy

    @staticmethod
    def create_ikepolicy(name, **kwargs):
        """
        Mock of create_ikepolicy method
        """
        return (name, kwargs)

    @staticmethod
    def delete_ikepolicy(ikepolicy):
        """
        Mock of delete_ikepolicy method
        """
        return ikepolicy

    @staticmethod
    def list_ipsecpolicies():
        """
        Mock of list_ipsecpolicies method
        """
        return True

    @staticmethod
    def show_ipsecpolicy(ipsecpolicy):
        """
        Mock of show_ipsecpolicy method
        """
        return ipsecpolicy

    @staticmethod
    def create_ipsecpolicy(name, **kwargs):
        """
        Mock of create_ikepolicy method
        """
        return (name, kwargs)

    @staticmethod
    def delete_ipsecpolicy(ipsecpolicy):
        """
        Mock of delete_ipsecpolicy method
        """
        return ipsecpolicy


class NeutronTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.neutron
    """

    def setup_loader_modules(self):
        return {neutron: {"_auth": MagicMock(return_value=MockNeutron())}}

    # 'get_quotas_tenant' function tests: 1

    def test_get_quotas_tenant(self):
        """
        Test if it fetches tenant info in server's context for
        following quota operation
        """
        self.assertTrue(neutron.get_quotas_tenant(profile="openstack1"))

    # 'list_quotas' function tests: 1

    def test_list_quotas(self):
        """
        Test if it fetches all tenants quotas
        """
        self.assertTrue(neutron.list_quotas(profile="openstack1"))

    # 'show_quota' function tests: 1

    def test_show_quota(self):
        """
        Test if it fetches information of a certain tenant's quotas
        """
        self.assertTrue(neutron.show_quota("Salt", profile="openstack1"))

    # 'update_quota' function tests: 1

    def test_update_quota(self):
        """
        Test if it update a tenant's quota
        """
        self.assertTrue(
            neutron.update_quota(
                "Salt",
                subnet="40",
                router="50",
                network="10",
                floatingip="30",
                port="30",
                security_group="10",
                security_group_rule="SS",
            )
        )

    # 'delete_quota' function tests: 1

    def test_delete_quota(self):
        """
        Test if it delete the specified tenant's quota value
        """
        self.assertTrue(neutron.delete_quota("Salt", profile="openstack1"))

    # 'list_extensions' function tests: 1

    def test_list_extensions(self):
        """
        Test if it fetches a list of all extensions on server side
        """
        self.assertTrue(neutron.list_extensions(profile="openstack1"))

    # 'list_ports' function tests: 1

    def test_list_ports(self):
        """
        Test if it fetches a list of all networks for a tenant
        """
        self.assertTrue(neutron.list_ports(profile="openstack1"))

    # 'show_port' function tests: 1

    def test_show_port(self):
        """
        Test if it fetches information of a certain port
        """
        self.assertTrue(neutron.show_port("1080", profile="openstack1"))

    # 'create_port' function tests: 1

    def test_create_port(self):
        """
        Test if it creates a new port
        """
        self.assertTrue(
            neutron.create_port(
                "Salt",
                "SALTSTACK",
                device_id="800",
                admin_state_up=True,
                profile="openstack1",
            )
        )

    # 'update_port' function tests: 1

    def test_update_port(self):
        """
        Test if it updates a port
        """
        self.assertTrue(
            neutron.update_port(
                "800", "SALTSTACK", admin_state_up=True, profile="openstack1"
            )
        )

    # 'delete_port' function tests: 1

    def test_delete_port(self):
        """
        Test if it deletes the specified port
        """
        self.assertTrue(neutron.delete_port("1080", profile="openstack1"))

    # 'list_networks' function tests: 1

    def test_list_networks(self):
        """
        Test if it fetches a list of all networks for a tenant
        """
        self.assertTrue(neutron.list_networks(profile="openstack1"))

    # 'show_network' function tests: 1

    def test_show_network(self):
        """
        Test if it fetches information of a certain network
        """
        self.assertTrue(neutron.show_network("SALTSTACK", profile="openstack1"))

    # 'create_network' function tests: 1

    def test_create_network(self):
        """
        Test if it creates a new network
        """
        self.assertTrue(neutron.create_network("SALT", profile="openstack1"))

    # 'update_network' function tests: 1

    def test_update_network(self):
        """
        Test if it updates a network
        """
        self.assertTrue(
            neutron.update_network("SALT", "SLATSTACK", profile="openstack1")
        )

    # 'delete_network' function tests: 1

    def test_delete_network(self):
        """
        Test if it deletes the specified network
        """
        self.assertTrue(neutron.delete_network("SALTSTACK", profile="openstack1"))

    # 'list_subnets' function tests: 1

    def test_list_subnets(self):
        """
        Test if it fetches a list of all networks for a tenant
        """
        self.assertTrue(neutron.list_subnets(profile="openstack1"))

    # 'show_subnet' function tests: 1

    def test_show_subnet(self):
        """
        Test if it fetches information of a certain subnet
        """
        self.assertTrue(neutron.show_subnet("SALTSTACK", profile="openstack1"))

    # 'create_subnet' function tests: 1

    def test_create_subnet(self):
        """
        Test if it creates a new subnet
        """
        self.assertTrue(
            neutron.create_subnet(
                "192.168.1.0",
                "192.168.1.0/24",
                name="Salt",
                ip_version=4,
                profile="openstack1",
            )
        )

    # 'update_subnet' function tests: 1

    def test_update_subnet(self):
        """
        Test if it updates a subnet
        """
        self.assertTrue(
            neutron.update_subnet("255.255.255.0", name="Salt", profile="openstack1")
        )

    # 'delete_subnet' function tests: 1

    def test_delete_subnet(self):
        """
        Test if it deletes the specified subnet
        """
        self.assertTrue(neutron.delete_subnet("255.255.255.0", profile="openstack1"))

    # 'list_routers' function tests: 1

    def test_list_routers(self):
        """
        Test if it fetches a list of all routers for a tenant
        """
        self.assertTrue(neutron.list_routers(profile="openstack1"))

    # 'show_router' function tests: 1

    def test_show_router(self):
        """
        Test if it fetches information of a certain router
        """
        self.assertTrue(neutron.show_router("SALTSTACK", profile="openstack1"))

    # 'create_router' function tests: 1

    def test_create_router(self):
        """
        Test if it creates a new router
        """
        self.assertTrue(
            neutron.create_router(
                "SALT", "192.168.1.0", admin_state_up=True, profile="openstack1"
            )
        )

    # 'update_router' function tests: 1

    def test_update_router(self):
        """
        Test if it updates a router
        """
        self.assertTrue(
            neutron.update_router("255.255.255.0", name="Salt", profile="openstack1")
        )

    # 'delete_router' function tests: 1

    def test_delete_router(self):
        """
        Test if it delete the specified router
        """
        self.assertTrue(neutron.delete_router("SALTSTACK", profile="openstack1"))

    # 'add_interface_router' function tests: 1

    def test_add_interface_router(self):
        """
        Test if it adds an internal network interface to the specified router
        """
        self.assertTrue(
            neutron.add_interface_router("Salt", "255.255.255.0", profile="openstack1")
        )

    # 'remove_interface_router' function tests: 1

    def test_remove_interface_router(self):
        """
        Test if it removes an internal network interface from the specified
        router
        """
        self.assertTrue(
            neutron.remove_interface_router(
                "Salt", "255.255.255.0", profile="openstack1"
            )
        )

    # 'add_gateway_router' function tests: 1

    def test_add_gateway_router(self):
        """
        Test if it adds an external network gateway to the specified router
        """
        self.assertTrue(
            neutron.add_gateway_router("Salt", "SALTSTACK", profile="openstack1")
        )

    # 'remove_gateway_router' function tests: 1

    def test_remove_gateway_router(self):
        """
        Test if it removes an external network gateway from the specified router
        """

        self.assertTrue(
            neutron.remove_gateway_router("SALTSTACK", profile="openstack1")
        )

    # 'list_floatingips' function tests: 1

    def test_list_floatingips(self):
        """
        Test if it fetch a list of all floatingIPs for a tenant
        """
        self.assertTrue(neutron.list_floatingips(profile="openstack1"))

    # 'show_floatingip' function tests: 1

    def test_show_floatingip(self):
        """
        Test if it fetches information of a certain floatingIP
        """
        self.assertTrue(neutron.show_floatingip("SALTSTACK", profile="openstack1"))

    # 'create_floatingip' function tests: 1

    def test_create_floatingip(self):
        """
        Test if it creates a new floatingIP
        """
        self.assertTrue(
            neutron.create_floatingip("SALTSTACK", port="800", profile="openstack1")
        )

    # 'update_floatingip' function tests: 1

    def test_update_floatingip(self):
        """
        Test if it updates a floatingIP
        """
        self.assertTrue(
            neutron.update_floatingip("SALTSTACK", port="800", profile="openstack1")
        )

    # 'delete_floatingip' function tests: 1

    def test_delete_floatingip(self):
        """
        Test if it deletes the specified floating IP
        """
        self.assertTrue(neutron.delete_floatingip("SALTSTACK", profile="openstack1"))

    # 'list_security_groups' function tests: 1

    def test_list_security_groups(self):
        """
        Test if it fetches a list of all security groups for a tenant
        """
        self.assertTrue(neutron.list_security_groups(profile="openstack1"))

    # 'show_security_group' function tests: 1

    def test_show_security_group(self):
        """
        Test if it fetches information of a certain security group
        """
        self.assertTrue(neutron.show_security_group("SALTSTACK", profile="openstack1"))

    # 'create_security_group' function tests: 1

    def test_create_security_group(self):
        """
        Test if it creates a new security group
        """
        self.assertTrue(
            neutron.create_security_group(
                "SALTSTACK", "Security group", profile="openstack1"
            )
        )

    # 'update_security_group' function tests: 1

    def test_update_security_group(self):
        """
        Test if it updates a security group
        """
        self.assertTrue(
            neutron.update_security_group(
                "SALT", "SALTSTACK", "Security group", profile="openstack1"
            )
        )

    # 'delete_security_group' function tests: 1

    def test_delete_security_group(self):
        """
        Test if it deletes the specified security group
        """
        self.assertTrue(neutron.delete_security_group("SALT", profile="openstack1"))

    # 'list_security_group_rules' function tests: 1

    def test_list_security_group_rules(self):
        """
        Test if it fetches a list of all security group rules for a tenant
        """
        self.assertTrue(neutron.list_security_group_rules(profile="openstack1"))

    # 'show_security_group_rule' function tests: 1

    def test_show_security_group_rule(self):
        """
        Test if it fetches information of a certain security group rule
        """
        self.assertTrue(
            neutron.show_security_group_rule("SALTSTACK", profile="openstack1")
        )

    # 'create_security_group_rule' function tests: 1

    def test_create_security_group_rule(self):
        """
        Test if it creates a new security group rule
        """
        self.assertTrue(
            neutron.create_security_group_rule("SALTSTACK", profile="openstack1")
        )

    # 'delete_security_group_rule' function tests: 1

    def test_delete_security_group_rule(self):
        """
        Test if it deletes the specified security group rule
        """
        self.assertTrue(
            neutron.delete_security_group_rule("SALTSTACK", profile="openstack1")
        )

    # 'list_vpnservices' function tests: 1

    def test_list_vpnservices(self):
        """
        Test if it fetches a list of all configured VPN services for a tenant
        """
        self.assertTrue(neutron.list_vpnservices(True, profile="openstack1"))

    # 'show_vpnservice' function tests: 1

    def test_show_vpnservice(self):
        """
        Test if it fetches information of a specific VPN service
        """
        self.assertTrue(neutron.show_vpnservice("SALT", profile="openstack1"))

    # 'create_vpnservice' function tests: 1

    def test_create_vpnservice(self):
        """
        Test if it creates a new VPN service
        """
        self.assertTrue(
            neutron.create_vpnservice(
                "255.255.255.0", "SALT", "SALTSTACK", True, profile="openstack1"
            )
        )

    # 'update_vpnservice' function tests: 1

    def test_update_vpnservice(self):
        """
        Test if it updates a VPN service
        """
        self.assertTrue(
            neutron.update_vpnservice("SALT", "VPN Service1", profile="openstack1")
        )

    # 'delete_vpnservice' function tests: 1

    def test_delete_vpnservice(self):
        """
        Test if it deletes the specified VPN service
        """
        self.assertTrue(
            neutron.delete_vpnservice("SALT VPN Service1", profile="openstack1")
        )

    # 'list_ipsec_site_connections' function tests: 1

    def test_list_ipsec_site(self):
        """
        Test if it fetches all configured IPsec Site Connections for a tenant
        """
        self.assertTrue(neutron.list_ipsec_site_connections(profile="openstack1"))

    # 'show_ipsec_site_connection' function tests: 1

    def test_show_ipsec_site_connection(self):
        """
        Test if it fetches information of a specific IPsecSiteConnection
        """
        self.assertTrue(
            neutron.show_ipsec_site_connection("SALT", profile="openstack1")
        )

    # 'create_ipsec_site_connection' function tests: 1

    def test_create_ipsec_site(self):
        """
        Test if it creates a new IPsecSiteConnection
        """
        self.assertTrue(
            neutron.create_ipsec_site_connection(
                "SALTSTACK",
                "A",
                "B",
                "C",
                "192.168.1.0/24",
                "192.168.1.11",
                "192.168.1.10",
                "secret",
                profile="openstack1",
            )
        )

    # 'delete_ipsec_site_connection' function tests: 1

    def test_delete_ipsec_site(self):
        """
        Test if it deletes the specified IPsecSiteConnection
        """
        self.assertTrue(
            neutron.delete_ipsec_site_connection(
                "SALT VPN Service1", profile="openstack1"
            )
        )

    # 'list_ikepolicies' function tests: 1

    def test_list_ikepolicies(self):
        """
        Test if it fetches a list of all configured IKEPolicies for a tenant
        """
        self.assertTrue(neutron.list_ikepolicies(profile="openstack1"))

    # 'show_ikepolicy' function tests: 1

    def test_show_ikepolicy(self):
        """
        Test if it fetches information of a specific IKEPolicy
        """
        self.assertTrue(neutron.show_ikepolicy("SALT", profile="openstack1"))

    # 'create_ikepolicy' function tests: 1

    def test_create_ikepolicy(self):
        """
        Test if it creates a new IKEPolicy
        """
        self.assertTrue(neutron.create_ikepolicy("SALTSTACK", profile="openstack1"))

    # 'delete_ikepolicy' function tests: 1

    def test_delete_ikepolicy(self):
        """
        Test if it deletes the specified IKEPolicy
        """
        self.assertTrue(neutron.delete_ikepolicy("SALT", profile="openstack1"))

    # 'list_ipsecpolicies' function tests: 1

    def test_list_ipsecpolicies(self):
        """
        Test if it fetches a list of all configured IPsecPolicies for a tenant
        """
        self.assertTrue(neutron.list_ipsecpolicies(profile="openstack1"))

    # 'show_ipsecpolicy' function tests: 1

    def test_show_ipsecpolicy(self):
        """
        Test if it fetches information of a specific IPsecPolicy
        """
        self.assertTrue(neutron.show_ipsecpolicy("SALT", profile="openstack1"))

    # 'create_ipsecpolicy' function tests: 1

    def test_create_ipsecpolicy(self):
        """
        Test if it creates a new IPsecPolicy
        """
        self.assertTrue(neutron.create_ipsecpolicy("SALTSTACK", profile="openstack1"))

    # 'delete_ipsecpolicy' function tests: 1

    def test_delete_ipsecpolicy(self):
        """
        Test if it deletes the specified IPsecPolicy
        """
        self.assertTrue(neutron.delete_ipsecpolicy("SALT", profile="openstack1"))
