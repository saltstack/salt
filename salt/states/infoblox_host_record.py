"""
Infoblox host record management.

functions accept api_opts:

    api_verifyssl: verify SSL [default to True or pillar value]
    api_url: server to connect to [default to pillar value]
    api_username:  [default to pillar value]
    api_password:  [default to pillar value]
"""


def present(name=None, data=None, ensure_data=True, **api_opts):
    """
    This will ensure that a host with the provided name exists.
    This will try to ensure that the state of the host matches the given data
    If the host is not found then one will be created.

    When trying to update a hostname ensure `name` is set to the hostname
    of the current record. You can give a new name in the `data.name`.

    Avoid race conditions, use func:nextavailableip:
        - func:nextavailableip:network/ZG54dfgsrDFEFfsfsLzA:10.0.0.0/8/default
        - func:nextavailableip:10.0.0.0/8
        - func:nextavailableip:10.0.0.0/8,externalconfigure_for_dns
        - func:nextavailableip:10.0.0.3-10.0.0.10

    State Example:

    .. code-block:: yaml

        # this would update `original_hostname.example.ca` to changed `data`.
        infoblox_host_record.present:
            - name: original_hostname.example.ca
            - data: {'namhostname.example.cae': 'hostname.example.ca',
                'aliases': ['hostname.math.example.ca'],
                'extattrs': [{'Business Contact': {'value': 'EXAMPLE@example.ca'}}],
                'ipv4addrs': [{'configure_for_dhcp': True,
                    'ipv4addr': 'func:nextavailableip:129.97.139.0/24',
                    'mac': '00:50:56:84:6e:ae'}],
                'ipv6addrs': [], }
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}
    if data is None:
        data = {}
    if "name" not in data:
        data.update({"name": name})

    obj = __salt__["infoblox.get_host"](name=name, **api_opts)
    if obj is None:
        # perhaps the user updated the name
        obj = __salt__["infoblox.get_host"](name=data["name"], **api_opts)
        if obj:
            # warn user that the host name was updated and does not match
            ret["result"] = False
            ret[
                "comment"
            ] = "please update the name: {} to equal the updated data name {}".format(
                name, data["name"]
            )
            return ret

    if obj:
        if not ensure_data:
            ret["result"] = True
            ret[
                "comment"
            ] = "infoblox record already created (supplied fields not ensured to match)"
            return ret

        obj = __salt__["infoblox.get_host_advanced"](name=name, **api_opts)
        diff = __salt__["infoblox.diff_objects"](data, obj)
        if not diff:
            ret["result"] = True
            ret["comment"] = (
                "supplied fields already updated (note: removing fields might not"
                " update)"
            )
            return ret

        if diff:
            ret["changes"] = {"diff": diff}
            if __opts__["test"]:
                ret["result"] = None
                ret["comment"] = "would attempt to update infoblox record"
                return ret

            # replace func:nextavailableip with current ip address if in range
            # get list of ipaddresses that are defined.
            obj_addrs = []
            if "ipv4addrs" in obj:
                for addr in obj["ipv4addrs"]:
                    if "ipv4addr" in addr:
                        obj_addrs.append(addr["ipv4addr"])
            if "ipv6addrs" in obj:
                for addr in obj["ipv6addrs"]:
                    if "ipv6addr" in addr:
                        obj_addrs.append(addr["ipv6addr"])

            # replace func:nextavailableip: if an ip address is already found in that range.
            if "ipv4addrs" in data:
                for addr in data["ipv4addrs"]:
                    if "ipv4addr" in addr:
                        addrobj = addr["ipv4addr"]
                        if addrobj.startswith("func:nextavailableip:"):
                            found_matches = 0
                            for ip in obj_addrs:
                                if __salt__["infoblox.is_ipaddr_in_ipfunc_range"](
                                    ip, addrobj
                                ):
                                    addr["ipv4addr"] = ip
                                    found_matches += 1
                            if found_matches > 1:
                                ret["comment"] = (
                                    "infoblox record cant updated because ipaddress {}"
                                    " matches multiple func:nextavailableip".format(ip)
                                )
                                ret["result"] = False
                                return ret

            new_obj = __salt__["infoblox.update_object"](
                obj["_ref"], data=data, **api_opts
            )
            ret["result"] = True
            ret["comment"] = (
                "infoblox record fields updated (note: removing fields might not"
                " update)"
            )
            # ret['changes'] = {'diff': diff }
            return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "would attempt to create infoblox record {}".format(name)
        return ret

    new_obj_ref = __salt__["infoblox.create_host"](data=data, **api_opts)
    new_obj = __salt__["infoblox.get_host"](name=name, **api_opts)

    ret["result"] = True
    ret["comment"] = "infoblox record created"
    ret["changes"] = {"old": "None", "new": {"_ref": new_obj_ref, "data": new_obj}}
    return ret


def absent(name=None, ipv4addr=None, mac=None, **api_opts):
    """
    Ensure the host with the given Name ipv4addr or mac is removed.

    State example:

    .. code-block:: yaml

        infoblox_host_record.absent:
            - name: hostname.of.record.to.remove

        infoblox_host_record.absent:
            - name:
            - ipv4addr: 192.168.0.1

        infoblox_host_record.absent:
            - name:
            - mac: 12:02:12:31:23:43
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}
    obj = __salt__["infoblox.get_host"](
        name=name, ipv4addr=ipv4addr, mac=mac, **api_opts
    )

    if not obj:
        ret["result"] = True
        ret["comment"] = "infoblox already removed"
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["changes"] = {"old": obj, "new": "absent"}
        return ret

    if __salt__["infoblox.delete_host"](name=name, mac=mac, **api_opts):
        ret["result"] = True
        ret["changes"] = {"old": obj, "new": "absent"}
    return ret
