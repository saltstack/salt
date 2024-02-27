"""
Neutron class
"""

import logging

import salt.utils.versions
from salt import exceptions

# pylint: disable=import-error
HAS_NEUTRON = False
try:
    from neutronclient.shell import NeutronShell
    from neutronclient.v2_0 import client

    HAS_NEUTRON = True
except ImportError:
    pass

HAS_KEYSTONEAUTH = False
try:
    import keystoneauth1.loading
    import keystoneauth1.session

    HAS_KEYSTONEAUTH = True
except ImportError:
    pass
# pylint: enable=import-error


# Get logging started
log = logging.getLogger(__name__)


def check_neutron():
    return HAS_NEUTRON


def check_keystone():
    return HAS_KEYSTONEAUTH


def sanitize_neutronclient(kwargs):
    variables = (
        "username",
        "user_id",
        "password",
        "token",
        "tenant_name",
        "tenant_id",
        "auth_url",
        "service_type",
        "endpoint_type",
        "region_name",
        "verify",
        "endpoint_url",
        "timeout",
        "insecure",
        "ca_cert",
        "retries",
        "raise_error",
        "session",
        "auth",
    )
    ret = {}
    for var in kwargs.keys():
        if var in variables:
            ret[var] = kwargs[var]

    return ret


# Function alias to not shadow built-ins
class SaltNeutron(NeutronShell):
    """
    Class for all neutronclient functions
    """

    def __init__(
        self,
        username,
        tenant_name,
        auth_url,
        password=None,
        region_name=None,
        service_type="network",
        os_auth_plugin=None,
        use_keystoneauth=False,
        **kwargs
    ):
        """
        Set up neutron credentials
        """
        salt.utils.versions.warn_until(
            "Argon",
            "The neutron module has been deprecated and will be removed in {version}.\n"
            "This includes\n"
            "* salt.utils.openstack.neutron\n"
            "* salt.modules.neutron\n"
            "* salt.pillar.neutron\n"
            "Please migrate to neutronng.\n"
            "salt.modules.neutron -> salt.modules.neutronng\n"
            "salt.pillar.neutron -> salt.pillar.neutronng\n"
            "Please update to using the neutronng module",
        )
        if not HAS_NEUTRON:
            return None

        elif all([use_keystoneauth, HAS_KEYSTONEAUTH]):
            self._new_init(
                username=username,
                project_name=tenant_name,
                auth_url=auth_url,
                region_name=region_name,
                service_type=service_type,
                os_auth_plugin=os_auth_plugin,
                password=password,
                **kwargs
            )
        else:
            self._old_init(
                username=username,
                tenant_name=tenant_name,
                auth_url=auth_url,
                region_name=region_name,
                service_type=service_type,
                os_auth_plugin=os_auth_plugin,
                password=password,
                **kwargs
            )

    def _new_init(
        self,
        username,
        project_name,
        auth_url,
        region_name,
        service_type,
        password,
        os_auth_plugin,
        auth=None,
        verify=True,
        **kwargs
    ):
        if auth is None:
            auth = {}

        loader = keystoneauth1.loading.get_plugin_loader(os_auth_plugin or "password")

        self.client_kwargs = kwargs.copy()
        self.kwargs = auth.copy()

        self.kwargs["username"] = username
        self.kwargs["project_name"] = project_name
        self.kwargs["auth_url"] = auth_url
        self.kwargs["password"] = password
        if auth_url.endswith("3"):
            self.kwargs["user_domain_name"] = kwargs.get("user_domain_name", "default")
            self.kwargs["project_domain_name"] = kwargs.get(
                "project_domain_name", "default"
            )

        self.client_kwargs["region_name"] = region_name
        self.client_kwargs["service_type"] = service_type

        self.client_kwargs = sanitize_neutronclient(self.client_kwargs)
        options = loader.load_from_options(**self.kwargs)
        self.session = keystoneauth1.session.Session(auth=options, verify=verify)
        self.network_conn = client.Client(session=self.session, **self.client_kwargs)

    def _old_init(
        self,
        username,
        tenant_name,
        auth_url,
        region_name,
        service_type,
        password,
        os_auth_plugin,
        auth=None,
        verify=True,
        **kwargs
    ):
        self.kwargs = kwargs.copy()

        self.kwargs["username"] = username
        self.kwargs["tenant_name"] = tenant_name
        self.kwargs["auth_url"] = auth_url
        self.kwargs["service_type"] = service_type
        self.kwargs["password"] = password
        self.kwargs["region_name"] = region_name
        self.kwargs["verify"] = verify

        self.kwargs = sanitize_neutronclient(self.kwargs)

        self.network_conn = client.Client(**self.kwargs)

    @staticmethod
    def _fetch(resources, name_or_id):
        ret = []
        for resource in resources:
            if resource["id"] == name_or_id:
                return resource
            if resource.get("name") == name_or_id:
                ret.append(resource)
        if not ret:
            raise exceptions.MinionError("Resource not found.")
        elif len(ret) >= 2:
            raise exceptions.MinionError("Multiple resource matches found.")
        else:
            return ret[0]

    def _find_port_id(self, resource):
        resource = self._fetch_port(resource)
        return resource["id"]

    def _find_network_id(self, resource):
        resource = self._fetch_network(resource)
        return resource["id"]

    def _find_subnet_id(self, resource):
        resource = self._fetch_subnet(resource)
        return resource["id"]

    def _find_router_id(self, resource):
        resource = self._fetch_router(resource)
        return resource["id"]

    def _find_security_group_id(self, resource):
        resource = self._fetch_security_group(resource)
        return resource["id"]

    def _find_vpnservice_id(self, resource):
        resource = self._fetch_vpnservice(resource)
        return resource["id"]

    def _find_ipsec_site_connection_id(self, resource):
        resource = self._fetch_ipsec_site_connection(resource)
        return resource["id"]

    def _find_ikepolicy_id(self, resource):
        resource = self._fetch_ikepolicy(resource)
        return resource["id"]

    def _find_ipsecpolicy_id(self, resource):
        resource = self._fetch_ipsecpolicy(resource)
        return resource["id"]

    def _find_firewall_rule_id(self, resource):
        resource = self._fetch_firewall_rule(resource)
        return resource["id"]

    def _fetch_port(self, name_or_id):
        resources = self.list_ports()["ports"]
        return self._fetch(resources, name_or_id)

    def _fetch_network(self, name_or_id):
        resources = self.list_networks()["networks"]
        return self._fetch(resources, name_or_id)

    def _fetch_subnet(self, name_or_id):
        resources = self.list_subnets()["subnets"]
        return self._fetch(resources, name_or_id)

    def _fetch_router(self, name_or_id):
        resources = self.list_routers()["routers"]
        return self._fetch(resources, name_or_id)

    def _fetch_security_group(self, name_or_id):
        resources = self.list_security_groups()["security_groups"]
        return self._fetch(resources, name_or_id)

    def _fetch_vpnservice(self, name_or_id):
        resources = self.list_vpnservices()["vpnservices"]
        return self._fetch(resources, name_or_id)

    def _fetch_ipsec_site_connection(self, name_or_id):
        resources = self.list_ipsec_site_connections()["ipsec_site_connections"]
        return self._fetch(resources, name_or_id)

    def _fetch_ikepolicy(self, name_or_id):
        resources = self.list_ikepolicies()["ikepolicies"]
        return self._fetch(resources, name_or_id)

    def _fetch_ipsecpolicy(self, name_or_id):
        resources = self.list_ipsecpolicies()["ipsecpolicies"]
        return self._fetch(resources, name_or_id)

    def _fetch_firewall_rule(self, name_or_id):
        resources = self.list_firewall_rules()["firewall_rules"]
        return self._fetch(resources, name_or_id)

    def _fetch_firewall(self, name_or_id):
        resources = self.list_firewalls()["firewalls"]
        return self._fetch(resources, name_or_id)

    def get_quotas_tenant(self):
        """
        Fetches tenant info in server's context
        for following quota operation
        """
        return self.get_quotas_tenant()

    def list_quotas(self):
        """
        Fetches all tenants quotas
        """
        return self.network_conn.list_quotas()

    def show_quota(self, tenant_id):
        """
        Fetches information of a certain tenant's quotas
        """
        return self.network_conn.show_quota(tenant_id=tenant_id)

    def update_quota(
        self,
        tenant_id,
        subnet=None,
        router=None,
        network=None,
        floatingip=None,
        port=None,
        sec_grp=None,
        sec_grp_rule=None,
    ):
        """
        Update a tenant's quota
        """
        body = {}
        if subnet:
            body["subnet"] = subnet
        if router:
            body["router"] = router
        if network:
            body["network"] = network
        if floatingip:
            body["floatingip"] = floatingip
        if port:
            body["port"] = port
        if sec_grp:
            body["security_group"] = sec_grp
        if sec_grp_rule:
            body["security_group_rule"] = sec_grp_rule
        return self.network_conn.update_quota(tenant_id=tenant_id, body={"quota": body})

    def delete_quota(self, tenant_id):
        """
        Delete the specified tenant's quota value
        """
        ret = self.network_conn.delete_quota(tenant_id=tenant_id)
        return ret if ret else True

    def list_extensions(self):
        """
        Fetches a list of all extensions on server side
        """
        return self.network_conn.list_extensions()

    def list_ports(self):
        """
        Fetches a list of all ports for a tenant
        """
        return self.network_conn.list_ports()

    def show_port(self, port):
        """
        Fetches information of a certain port
        """
        return self._fetch_port(port)

    def create_port(self, name, network, device_id=None, admin_state_up=True):
        """
        Creates a new port
        """
        net_id = self._find_network_id(network)
        body = {"admin_state_up": admin_state_up, "name": name, "network_id": net_id}
        if device_id:
            body["device_id"] = device_id
        return self.network_conn.create_port(body={"port": body})

    def update_port(self, port, name, admin_state_up=True):
        """
        Updates a port
        """
        port_id = self._find_port_id(port)
        body = {"name": name, "admin_state_up": admin_state_up}
        return self.network_conn.update_port(port=port_id, body={"port": body})

    def delete_port(self, port):
        """
        Deletes the specified port
        """
        port_id = self._find_port_id(port)
        ret = self.network_conn.delete_port(port=port_id)
        return ret if ret else True

    def list_networks(self):
        """
        Fetches a list of all networks for a tenant
        """
        return self.network_conn.list_networks()

    def show_network(self, network):
        """
        Fetches information of a certain network
        """
        return self._fetch_network(network)

    def create_network(
        self,
        name,
        admin_state_up=True,
        router_ext=None,
        network_type=None,
        physical_network=None,
        segmentation_id=None,
        shared=None,
        vlan_transparent=None,
    ):
        """
        Creates a new network
        """
        body = {"name": name, "admin_state_up": admin_state_up}
        if router_ext:
            body["router:external"] = router_ext
        if network_type:
            body["provider:network_type"] = network_type
        if physical_network:
            body["provider:physical_network"] = physical_network
        if segmentation_id:
            body["provider:segmentation_id"] = segmentation_id
        if shared:
            body["shared"] = shared
        if vlan_transparent:
            body["vlan_transparent"] = vlan_transparent
        return self.network_conn.create_network(body={"network": body})

    def update_network(self, network, name):
        """
        Updates a network
        """
        net_id = self._find_network_id(network)
        return self.network_conn.update_network(
            network=net_id, body={"network": {"name": name}}
        )

    def delete_network(self, network):
        """
        Deletes the specified network
        """
        net_id = self._find_network_id(network)
        ret = self.network_conn.delete_network(network=net_id)
        return ret if ret else True

    def list_subnets(self):
        """
        Fetches a list of all networks for a tenant
        """
        return self.network_conn.list_subnets()

    def show_subnet(self, subnet):
        """
        Fetches information of a certain subnet
        """
        return self._fetch_subnet(subnet)

    def create_subnet(self, network, cidr, name=None, ip_version=4):
        """
        Creates a new subnet
        """
        net_id = self._find_network_id(network)
        body = {
            "cidr": cidr,
            "ip_version": ip_version,
            "network_id": net_id,
            "name": name,
        }
        return self.network_conn.create_subnet(body={"subnet": body})

    def update_subnet(self, subnet, name=None):
        """
        Updates a subnet
        """
        subnet_id = self._find_subnet_id(subnet)
        return self.network_conn.update_subnet(
            subnet=subnet_id, body={"subnet": {"name": name}}
        )

    def delete_subnet(self, subnet):
        """
        Deletes the specified subnet
        """
        subnet_id = self._find_subnet_id(subnet)
        ret = self.network_conn.delete_subnet(subnet=subnet_id)
        return ret if ret else True

    def list_routers(self):
        """
        Fetches a list of all routers for a tenant
        """
        return self.network_conn.list_routers()

    def show_router(self, router):
        """
        Fetches information of a certain router
        """
        return self._fetch_router(router)

    def create_router(self, name, ext_network=None, admin_state_up=True):
        """
        Creates a new router
        """
        body = {"name": name, "admin_state_up": admin_state_up}
        if ext_network:
            net_id = self._find_network_id(ext_network)
            body["external_gateway_info"] = {"network_id": net_id}
        return self.network_conn.create_router(body={"router": body})

    def update_router(self, router, name=None, admin_state_up=None, **kwargs):
        """
        Updates a router
        """
        router_id = self._find_router_id(router)
        body = {}

        if "ext_network" in kwargs:
            if kwargs.get("ext_network") is None:
                body["external_gateway_info"] = None
            else:
                net_id = self._find_network_id(kwargs.get("ext_network"))
                body["external_gateway_info"] = {"network_id": net_id}
        if name is not None:
            body["name"] = name
        if admin_state_up is not None:
            body["admin_state_up"] = admin_state_up
        return self.network_conn.update_router(router=router_id, body={"router": body})

    def delete_router(self, router):
        """
        Delete the specified router
        """
        router_id = self._find_router_id(router)
        ret = self.network_conn.delete_router(router=router_id)
        return ret if ret else True

    def add_interface_router(self, router, subnet):
        """
        Adds an internal network interface to the specified router
        """
        router_id = self._find_router_id(router)
        subnet_id = self._find_subnet_id(subnet)
        return self.network_conn.add_interface_router(
            router=router_id, body={"subnet_id": subnet_id}
        )

    def remove_interface_router(self, router, subnet):
        """
        Removes an internal network interface from the specified router
        """
        router_id = self._find_router_id(router)
        subnet_id = self._find_subnet_id(subnet)
        return self.network_conn.remove_interface_router(
            router=router_id, body={"subnet_id": subnet_id}
        )

    def add_gateway_router(self, router, network):
        """
        Adds an external network gateway to the specified router
        """
        router_id = self._find_router_id(router)
        net_id = self._find_network_id(network)
        return self.network_conn.add_gateway_router(
            router=router_id, body={"network_id": net_id}
        )

    def remove_gateway_router(self, router):
        """
        Removes an external network gateway from the specified router
        """
        router_id = self._find_router_id(router)
        return self.network_conn.remove_gateway_router(router=router_id)

    def list_floatingips(self):
        """
        Fetch a list of all floatingips for a tenant
        """
        return self.network_conn.list_floatingips()

    def show_floatingip(self, floatingip_id):
        """
        Fetches information of a certain floatingip
        """
        return self.network_conn.show_floatingip(floatingip_id)

    def create_floatingip(self, floating_network, port=None):
        """
        Creates a new floatingip
        """
        net_id = self._find_network_id(floating_network)
        body = {"floating_network_id": net_id}
        if port:
            port_id = self._find_port_id(port)
            body["port_id"] = port_id

        return self.network_conn.create_floatingip(body={"floatingip": body})

    def update_floatingip(self, floatingip_id, port=None):
        """
        Updates a floatingip, disassociates the floating ip if
        port is set to `None`
        """
        if port is None:
            body = {"floatingip": {}}
        else:
            port_id = self._find_port_id(port)
            body = {"floatingip": {"port_id": port_id}}
        return self.network_conn.update_floatingip(floatingip=floatingip_id, body=body)

    def delete_floatingip(self, floatingip_id):
        """
        Deletes the specified floatingip
        """
        ret = self.network_conn.delete_floatingip(floatingip_id)
        return ret if ret else True

    def list_security_groups(self):
        """
        Fetches a list of all security groups for a tenant
        """
        return self.network_conn.list_security_groups()

    def show_security_group(self, sec_grp):
        """
        Fetches information of a certain security group
        """
        return self._fetch_security_group(sec_grp)

    def create_security_group(self, name, desc=None):
        """
        Creates a new security group
        """
        body = {"security_group": {"name": name, "description": desc}}
        return self.network_conn.create_security_group(body=body)

    def update_security_group(self, sec_grp, name=None, desc=None):
        """
        Updates a security group
        """
        sec_grp_id = self._find_security_group_id(sec_grp)
        body = {"security_group": {}}
        if name:
            body["security_group"]["name"] = name
        if desc:
            body["security_group"]["description"] = desc
        return self.network_conn.update_security_group(sec_grp_id, body=body)

    def delete_security_group(self, sec_grp):
        """
        Deletes the specified security group
        """
        sec_grp_id = self._find_security_group_id(sec_grp)
        ret = self.network_conn.delete_security_group(sec_grp_id)
        return ret if ret else True

    def list_security_group_rules(self):
        """
        Fetches a list of all security group rules for a tenant
        """
        return self.network_conn.list_security_group_rules()

    def show_security_group_rule(self, sec_grp_rule_id):
        """
        Fetches information of a certain security group rule
        """
        return self.network_conn.show_security_group_rule(sec_grp_rule_id)[
            "security_group_rule"
        ]

    def create_security_group_rule(
        self,
        sec_grp,
        remote_grp_id=None,
        direction="ingress",
        protocol=None,
        port_range_min=None,
        port_range_max=None,
        ether=None,
    ):
        """
        Creates a new security group rule
        """
        sec_grp_id = self._find_security_group_id(sec_grp)
        body = {
            "security_group_id": sec_grp_id,
            "remote_group_id": remote_grp_id,
            "direction": direction,
            "protocol": protocol,
            "port_range_min": port_range_min,
            "port_range_max": port_range_max,
            "ethertype": ether,
        }
        return self.network_conn.create_security_group_rule(
            body={"security_group_rule": body}
        )

    def delete_security_group_rule(self, sec_grp_rule_id):
        """
        Deletes the specified security group rule
        """
        ret = self.network_conn.delete_security_group_rule(
            security_group_rule=sec_grp_rule_id
        )
        return ret if ret else True

    def list_vpnservices(self, retrieve_all=True, **kwargs):
        """
        Fetches a list of all configured VPN services for a tenant
        """
        return self.network_conn.list_vpnservices(retrieve_all, **kwargs)

    def show_vpnservice(self, vpnservice, **kwargs):
        """
        Fetches information of a specific VPN service
        """
        vpnservice_id = self._find_vpnservice_id(vpnservice)
        return self.network_conn.show_vpnservice(vpnservice_id, **kwargs)

    def create_vpnservice(self, subnet, router, name, admin_state_up=True):
        """
        Creates a new VPN service
        """
        subnet_id = self._find_subnet_id(subnet)
        router_id = self._find_router_id(router)
        body = {
            "subnet_id": subnet_id,
            "router_id": router_id,
            "name": name,
            "admin_state_up": admin_state_up,
        }
        return self.network_conn.create_vpnservice(body={"vpnservice": body})

    def update_vpnservice(self, vpnservice, desc):
        """
        Updates a VPN service
        """
        vpnservice_id = self._find_vpnservice_id(vpnservice)
        body = {"description": desc}
        return self.network_conn.update_vpnservice(
            vpnservice_id, body={"vpnservice": body}
        )

    def delete_vpnservice(self, vpnservice):
        """
        Deletes the specified VPN service
        """
        vpnservice_id = self._find_vpnservice_id(vpnservice)
        ret = self.network_conn.delete_vpnservice(vpnservice_id)
        return ret if ret else True

    def list_ipsec_site_connections(self):
        """
        Fetches all configured IPsec Site Connections for a tenant
        """
        return self.network_conn.list_ipsec_site_connections()

    def show_ipsec_site_connection(self, ipsec_site_connection):
        """
        Fetches information of a specific IPsecSiteConnection
        """
        return self._fetch_ipsec_site_connection(ipsec_site_connection)

    def create_ipsec_site_connection(
        self,
        name,
        ipsecpolicy,
        ikepolicy,
        vpnservice,
        peer_cidrs,
        peer_address,
        peer_id,
        psk,
        admin_state_up=True,
        **kwargs
    ):
        """
        Creates a new IPsecSiteConnection
        """
        ipsecpolicy_id = self._find_ipsecpolicy_id(ipsecpolicy)
        ikepolicy_id = self._find_ikepolicy_id(ikepolicy)
        vpnservice_id = self._find_vpnservice_id(vpnservice)
        body = {
            "psk": psk,
            "ipsecpolicy_id": ipsecpolicy_id,
            "admin_state_up": admin_state_up,
            "peer_cidrs": [peer_cidrs],
            "ikepolicy_id": ikepolicy_id,
            "vpnservice_id": vpnservice_id,
            "peer_address": peer_address,
            "peer_id": peer_id,
            "name": name,
        }
        if "initiator" in kwargs:
            body["initiator"] = kwargs["initiator"]
        if "mtu" in kwargs:
            body["mtu"] = kwargs["mtu"]
        if "dpd_action" in kwargs:
            body["dpd"] = {"action": kwargs["dpd_action"]}
        if "dpd_interval" in kwargs:
            if "dpd" not in body:
                body["dpd"] = {}
            body["dpd"]["interval"] = kwargs["dpd_interval"]
        if "dpd_timeout" in kwargs:
            if "dpd" not in body:
                body["dpd"] = {}
            body["dpd"]["timeout"] = kwargs["dpd_timeout"]
        return self.network_conn.create_ipsec_site_connection(
            body={"ipsec_site_connection": body}
        )

    def delete_ipsec_site_connection(self, ipsec_site_connection):
        """
        Deletes the specified IPsecSiteConnection
        """
        ipsec_site_connection_id = self._find_ipsec_site_connection_id(
            ipsec_site_connection
        )
        ret = self.network_conn.delete_ipsec_site_connection(ipsec_site_connection_id)
        return ret if ret else True

    def list_ikepolicies(self):
        """
        Fetches a list of all configured IKEPolicies for a tenant
        """
        return self.network_conn.list_ikepolicies()

    def show_ikepolicy(self, ikepolicy):
        """
        Fetches information of a specific IKEPolicy
        """
        return self._fetch_ikepolicy(ikepolicy)

    def create_ikepolicy(self, name, **kwargs):
        """
        Creates a new IKEPolicy
        """
        body = {"name": name}
        if "phase1_negotiation_mode" in kwargs:
            body["phase1_negotiation_mode"] = kwargs["phase1_negotiation_mode"]
        if "auth_algorithm" in kwargs:
            body["auth_algorithm"] = kwargs["auth_algorithm"]
        if "encryption_algorithm" in kwargs:
            body["encryption_algorithm"] = kwargs["encryption_algorithm"]
        if "pfs" in kwargs:
            body["pfs"] = kwargs["pfs"]
        if "ike_version" in kwargs:
            body["ike_version"] = kwargs["ike_version"]
        if "units" in kwargs:
            body["lifetime"] = {"units": kwargs["units"]}
        if "value" in kwargs:
            if "lifetime" not in body:
                body["lifetime"] = {}
            body["lifetime"]["value"] = kwargs["value"]
        return self.network_conn.create_ikepolicy(body={"ikepolicy": body})

    def delete_ikepolicy(self, ikepolicy):
        """
        Deletes the specified IKEPolicy
        """
        ikepolicy_id = self._find_ikepolicy_id(ikepolicy)
        ret = self.network_conn.delete_ikepolicy(ikepolicy_id)
        return ret if ret else True

    def list_ipsecpolicies(self):
        """
        Fetches a list of all configured IPsecPolicies for a tenant
        """
        return self.network_conn.list_ipsecpolicies()

    def show_ipsecpolicy(self, ipsecpolicy):
        """
        Fetches information of a specific IPsecPolicy
        """
        return self._fetch_ipsecpolicy(ipsecpolicy)

    def create_ipsecpolicy(self, name, **kwargs):
        """
        Creates a new IPsecPolicy
        """
        body = {"name": name}
        if "transform_protocol" in kwargs:
            body["transform_protocol"] = kwargs["transform_protocol"]
        if "auth_algorithm" in kwargs:
            body["auth_algorithm"] = kwargs["auth_algorithm"]
        if "encapsulation_mode" in kwargs:
            body["encapsulation_mode"] = kwargs["encapsulation_mode"]
        if "encryption_algorithm" in kwargs:
            body["encryption_algorithm"] = kwargs["encryption_algorithm"]
        if "pfs" in kwargs:
            body["pfs"] = kwargs["pfs"]
        if "units" in kwargs:
            body["lifetime"] = {"units": kwargs["units"]}
        if "value" in kwargs:
            if "lifetime" not in body:
                body["lifetime"] = {}
            body["lifetime"]["value"] = kwargs["value"]
        return self.network_conn.create_ipsecpolicy(body={"ipsecpolicy": body})

    def delete_ipsecpolicy(self, ipseecpolicy):
        """
        Deletes the specified IPsecPolicy
        """
        ipseecpolicy_id = self._find_ipsecpolicy_id(ipseecpolicy)
        ret = self.network_conn.delete_ipsecpolicy(ipseecpolicy_id)
        return ret if ret else True

    def list_firewall_rules(self):
        """
        Fetches a list of all configured firewall rules for a tenant
        """
        return self.network_conn.list_firewall_rules()

    def show_firewall_rule(self, firewall_rule):
        """
        Fetches information of a specific firewall rule
        """
        return self._fetch_firewall_rule(firewall_rule)

    def create_firewall_rule(self, protocol, action, **kwargs):
        """
        Create a new firlwall rule
        """
        body = {"protocol": protocol, "action": action}
        if "tenant_id" in kwargs:
            body["tenant_id"] = kwargs["tenant_id"]
        if "name" in kwargs:
            body["name"] = kwargs["name"]
        if "description" in kwargs:
            body["description"] = kwargs["description"]
        if "ip_version" in kwargs:
            body["ip_version"] = kwargs["ip_version"]
        if "source_ip_address" in kwargs:
            body["source_ip_address"] = kwargs["source_ip_address"]
        if "destination_port" in kwargs:
            body["destination_port"] = kwargs["destination_port"]
        if "shared" in kwargs:
            body["shared"] = kwargs["shared"]
        if "enabled" in kwargs:
            body["enabled"] = kwargs["enabled"]
        return self.network_conn.create_firewall_rule(body={"firewall_rule": body})

    def delete_firewall_rule(self, firewall_rule):
        """
        Deletes the specified firewall rule
        """
        firewall_rule_id = self._find_firewall_rule_id(firewall_rule)
        ret = self.network_conn.delete_firewall_rule(firewall_rule_id)
        return ret if ret else True

    def update_firewall_rule(
        self,
        firewall_rule,
        protocol=None,
        action=None,
        name=None,
        description=None,
        ip_version=None,
        source_ip_address=None,
        destination_ip_address=None,
        source_port=None,
        destination_port=None,
        shared=None,
        enabled=None,
    ):
        """
        Update a firewall rule
        """
        body = {}
        if protocol:
            body["protocol"] = protocol
        if action:
            body["action"] = action
        if name:
            body["name"] = name
        if description:
            body["description"] = description
        if ip_version:
            body["ip_version"] = ip_version
        if source_ip_address:
            body["source_ip_address"] = source_ip_address
        if destination_ip_address:
            body["destination_ip_address"] = destination_ip_address
        if source_port:
            body["source_port"] = source_port
        if destination_port:
            body["destination_port"] = destination_port
        if shared:
            body["shared"] = shared
        if enabled:
            body["enabled"] = enabled
        return self.network_conn.update_firewall_rule(
            firewall_rule, body={"firewall_rule": body}
        )

    def list_firewalls(self):
        """
        Fetches a list of all firewalls for a tenant
        """
        return self.network_conn.list_firewalls()

    def show_firewall(self, firewall):
        """
        Fetches information of a specific firewall
        """
        return self._fetch_firewall(firewall)

    def list_l3_agent_hosting_routers(self, router):
        """
        List L3 agents.
        """
        return self.network_conn.list_l3_agent_hosting_routers(router)

    def list_agents(self):
        """
        List agents.
        """
        return self.network_conn.list_agents()


