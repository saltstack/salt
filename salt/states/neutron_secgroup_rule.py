"""
Management of OpenStack Neutron Security Group Rules
====================================================

.. versionadded:: 2018.3.0

:depends: shade
:configuration: see :py:mod:`salt.modules.neutronng` for setup instructions

Example States

.. code-block:: yaml

    create security group rule:
      neutron_secgroup_rule.present:
        - name: security_group1
        - project_name: Project1
        - protocol: icmp

    delete security group:
      neutron_secgroup_rule.absent:
        - name_or_id: security_group1

    create security group with optional params:
      neutron_secgroup_rule.present:
        - name: security_group1
        - description: "Very Secure Security Group"
        - project_id: 1dcac318a83b4610b7a7f7ba01465548
"""


__virtualname__ = "neutron_secgroup_rule"


def __virtual__():
    if "neutronng.list_subnets" in __salt__:
        return __virtualname__
    return (
        False,
        "The neutronng execution module failed to load: shade python module is not available",
    )


def _rule_compare(rule1, rule2):
    """
    Compare the common keys between security group rules against eachother
    """

    commonkeys = set(rule1.keys()).intersection(rule2.keys())
    for key in commonkeys:
        if rule1[key] != rule2[key]:
            return False
    return True


def present(name, auth=None, **kwargs):
    """
    Ensure a security group rule exists

    defaults: port_range_min=None, port_range_max=None, protocol=None,
              remote_ip_prefix=None, remote_group_id=None, direction='ingress',
              ethertype='IPv4', project_id=None

    name
        Name of the security group to associate with this rule

    project_name
        Name of the project associated with the security group

    protocol
        The protocol that is matched by the security group rule.
        Valid values are None, tcp, udp, and icmp.

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
        ret["comment"] = "Project does not exist"
        return ret

    secgroup = __salt__["neutronng.security_group_get"](
        name=name, filters={"tenant_id": project.id}
    )

    if secgroup is None:
        ret["result"] = False
        ret["changes"] = ({},)
        ret["comment"] = "Security Group does not exist {}".format(name)
        return ret

    # we have to search through all secgroup rules for a possible match
    rule_exists = None
    for rule in secgroup["security_group_rules"]:
        if _rule_compare(rule, kwargs) is True:
            rule_exists = True

    if rule_exists is None:
        if __opts__["test"] is True:
            ret["result"] = None
            ret["changes"] = kwargs
            ret["comment"] = "Security Group rule will be created."
            return ret

        # The variable differences are a little clumsy right now
        kwargs["secgroup_name_or_id"] = secgroup

        new_rule = __salt__["neutronng.security_group_rule_create"](**kwargs)
        ret["changes"] = new_rule
        ret["comment"] = "Created security group rule"
        return ret

    return ret


def absent(name, auth=None, **kwargs):
    """
    Ensure a security group rule does not exist

    name
        name or id of the security group rule to delete

    rule_id
        uuid of the rule to delete

    project_id
        id of project to delete rule from
    """
    rule_id = kwargs["rule_id"]
    ret = {"name": rule_id, "changes": {}, "result": True, "comment": ""}

    __salt__["neutronng.setup_clouds"](auth)

    secgroup = __salt__["neutronng.security_group_get"](
        name=name, filters={"tenant_id": kwargs["project_id"]}
    )

    # no need to delete a rule if the security group doesn't exist
    if secgroup is None:
        ret["comment"] = "security group does not exist"
        return ret

    # This should probably be done with compare on fields instead of
    # rule_id in the future
    rule_exists = None
    for rule in secgroup["security_group_rules"]:
        if _rule_compare(rule, {"id": rule_id}) is True:
            rule_exists = True

    if rule_exists:
        if __opts__["test"]:
            ret["result"] = None
            ret["changes"] = {"id": kwargs["rule_id"]}
            ret["comment"] = "Security group rule will be deleted."
            return ret

        __salt__["neutronng.security_group_rule_delete"](rule_id=rule_id)
        ret["changes"]["id"] = rule_id
        ret["comment"] = "Deleted security group rule"

    return ret
