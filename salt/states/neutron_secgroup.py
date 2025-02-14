"""
Management of OpenStack Neutron Security Groups
===============================================

.. versionadded:: 2018.3.0

:depends: shade
:configuration: see :py:mod:`salt.modules.neutronng` for setup instructions

Example States

.. code-block:: yaml

    create security group;
      neutron_secgroup.present:
        - name: security_group1
        - description: "Very Secure Security Group"

    delete security group:
      neutron_secgroup.absent:
        - name_or_id: security_group1
        - project_name: Project1

    create security group with optional params:
      neutron_secgroup.present:
        - name: security_group1
        - description: "Very Secure Security Group"
        - project_id: 1dcac318a83b4610b7a7f7ba01465548

    create security group with optional params:
      neutron_secgroup.present:
        - name: security_group1
        - description: "Very Secure Security Group"
        - project_name: Project1
"""

__virtualname__ = "neutron_secgroup"


def __virtual__():
    if "neutronng.list_subnets" in __salt__:
        return __virtualname__
    return (
        False,
        "The neutronng execution module failed to load: shade python module is not available",
    )


def present(name, auth=None, **kwargs):
    """
    Ensure a security group exists.

    You can supply either project_name or project_id.

    Creating a default security group will not show up as a change;
    it gets created through the lookup process.

    name
        Name of the security group

    description
        Description of the security group

    project_name
        Name of Project

    project_id
        ID of Project

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    kwargs = __utils__["args.clean_kwargs"](**kwargs)

    __salt__["neutronng.setup_clouds"](auth)

    if "project_name" in kwargs:
        kwargs["project_id"] = kwargs["project_name"]
        del kwargs["project_name"]

    project = __salt__["keystoneng.project_get"](name=kwargs["project_id"])

    if project is None:
        ret["result"] = False
        ret["comment"] = "project does not exist"
        return ret

    secgroup = __salt__["neutronng.security_group_get"](
        name=name, filters={"tenant_id": project.id}
    )

    if secgroup is None:
        if __opts__["test"] is True:
            ret["result"] = None
            ret["changes"] = kwargs
            ret["comment"] = "Security Group will be created."
            return ret

        secgroup = __salt__["neutronng.security_group_create"](**kwargs)
        ret["changes"] = secgroup
        ret["comment"] = "Created security group"
        return ret

    changes = __salt__["neutronng.compare_changes"](secgroup, **kwargs)
    if changes:
        if __opts__["test"] is True:
            ret["result"] = None
            ret["changes"] = changes
            ret["comment"] = "Security Group will be updated."
            return ret

        __salt__["neutronng.security_group_update"](secgroup=secgroup, **changes)
        ret["changes"].update(changes)
        ret["comment"] = "Updated security group"

    return ret


def absent(name, auth=None, **kwargs):
    """
    Ensure a security group does not exist

    name
        Name of the security group

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    kwargs = __utils__["args.clean_kwargs"](**kwargs)

    __salt__["neutronng.setup_clouds"](auth)

    kwargs["project_id"] = __salt__["keystoneng.project_get"](
        name=kwargs["project_name"]
    )

    secgroup = __salt__["neutronng.security_group_get"](
        name=name, filters={"project_id": kwargs["project_id"]}
    )

    if secgroup:
        if __opts__["test"] is True:
            ret["result"] = None
            ret["changes"] = {"id": secgroup.id}
            ret["comment"] = "Security group will be deleted."
            return ret

        __salt__["neutronng.security_group_delete"](name=secgroup)
        ret["changes"]["id"] = name
        ret["comment"] = "Deleted security group"

    return ret
