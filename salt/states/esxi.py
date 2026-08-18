"""
Manage VMware ESXi Hosts.

.. Warning::
    This module will be deprecated in a future release of Salt. VMware strongly
    recommends using the
    `VMware Salt extensions <https://docs.saltproject.io/salt/extensions/salt-ext-modules-vmware/en/latest/all.html>`_
    instead of the ESXi module. Because the Salt extensions are newer and
    actively supported by VMware, they are more compatible with current versions
    of ESXi and they work well with the latest features in the VMware product
    line.


Dependencies
============

- pyVmomi Python Module
- ESXCLI


pyVmomi
-------

PyVmomi can be installed via pip:

.. code-block:: bash

    pip install pyVmomi

.. note::

    Version 6.0 of pyVmomi has some problems with SSL error handling on certain
    versions of Python. If using version 6.0 of pyVmomi, Python 2.6,
    Python 2.7.9, or newer must be present. This is due to an upstream dependency
    in pyVmomi 6.0 that is not supported in Python versions 2.7 to 2.7.8. If the
    version of Python is not in the supported range, you will need to install an
    earlier version of pyVmomi. See `Issue #29537`_ for more information.

.. _Issue #29537: https://github.com/saltstack/salt/issues/29537

Based on the note above, to install an earlier version of pyVmomi than the
version currently listed in PyPi, run the following:

.. code-block:: bash

    pip install pyVmomi==5.5.0.2014.1.1

The 5.5.0.2014.1.1 is a known stable version that this original ESXi State
Module was developed against.

ESXCLI
------

Currently, about a third of the functions used in the vSphere Execution Module require
the ESXCLI package be installed on the machine running the Proxy Minion process.

The ESXCLI package is also referred to as the VMware vSphere CLI, or vCLI. VMware
provides vCLI package installation instructions for `vSphere 5.5`_ and
`vSphere 6.0`_.

.. _vSphere 5.5: http://pubs.vmware.com/vsphere-55/index.jsp#com.vmware.vcli.getstart.doc/cli_install.4.2.html
.. _vSphere 6.0: http://pubs.vmware.com/vsphere-60/index.jsp#com.vmware.vcli.getstart.doc/cli_install.4.2.html

Once all of the required dependencies are in place and the vCLI package is
installed, you can check to see if you can connect to your ESXi host or vCenter
server by running the following command:

.. code-block:: bash

    esxcli -s <host-location> -u <username> -p <password> system syslog config get

If the connection was successful, ESXCLI was successfully installed on your system.
You should see output related to the ESXi host's syslog configuration.

.. note::

    Be aware that some functionality in this state module may depend on the
    type of license attached to the ESXi host.

    For example, certain services are only available to manipulate service state
    or policies with a VMware vSphere Enterprise or Enterprise Plus license, while
    others are available with a Standard license. The ``ntpd`` service is restricted
    to an Enterprise Plus license, while ``ssh`` is available via the Standard
    license.

    Please see the `vSphere Comparison`_ page for more information.

.. _vSphere Comparison: https://www.vmware.com/products/vsphere/compare

About
-----

This state module was written to be used in conjunction with Salt's
:mod:`ESXi Proxy Minion <salt.proxy.esxi>`. For a tutorial on how to use Salt's
ESXi Proxy Minion, please refer to the
:ref:`ESXi Proxy Minion Tutorial <tutorial-esxi-proxy>` for
configuration examples, dependency installation instructions, how to run remote
execution functions against ESXi hosts via a Salt Proxy Minion, and a larger state
example.
"""

import logging
import re
import sys
from functools import wraps

import salt.utils.files
from salt.config.schemas.esxi import DiskGroupsDiskScsiAddressSchema, HostCacheSchema
from salt.exceptions import (
    ArgumentValueError,
    CommandExecutionError,
    InvalidConfigError,
    VMwareApiError,
    VMwareObjectRetrievalError,
    VMwareSaltError,
)
from salt.utils.decorators import depends

# External libraries
try:
    import jsonschema

    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

# Get Logging Started
log = logging.getLogger(__name__)

try:
    from pyVmomi import VmomiSupport

    # We check the supported vim versions to infer the pyVmomi version
    if (
        "vim25/6.0" in VmomiSupport.versionMap
        and sys.version_info > (2, 7)
        and sys.version_info < (2, 7, 9)
    ):

        log.debug(
            "pyVmomi not loaded: Incompatible versions of Python. See Issue #29537."
        )
        raise ImportError()
    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False


def __virtual__():
    if "esxi.cmd" in __salt__:
        return True
    return (False, "esxi module could not be loaded")


