"""
Management of OpenStack Neutron Subnets
=========================================

.. versionadded:: 2018.3.0

:depends: shade
:configuration: see :py:mod:`salt.modules.neutronng` for setup instructions

Example States

.. code-block:: yaml

    create subnet:
      neutron_subnet.present:
        - name: subnet1
        - network_name_or_id: network1
        - cidr: 192.168.199.0/24


    delete subnet:
      neutron_subnet.absent:
        - name: subnet2

    create subnet with optional params:
      neutron_subnet.present:
        - name: subnet1
        - network_name_or_id: network1
        - enable_dhcp: True
        - cidr: 192.168.199.0/24
        - allocation_pools:
          - start: 192.168.199.5
            end: 192.168.199.250
        - host_routes:
          - destination: 192.168..0.0/24
            nexthop: 192.168.0.1
        - gateway_ip: 192.168.199.1
        - dns_nameservers:
          - 8.8.8.8
          - 8.8.8.7

    create ipv6 subnet:
      neutron_subnet.present:
        - name: v6subnet1
        - network_name_or_id: network1
        - ip_version: 6
"""


__virtualname__ = "neutron_subnet"


def __virtual__():
    if "neutronng.list_subnets" in __salt__:
        return __virtualname__
    return (
        False,
        "The neutronng execution module failed to load: shade python module is not available",
    )


def present(name, auth=None, **kwargs):
    """
    Ensure a subnet exists and is up-to-date

    name
        Name of the subnet

    network_name_or_id
        The unique name or ID of the attached network.
        If a non-unique name is supplied, an exception is raised.

    allocation_pools
        A list of dictionaries of the start and end addresses
        for the allocation pools

    gateway_ip
        The gateway IP address.

    dns_nameservers
        A list of DNS name servers for the subnet.

    host_routes
        A list of host route dictionaries for the subnet.

    ipv6_ra_mode
        IPv6 Router Advertisement mode.
        Valid values are: ‘dhcpv6-stateful’, ‘dhcpv6-stateless’, or ‘slaac’.

    ipv6_address_mode
        IPv6 address mode.
        Valid values are: ‘dhcpv6-stateful’, ‘dhcpv6-stateless’, or ‘slaac’.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    kwargs = __utils__["args.clean_kwargs"](**kwargs)

    __salt__["neutronng.setup_clouds"](auth)

    kwargs["subnet_name"] = name
    subnet = __salt__["neutronng.subnet_get"](name=name)

    if subnet is None:
        if __opts__["test"]:
            ret["result"] = None
            ret["changes"] = kwargs
            ret["comment"] = "Subnet will be created."
            return ret

        new_subnet = __salt__["neutronng.subnet_create"](**kwargs)
        ret["changes"] = new_subnet
        ret["comment"] = "Created subnet"
        return ret

    changes = __salt__["neutronng.compare_changes"](subnet, **kwargs)
    if changes:
        if __opts__["test"] is True:
            ret["result"] = None
            ret["changes"] = changes
            ret["comment"] = "Project will be updated."
            return ret

        # update_subnet does not support changing cidr,
        # so we have to delete and recreate the subnet in this case.
        if "cidr" in changes or "tenant_id" in changes:
            __salt__["neutronng.subnet_delete"](name=name)
            new_subnet = __salt__["neutronng.subnet_create"](**kwargs)
            ret["changes"] = new_subnet
            ret["comment"] = "Deleted and recreated subnet"
            return ret

        __salt__["neutronng.subnet_update"](**kwargs)
        ret["changes"].update(changes)
        ret["comment"] = "Updated subnet"

    return ret


def absent(name, auth=None):
    """
    Ensure a subnet does not exists

    name
        Name of the subnet

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    __salt__["neutronng.setup_clouds"](auth)

    subnet = __salt__["neutronng.subnet_get"](name=name)

    if subnet:
        if __opts__["test"] is True:
            ret["result"] = None
            ret["changes"] = {"id": subnet.id}
            ret["comment"] = "Project will be deleted."
            return ret

        __salt__["neutronng.subnet_delete"](name=subnet)
        ret["changes"]["id"] = name
        ret["comment"] = "Deleted subnet"

    return ret
