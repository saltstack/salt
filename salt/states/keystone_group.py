"""
Management of OpenStack Keystone Groups
=======================================

.. versionadded:: 2018.3.0

:depends: shade
:configuration: see :py:mod:`salt.modules.keystoneng` for setup instructions

Example States

.. code-block:: yaml

    create group:
      keystone_group.present:
        - name: group1

    delete group:
      keystone_group.absent:
        - name: group1

    create group with optional params:
      keystone_group.present:
        - name: group1
        - domain: domain1
        - description: 'my group'
"""


__virtualname__ = "keystone_group"


def __virtual__():
    if "keystoneng.group_get" in __salt__:
        return __virtualname__
    return (
        False,
        "The keystoneng execution module failed to load: shade python module is not"
        " available",
    )


def _common(kwargs):
    """
    Returns: None if group wasn't found, otherwise a group object
    """
    search_kwargs = {"name": kwargs["name"]}
    if "domain" in kwargs:
        domain = __salt__["keystoneng.get_entity"]("domain", name=kwargs.pop("domain"))
        domain_id = domain.id if hasattr(domain, "id") else domain
        search_kwargs["filters"] = {"domain_id": domain_id}
        kwargs["domain"] = domain

    return __salt__["keystoneng.group_get"](**search_kwargs)


def present(name, auth=None, **kwargs):
    """
    Ensure an group exists and is up-to-date

    name
        Name of the group

    domain
        The name or id of the domain

    description
        An arbitrary description of the group
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    __salt__["keystoneng.setup_cloud"](auth)

    kwargs = __utils__["args.clean_kwargs"](**kwargs)

    kwargs["name"] = name
    group = _common(kwargs)

    if group is None:
        if __opts__["test"] is True:
            ret["result"] = None
            ret["changes"] = kwargs
            ret["comment"] = "Group will be created."
            return ret

        group = __salt__["keystoneng.group_create"](**kwargs)
        ret["changes"] = group
        ret["comment"] = "Created group"
        return ret

    changes = __salt__["keystoneng.compare_changes"](group, **kwargs)
    if changes:
        if __opts__["test"] is True:
            ret["result"] = None
            ret["changes"] = changes
            ret["comment"] = "Group will be updated."
            return ret

        __salt__["keystoneng.group_update"](**kwargs)
        ret["changes"].update(changes)
        ret["comment"] = "Updated group"

    return ret


def absent(name, auth=None, **kwargs):
    """
    Ensure group does not exist

    name
        Name of the group

    domain
        The name or id of the domain
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    kwargs = __utils__["args.clean_kwargs"](**kwargs)

    __salt__["keystoneng.setup_cloud"](auth)

    kwargs["name"] = name
    group = _common(kwargs)

    if group:
        if __opts__["test"] is True:
            ret["result"] = None
            ret["changes"] = {"id": group.id}
            ret["comment"] = "Group will be deleted."
            return ret

        __salt__["keystoneng.group_delete"](name=group)
        ret["changes"]["id"] = group.id
        ret["comment"] = "Deleted group"

    return ret
