"""
Infoblox host record management.

functions accept api_opts:

    api_verifyssl: verify SSL [default to True or pillar value]
    api_url: server to connect to [default to pillar value]
    api_username:  [default to pillar value]
    api_password:  [default to pillar value]
"""


def present(name=None, start_addr=None, end_addr=None, data=None, **api_opts):
    """
    Ensure range record is present.

    infoblox_range.present:
        start_addr: '129.97.150.160',
        end_addr: '129.97.150.170',

    Verbose state example:

    .. code-block:: yaml

        infoblox_range.present:
            data: {
                'always_update_dns': False,
                'authority': False,
                'comment': 'range of IP addresses used for salt.. was used for ghost images deployment',
                'ddns_generate_hostname': True,
                'deny_all_clients': False,
                'deny_bootp': False,
                'disable': False,
                'email_list': [],
                'enable_ddns': False,
                'enable_dhcp_thresholds': False,
                'enable_email_warnings': False,
                'enable_ifmap_publishing': False,
                'enable_snmp_warnings': False,
                'end_addr': '129.97.150.169',
                'exclude': [],
                'extattrs': {},
                'fingerprint_filter_rules': [],
                'high_water_mark': 95,
                'high_water_mark_reset': 85,
                'ignore_dhcp_option_list_request': False,
                'lease_scavenge_time': -1,
                'logic_filter_rules': [],
                'low_water_mark': 0,
                'low_water_mark_reset': 10,
                'mac_filter_rules': [],
                'member': {'_struct': 'dhcpmember',
                        'ipv4addr': '129.97.128.9',
                        'name': 'cn-dhcp-mc.example.ca'},
                'ms_options': [],
                'nac_filter_rules': [],
                'name': 'ghost-range',
                'network': '129.97.150.0/24',
                'network_view': 'default',
                'option_filter_rules': [],
                'options': [{'name': 'dhcp-lease-time',
                            'num': 51,
                            'use_option': False,
                            'value': '43200',
                            'vendor_class': 'DHCP'}],
                'recycle_leases': True,
                'relay_agent_filter_rules': [],
                'server_association_type': 'MEMBER',
                'start_addr': '129.97.150.160',
                'update_dns_on_lease_renewal': False,
                'use_authority': False,
                'use_bootfile': False,
                'use_bootserver': False,
                'use_ddns_domainname': False,
                'use_ddns_generate_hostname': True,
                'use_deny_bootp': False,
                'use_email_list': False,
                'use_enable_ddns': False,
                'use_enable_dhcp_thresholds': False,
                'use_enable_ifmap_publishing': False,
                'use_ignore_dhcp_option_list_request': False,
                'use_known_clients': False,
                'use_lease_scavenge_time': False,
                'use_nextserver': False,
                'use_options': False,
                'use_recycle_leases': False,
                'use_unknown_clients': False,
                'use_update_dns_on_lease_renewal': False
            }
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    if not data:
        data = {}
    if "name" not in data:
        data.update({"name": name})
    if "start_addr" not in data:
        data.update({"start_addr": start_addr})
    if "end_addr" not in data:
        data.update({"end_addr": end_addr})

    obj = __salt__["infoblox.get_ipv4_range"](
        data["start_addr"], data["end_addr"], **api_opts
    )
    if obj is None:
        obj = __salt__["infoblox.get_ipv4_range"](
            start_addr=data["start_addr"], end_addr=None, **api_opts
        )
        if obj is None:
            obj = __salt__["infoblox.get_ipv4_range"](
                start_addr=None, end_addr=data["end_addr"], **api_opts
            )

    if obj:
        diff = __salt__["infoblox.diff_objects"](data, obj)
        if not diff:
            ret["result"] = True
            ret["comment"] = "supplied fields in correct state"
            return ret
        if diff:
            if __opts__["test"]:
                ret["result"] = None
                ret["comment"] = "would attempt to update record"
                return ret
            new_obj = __salt__["infoblox.update_object"](
                obj["_ref"], data=data, **api_opts
            )
            ret["result"] = True
            ret["comment"] = "record fields updated"
            ret["changes"] = {"diff": diff}
            return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"would attempt to create record {name}"
        return ret

    new_obj_ref = __salt__["infoblox.create_ipv4_range"](data, **api_opts)
    new_obj = __salt__["infoblox.get_ipv4_range"](
        data["start_addr"], data["end_addr"], **api_opts
    )

    ret["result"] = True
    ret["comment"] = "record created"
    ret["changes"] = {"old": "None", "new": {"_ref": new_obj_ref, "data": new_obj}}
    return ret


def absent(name=None, start_addr=None, end_addr=None, data=None, **api_opts):
    """
    Ensure the range is removed

    Supplying the end of the range is optional.

    State example:

    .. code-block:: yaml

        infoblox_range.absent:
            - name: 'vlan10'

        infoblox_range.absent:
            - name:
            - start_addr: 127.0.1.20
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    if not data:
        data = {}
    if "name" not in data:
        data.update({"name": name})
    if "start_addr" not in data:
        data.update({"start_addr": start_addr})
    if "end_addr" not in data:
        data.update({"end_addr": end_addr})

    obj = __salt__["infoblox.get_ipv4_range"](
        data["start_addr"], data["end_addr"], **api_opts
    )
    if obj is None:
        obj = __salt__["infoblox.get_ipv4_range"](
            start_addr=data["start_addr"], end_addr=None, **api_opts
        )
        if obj is None:
            obj = __salt__["infoblox.get_ipv4_range"](
                start_addr=None, end_addr=data["end_addr"], **api_opts
            )

    if not obj:
        ret["result"] = True
        ret["comment"] = "already deleted"
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "would attempt to delete range"
        return ret

    if __salt__["infoblox.delete_object"](objref=obj["_ref"]):
        ret["result"] = True
        ret["changes"] = {
            "old": f"Found {start_addr} - {end_addr}",
            "new": "Removed",
        }
    return ret