def _deprecation_message(function):
    """
    Decorator wrapper to warn about azurearm deprecation
    """

    @wraps(function)
    def wrapped(*args, **kwargs):
        salt.utils.versions.warn_until(
            3008,
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
def coredump_configured(name, enabled, dump_ip, host_vnic="vmk0", dump_port=6500):
    """
    Ensures a host's core dump configuration.

    name
        Name of the state.

    enabled
        Sets whether or not ESXi core dump collection should be enabled.
        This is a boolean value set to ``True`` or ``False`` to enable
        or disable core dumps.

        Note that ESXi requires that the core dump must be enabled before
        any other parameters may be set. This also affects the ``changes``
        results in the state return dictionary. If ``enabled`` is ``False``,
        we can't obtain any previous settings to compare other state variables,
        resulting in many ``old`` references returning ``None``.

        Once ``enabled`` is ``True`` the ``changes`` dictionary comparisons
        will be more accurate. This is due to the way the system coredemp
        network configuration command returns data.

    dump_ip
        The IP address of host that will accept the dump.

    host_vnic
        Host VNic port through which to communicate. Defaults to ``vmk0``.

    dump_port
        TCP port to use for the dump. Defaults to ``6500``.

    Example:

    .. code-block:: yaml

        configure-host-coredump:
          esxi.coredump_configured:
            - enabled: True
            - dump_ip: 'my-coredump-ip.example.com'

    """
    ret = {"name": name, "result": False, "changes": {}, "comment": ""}
    esxi_cmd = "esxi.cmd"
    enabled_msg = (
        "ESXi requires that the core dump must be enabled "
        "before any other parameters may be set."
    )
    host = __pillar__["proxy"]["host"]

    current_config = __salt__[esxi_cmd]("get_coredump_network_config").get(host)
    error = current_config.get("Error")
    if error:
        ret["comment"] = f"Error: {error}"
        return ret

    current_config = current_config.get("Coredump Config")
    current_enabled = current_config.get("enabled")

    # Configure coredump enabled state, if there are changes.
    if current_enabled != enabled:
        enabled_changes = {"enabled": {"old": current_enabled, "new": enabled}}
        # Only run the command if not using test=True
        if not __opts__["test"]:
            response = __salt__[esxi_cmd](
                "coredump_network_enable", enabled=enabled
            ).get(host)
            error = response.get("Error")
            if error:
                ret["comment"] = f"Error: {error}"
                return ret

            # Allow users to disable core dump, but then return since
            # nothing else can be set if core dump is disabled.
            if not enabled:
                ret["result"] = True
                ret["comment"] = enabled_msg
                ret["changes"].update(enabled_changes)
                return ret

        ret["changes"].update(enabled_changes)

    elif not enabled:
        # If current_enabled and enabled match, but are both False,
        # We must return before configuring anything. This isn't a
        # failure as core dump may be disabled intentionally.
        ret["result"] = True
        ret["comment"] = enabled_msg
        return ret

    # Test for changes with all remaining configurations. The changes flag is used
    # To detect changes, and then set_coredump_network_config is called one time.
    changes = False
    current_ip = current_config.get("ip")
    if current_ip != dump_ip:
        ret["changes"].update({"dump_ip": {"old": current_ip, "new": dump_ip}})
        changes = True

    current_vnic = current_config.get("host_vnic")
    if current_vnic != host_vnic:
        ret["changes"].update({"host_vnic": {"old": current_vnic, "new": host_vnic}})
        changes = True

    current_port = current_config.get("port")
    if current_port != str(dump_port):
        ret["changes"].update(
            {"dump_port": {"old": current_port, "new": str(dump_port)}}
        )
        changes = True

    # Only run the command if not using test=True and changes were detected.
    if not __opts__["test"] and changes is True:
        response = __salt__[esxi_cmd](
            "set_coredump_network_config",
            dump_ip=dump_ip,
            host_vnic=host_vnic,
            dump_port=dump_port,
        ).get(host)
        if response.get("success") is False:
            msg = response.get("stderr")
            if not msg:
                msg = response.get("stdout")
            ret["comment"] = f"Error: {msg}"
            return ret

    ret["result"] = True
    if ret["changes"] == {}:
        ret["comment"] = "Core Dump configuration is already in the desired state."
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "Core dump configuration will change."

    return ret


@_deprecation_message
def password_present(name, password):
    """
    Ensures the given password is set on the ESXi host. Passwords cannot be obtained from
    host, so if a password is set in this state, the ``vsphere.update_host_password``
    function will always run (except when using test=True functionality) and the state's
    changes dictionary will always be populated.

    The username for which the password will change is the same username that is used to
    authenticate against the ESXi host via the Proxy Minion. For example, if the pillar
    definition for the proxy username is defined as ``root``, then the username that the
    password will be updated for via this state is ``root``.

    name
        Name of the state.

    password
        The new password to change on the host.

    Example:

    .. code-block:: yaml

        configure-host-password:
          esxi.password_present:
            - password: 'new-bad-password'
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {"old": "unknown", "new": "********"},
        "comment": "Host password was updated.",
    }
    esxi_cmd = "esxi.cmd"

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "Host password will change."
        return ret
    else:
        try:
            __salt__[esxi_cmd]("update_host_password", new_password=password)
        except CommandExecutionError as err:
            ret["result"] = False
            ret["comment"] = f"Error: {err}"
            return ret

    return ret


@_deprecation_message
def ntp_configured(
    name,
    service_running,
    ntp_servers=None,
    service_policy=None,
    service_restart=False,
    update_datetime=False,
):
    """
    Ensures a host's NTP server configuration such as setting NTP servers, ensuring the
    NTP daemon is running or stopped, or restarting the NTP daemon for the ESXi host.

    name
        Name of the state.

    service_running
        Ensures the running state of the ntp daemon for the host. Boolean value where
        ``True`` indicates that ntpd should be running and ``False`` indicates that it
        should be stopped.

    ntp_servers
        A list of servers that should be added to the ESXi host's NTP configuration.

    service_policy
        The policy to set for the NTP service.

        .. note::

            When setting the service policy to ``off`` or ``on``, you *must* quote the
            setting. If you don't, the yaml parser will set the string to a boolean,
            which will cause trouble checking for stateful changes and will error when
            trying to set the policy on the ESXi host.


    service_restart
        If set to ``True``, the ntp daemon will be restarted, regardless of its previous
        running state. Default is ``False``.

    update_datetime
        If set to ``True``, the date/time on the given host will be updated to UTC.
        Default setting is ``False``. This option should be used with caution since
        network delays and execution delays can result in time skews.

    Example:

    .. code-block:: yaml

        configure-host-ntp:
          esxi.ntp_configured:
            - service_running: True
            - ntp_servers:
              - 192.174.1.100
              - 192.174.1.200
            - service_policy: 'on'
            - service_restart: True

    """
    ret = {"name": name, "result": False, "changes": {}, "comment": ""}
    esxi_cmd = "esxi.cmd"
    host = __pillar__["proxy"]["host"]
    ntpd = "ntpd"

    ntp_config = __salt__[esxi_cmd]("get_ntp_config").get(host)
    ntp_running = __salt__[esxi_cmd]("get_service_running", service_name=ntpd).get(host)
    error = ntp_running.get("Error")
    if error:
        ret["comment"] = f"Error: {error}"
        return ret
    ntp_running = ntp_running.get(ntpd)

    # Configure NTP Servers for the Host
    if ntp_servers and set(ntp_servers) != set(ntp_config):
        # Only run the command if not using test=True
        if not __opts__["test"]:
            response = __salt__[esxi_cmd](
                "set_ntp_config", ntp_servers=ntp_servers
            ).get(host)
            error = response.get("Error")
            if error:
                ret["comment"] = f"Error: {error}"
                return ret
        # Set changes dictionary for ntp_servers
        ret["changes"].update({"ntp_servers": {"old": ntp_config, "new": ntp_servers}})

    # Configure service_running state
    if service_running != ntp_running:
        # Only run the command if not using test=True
        if not __opts__["test"]:
            # Start ntdp if service_running=True
            if ntp_running is True:
                response = __salt__[esxi_cmd]("service_start", service_name=ntpd).get(
                    host
                )
                error = response.get("Error")
                if error:
                    ret["comment"] = f"Error: {error}"
                    return ret
            # Stop ntpd if service_running=False
            else:
                response = __salt__[esxi_cmd]("service_stop", service_name=ntpd).get(
                    host
                )
                error = response.get("Error")
                if error:
                    ret["comment"] = f"Error: {error}"
                    return ret
        ret["changes"].update(
            {"service_running": {"old": ntp_running, "new": service_running}}
        )

    # Configure service_policy
    if service_policy:
        current_service_policy = __salt__[esxi_cmd](
            "get_service_policy", service_name=ntpd
        ).get(host)
        error = current_service_policy.get("Error")
        if error:
            ret["comment"] = f"Error: {error}"
            return ret
        current_service_policy = current_service_policy.get(ntpd)

        if service_policy != current_service_policy:
            # Only run the command if not using test=True
            if not __opts__["test"]:
                response = __salt__[esxi_cmd](
                    "set_service_policy",
                    service_name=ntpd,
                    service_policy=service_policy,
                ).get(host)
                error = response.get("Error")
                if error:
                    ret["comment"] = f"Error: {error}"
                    return ret
            ret["changes"].update(
                {
                    "service_policy": {
                        "old": current_service_policy,
                        "new": service_policy,
                    }
                }
            )

    # Update datetime, if requested.
    if update_datetime:
        # Only run the command if not using test=True
        if not __opts__["test"]:
            response = __salt__[esxi_cmd]("update_host_datetime").get(host)
            error = response.get("Error")
            if error:
                ret["comment"] = f"Error: {error}"
                return ret
        ret["changes"].update(
            {"update_datetime": {"old": "", "new": "Host datetime was updated."}}
        )

    # Restart ntp_service if service_restart=True
    if service_restart:
        # Only run the command if not using test=True
        if not __opts__["test"]:
            response = __salt__[esxi_cmd]("service_restart", service_name=ntpd).get(
                host
            )
            error = response.get("Error")
            if error:
                ret["comment"] = f"Error: {error}"
                return ret
        ret["changes"].update(
            {"service_restart": {"old": "", "new": "NTP Daemon Restarted."}}
        )

    ret["result"] = True
    if ret["changes"] == {}:
        ret["comment"] = "NTP is already in the desired state."
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "NTP state will change."

    return ret


@_deprecation_message
def vmotion_configured(name, enabled, device="vmk0"):
    """
    Configures a host's VMotion properties such as enabling VMotion and setting
    the device VirtualNic that VMotion will use.

    name
        Name of the state.

    enabled
        Ensures whether or not VMotion should be enabled on a host as a boolean
        value where ``True`` indicates that VMotion should be enabled and ``False``
        indicates that VMotion should be disabled.

    device
        The device that uniquely identifies the VirtualNic that will be used for
        VMotion for the host. Defaults to ``vmk0``.

    Example:

    .. code-block:: yaml

        configure-vmotion:
          esxi.vmotion_configured:
            - enabled: True
            - device: sample-device

    """
    ret = {"name": name, "result": False, "changes": {}, "comment": ""}
    esxi_cmd = "esxi.cmd"
    host = __pillar__["proxy"]["host"]

    current_vmotion_enabled = __salt__[esxi_cmd]("get_vmotion_enabled").get(host)
    current_vmotion_enabled = current_vmotion_enabled.get("VMotion Enabled")

    # Configure VMotion Enabled state, if changed.
    if enabled != current_vmotion_enabled:
        # Only run the command if not using test=True
        if not __opts__["test"]:
            # Enable VMotion if enabled=True
            if enabled is True:
                response = __salt__[esxi_cmd]("vmotion_enable", device=device).get(host)
                error = response.get("Error")
                if error:
                    ret["comment"] = f"Error: {error}"
                    return ret
            # Disable VMotion if enabled=False
            else:
                response = __salt__[esxi_cmd]("vmotion_disable").get(host)
                error = response.get("Error")
                if error:
                    ret["comment"] = f"Error: {error}"
                    return ret
        ret["changes"].update(
            {"enabled": {"old": current_vmotion_enabled, "new": enabled}}
        )

    ret["result"] = True
    if ret["changes"] == {}:
        ret["comment"] = "VMotion configuration is already in the desired state."
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "VMotion configuration will change."

    return ret


@_deprecation_message
def vsan_configured(name, enabled, add_disks_to_vsan=False):
    """
    Configures a host's VSAN properties such as enabling or disabling VSAN, or
    adding VSAN-eligible disks to the VSAN system for the host.

    name
        Name of the state.

    enabled
        Ensures whether or not VSAN should be enabled on a host as a boolean
        value where ``True`` indicates that VSAN should be enabled and ``False``
        indicates that VSAN should be disabled.

    add_disks_to_vsan
        If set to ``True``, any VSAN-eligible disks for the given host will be added
        to the host's VSAN system. Default is ``False``.

    Example:

    .. code-block:: yaml

        configure-host-vsan:
          esxi.vsan_configured:
            - enabled: True
            - add_disks_to_vsan: True

    """
    ret = {"name": name, "result": False, "changes": {}, "comment": ""}
    esxi_cmd = "esxi.cmd"
    host = __pillar__["proxy"]["host"]

    current_vsan_enabled = __salt__[esxi_cmd]("get_vsan_enabled").get(host)
    error = current_vsan_enabled.get("Error")
    if error:
        ret["comment"] = f"Error: {error}"
        return ret
    current_vsan_enabled = current_vsan_enabled.get("VSAN Enabled")

    # Configure VSAN Enabled state, if changed.
    if enabled != current_vsan_enabled:
        # Only run the command if not using test=True
        if not __opts__["test"]:
            # Enable VSAN if enabled=True
            if enabled is True:
                response = __salt__[esxi_cmd]("vsan_enable").get(host)
                error = response.get("Error")
                if error:
                    ret["comment"] = f"Error: {error}"
                    return ret
            # Disable VSAN if enabled=False
            else:
                response = __salt__[esxi_cmd]("vsan_disable").get(host)
                error = response.get("Error")
                if error:
                    ret["comment"] = f"Error: {error}"
                    return ret
        ret["changes"].update(
            {"enabled": {"old": current_vsan_enabled, "new": enabled}}
        )

    # Add any eligible disks to VSAN, if requested.
    if add_disks_to_vsan:
        current_eligible_disks = __salt__[esxi_cmd]("get_vsan_eligible_disks").get(host)
        error = current_eligible_disks.get("Error")
        if error:
            ret["comment"] = f"Error: {error}"
            return ret

        disks = current_eligible_disks.get("Eligible")
        if disks and isinstance(disks, list):
            # Only run the command if not using test=True
            if not __opts__["test"]:
                response = __salt__[esxi_cmd]("vsan_add_disks").get(host)
                error = response.get("Error")
                if error:
                    ret["comment"] = f"Error: {error}"
                    return ret

            ret["changes"].update({"add_disks_to_vsan": {"old": "", "new": disks}})

    ret["result"] = True
    if ret["changes"] == {}:
        ret["comment"] = "VSAN configuration is already in the desired state."
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "VSAN configuration will change."

    return ret


@_deprecation_message
def ssh_configured(
    name,
    service_running,
    ssh_key=None,
    ssh_key_file=None,
    service_policy=None,
    service_restart=False,
    certificate_verify=None,
):
    """
    Manage the SSH configuration for a host including whether or not SSH is running or
    the presence of a given SSH key. Note: Only one ssh key can be uploaded for root.
    Uploading a second key will replace any existing key.

    name
        Name of the state.

    service_running
        Ensures whether or not the SSH service should be running on a host. Represented
        as a boolean value where ``True`` indicates that SSH should be running and
        ``False`` indicates that SSH should stopped.

        In order to update SSH keys, the SSH service must be running.

    ssh_key
        Public SSH key to added to the authorized_keys file on the ESXi host. You can
        use ``ssh_key`` or ``ssh_key_file``, but not both.

    ssh_key_file
        File containing the public SSH key to be added to the authorized_keys file on
        the ESXi host. You can use ``ssh_key_file`` or ``ssh_key``, but not both.

    service_policy
        The policy to set for the NTP service.

        .. note::

            When setting the service policy to ``off`` or ``on``, you *must* quote the
            setting. If you don't, the yaml parser will set the string to a boolean,
            which will cause trouble checking for stateful changes and will error when
            trying to set the policy on the ESXi host.

    service_restart
        If set to ``True``, the SSH service will be restarted, regardless of its
        previous running state. Default is ``False``.

    certificate_verify
        If set to ``True``, the SSL connection must present a valid certificate.
        Default is ``True``.

    Example:

    .. code-block:: yaml

        configure-host-ssh:
          esxi.ssh_configured:
            - service_running: True
            - ssh_key_file: /etc/salt/ssh_keys/my_key.pub
            - service_policy: 'on'
            - service_restart: True
            - certificate_verify: True

    """
    if certificate_verify is None:
        certificate_verify = True
    ret = {"name": name, "result": False, "changes": {}, "comment": ""}
    esxi_cmd = "esxi.cmd"
    host = __pillar__["proxy"]["host"]
    ssh = "ssh"

    ssh_running = __salt__[esxi_cmd]("get_service_running", service_name=ssh).get(host)
    error = ssh_running.get("Error")
    if error:
        ret["comment"] = f"Error: {error}"
        return ret
    ssh_running = ssh_running.get(ssh)

    # Configure SSH service_running state, if changed.
    if service_running != ssh_running:
        # Only actually run the command if not using test=True
        if not __opts__["test"]:
            # Start SSH if service_running=True
            if service_running is True:
                enable = __salt__[esxi_cmd]("service_start", service_name=ssh).get(host)
                error = enable.get("Error")
                if error:
                    ret["comment"] = f"Error: {error}"
                    return ret
            # Disable SSH if service_running=False
            else:
                disable = __salt__[esxi_cmd]("service_stop", service_name=ssh).get(host)
                error = disable.get("Error")
                if error:
                    ret["comment"] = f"Error: {error}"
                    return ret

        ret["changes"].update(
            {"service_running": {"old": ssh_running, "new": service_running}}
        )

    # If uploading an SSH key or SSH key file, see if there's a current
    # SSH key and compare the current key to the key set in the state.
    current_ssh_key, ssh_key_changed = None, False
    if ssh_key or ssh_key_file:
        current_ssh_key = __salt__[esxi_cmd](
            "get_ssh_key", certificate_verify=certificate_verify
        )
        error = current_ssh_key.get("Error")
        if error:
            ret["comment"] = f"Error: {error}"
            return ret
        current_ssh_key = current_ssh_key.get("key")
        if current_ssh_key:
            clean_current_key = _strip_key(current_ssh_key).split(" ")
            if not ssh_key:
                ssh_key = ""
                # Open ssh key file and read in contents to create one key string
                with salt.utils.files.fopen(ssh_key_file, "r") as key_file:
                    for line in key_file:
                        if line.startswith("#"):
                            # Commented line
                            continue
                        ssh_key = ssh_key + line

            clean_ssh_key = _strip_key(ssh_key).split(" ")
            # Check that the first two list items of clean key lists are equal.
            if (
                clean_current_key[0] != clean_ssh_key[0]
                or clean_current_key[1] != clean_ssh_key[1]
            ):
                ssh_key_changed = True
        else:
            # If current_ssh_key is None, but we're setting a new key with
            # either ssh_key or ssh_key_file, then we need to flag the change.
            ssh_key_changed = True

    # Upload SSH key, if changed.
    if ssh_key_changed:
        if not __opts__["test"]:
            # Upload key
            response = __salt__[esxi_cmd](
                "upload_ssh_key",
                ssh_key=ssh_key,
                ssh_key_file=ssh_key_file,
                certificate_verify=certificate_verify,
            )
            error = response.get("Error")
            if error:
                ret["comment"] = f"Error: {error}"
                return ret
        ret["changes"].update(
            {
                "SSH Key": {
                    "old": current_ssh_key,
                    "new": ssh_key if ssh_key else ssh_key_file,
                }
            }
        )

    # Configure service_policy
    if service_policy:
        current_service_policy = __salt__[esxi_cmd](
            "get_service_policy", service_name=ssh
        ).get(host)
        error = current_service_policy.get("Error")
        if error:
            ret["comment"] = f"Error: {error}"
            return ret
        current_service_policy = current_service_policy.get(ssh)

        if service_policy != current_service_policy:
            # Only run the command if not using test=True
            if not __opts__["test"]:
                response = __salt__[esxi_cmd](
                    "set_service_policy",
                    service_name=ssh,
                    service_policy=service_policy,
                ).get(host)
                error = response.get("Error")
                if error:
                    ret["comment"] = f"Error: {error}"
                    return ret
            ret["changes"].update(
                {
                    "service_policy": {
                        "old": current_service_policy,
                        "new": service_policy,
                    }
                }
            )

    # Restart ssh_service if service_restart=True
    if service_restart:
        # Only run the command if not using test=True
        if not __opts__["test"]:
            response = __salt__[esxi_cmd]("service_restart", service_name=ssh).get(host)
            error = response.get("Error")
            if error:
                ret["comment"] = f"Error: {error}"
                return ret
        ret["changes"].update(
            {"service_restart": {"old": "", "new": "SSH service restarted."}}
        )

    ret["result"] = True
    if ret["changes"] == {}:
        ret["comment"] = "SSH service is already in the desired state."
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "SSH service state will change."

    return ret


@_deprecation_message
def syslog_configured(
    name,
    syslog_configs,
    firewall=True,
    reset_service=True,
    reset_syslog_config=False,
    reset_configs=None,
):
    """
    Ensures the specified syslog configuration parameters. By default,
    this state will reset the syslog service after any new or changed
    parameters are set successfully.

    name
        Name of the state.

    syslog_configs
        Name of parameter to set (corresponds to the command line switch for
        esxcli without the double dashes (--))

        Valid syslog_config values are ``logdir``, ``loghost``, ``logdir-unique``,
        ``default-rotate``, ``default-size``, and ``default-timeout``.

        Each syslog_config option also needs a configuration value to set.
        For example, ``loghost`` requires URLs or IP addresses to use for
        logging. Multiple log servers can be specified by listing them,
        comma-separated, but without spaces before or after commas

        (reference: https://blogs.vmware.com/vsphere/2012/04/configuring-multiple-syslog-servers-for-esxi-5.html)

    firewall
        Enable the firewall rule set for syslog. Defaults to ``True``.

    reset_service
        After a successful parameter set, reset the service. Defaults to ``True``.

    reset_syslog_config
        Resets the syslog service to its default settings. Defaults to ``False``.
        If set to ``True``, default settings defined by the list of syslog configs
        in ``reset_configs`` will be reset before running any other syslog settings.

    reset_configs
        A comma-delimited list of parameters to reset. Only runs if
        ``reset_syslog_config`` is set to ``True``. If ``reset_syslog_config`` is set
        to ``True``, but no syslog configs are listed in ``reset_configs``, then
        ``reset_configs`` will be set to ``all`` by default.

        See ``syslog_configs`` parameter above for a list of valid options.

    Example:

    .. code-block:: yaml

        configure-host-syslog:
          esxi.syslog_configured:
            - syslog_configs:
                loghost: ssl://localhost:5432,tcp://10.1.0.1:1514
                default-timeout: 120
            - firewall: True
            - reset_service: True
            - reset_syslog_config: True
            - reset_configs: loghost,default-timeout
    """
    ret = {"name": name, "result": False, "changes": {}, "comment": ""}
    esxi_cmd = "esxi.cmd"
    host = __pillar__["proxy"]["host"]

    if reset_syslog_config:
        if not reset_configs:
            reset_configs = "all"
        # Only run the command if not using test=True
        if not __opts__["test"]:
            reset = __salt__[esxi_cmd](
                "reset_syslog_config", syslog_config=reset_configs
            ).get(host)
            for key, val in reset.items():
                if isinstance(val, bool):
                    continue
                if not val.get("success"):
                    msg = val.get("message")
                    if not msg:
                        msg = (
                            "There was an error resetting a syslog config '{}'."
                            "Please check debug logs.".format(val)
                        )
                    ret["comment"] = f"Error: {msg}"
                    return ret

        ret["changes"].update(
            {"reset_syslog_config": {"old": "", "new": reset_configs}}
        )

    current_firewall = __salt__[esxi_cmd]("get_firewall_status").get(host)
    error = current_firewall.get("Error")
    if error:
        ret["comment"] = f"Error: {error}"
        return ret

    current_firewall = current_firewall.get("rulesets").get("syslog")
    if current_firewall != firewall:
        # Only run the command if not using test=True
        if not __opts__["test"]:
            enabled = __salt__[esxi_cmd](
                "enable_firewall_ruleset",
                ruleset_enable=firewall,
                ruleset_name="syslog",
            ).get(host)
            if enabled.get("retcode") != 0:
                err = enabled.get("stderr")
                out = enabled.get("stdout")
                ret["comment"] = f"Error: {err if err else out}"
                return ret

        ret["changes"].update({"firewall": {"old": current_firewall, "new": firewall}})

    current_syslog_config = __salt__[esxi_cmd]("get_syslog_config").get(host)
    for key, val in syslog_configs.items():
        # The output of get_syslog_config has different keys than the keys
        # Used to set syslog_config values. We need to look them up first.
        try:
            lookup_key = _lookup_syslog_config(key)
        except KeyError:
            ret["comment"] = f"'{key}' is not a valid config variable."
            return ret

        current_val = current_syslog_config[lookup_key]
        if str(current_val) != str(val):
            # Only run the command if not using test=True
            if not __opts__["test"]:
                response = __salt__[esxi_cmd](
                    "set_syslog_config",
                    syslog_config=key,
                    config_value=val,
                    firewall=firewall,
                    reset_service=reset_service,
                ).get(host)
                success = response.get(key).get("success")
                if not success:
                    msg = response.get(key).get("message")
                    if not msg:
                        msg = (
                            "There was an error setting syslog config '{}'. "
                            "Please check debug logs.".format(key)
                        )
                    ret["comment"] = msg
                    return ret

            if not ret["changes"].get("syslog_config"):
                ret["changes"].update({"syslog_config": {}})
            ret["changes"]["syslog_config"].update(
                {key: {"old": current_val, "new": val}}
            )

    ret["result"] = True
    if ret["changes"] == {}:
        ret["comment"] = "Syslog is already in the desired state."
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "Syslog state will change."

    return ret


@depends(HAS_PYVMOMI)
@depends(HAS_JSONSCHEMA)
@_deprecation_message
def diskgroups_configured(name, diskgroups, erase_disks=False):
    """
    Configures the disk groups to use for vsan.

    This function will do the following:

    1. Check whether or not all disks in the diskgroup spec exist, and raises
       and errors if they do not.

    2. Create diskgroups with the correct disk configurations if diskgroup
       (identified by the cache disk canonical name) doesn't exist

    3. Adds extra capacity disks to the existing diskgroup

    Example:

    .. code:: python

        {
            'cache_scsi_addr': 'vmhba1:C0:T0:L0',
            'capacity_scsi_addrs': [
                'vmhba2:C0:T0:L0',
                'vmhba3:C0:T0:L0',
                'vmhba4:C0:T0:L0',
            ]
        }

    name
        Mandatory state name

    diskgroups
        Disk group representation containing scsi disk addresses.
        Scsi addresses are expected for disks in the diskgroup:

    erase_disks
        Specifies whether to erase all partitions on all disks member of the
        disk group before the disk group is created. Default value is False.
    """
    proxy_details = __salt__["esxi.get_details"]()
    hostname = (
        proxy_details["host"]
        if not proxy_details.get("vcenter")
        else proxy_details["esxi_host"]
    )
    log.info("Running state %s for host '%s'", name, hostname)
    # Variable used to return the result of the invocation
    ret = {"name": name, "result": None, "changes": {}, "comments": None}
    # Signals if errors have been encountered
    errors = False
    # Signals if changes are required
    changes = False
    comments = []
    diskgroup_changes = {}
    si = None
    try:
        log.trace("Validating diskgroups_configured input")
        schema = DiskGroupsDiskScsiAddressSchema.serialize()
        try:
            jsonschema.validate(
                {"diskgroups": diskgroups, "erase_disks": erase_disks}, schema
            )
        except jsonschema.exceptions.ValidationError as exc:
            raise InvalidConfigError(exc)
        si = __salt__["vsphere.get_service_instance_via_proxy"]()
        host_disks = __salt__["vsphere.list_disks"](service_instance=si)
        if not host_disks:
            raise VMwareObjectRetrievalError(
                f"No disks retrieved from host '{hostname}'"
            )
        scsi_addr_to_disk_map = {d["scsi_address"]: d for d in host_disks}
        log.trace("scsi_addr_to_disk_map = %s", scsi_addr_to_disk_map)
        existing_diskgroups = __salt__["vsphere.list_diskgroups"](service_instance=si)
        cache_disk_to_existing_diskgroup_map = {
            dg["cache_disk"]: dg for dg in existing_diskgroups
        }
    except CommandExecutionError as err:
        log.error("Error: %s", err)
        if si:
            __salt__["vsphere.disconnect"](si)
        ret.update(
            {"result": False if not __opts__["test"] else None, "comment": str(err)}
        )
        return ret

    # Iterate through all of the disk groups
    for idx, dg in enumerate(diskgroups):
        # Check for cache disk
        if not dg["cache_scsi_addr"] in scsi_addr_to_disk_map:
            comments.append(
                "No cache disk with scsi address '{}' was found.".format(
                    dg["cache_scsi_addr"]
                )
            )
            log.error(comments[-1])
            errors = True
            continue

        # Check for capacity disks
        cache_disk_id = scsi_addr_to_disk_map[dg["cache_scsi_addr"]]["id"]
        cache_disk_display = "{} (id:{})".format(dg["cache_scsi_addr"], cache_disk_id)
        bad_scsi_addrs = []
        capacity_disk_ids = []
        capacity_disk_displays = []
        for scsi_addr in dg["capacity_scsi_addrs"]:
            if scsi_addr not in scsi_addr_to_disk_map:
                bad_scsi_addrs.append(scsi_addr)
                continue
            capacity_disk_ids.append(scsi_addr_to_disk_map[scsi_addr]["id"])
            capacity_disk_displays.append(f"{scsi_addr} (id:{capacity_disk_ids[-1]})")
        if bad_scsi_addrs:
            comments.append(
                "Error in diskgroup #{}: capacity disks with scsi addresses {} "
                "were not found.".format(
                    idx, ", ".join([f"'{a}'" for a in bad_scsi_addrs])
                )
            )
            log.error(comments[-1])
            errors = True
            continue

        if not cache_disk_to_existing_diskgroup_map.get(cache_disk_id):
            # A new diskgroup needs to be created
            log.trace("erase_disks = %s", erase_disks)
            if erase_disks:
                if __opts__["test"]:
                    comments.append(
                        "State {} will "
                        "erase all disks of disk group #{}; "
                        "cache disk: '{}', "
                        "capacity disk(s): {}."
                        "".format(
                            name,
                            idx,
                            cache_disk_display,
                            ", ".join([f"'{a}'" for a in capacity_disk_displays]),
                        )
                    )
                else:
                    # Erase disk group disks
                    for disk_id in [cache_disk_id] + capacity_disk_ids:
                        __salt__["vsphere.erase_disk_partitions"](
                            disk_id=disk_id, service_instance=si
                        )
                    comments.append(
                        "Erased disks of diskgroup #{}; "
                        "cache disk: '{}', capacity disk(s): "
                        "{}".format(
                            idx,
                            cache_disk_display,
                            ", ".join([f"'{a}'" for a in capacity_disk_displays]),
                        )
                    )
                    log.info(comments[-1])

            if __opts__["test"]:
                comments.append(
                    "State {} will create "
                    "the disk group #{}; cache disk: '{}', "
                    "capacity disk(s): {}.".format(
                        name,
                        idx,
                        cache_disk_display,
                        ", ".join([f"'{a}'" for a in capacity_disk_displays]),
                    )
                )
                log.info(comments[-1])
                changes = True
                continue
            try:
                __salt__["vsphere.create_diskgroup"](
                    cache_disk_id,
                    capacity_disk_ids,
                    safety_checks=False,
                    service_instance=si,
                )
            except VMwareSaltError as err:
                comments.append(f"Error creating disk group #{idx}: {err}.")
                log.error(comments[-1])
                errors = True
                continue

            comments.append(f"Created disk group #'{idx}'.")
            log.info(comments[-1])
            diskgroup_changes[str(idx)] = {
                "new": {"cache": cache_disk_display, "capacity": capacity_disk_displays}
            }
            changes = True
            continue

        # The diskgroup exists; checking the capacity disks
        log.debug(
            "Disk group #%s exists. Checking capacity disks: %s.",
            idx,
            capacity_disk_displays,
        )
        existing_diskgroup = cache_disk_to_existing_diskgroup_map.get(cache_disk_id)
        existing_capacity_disk_displays = [
            "{} (id:{})".format(
                [d["scsi_address"] for d in host_disks if d["id"] == disk_id][0],
                disk_id,
            )
            for disk_id in existing_diskgroup["capacity_disks"]
        ]
        # Populate added disks and removed disks and their displays
        added_capacity_disk_ids = []
        added_capacity_disk_displays = []
        removed_capacity_disk_ids = []
        removed_capacity_disk_displays = []
        for disk_id in capacity_disk_ids:
            if disk_id not in existing_diskgroup["capacity_disks"]:
                disk_scsi_addr = [
                    d["scsi_address"] for d in host_disks if d["id"] == disk_id
                ][0]
                added_capacity_disk_ids.append(disk_id)
                added_capacity_disk_displays.append(f"{disk_scsi_addr} (id:{disk_id})")
        for disk_id in existing_diskgroup["capacity_disks"]:
            if disk_id not in capacity_disk_ids:
                disk_scsi_addr = [
                    d["scsi_address"] for d in host_disks if d["id"] == disk_id
                ][0]
                removed_capacity_disk_ids.append(disk_id)
                removed_capacity_disk_displays.append(
                    f"{disk_scsi_addr} (id:{disk_id})"
                )

        log.debug(
            "Disk group #%s: existing capacity disk ids: %s; added "
            "capacity disk ids: %s; removed capacity disk ids: %s",
            idx,
            existing_capacity_disk_displays,
            added_capacity_disk_displays,
            removed_capacity_disk_displays,
        )

        # TODO revisit this when removing capacity disks is supported
        if removed_capacity_disk_ids:
            comments.append(
                "Error removing capacity disk(s) {} from disk group #{}; "
                "operation is not supported."
                "".format(
                    ", ".join([f"'{id}'" for id in removed_capacity_disk_displays]),
                    idx,
                )
            )
            log.error(comments[-1])
            errors = True
            continue

        if added_capacity_disk_ids:
            # Capacity disks need to be added to disk group

            # Building a string representation of the capacity disks
            # that need to be added
            s = ", ".join([f"'{id}'" for id in added_capacity_disk_displays])
            if __opts__["test"]:
                comments.append(
                    "State {} will add capacity disk(s) {} to disk group #{}.".format(
                        name, s, idx
                    )
                )
                log.info(comments[-1])
                changes = True
                continue
            try:
                __salt__["vsphere.add_capacity_to_diskgroup"](
                    cache_disk_id,
                    added_capacity_disk_ids,
                    safety_checks=False,
                    service_instance=si,
                )
            except VMwareSaltError as err:
                comments.append(
                    "Error adding capacity disk(s) {} to disk group #{}: {}.".format(
                        s, idx, err
                    )
                )
                log.error(comments[-1])
                errors = True
                continue

            com = f"Added capacity disk(s) {s} to disk group #{idx}"
            log.info(com)
            comments.append(com)
            diskgroup_changes[str(idx)] = {
                "new": {
                    "cache": cache_disk_display,
                    "capacity": capacity_disk_displays,
                },
                "old": {
                    "cache": cache_disk_display,
                    "capacity": existing_capacity_disk_displays,
                },
            }
            changes = True
            continue

        # No capacity needs to be added
        s = f"Disk group #{idx} is correctly configured. Nothing to be done."
        log.info(s)
        comments.append(s)
    __salt__["vsphere.disconnect"](si)

    # Build the final return message
    result = (
        True
        if not (changes or errors)
        else (
            None  # no changes/errors
            if __opts__["test"]
            else False if errors else True  # running in test mode
        )
    )  # found errors; defaults to True
    ret.update(
        {"result": result, "comment": "\n".join(comments), "changes": diskgroup_changes}
    )
    return ret


@depends(HAS_PYVMOMI)
@depends(HAS_JSONSCHEMA)
@_deprecation_message
def host_cache_configured(
    name,
    enabled,
    datastore,
    swap_size="100%",
    dedicated_backing_disk=False,
    erase_backing_disk=False,
):
    """
    Configures the host cache used for swapping.

    It will do the following:

    1. Checks if backing disk exists

    2. Creates the VMFS datastore if doesn't exist (datastore partition will be
       created and use the entire disk)

    3. Raises an error if ``dedicated_backing_disk`` is ``True`` and partitions
       already exist on the backing disk

    4. Configures host_cache to use a portion of the datastore for caching
       (either a specific size or a percentage of the datastore)

    Examples

    Percentage swap size (can't be 100%)

    .. code:: python

        {
            'enabled': true,
            'datastore': {
                'backing_disk_scsi_addr': 'vmhba0:C0:T0:L0',
                'vmfs_version': 5,
                'name': 'hostcache'
                }
            'dedicated_backing_disk': false
            'swap_size': '98%',
        }

    Fixed sized swap size

    .. code:: python

        {
            'enabled': true,
            'datastore': {
                'backing_disk_scsi_addr': 'vmhba0:C0:T0:L0',
                'vmfs_version': 5,
                'name': 'hostcache'
                }
            'dedicated_backing_disk': true
            'swap_size': '10GiB',
        }

    name
        Mandatory state name.

    enabled
        Specifies whether the host cache is enabled.

    datastore
        Specifies the host cache datastore.

    swap_size
        Specifies the size of the host cache swap. Can be a percentage or a
        value in GiB. Default value is ``100%``.

    dedicated_backing_disk
        Specifies whether the backing disk is dedicated to the host cache which
        means it must have no other partitions. Default is False

    erase_backing_disk
        Specifies whether to erase all partitions on the backing disk before
        the datastore is created. Default value is False.
    """
    log.trace("enabled = %s", enabled)
    log.trace("datastore = %s", datastore)
    log.trace("swap_size = %s", swap_size)
    log.trace("erase_backing_disk = %s", erase_backing_disk)
    # Variable used to return the result of the invocation
    proxy_details = __salt__["esxi.get_details"]()
    hostname = (
        proxy_details["host"]
        if not proxy_details.get("vcenter")
        else proxy_details["esxi_host"]
    )
    log.trace("hostname = %s", hostname)
    log.info("Running host_cache_swap_configured for host '%s'", hostname)
    ret = {
        "name": hostname,
        "comment": "Default comments",
        "result": None,
        "changes": {},
    }
    result = None if __opts__["test"] else True  # We assume success
    needs_setting = False
    comments = []
    changes = {}
    si = None
    try:
        log.debug("Validating host_cache_configured input")
        schema = HostCacheSchema.serialize()
        try:
            jsonschema.validate(
                {
                    "enabled": enabled,
                    "datastore": datastore,
                    "swap_size": swap_size,
                    "erase_backing_disk": erase_backing_disk,
                },
                schema,
            )
        except jsonschema.exceptions.ValidationError as exc:
            raise InvalidConfigError(exc)
        m = re.match(r"(\d+)(%|GiB)", swap_size)
        swap_size_value = int(m.group(1))
        swap_type = m.group(2)
        log.trace("swap_size_value = %s; swap_type = %s", swap_size_value, swap_type)
        si = __salt__["vsphere.get_service_instance_via_proxy"]()
        host_cache = __salt__["vsphere.get_host_cache"](service_instance=si)

        # Check enabled
        if host_cache["enabled"] != enabled:
            changes.update({"enabled": {"old": host_cache["enabled"], "new": enabled}})
            needs_setting = True

        # Check datastores
        existing_datastores = None
        if host_cache.get("datastore"):
            existing_datastores = __salt__["vsphere.list_datastores_via_proxy"](
                datastore_names=[datastore["name"]], service_instance=si
            )
        # Retrieve backing disks
        existing_disks = __salt__["vsphere.list_disks"](
            scsi_addresses=[datastore["backing_disk_scsi_addr"]], service_instance=si
        )
        if not existing_disks:
            raise VMwareObjectRetrievalError(
                "Disk with scsi address '{}' was not found in host '{}'".format(
                    datastore["backing_disk_scsi_addr"], hostname
                )
            )
        backing_disk = existing_disks[0]
        backing_disk_display = "{} (id:{})".format(
            backing_disk["scsi_address"], backing_disk["id"]
        )
        log.trace("backing_disk = %s", backing_disk_display)

        existing_datastore = None
        if not existing_datastores:
            # Check if disk needs to be erased
            if erase_backing_disk:
                if __opts__["test"]:
                    comments.append(
                        "State {} will erase the backing disk '{}' on host '{}'.".format(
                            name, backing_disk_display, hostname
                        )
                    )
                    log.info(comments[-1])
                else:
                    # Erase disk
                    __salt__["vsphere.erase_disk_partitions"](
                        disk_id=backing_disk["id"], service_instance=si
                    )
                    comments.append(
                        "Erased backing disk '{}' on host '{}'.".format(
                            backing_disk_display, hostname
                        )
                    )
                    log.info(comments[-1])
            # Create the datastore
            if __opts__["test"]:
                comments.append(
                    "State {} will create the datastore '{}', with backing disk "
                    "'{}', on host '{}'.".format(
                        name, datastore["name"], backing_disk_display, hostname
                    )
                )
                log.info(comments[-1])
            else:
                if dedicated_backing_disk:
                    # Check backing disk doesn't already have partitions
                    partitions = __salt__["vsphere.list_disk_partitions"](
                        disk_id=backing_disk["id"], service_instance=si
                    )
                    log.trace("partitions = %s", partitions)
                    # We will ignore the mbr partitions
                    non_mbr_partitions = [p for p in partitions if p["format"] != "mbr"]
                    if len(non_mbr_partitions) > 0:
                        raise VMwareApiError(
                            "Backing disk '{}' has unexpected partitions".format(
                                backing_disk_display
                            )
                        )
                __salt__["vsphere.create_vmfs_datastore"](
                    datastore["name"],
                    existing_disks[0]["id"],
                    datastore["vmfs_version"],
                    service_instance=si,
                )
                comments.append(
                    "Created vmfs datastore '{}', backed by "
                    "disk '{}', on host '{}'.".format(
                        datastore["name"], backing_disk_display, hostname
                    )
                )
                log.info(comments[-1])
                changes.update(
                    {
                        "datastore": {
                            "new": {
                                "name": datastore["name"],
                                "backing_disk": backing_disk_display,
                            }
                        }
                    }
                )
                existing_datastore = __salt__["vsphere.list_datastores_via_proxy"](
                    datastore_names=[datastore["name"]], service_instance=si
                )[0]
            needs_setting = True
        else:
            # Check datastore is backed by the correct disk
            if not existing_datastores[0].get("backing_disk_ids"):
                raise VMwareSaltError(
                    "Datastore '{}' doesn't have a backing disk".format(
                        datastore["name"]
                    )
                )
            if backing_disk["id"] not in existing_datastores[0]["backing_disk_ids"]:

                raise VMwareSaltError(
                    "Datastore '{}' is not backed by the correct disk: "
                    "expected '{}'; got {}".format(
                        datastore["name"],
                        backing_disk["id"],
                        ", ".join(
                            [
                                f"'{disk}'"
                                for disk in existing_datastores[0]["backing_disk_ids"]
                            ]
                        ),
                    )
                )

            comments.append(
                "Datastore '{}' already exists on host '{}' "
                "and is backed by disk '{}'. Nothing to be "
                "done.".format(datastore["name"], hostname, backing_disk_display)
            )
            existing_datastore = existing_datastores[0]
            log.trace("existing_datastore = %s", existing_datastore)
            log.info(comments[-1])

        if existing_datastore:
            # The following comparisons can be done if the existing_datastore
            # is set; it may not be set if running in test mode
            #
            # We support percent, as well as MiB, we will convert the size
            # to MiB, multiples of 1024 (VMware SDK limitation)
            if swap_type == "%":
                # Percentage swap size
                # Convert from bytes to MiB
                raw_size_MiB = (swap_size_value / 100.0) * (
                    existing_datastore["capacity"] / 1024 / 1024
                )
            else:
                raw_size_MiB = swap_size_value * 1024
            log.trace("raw_size = %sMiB", raw_size_MiB)
            swap_size_MiB = int(raw_size_MiB / 1024) * 1024
            log.trace("adjusted swap_size = %sMiB", swap_size_MiB)
            existing_swap_size_MiB = 0
            m = (
                re.match(r"(\d+)MiB", host_cache.get("swap_size"))
                if host_cache.get("swap_size")
                else None
            )
            if m:
                # if swap_size from the host is set and has an expected value
                # we are going to parse it to get the number of MiBs
                existing_swap_size_MiB = int(m.group(1))
            if not existing_swap_size_MiB == swap_size_MiB:
                needs_setting = True
                changes.update(
                    {
                        "swap_size": {
                            "old": f"{existing_swap_size_MiB / 1024}GiB",
                            "new": f"{swap_size_MiB / 1024}GiB",
                        }
                    }
                )

        if needs_setting:
            if __opts__["test"]:
                comments.append(
                    "State {} will configure the host cache on host '{}' to: {}.".format(
                        name,
                        hostname,
                        {
                            "enabled": enabled,
                            "datastore_name": datastore["name"],
                            "swap_size": swap_size,
                        },
                    )
                )
            else:
                if (existing_datastore["capacity"] / 1024.0**2) < swap_size_MiB:

                    raise ArgumentValueError(
                        "Capacity of host cache datastore '{}' ({} MiB) is "
                        "smaller than the required swap size ({} MiB)".format(
                            existing_datastore["name"],
                            existing_datastore["capacity"] / 1024.0**2,
                            swap_size_MiB,
                        )
                    )
                __salt__["vsphere.configure_host_cache"](
                    enabled,
                    datastore["name"],
                    swap_size_MiB=swap_size_MiB,
                    service_instance=si,
                )
                comments.append(f"Host cache configured on host '{hostname}'.")
        else:
            comments.append(
                "Host cache on host '{}' is already correctly "
                "configured. Nothing to be done.".format(hostname)
            )
            result = True
        __salt__["vsphere.disconnect"](si)
        log.info(comments[-1])
        ret.update(
            {"comment": "\n".join(comments), "result": result, "changes": changes}
        )
        return ret
    except CommandExecutionError as err:
        log.error("Error: %s.", err)
        if si:
            __salt__["vsphere.disconnect"](si)
        ret.update(
            {
                "result": False if not __opts__["test"] else None,
                "comment": f"{err}.",
            }
        )
        return ret


def _lookup_syslog_config(config):
    """
    Helper function that looks up syslog_config keys available from
    ``vsphere.get_syslog_config``.
    """
    lookup = {
        "default-timeout": "Default Network Retry Timeout",
        "logdir": "Local Log Output",
        "default-size": "Local Logging Default Rotation Size",
        "logdir-unique": "Log To Unique Subdirectory",
        "default-rotate": "Local Logging Default Rotations",
        "loghost": "Remote Host",
    }

    return lookup.get(config)


def _strip_key(key_string):
    """
    Strips an SSH key string of white space and line endings and returns the new string.

    key_string
        The string to be stripped.
    """
    key_string.strip()
    key_string.replace("\n", "")
    key_string.replace("\r\n", "")
    return key_string
