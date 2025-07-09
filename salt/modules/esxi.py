"""
Glues the VMware vSphere Execution Module to the VMware ESXi Proxy Minions to the
:mod:`esxi proxymodule <salt.proxy.esxi>`.

.. Warning::
    This module will be deprecated in a future release of Salt. VMware strongly
    recommends using the
    `VMware Salt extensions <https://docs.saltproject.io/salt/extensions/salt-ext-modules-vmware/en/latest/all.html>`_
    instead of the ESXi module. Because the Salt extensions are newer and
    actively supported by VMware, they are more compatible with current versions
    of ESXi and they work well with the latest features in the VMware product
    line.


Depends: :mod:`vSphere Remote Execution Module (salt.modules.vsphere)
<salt.modules.vsphere>`

For documentation on commands that you can direct to an ESXi host via proxy,
look in the documentation for :mod:`salt.modules.vsphere <salt.modules.vsphere>`.

This execution module calls through to a function in the ESXi proxy module
called ``ch_config``, which looks up the function passed in the ``command``
parameter in :mod:`salt.modules.vsphere <salt.modules.vsphere>` and calls it.

To execute commands with an ESXi Proxy Minion using the vSphere Execution Module,
use the ``esxi.cmd <vsphere-function-name>`` syntax. Both args and kwargs needed
for various vsphere execution module functions must be passed through in a kwarg-
type manor.

.. code-block:: bash

    salt 'esxi-proxy' esxi.cmd system_info
    salt 'exsi-proxy' esxi.cmd get_service_policy service_name='ssh'

"""

import logging
from functools import wraps

import salt.utils.platform

log = logging.getLogger(__name__)

__proxyenabled__ = ["esxi"]
__virtualname__ = "esxi"


def __virtual__():
    """
    Only work on proxy
    """
    if salt.utils.platform.is_proxy():
        return __virtualname__
    return (
        False,
        "The esxi execution module failed to load: only available on proxy minions.",
    )


def _deprecation_message(function):
    """
    Decorator wrapper to warn about azurearm deprecation
    """

    @wraps(function)
    def wrapped(*args, **kwargs):
        salt.utils.versions.warn_until(
            "Argon",
            "The 'esxi' functionality in Salt has been deprecated and its "
            "functionality will be removed in version 3008 in favor of the "
            "saltext.vmware Salt Extension. "
            "(https://github.com/saltstack/salt-ext-modules-vmware)",
            category=FutureWarning,
        )
        ret = function(*args, **salt.utils.args.clean_kwargs(**kwargs))
        return ret

    return wrapped


@_deprecation_message
def cmd(command, *args, **kwargs):
    proxy_prefix = __opts__["proxy"]["proxytype"]
    proxy_cmd = proxy_prefix + ".ch_config"

    return __proxy__[proxy_cmd](command, *args, **kwargs)


@_deprecation_message
def get_details():
    return __proxy__["esxi.get_details"]()
