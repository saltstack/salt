"""
Consul Management
=================

.. versionadded:: 3005

The consul module is used to create and manage Consul ACLs

.. code-block:: yaml

    acl_present:
      consul.acl_present:
        - id: 38AC8470-4A83-4140-8DFD-F924CD32917F
        - name: acl_name
        - rules: node "" {policy = "write"} service "" {policy = "read"} key "_rexec" {policy = "write"}
        - type: client
        - consul_url: http://localhost:8500

    acl_delete:
       consul.acl_absent:
         - id: 38AC8470-4A83-4140-8DFD-F924CD32917F
"""

import logging

log = logging.getLogger(__name__)


def _acl_changes(name, id=None, type=None, rules=None, consul_url=None, token=None):
    """
    return True if the acl need to be update, False if it doesn't need to be update
    """
    info = __salt__["consul.acl_info"](id=id, token=token, consul_url=consul_url)

    if info["res"] and info["data"][0]["Name"] != name:
        return True
    elif info["res"] and info["data"][0]["Rules"] != rules:
        return True
    elif info["res"] and info["data"][0]["Type"] != type:
        return True
    else:
        return False


def _acl_exists(name=None, id=None, token=None, consul_url=None):
    """
    Check the acl exists by using the name or the ID,
    name is ignored if ID is specified,
    if only Name is used the ID associated with it is returned
    """

    ret = {"result": False, "id": None}

    if id:
        info = __salt__["consul.acl_info"](id=id, token=token, consul_url=consul_url)
    elif name:
        info = __salt__["consul.acl_list"](token=token, consul_url=consul_url)
    else:
        return ret

    if info.get("data"):
        for acl in info["data"]:
            if id and acl["ID"] == id:
                ret["result"] = True
                ret["id"] = id
            elif name and acl["Name"] == name:
                ret["result"] = True
                ret["id"] = acl["ID"]

    return ret


def acl_present(
    name,
    id=None,
    token=None,
    type="client",
    rules="",
    consul_url="http://localhost:8500",
):
    """
    Ensure the ACL is present

    name
        Specifies a human-friendly name for the ACL token.

    id
        Specifies the ID of the ACL.

    type: client
        Specifies the type of ACL token. Valid values are: client and management.

    rules
        Specifies rules for this ACL token.

    consul_url : http://locahost:8500
        consul URL to query

    .. note::
        For more information https://www.consul.io/api/acl.html#create-acl-token, https://www.consul.io/api/acl.html#update-acl-token
    """

    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": f'ACL "{name}" exists and is up to date',
    }

    exists = _acl_exists(name, id, token, consul_url)

    if not exists["result"]:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "The acl doesn't exist, it will be created"
            return ret

        create = __salt__["consul.acl_create"](
            name=name, id=id, token=token, type=type, rules=rules, consul_url=consul_url
        )
        if create["res"]:
            ret["result"] = True
            ret["comment"] = "The acl has been created"
        elif not create["res"]:
            ret["result"] = False
            ret["comment"] = "Failed to create the acl"
    elif exists["result"]:
        changes = _acl_changes(
            name=name,
            id=exists["id"],
            token=token,
            type=type,
            rules=rules,
            consul_url=consul_url,
        )
        if changes:
            if __opts__["test"]:
                ret["result"] = None
                ret["comment"] = "The acl exists and will be updated"
                return ret

            update = __salt__["consul.acl_update"](
                name=name,
                id=exists["id"],
                token=token,
                type=type,
                rules=rules,
                consul_url=consul_url,
            )
            if update["res"]:
                ret["result"] = True
                ret["comment"] = "The acl has been updated"
            elif not update["res"]:
                ret["result"] = False
                ret["comment"] = "Failed to update the acl"

    return ret


def acl_absent(name, id=None, token=None, consul_url="http://localhost:8500"):
    """
    Ensure the ACL is absent

    name
        Specifies a human-friendly name for the ACL token.

    id
        Specifies the ID of the ACL.

    token
        token to authenticate you Consul query

    consul_url : http://locahost:8500
        consul URL to query

    .. note::
        For more information https://www.consul.io/api/acl.html#delete-acl-token

    """
    ret = {
        "name": id,
        "changes": {},
        "result": True,
        "comment": f'ACL "{id}" does not exist',
    }

    exists = _acl_exists(name, id, token, consul_url)
    if exists["result"]:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "The acl exists, it will be deleted"
            return ret

        delete = __salt__["consul.acl_delete"](
            id=exists["id"], token=token, consul_url=consul_url
        )
        if delete["res"]:
            ret["result"] = True
            ret["comment"] = "The acl has been deleted"
        elif not delete["res"]:
            ret["result"] = False
            ret["comment"] = "Failed to delete the acl"

    return ret
