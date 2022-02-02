"""
Management of OpenStack Neutron Networks
=========================================

.. versionadded:: 2018.3.0

:depends: shade
:configuration: see :py:mod:`salt.modules.neutronng` for setup instructions

Example States

.. code-block:: yaml

    create network:
      neutron_network.present:
        - name: network1

    delete network:
      neutron_network.absent:
        - name: network1

    create network with optional params:
      neutron_network.present:
        - name: network1
        - vlan: 200
        - shared: False
        - external: False
        - project: project1
"""


__virtualname__ = "neutron_network"


def __virtual__():
    if "neutronng.list_networks" in __salt__:
        return __virtualname__
    return (
        False,
        "The neutronng execution module failed to load: shade python module is not available",
    )


def present(name, auth=None, **kwargs):
    """
    Ensure a network exists and is up-to-date

    name
        Name of the network

    provider
        A dict of network provider options.

    shared
        Set the network as shared.

    external
        Whether this network is externally accessible.

    admin_state_up
         Set the network administrative state to up.

    vlan
        Vlan ID. Alias for provider

        - physical_network: provider
        - network_type: vlan
        - segmentation_id: (vlan id)
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    kwargs = __utils__["args.clean_kwargs"](**kwargs)

    __salt__["neutronng.setup_clouds"](auth)

    kwargs["name"] = name
    network = __salt__["neutronng.network_get"](name=name)

    if network is None:
        if __opts__["test"] is True:
            ret["result"] = None
            ret["changes"] = kwargs
            ret["comment"] = "Network will be created."
            return ret

        if "vlan" in kwargs:
            kwargs["provider"] = {
                "physical_network": "provider",
                "network_type": "vlan",
                "segmentation_id": kwargs["vlan"],
            }
            del kwargs["vlan"]

        if "project" in kwargs:
            projectname = kwargs["project"]
            project = __salt__["keystoneng.project_get"](name=projectname)
            if project:
                kwargs["project_id"] = project.id
                del kwargs["project"]
            else:
                ret["result"] = False
                ret["comment"] = "Project:{} not found.".format(projectname)
                return ret

        network = __salt__["neutronng.network_create"](**kwargs)
        ret["changes"] = network
        ret["comment"] = "Created network"
        return ret

    changes = __salt__["neutronng.compare_changes"](network, **kwargs)

    # there's no method for network update in shade right now;
    # can only delete and recreate
    if changes:
        if __opts__["test"] is True:
            ret["result"] = None
            ret["changes"] = changes
            ret["comment"] = "Project will be updated."
            return ret

        __salt__["neutronng.network_delete"](name=network)
        __salt__["neutronng.network_create"](**kwargs)
        ret["changes"].update(changes)
        ret["comment"] = "Updated network"

    return ret


def absent(name, auth=None, **kwargs):
    """
    Ensure a network does not exists

    name
        Name of the network

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    kwargs = __utils__["args.clean_kwargs"](**kwargs)

    __salt__["neutronng.setup_clouds"](auth)

    kwargs["name"] = name
    network = __salt__["neutronng.network_get"](name=name)

    if network:
        if __opts__["test"] is True:
            ret["result"] = None
            ret["changes"] = {"id": network.id}
            ret["comment"] = "Network will be deleted."
            return ret

        __salt__["neutronng.network_delete"](name=network)
        ret["changes"]["id"] = network.id
        ret["comment"] = "Deleted network"

    return ret
