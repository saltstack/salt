"""
CenturyLink Cloud Module
========================

.. versionadded:: 2018.3

The CLC cloud module allows you to manage CLC Via the CLC SDK.

:codeauthor: Stephan Looney <slooney@stephanlooney.com>


Dependencies
============

- clc-sdk Python Module
- flask

CLC SDK
-------

clc-sdk can be installed via pip:

.. code-block:: bash

    pip install clc-sdk

.. note::
  For sdk reference see: https://github.com/CenturyLinkCloud/clc-python-sdk

Flask
-----

flask can be installed via pip:

.. code-block:: bash

    pip install flask

Configuration
=============

To use this module: set up the clc-sdk, user, password, key in the
cloud configuration at
``/etc/salt/cloud.providers`` or ``/etc/salt/cloud.providers.d/clc.conf``:

.. code-block:: yaml

    my-clc-config:
      driver: clc
      user: 'web-user'
      password: 'verybadpass'
      token: ''
      token_pass:''
      accountalias: 'ACT'
.. note::

    The ``provider`` parameter in cloud provider configuration was renamed to ``driver``.
    This change was made to avoid confusion with the ``provider`` parameter that is
    used in cloud profile configuration. Cloud provider configuration now uses ``driver``
    to refer to the salt-cloud driver that provides the underlying functionality to
    connect to a cloud provider, while cloud profile configuration continues to use
    ``provider`` to refer to the cloud provider configuration that you define.

"""

import importlib
import logging
import time

import salt.config as config
import salt.utils.json
from salt.exceptions import SaltCloudSystemExit

# Attempt to import clc-sdk lib
try:
    # when running this in linode's Ubuntu 16.x version the following line is required
    # to get the clc sdk libraries to load
    importlib.import_module("clc")
    import clc

    HAS_CLC = True
except ImportError:
    HAS_CLC = False
# Disable InsecureRequestWarning generated on python > 2.6
try:
    from requests.packages.urllib3 import (  # pylint: disable=no-name-in-module
        disable_warnings,
    )

    disable_warnings()
except Exception:  # pylint: disable=broad-except
    pass

log = logging.getLogger(__name__)


__virtualname__ = "clc"


# Only load in this module if the CLC configurations are in place
def __virtual__():
    """
    Check for CLC configuration and if required libs are available.
    """
    if get_configured_provider() is False or get_dependencies() is False:
        return False

    return __virtualname__


def _get_active_provider_name():
    try:
        return __active_provider_name__.value()
    except AttributeError:
        return __active_provider_name__


def get_configured_provider():
    return config.is_provider_configured(
        __opts__,
        _get_active_provider_name() or __virtualname__,
        (
            "token",
            "token_pass",
            "user",
            "password",
        ),
    )


def get_dependencies():
    """
    Warn if dependencies aren't met.
    """
    deps = {
        "clc": HAS_CLC,
    }
    return config.check_driver_dependencies(__virtualname__, deps)


def get_creds():
    user = config.get_cloud_config_value(
        "user", get_configured_provider(), __opts__, search_global=False
    )
    password = config.get_cloud_config_value(
        "password", get_configured_provider(), __opts__, search_global=False
    )
    accountalias = config.get_cloud_config_value(
        "accountalias", get_configured_provider(), __opts__, search_global=False
    )
    token = config.get_cloud_config_value(
        "token", get_configured_provider(), __opts__, search_global=False
    )
    token_pass = config.get_cloud_config_value(
        "token_pass", get_configured_provider(), __opts__, search_global=False
    )
    creds = {
        "user": user,
        "password": password,
        "token": token,
        "token_pass": token_pass,
        "accountalias": accountalias,
    }
    return creds