# The following is a list of functions that need to be incorporated in the
# neutron module. This list should be updated as functions are added.
#
# update_ipsec_site_connection
#                       Updates an IPsecSiteConnection.
# update_ikepolicy      Updates an IKEPolicy
# update_ipsecpolicy    Updates an IPsecPolicy
# list_vips             Fetches a list of all load balancer vips for a tenant.
# show_vip              Fetches information of a certain load balancer vip.
# create_vip            Creates a new load balancer vip.
# update_vip            Updates a load balancer vip.
# delete_vip            Deletes the specified load balancer vip.
# list_pools            Fetches a list of all load balancer pools for a tenant.
# show_pool             Fetches information of a certain load balancer pool.
# create_pool           Creates a new load balancer pool.
# update_pool           Updates a load balancer pool.
# delete_pool           Deletes the specified load balancer pool.
# retrieve_pool_stats   Retrieves stats for a certain load balancer pool.
# list_members          Fetches a list of all load balancer members for
#                       a tenant.
# show_member           Fetches information of a certain load balancer member.
# create_member         Creates a new load balancer member.
# update_member         Updates a load balancer member.
# delete_member         Deletes the specified load balancer member.
# list_health_monitors  Fetches a list of all load balancer health monitors for
#                       a tenant.
# show_health_monitor   Fetches information of a certain load balancer
#                       health monitor.
# create_health_monitor
#                       Creates a new load balancer health monitor.
# update_health_monitor
#                       Updates a load balancer health monitor.
# delete_health_monitor
#                       Deletes the specified load balancer health monitor.
# associate_health_monitor
#                       Associate  specified load balancer health monitor
#                       and pool.
# disassociate_health_monitor
#                       Disassociate specified load balancer health monitor
#                       and pool.
# create_qos_queue      Creates a new queue.
# list_qos_queues       Fetches a list of all queues for a tenant.
# show_qos_queue        Fetches information of a certain queue.
# delete_qos_queue      Deletes the specified queue.
# list_agents           Fetches agents.
# show_agent            Fetches information of a certain agent.
# update_agent          Updates an agent.
# delete_agent          Deletes the specified agent.
# list_network_gateways
#                       Retrieve network gateways.
# show_network_gateway  Fetch a network gateway.
# create_network_gateway
#                       Create a new network gateway.
# update_network_gateway
#                       Update a network gateway.
# delete_network_gateway
#                       Delete the specified network gateway.
# connect_network_gateway
#                       Connect a network gateway to the specified network.
# disconnect_network_gateway
#                       Disconnect a network from the specified gateway.
# list_gateway_devices  Retrieve gateway devices.
# show_gateway_device   Fetch a gateway device.
# create_gateway_device
#                       Create a new gateway device.
# update_gateway_device
#                       Updates a new gateway device.
# delete_gateway_device
#                       Delete the specified gateway device.
# list_dhcp_agent_hosting_networks
#                       Fetches a list of dhcp agents hosting a network.
# list_networks_on_dhcp_agent
#                       Fetches a list of dhcp agents hosting a network.
# add_network_to_dhcp_agent
#                       Adds a network to dhcp agent.
# remove_network_from_dhcp_agent
#                       Remove a network from dhcp agent.
# list_l3_agent_hosting_routers
#                       Fetches a list of L3 agents hosting a router.
# list_routers_on_l3_agent
#                       Fetches a list of L3 agents hosting a router.
# add_router_to_l3_agent
#                       Adds a router to L3 agent.
# list_firewall_rules   Fetches a list of all firewall rules for a tenant.
# show_firewall_rule    Fetches information of a certain firewall rule.
# create_firewall_rule  Creates a new firewall rule.
# update_firewall_rule  Updates a firewall rule.
# delete_firewall_rule  Deletes the specified firewall rule.
# list_firewall_policies
#                       Fetches a list of all firewall policies for a tenant.
# show_firewall_policy  Fetches information of a certain firewall policy.
# create_firewall_policy
#                       Creates a new firewall policy.
# update_firewall_policy
#                       Updates a firewall policy.
# delete_firewall_policy
#                       Deletes the specified firewall policy.
# firewall_policy_insert_rule
#                       Inserts specified rule into firewall policy.
# firewall_policy_remove_rule
#                       Removes specified rule from firewall policy.
# list_firewalls        Fetches a list of all firewals for a tenant.
# show_firewall         Fetches information of a certain firewall.
# create_firewall       Creates a new firewall.
# update_firewall       Updates a firewall.
# delete_firewall       Deletes the specified firewall.
# remove_router_from_l3_agent
#                       Remove a router from l3 agent.
# get_lbaas_agent_hosting_pool
#                       Fetches a loadbalancer agent hosting a pool.
# list_pools_on_lbaas_agent
#                       Fetches a list of pools hosted by
#                       the loadbalancer agent.
# list_service_providers
#                       Fetches service providers.
# list_credentials      Fetch a list of all credentials for a tenant.
# show_credential       Fetch a credential.
# create_credential     Create a new credential.
# update_credential     Update a credential.
# delete_credential     Delete the specified credential.
# list_network_profile_bindings
#                       Fetch a list of all tenants associated for
#                       a network profile.
# list_network_profiles
#                       Fetch a list of all network profiles for a tenant.
# show_network_profile  Fetch a network profile.
# create_network_profile
#                       Create a network profile.
# update_network_profile
#                       Update a network profile.
# delete_network_profile
#                       Delete the network profile.
# list_policy_profile_bindings
#                       Fetch a list of all tenants associated for
#                       a policy profile.
# list_policy_profiles  Fetch a list of all network profiles for a tenant.
# show_policy_profile   Fetch a network profile.
# update_policy_profile
#                       Update a policy profile.
# create_metering_label
#                       Creates a metering label.
# delete_metering_label
#                       Deletes the specified metering label.
# list_metering_labels  Fetches a list of all metering labels for a tenant.
# show_metering_label   Fetches information of a certain metering label.
# create_metering_label_rule
#                       Creates a metering label rule.
# delete_metering_label_rule
#                       Deletes the specified metering label rule.
# list_metering_label_rules
#                       Fetches a list of all metering label rules for a label.
# show_metering_label_rule
#                       Fetches information of a certain metering label rule.
# list_net_partitions   Fetch a list of all network partitions for a tenant.
# show_net_partition    etch a network partition.
# create_net_partition  Create a network partition.
# delete_net_partition  Delete the network partition.
# create_packet_filter  Create a new packet filter.
# update_packet_filter  Update a packet filter.
# list_packet_filters   Fetch a list of all packet filters for a tenant.
# show_packet_filter    Fetch information of a certain packet filter.
# delete_packet_filter  Delete the specified packet filter.
