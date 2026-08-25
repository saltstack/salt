"""
Infoblox CNAME management.

functions accept api_opts:

    api_verifyssl: verify SSL [default to True or pillar value]
    api_url: server to connect to [default to pillar value]
    api_username:  [default to pillar value]
    api_password:  [default to pillar value]
"""


def present(name=None, data=None, ensure_data=True, **api_opts):
    """
    Ensure the CNAME with the given data is present.

    name
        CNAME of record
    data
        raw CNAME api data see: https://INFOBLOX/wapidoc

    State example:

    .. code-block:: yaml

        infoblox_cname.present:
            - name: example-ha-0.domain.com
            - data:
                name: example-ha-0.domain.com
                canonical: example.domain.com
                zone: example.com
                view: Internal
                comment: Example comment

        infoblox_cname.present:
            - name: example-ha-0.domain.com
            - data:
                name: example-ha-0.domain.com
                canonical: example.domain.com
                zone: example.com
                view: Internal
                comment: Example comment
            - api_url: https://INFOBLOX/wapi/v1.2.1
            - api_username: username
            - api_password: passwd
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}
    if not data:
        data = {}
    if "name" not in data:
        data.update({"name": name})

    obj = __salt__["infoblox.get_cname"](name=name, **api_opts)
    if obj is None:
        # perhaps the user updated the name
        obj = __salt__["infoblox.get_cname"](name=data["name"], **api_opts)
        if obj:
            # warn user that the data was updated and does not match
            ret["result"] = False
            ret["comment"] = (
                "** please update the name: {} to equal the updated data name {}".format(
                    name, data["name"]
                )
            )
            return ret

    if obj:
        if not ensure_data:
            ret["result"] = True
            ret["comment"] = (
                "infoblox record already created (supplied fields not ensured to match)"
            )
            return ret

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
            new_obj = __salt__["infoblox.update_object"](
                obj["_ref"], data=data, **api_opts
            )
            ret["result"] = True
            ret["comment"] = (
                "infoblox record fields updated (note: removing fields might not"
                " update)"
            )
            return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "would attempt to create infoblox record {}".format(
            data["name"]
        )
        return ret

    new_obj_ref = __salt__["infoblox.create_cname"](data=data, **api_opts)
    new_obj = __salt__["infoblox.get_cname"](name=name, **api_opts)

    ret["result"] = True
    ret["comment"] = "infoblox record created"
    ret["changes"] = {"old": "None", "new": {"_ref": new_obj_ref, "data": new_obj}}
    return ret


def absent(name=None, canonical=None, **api_opts):
    """
    Ensure the CNAME with the given name or canonical name is removed
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}
    obj = __salt__["infoblox.get_cname"](name=name, canonical=canonical, **api_opts)

    if not obj:
        ret["result"] = True
        ret["comment"] = "infoblox already removed"
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["changes"] = {"old": obj, "new": "absent"}
        return ret

    if __salt__["infoblox.delete_cname"](name=name, canonical=canonical, **api_opts):
        ret["result"] = True
        ret["changes"] = {"old": obj, "new": "absent"}
    return ret