def list_nodes_full(call=None, for_output=True):
    """
    Return a list of the VMs that are on the provider
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_nodes_full function must be called with -f or --function."
        )
    creds = get_creds()
    clc.v1.SetCredentials(creds["token"], creds["token_pass"])
    servers_raw = clc.v1.Server.GetServers(location=None)
    servers_raw = salt.utils.json.dumps(servers_raw)
    servers = salt.utils.json.loads(servers_raw)
    return servers


def get_queue_data(call=None, for_output=True):
    creds = get_creds()
    clc.v1.SetCredentials(creds["token"], creds["token_pass"])
    cl_queue = clc.v1.Queue.List()
    return cl_queue


def get_monthly_estimate(call=None, for_output=True):
    """
    Return a list of the VMs that are on the provider
    """
    creds = get_creds()
    clc.v1.SetCredentials(creds["token"], creds["token_pass"])
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_nodes_full function must be called with -f or --function."
        )
    try:
        billing_raw = clc.v1.Billing.GetAccountSummary(alias=creds["accountalias"])
        billing_raw = salt.utils.json.dumps(billing_raw)
        billing = salt.utils.json.loads(billing_raw)
        billing = round(billing["MonthlyEstimate"], 2)
        return {"Monthly Estimate": billing}
    except RuntimeError:
        return {"Monthly Estimate": 0}


def get_month_to_date(call=None, for_output=True):
    """
    Return a list of the VMs that are on the provider
    """
    creds = get_creds()
    clc.v1.SetCredentials(creds["token"], creds["token_pass"])
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_nodes_full function must be called with -f or --function."
        )
    try:
        billing_raw = clc.v1.Billing.GetAccountSummary(alias=creds["accountalias"])
        billing_raw = salt.utils.json.dumps(billing_raw)
        billing = salt.utils.json.loads(billing_raw)
        billing = round(billing["MonthToDateTotal"], 2)
        return {"Month To Date": billing}
    except RuntimeError:
        return 0


def get_server_alerts(call=None, for_output=True, **kwargs):
    """
    Return a list of alerts from CLC as reported by their infra
    """
    for key, value in kwargs.items():
        servername = ""
        if key == "servername":
            servername = value
    creds = get_creds()
    clc.v2.SetCredentials(creds["user"], creds["password"])
    alerts = clc.v2.Server(servername).Alerts()
    return alerts


def get_group_estimate(call=None, for_output=True, **kwargs):
    """
    Return a list of the VMs that are on the provider
    usage: "salt-cloud -f get_group_estimate clc group=Dev location=VA1"
    """
    for key, value in kwargs.items():
        group = ""
        location = ""
        if key == "group":
            group = value
        if key == "location":
            location = value
    creds = get_creds()
    clc.v1.SetCredentials(creds["token"], creds["token_pass"])
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_nodes_full function must be called with -f or --function."
        )
    try:
        billing_raw = clc.v1.Billing.GetGroupEstimate(
            group=group, alias=creds["accountalias"], location=location
        )
        billing_raw = salt.utils.json.dumps(billing_raw)
        billing = salt.utils.json.loads(billing_raw)
        estimate = round(billing["MonthlyEstimate"], 2)
        month_to_date = round(billing["MonthToDate"], 2)
        return {"Monthly Estimate": estimate, "Month to Date": month_to_date}
    except RuntimeError:
        return 0


def avail_images(call=None):
    """
    returns a list of images available to you
    """
    all_servers = list_nodes_full()
    templates = {}
    for server in all_servers:
        if server["IsTemplate"]:
            templates.update({"Template Name": server["Name"]})
    return templates


def avail_locations(call=None):
    """
    returns a list of locations available to you
    """
    creds = get_creds()
    clc.v1.SetCredentials(creds["token"], creds["token_pass"])
    locations = clc.v1.Account.GetLocations()
    return locations


def avail_sizes(call=None):
    """
    use templates for this
    """
    return {"Sizes": "Sizes are built into templates. Choose appropriate template"}


def get_build_status(req_id, nodename):
    """
    get the build status from CLC to make sure we don't return to early
    """
    counter = 0
    req_id = str(req_id)
    while counter < 10:
        queue = clc.v1.Blueprint.GetStatus(request_id=(req_id))
        if queue["PercentComplete"] == 100:
            server_name = queue["Servers"][0]
            creds = get_creds()
            clc.v2.SetCredentials(creds["user"], creds["password"])
            ip_addresses = clc.v2.Server(server_name).ip_addresses
            internal_ip_address = ip_addresses[0]["internal"]
            return internal_ip_address
        else:
            counter = counter + 1
            log.info(
                "Creating Cloud VM %s Time out in %s minutes",
                nodename,
                str(10 - counter),
            )
            time.sleep(60)


def create(vm_):
    """
    get the system build going
    """
    creds = get_creds()
    clc.v1.SetCredentials(creds["token"], creds["token_pass"])
    cloud_profile = config.is_provider_configured(
        __opts__, _get_active_provider_name() or __virtualname__, ("token",)
    )
    group = config.get_cloud_config_value(
        "group",
        vm_,
        __opts__,
        search_global=False,
        default=None,
    )
    name = vm_["name"]
    description = config.get_cloud_config_value(
        "description",
        vm_,
        __opts__,
        search_global=False,
        default=None,
    )
    ram = config.get_cloud_config_value(
        "ram",
        vm_,
        __opts__,
        search_global=False,
        default=None,
    )
    backup_level = config.get_cloud_config_value(
        "backup_level",
        vm_,
        __opts__,
        search_global=False,
        default=None,
    )
    template = config.get_cloud_config_value(
        "template",
        vm_,
        __opts__,
        search_global=False,
        default=None,
    )
    password = config.get_cloud_config_value(
        "password",
        vm_,
        __opts__,
        search_global=False,
        default=None,
    )
    cpu = config.get_cloud_config_value(
        "cpu",
        vm_,
        __opts__,
        search_global=False,
        default=None,
    )
    network = config.get_cloud_config_value(
        "network",
        vm_,
        __opts__,
        search_global=False,
        default=None,
    )
    location = config.get_cloud_config_value(
        "location",
        vm_,
        __opts__,
        search_global=False,
        default=None,
    )
    if len(name) > 6:
        name = name[0:6]
    if len(password) < 9:
        password = ""
    clc_return = clc.v1.Server.Create(
        alias=None,
        location=(location),
        name=(name),
        template=(template),
        cpu=(cpu),
        ram=(ram),
        backup_level=(backup_level),
        group=(group),
        network=(network),
        description=(description),
        password=(password),
    )
    req_id = clc_return["RequestID"]
    vm_["ssh_host"] = get_build_status(req_id, name)
    __utils__["cloud.fire_event"](
        "event",
        "waiting for ssh",
        "salt/cloud/{}/waiting_for_ssh".format(name),
        sock_dir=__opts__["sock_dir"],
        args={"ip_address": vm_["ssh_host"]},
        transport=__opts__["transport"],
    )

    # Bootstrap!
    ret = __utils__["cloud.bootstrap"](vm_, __opts__)
    return_message = {"Server Name": name, "IP Address": vm_["ssh_host"]}
    ret.update(return_message)
    return return_message


def destroy(name, call=None):
    """
    destroy the vm
    """
    return {"status": "destroying must be done via https://control.ctl.io at this time"}
