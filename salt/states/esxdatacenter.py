"""
Salt states to create and manage VMware vSphere datacenters (datacenters).

:codeauthor: `Alexandru Bleotu <alexandru.bleotu@morganstaley.com>`

.. Warning::
    This module will be deprecated in a future release of Salt. VMware strongly
    recommends using the
    `VMware Salt extensions <https://docs.saltproject.io/salt/extensions/salt-ext-modules-vmware/en/latest/all.html>`_
    instead of the ESX data center module. Because the Salt extensions are newer
    and actively supported by VMware, they are more compatible with current
    versions of ESXi and they work well with the latest features in the VMware
    product line.


Dependencies
============

- pyVmomi Python Module

States
======

datacenter_configured
---------------------

Makes sure a datacenter exists and is correctly configured.

If the state is run by an ``esxdatacenter`` minion, the name of the datacenter
is retrieved from the proxy details, otherwise the datacenter has the same name
as the state.

Supported proxies: esxdatacenter


Example:

1. Make sure that a datacenter named ``target_dc`` exists on the vCenter, using a
``esxdatacenter`` proxy:

Proxy minion configuration (connects passthrough to the vCenter):

.. code-block:: yaml

    proxy:
      proxytype: esxdatacenter
      datacenter: target_dc
      vcenter: vcenter.fake.com
      mechanism: sspi
      domain: fake.com
      principal: host

State configuration:

.. code-block:: yaml

    datacenter_state:
      esxdatacenter.datacenter_configured
"""

import logging
from functools import wraps

import salt.exceptions

# Get Logging Started
log = logging.getLogger(__name__)
LOGIN_DETAILS = {}


def __virtual__():
    return "esxdatacenter"


def _deprecation_message(function):
    """
    Decorator wrapper to warn about azurearm deprecation
    """

    @wraps(function)
    def wrapped(*args, **kwargs):
        salt.utils.versions.warn_until(
            3008,
            "The 'esxdatacenter' functionality in Salt has been deprecated and its "
            "functionality will be removed in version 3008 in favor of the "
            "saltext.vmware Salt Extension. "
            "(https://github.com/saltstack/salt-ext-modules-vmware)",
            category=FutureWarning,
        )
        ret = function(*args, **salt.utils.args.clean_kwargs(**kwargs))
        return ret

    return wrapped


@_deprecation_message
def mod_init(low):
    return True


@_deprecation_message
def datacenter_configured(name):
    """
    Makes sure a datacenter exists.

    If the state is run by an ``esxdatacenter`` minion, the name of the
    datacenter is retrieved from the proxy details, otherwise the datacenter
    has the same name as the state.

    Supported proxies: esxdatacenter

    name:
        Datacenter name. Ignored if the proxytype is ``esxdatacenter``.
    """
    proxy_type = __salt__["vsphere.get_proxy_type"]()
    if proxy_type == "esxdatacenter":
        dc_name = __salt__["esxdatacenter.get_details"]()["datacenter"]
    else:
        dc_name = name
    log.info("Running datacenter_configured for datacenter '%s'", dc_name)
    ret = {"name": name, "changes": {}, "result": None, "comment": "Default"}
    comments = []
    si = None
    try:
        si = __salt__["vsphere.get_service_instance_via_proxy"]()
        dcs = __salt__["vsphere.list_datacenters_via_proxy"](
            datacenter_names=[dc_name], service_instance=si
        )
        if not dcs:
            if __opts__["test"]:
                comments.append(f"State will create datacenter '{dc_name}'.")
            else:
                log.debug("Creating datacenter '%s'", dc_name)
                __salt__["vsphere.create_datacenter"](dc_name, si)
                comments.append(f"Created datacenter '{dc_name}'.")
            log.info(comments[-1])
            ret["changes"].update({"new": {"name": dc_name}})
        else:
            comments.append(
                f"Datacenter '{dc_name}' already exists. Nothing to be done."
            )
            log.info(comments[-1])
        __salt__["vsphere.disconnect"](si)
        ret["comment"] = "\n".join(comments)
        ret["result"] = None if __opts__["test"] and ret["changes"] else True
        return ret
    except salt.exceptions.CommandExecutionError as exc:
        log.error("Error: %s", exc)
        if si:
            __salt__["vsphere.disconnect"](si)
        ret.update(
            {"result": False if not __opts__["test"] else None, "comment": str(exc)}
        )
        return ret
