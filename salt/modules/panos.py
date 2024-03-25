"""
Module to provide Palo Alto compatibility to Salt

:codeauthor: ``Spencer Ervin <spencer_ervin@hotmail.com>``
:maturity:   new
:depends:    none
:platform:   unix

.. versionadded:: 2018.3.0

Configuration
=============

This module accepts connection configuration details either as
parameters, or as configuration settings in pillar as a Salt proxy.
Options passed into opts will be ignored if options are passed into pillar.

.. seealso::
    :py:mod:`Palo Alto Proxy Module <salt.proxy.panos>`

About
=====

This execution module was designed to handle connections to a Palo Alto based
firewall. This module adds support to send connections directly to the device
through the XML API or through a brokered connection to Panorama.

"""

import logging
import time

import salt.proxy.panos
import salt.utils.platform
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

__virtualname__ = "panos"


def __virtual__():
    """
    Will load for the panos proxy minions.
    """
    try:
        if salt.utils.platform.is_proxy() and __opts__["proxy"]["proxytype"] == "panos":
            return __virtualname__
    except KeyError:
        pass

    return (
        False,
        "The panos execution module can only be loaded for panos proxy minions.",
    )


def _get_job_results(query=None):
    """
    Executes a query that requires a job for completion. This function will wait for the job to complete
    and return the results.
    """
    if not query:
        raise CommandExecutionError("Query parameters cannot be empty.")

    response = __proxy__["panos.call"](query)

    # If the response contains a job, we will wait for the results
    if "result" in response and "job" in response["result"]:
        jid = response["result"]["job"]

        while get_job(jid)["result"]["job"]["status"] != "FIN":
            time.sleep(5)

        return get_job(jid)
    else:
        return response


def add_config_lock():
    """
    Prevent other users from changing configuration until the lock is released.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.add_config_lock

    """
    query = {
        "type": "op",
        "cmd": "<request><config-lock><add></add></config-lock></request>",
    }

    return __proxy__["panos.call"](query)


def check_antivirus():
    """
    Get anti-virus information from PaloAlto Networks server

    CLI Example:

    .. code-block:: bash

        salt '*' panos.check_antivirus

    """
    query = {
        "type": "op",
        "cmd": "<request><anti-virus><upgrade><check></check></upgrade></anti-virus></request>",
    }

    return __proxy__["panos.call"](query)


def check_software():
    """
    Get software information from PaloAlto Networks server.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.check_software

    """
    query = {
        "type": "op",
        "cmd": (
            "<request><system><software><check></check></software></system></request>"
        ),
    }

    return __proxy__["panos.call"](query)


def clear_commit_tasks():
    """
    Clear all commit tasks.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.clear_commit_tasks

    """
    query = {
        "type": "op",
        "cmd": "<request><clear-commit-tasks></clear-commit-tasks></request>",
    }

    return __proxy__["panos.call"](query)


def commit():
    """
    Commits the candidate configuration to the running configuration.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.commit

    """
    query = {"type": "commit", "cmd": "<commit></commit>"}

    return _get_job_results(query)


def deactivate_license(key_name=None):
    """
    Deactivates an installed license.
    Required version 7.0.0 or greater.

    key_name(str): The file name of the license key installed.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.deactivate_license key_name=License_File_Name.key

    """

    _required_version = "7.0.0"
    if not __proxy__["panos.is_required_version"](_required_version):
        return (
            False,
            "The panos device requires version {} or greater for this command.".format(
                _required_version
            ),
        )

    if not key_name:
        return False, "You must specify a key_name."
    else:
        query = {
            "type": "op",
            "cmd": (
                "<request><license><deactivate><key><features><member>{}</member></features>"
                "</key></deactivate></license></request>".format(key_name)
            ),
        }

    return __proxy__["panos.call"](query)


def delete_license(key_name=None):
    """
    Remove license keys on disk.

    key_name(str): The file name of the license key to be deleted.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.delete_license key_name=License_File_Name.key

    """

    if not key_name:
        return False, "You must specify a key_name."
    else:
        query = {
            "type": "op",
            "cmd": f"<delete><license><key>{key_name}</key></license></delete>",
        }

    return __proxy__["panos.call"](query)


def download_antivirus():
    """
    Download the most recent anti-virus package.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.download_antivirus

    """
    query = {
        "type": "op",
        "cmd": (
            "<request><anti-virus><upgrade><download>"
            "<latest></latest></download></upgrade></anti-virus></request>"
        ),
    }

    return _get_job_results(query)


def download_software_file(filename=None, synch=False):
    """
    Download software packages by filename.

    Args:
        filename(str): The filename of the PANOS file to download.

        synch (bool): If true then the file will synch to the peer unit.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.download_software_file PanOS_5000-8.0.0
        salt '*' panos.download_software_file PanOS_5000-8.0.0 True

    """
    if not filename:
        raise CommandExecutionError("Filename option must not be none.")

    if not isinstance(synch, bool):
        raise CommandExecutionError("Synch option must be boolean..")

    if synch is True:
        query = {
            "type": "op",
            "cmd": (
                "<request><system><software><download>"
                "<file>{}</file></download></software></system></request>".format(
                    filename
                )
            ),
        }
    else:
        query = {
            "type": "op",
            "cmd": (
                "<request><system><software><download><sync-to-peer>yes</sync-to-peer>"
                "<file>{}</file></download></software></system></request>".format(
                    filename
                )
            ),
        }

    return _get_job_results(query)


def download_software_version(version=None, synch=False):
    """
    Download software packages by version number.

    Args:
        version(str): The version of the PANOS file to download.

        synch (bool): If true then the file will synch to the peer unit.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.download_software_version 8.0.0
        salt '*' panos.download_software_version 8.0.0 True

    """
    if not version:
        raise CommandExecutionError("Version option must not be none.")

    if not isinstance(synch, bool):
        raise CommandExecutionError("Synch option must be boolean..")

    if synch is True:
        query = {
            "type": "op",
            "cmd": (
                "<request><system><software><download>"
                "<version>{}</version></download></software></system></request>".format(
                    version
                )
            ),
        }
    else:
        query = {
            "type": "op",
            "cmd": (
                "<request><system><software><download><sync-to-peer>yes</sync-to-peer>"
                "<version>{}</version></download></software></system></request>".format(
                    version
                )
            ),
        }

    return _get_job_results(query)


def fetch_license(auth_code=None):
    """
    Get new license(s) using from the Palo Alto Network Server.

    auth_code
        The license authorization code.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.fetch_license
        salt '*' panos.fetch_license auth_code=foobar

    """
    if not auth_code:
        query = {
            "type": "op",
            "cmd": "<request><license><fetch></fetch></license></request>",
        }
    else:
        query = {
            "type": "op",
            "cmd": (
                "<request><license><fetch><auth-code>{}</auth-code></fetch></license>"
                "</request>".format(auth_code)
            ),
        }

    return __proxy__["panos.call"](query)


def get_address(address=None, vsys="1"):
    """
    Get the candidate configuration for the specified get_address object. This will not return address objects that are
    marked as pre-defined objects.

    address(str): The name of the address object.

    vsys(str): The string representation of the VSYS ID.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_address myhost
        salt '*' panos.get_address myhost 3

    """
    query = {
        "type": "config",
        "action": "get",
        "xpath": (
            "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys{}']/"
            "address/entry[@name='{}']".format(vsys, address)
        ),
    }

    return __proxy__["panos.call"](query)


def get_address_group(addressgroup=None, vsys="1"):
    """
    Get the candidate configuration for the specified address group. This will not return address groups that are
    marked as pre-defined objects.

    addressgroup(str): The name of the address group.

    vsys(str): The string representation of the VSYS ID.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_address_group foobar
        salt '*' panos.get_address_group foobar 3

    """
    query = {
        "type": "config",
        "action": "get",
        "xpath": (
            "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys{}']/"
            "address-group/entry[@name='{}']".format(vsys, addressgroup)
        ),
    }

    return __proxy__["panos.call"](query)


def get_admins_active():
    """
    Show active administrators.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_admins_active

    """
    query = {"type": "op", "cmd": "<show><admins></admins></show>"}

    return __proxy__["panos.call"](query)


def get_admins_all():
    """
    Show all administrators.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_admins_all

    """
    query = {"type": "op", "cmd": "<show><admins><all></all></admins></show>"}

    return __proxy__["panos.call"](query)


def get_antivirus_info():
    """
    Show information about available anti-virus packages.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_antivirus_info

    """
    query = {
        "type": "op",
        "cmd": "<request><anti-virus><upgrade><info></info></upgrade></anti-virus></request>",
    }

    return __proxy__["panos.call"](query)


def get_arp():
    """
    Show ARP information.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_arp

    """
    query = {"type": "op", "cmd": "<show><arp><entry name = 'all'/></arp></show>"}

    return __proxy__["panos.call"](query)


def get_cli_idle_timeout():
    """
    Show timeout information for this administrative session.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_cli_idle_timeout

    """
    query = {
        "type": "op",
        "cmd": "<show><cli><idle-timeout></idle-timeout></cli></show>",
    }

    return __proxy__["panos.call"](query)


def get_cli_permissions():
    """
    Show cli administrative permissions.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_cli_permissions

    """
    query = {"type": "op", "cmd": "<show><cli><permissions></permissions></cli></show>"}

    return __proxy__["panos.call"](query)


def get_disk_usage():
    """
    Report filesystem disk space usage.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_disk_usage

    """
    query = {
        "type": "op",
        "cmd": "<show><system><disk-space></disk-space></system></show>",
    }

    return __proxy__["panos.call"](query)


def get_dns_server_config():
    """
    Get the DNS server configuration from the candidate configuration.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_dns_server_config

    """
    query = {
        "type": "config",
        "action": "get",
        "xpath": "/config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/dns-setting/servers",
    }

    return __proxy__["panos.call"](query)


def get_domain_config():
    """
    Get the domain name configuration from the candidate configuration.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_domain_config

    """
    query = {
        "type": "config",
        "action": "get",
        "xpath": "/config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/domain",
    }

    return __proxy__["panos.call"](query)


def get_dos_blocks():
    """
    Show the DoS block-ip table.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_dos_blocks

    """
    query = {
        "type": "op",
        "cmd": "<show><dos-block-table><all></all></dos-block-table></show>",
    }

    return __proxy__["panos.call"](query)


def get_fqdn_cache():
    """
    Print FQDNs used in rules and their IPs.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_fqdn_cache

    """
    query = {
        "type": "op",
        "cmd": "<request><system><fqdn><show></show></fqdn></system></request>",
    }

    return __proxy__["panos.call"](query)


def get_ha_config():
    """
    Get the high availability configuration.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_ha_config

    """
    query = {
        "type": "config",
        "action": "get",
        "xpath": "/config/devices/entry[@name='localhost.localdomain']/deviceconfig/high-availability",
    }

    return __proxy__["panos.call"](query)


def get_ha_link():
    """
     Show high-availability link-monitoring state.

     CLI Example:

    .. code-block:: bash

         salt '*' panos.get_ha_link

    """
    query = {
        "type": "op",
        "cmd": "<show><high-availability><link-monitoring></link-monitoring></high-availability></show>",
    }

    return __proxy__["panos.call"](query)


def get_ha_path():
    """
    Show high-availability path-monitoring state.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_ha_path

    """
    query = {
        "type": "op",
        "cmd": "<show><high-availability><path-monitoring></path-monitoring></high-availability></show>",
    }

    return __proxy__["panos.call"](query)


def get_ha_state():
    """
    Show high-availability state information.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_ha_state

    """

    query = {
        "type": "op",
        "cmd": "<show><high-availability><state></state></high-availability></show>",
    }

    return __proxy__["panos.call"](query)


def get_ha_transitions():
    """
    Show high-availability transition statistic information.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_ha_transitions

    """

    query = {
        "type": "op",
        "cmd": "<show><high-availability><transitions></transitions></high-availability></show>",
    }

    return __proxy__["panos.call"](query)


def get_hostname():
    """
    Get the hostname of the device.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_hostname

    """
    query = {
        "type": "config",
        "action": "get",
        "xpath": "/config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/hostname",
    }

    return __proxy__["panos.call"](query)


def get_interface_counters(name="all"):
    """
    Get the counter statistics for interfaces.

    Args:
        name (str): The name of the interface to view. By default, all interface statistics are viewed.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_interface_counters
        salt '*' panos.get_interface_counters ethernet1/1

    """
    query = {
        "type": "op",
        "cmd": f"<show><counter><interface>{name}</interface></counter></show>",
    }

    return __proxy__["panos.call"](query)


def get_interfaces(name="all"):
    """
    Show interface information.

    Args:
        name (str): The name of the interface to view. By default, all interface statistics are viewed.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_interfaces
        salt '*' panos.get_interfaces ethernet1/1

    """
    query = {
        "type": "op",
        "cmd": f"<show><interface>{name}</interface></show>",
    }

    return __proxy__["panos.call"](query)


def get_job(jid=None):
    """
    List all a single job by ID.

    jid
        The ID of the job to retrieve.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_job jid=15

    """
    if not jid:
        raise CommandExecutionError("ID option must not be none.")

    query = {"type": "op", "cmd": f"<show><jobs><id>{jid}</id></jobs></show>"}

    return __proxy__["panos.call"](query)


def get_jobs(state="all"):
    """
    List all jobs on the device.

    state
        The state of the jobs to display. Valid options are all, pending, or processed. Pending jobs are jobs
        that are currently in a running or waiting state. Processed jobs are jobs that have completed
        execution.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_jobs
        salt '*' panos.get_jobs state=pending

    """
    if state.lower() == "all":
        query = {"type": "op", "cmd": "<show><jobs><all></all></jobs></show>"}
    elif state.lower() == "pending":
        query = {"type": "op", "cmd": "<show><jobs><pending></pending></jobs></show>"}
    elif state.lower() == "processed":
        query = {
            "type": "op",
            "cmd": "<show><jobs><processed></processed></jobs></show>",
        }
    else:
        raise CommandExecutionError(
            "The state parameter must be all, pending, or processed."
        )

    return __proxy__["panos.call"](query)


def get_lacp():
    """
    Show LACP state.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_lacp

    """
    query = {
        "type": "op",
        "cmd": "<show><lacp><aggregate-ethernet>all</aggregate-ethernet></lacp></show>",
    }

    return __proxy__["panos.call"](query)


def get_license_info():
    """
    Show information about owned license(s).

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_license_info

    """
    query = {"type": "op", "cmd": "<request><license><info></info></license></request>"}

    return __proxy__["panos.call"](query)


def get_license_tokens():
    """
    Show license token files for manual license deactivation.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_license_tokens

    """
    query = {
        "type": "op",
        "cmd": "<show><license-token-files></license-token-files></show>",
    }

    return __proxy__["panos.call"](query)


def get_lldp_config():
    """
    Show lldp config for interfaces.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_lldp_config

    """
    query = {"type": "op", "cmd": "<show><lldp><config>all</config></lldp></show>"}

    return __proxy__["panos.call"](query)


def get_lldp_counters():
    """
    Show lldp counters for interfaces.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_lldp_counters

    """
    query = {"type": "op", "cmd": "<show><lldp><counters>all</counters></lldp></show>"}

    return __proxy__["panos.call"](query)


def get_lldp_local():
    """
    Show lldp local info for interfaces.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_lldp_local

    """
    query = {"type": "op", "cmd": "<show><lldp><local>all</local></lldp></show>"}

    return __proxy__["panos.call"](query)


def get_lldp_neighbors():
    """
    Show lldp neighbors info for interfaces.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_lldp_neighbors

    """
    query = {
        "type": "op",
        "cmd": "<show><lldp><neighbors>all</neighbors></lldp></show>",
    }

    return __proxy__["panos.call"](query)


def get_local_admins():
    """
    Show all local administrator accounts.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_local_admins

    """
    admin_list = get_users_config()
    response = []

    if "users" not in admin_list["result"]:
        return response

    if isinstance(admin_list["result"]["users"]["entry"], list):
        for entry in admin_list["result"]["users"]["entry"]:
            response.append(entry["name"])
    else:
        response.append(admin_list["result"]["users"]["entry"]["name"])

    return response


def get_logdb_quota():
    """
    Report the logdb quotas.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_logdb_quota

    """
    query = {
        "type": "op",
        "cmd": "<show><system><logdb-quota></logdb-quota></system></show>",
    }

    return __proxy__["panos.call"](query)


def get_master_key():
    """
    Get the master key properties.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_master_key

    """
    query = {
        "type": "op",
        "cmd": "<show><system><masterkey-properties></masterkey-properties></system></show>",
    }

    return __proxy__["panos.call"](query)


def get_ntp_config():
    """
    Get the NTP configuration from the candidate configuration.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_ntp_config

    """
    query = {
        "type": "config",
        "action": "get",
        "xpath": "/config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/ntp-servers",
    }

    return __proxy__["panos.call"](query)


def get_ntp_servers():
    """
    Get list of configured NTP servers.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_ntp_servers

    """
    query = {"type": "op", "cmd": "<show><ntp></ntp></show>"}

    return __proxy__["panos.call"](query)


def get_operational_mode():
    """
    Show device operational mode setting.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_operational_mode

    """
    query = {"type": "op", "cmd": "<show><operational-mode></operational-mode></show>"}

    return __proxy__["panos.call"](query)


def get_panorama_status():
    """
    Show panorama connection status.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_panorama_status

    """
    query = {"type": "op", "cmd": "<show><panorama-status></panorama-status></show>"}

    return __proxy__["panos.call"](query)


def get_permitted_ips():
    """
    Get the IP addresses that are permitted to establish management connections to the device.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_permitted_ips

    """
    query = {
        "type": "config",
        "action": "get",
        "xpath": "/config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/permitted-ip",
    }

    return __proxy__["panos.call"](query)


def get_platform():
    """
    Get the platform model information and limitations.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_platform

    """
    query = {
        "type": "config",
        "action": "get",
        "xpath": "/config/devices/entry[@name='localhost.localdomain']/platform",
    }

    return __proxy__["panos.call"](query)


def get_predefined_application(application=None):
    """
    Get the configuration for the specified pre-defined application object. This will only return pre-defined
    application objects.

    application(str): The name of the pre-defined application object.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_predefined_application saltstack

    """
    query = {
        "type": "config",
        "action": "get",
        "xpath": f"/config/predefined/application/entry[@name='{application}']",
    }

    return __proxy__["panos.call"](query)


def get_security_rule(rulename=None, vsys="1"):
    """
    Get the candidate configuration for the specified security rule.

    rulename(str): The name of the security rule.

    vsys(str): The string representation of the VSYS ID.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_security_rule rule01
        salt '*' panos.get_security_rule rule01 3

    """
    query = {
        "type": "config",
        "action": "get",
        "xpath": (
            "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys{}']/"
            "rulebase/security/rules/entry[@name='{}']".format(vsys, rulename)
        ),
    }

    return __proxy__["panos.call"](query)


def get_service(service=None, vsys="1"):
    """
    Get the candidate configuration for the specified service object. This will not return services that are marked
    as pre-defined objects.

    service(str): The name of the service object.

    vsys(str): The string representation of the VSYS ID.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_service tcp-443
        salt '*' panos.get_service tcp-443 3

    """
    query = {
        "type": "config",
        "action": "get",
        "xpath": (
            "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys{}']/"
            "service/entry[@name='{}']".format(vsys, service)
        ),
    }

    return __proxy__["panos.call"](query)


def get_service_group(servicegroup=None, vsys="1"):
    """
    Get the candidate configuration for the specified service group. This will not return service groups that are
    marked as pre-defined objects.

    servicegroup(str): The name of the service group.

    vsys(str): The string representation of the VSYS ID.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_service_group foobar
        salt '*' panos.get_service_group foobar 3

    """
    query = {
        "type": "config",
        "action": "get",
        "xpath": (
            "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys{}']/"
            "service-group/entry[@name='{}']".format(vsys, servicegroup)
        ),
    }

    return __proxy__["panos.call"](query)


def get_session_info():
    """
    Show device session statistics.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_session_info

    """
    query = {"type": "op", "cmd": "<show><session><info></info></session></show>"}

    return __proxy__["panos.call"](query)


def get_snmp_config():
    """
    Get the SNMP configuration from the device.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_snmp_config

    """
    query = {
        "type": "config",
        "action": "get",
        "xpath": "/config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/snmp-setting",
    }

    return __proxy__["panos.call"](query)


def get_software_info():
    """
    Show information about available software packages.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_software_info

    """
    query = {
        "type": "op",
        "cmd": "<request><system><software><info></info></software></system></request>",
    }

    return __proxy__["panos.call"](query)


def get_system_date_time():
    """
    Get the system date/time.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_system_date_time

    """
    query = {"type": "op", "cmd": "<show><clock></clock></show>"}

    return __proxy__["panos.call"](query)


def get_system_files():
    """
    List important files in the system.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_system_files

    """
    query = {"type": "op", "cmd": "<show><system><files></files></system></show>"}

    return __proxy__["panos.call"](query)


def get_system_info():
    """
    Get the system information.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_system_info

    """
    query = {"type": "op", "cmd": "<show><system><info></info></system></show>"}

    return __proxy__["panos.call"](query)


def get_system_services():
    """
    Show system services.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_system_services

    """
    query = {"type": "op", "cmd": "<show><system><services></services></system></show>"}

    return __proxy__["panos.call"](query)


def get_system_state(mask=None):
    """
    Show the system state variables.

    mask
        Filters by a subtree or a wildcard.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_system_state
        salt '*' panos.get_system_state mask=cfg.ha.config.enabled
        salt '*' panos.get_system_state mask=cfg.ha.*

    """
    if mask:
        query = {
            "type": "op",
            "cmd": (
                "<show><system><state><filter>{}</filter></state></system></show>".format(
                    mask
                )
            ),
        }
    else:
        query = {"type": "op", "cmd": "<show><system><state></state></system></show>"}

    return __proxy__["panos.call"](query)


def get_uncommitted_changes():
    """
    Retrieve a list of all uncommitted changes on the device.
    Requires PANOS version 8.0.0 or greater.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_uncommitted_changes

    """
    _required_version = "8.0.0"
    if not __proxy__["panos.is_required_version"](_required_version):
        return (
            False,
            "The panos device requires version {} or greater for this command.".format(
                _required_version
            ),
        )

    query = {
        "type": "op",
        "cmd": "<show><config><list><changes></changes></list></config></show>",
    }

    return __proxy__["panos.call"](query)


def get_users_config():
    """
    Get the local administrative user account configuration.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_users_config

    """
    query = {"type": "config", "action": "get", "xpath": "/config/mgt-config/users"}

    return __proxy__["panos.call"](query)


def get_vlans():
    """
    Show all VLAN information.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_vlans

    """
    query = {"type": "op", "cmd": "<show><vlan>all</vlan></show>"}

    return __proxy__["panos.call"](query)


def get_xpath(xpath=""):
    """
    Retrieve a specified xpath from the candidate configuration.

    xpath(str): The specified xpath in the candidate configuration.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_xpath /config/shared/service

    """
    query = {"type": "config", "action": "get", "xpath": xpath}

    return __proxy__["panos.call"](query)


def get_zone(zone="", vsys="1"):
    """
    Get the candidate configuration for the specified zone.

    zone(str): The name of the zone.

    vsys(str): The string representation of the VSYS ID.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_zone trust
        salt '*' panos.get_zone trust 2

    """
    query = {
        "type": "config",
        "action": "get",
        "xpath": (
            "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys{}']/"
            "zone/entry[@name='{}']".format(vsys, zone)
        ),
    }

    return __proxy__["panos.call"](query)


def get_zones(vsys="1"):
    """
    Get all the zones in the candidate configuration.

    vsys(str): The string representation of the VSYS ID.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.get_zones
        salt '*' panos.get_zones 2

    """
    query = {
        "type": "config",
        "action": "get",
        "xpath": (
            "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys{}']/"
            "zone".format(vsys)
        ),
    }

    return __proxy__["panos.call"](query)


def install_antivirus(
    version=None,
    latest=False,
    synch=False,
    skip_commit=False,
):
    """
    Install anti-virus packages.

    Args:
        version(str): The version of the PANOS file to install.

        latest(bool): If true, the latest anti-virus file will be installed.
                      The specified version option will be ignored.

        synch(bool): If true, the anti-virus will synch to the peer unit.

        skip_commit(bool): If true, the install will skip committing to the device.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.install_antivirus 8.0.0

    """
    if not version and latest is False:
        raise CommandExecutionError("Version option must not be none.")

    if synch is True:
        s = "yes"
    else:
        s = "no"

    if skip_commit is True:
        c = "yes"
    else:
        c = "no"

    if latest is True:
        query = {
            "type": "op",
            "cmd": (
                "<request><anti-virus><upgrade><install>"
                "<commit>{}</commit><sync-to-peer>{}</sync-to-peer>"
                "<version>latest</version></install></upgrade></anti-virus></request>".format(
                    c, s
                )
            ),
        }
    else:
        query = {
            "type": "op",
            "cmd": (
                "<request><anti-virus><upgrade><install>"
                "<commit>{}</commit><sync-to-peer>{}</sync-to-peer>"
                "<version>{}</version></install></upgrade></anti-virus></request>".format(
                    c, s, version
                )
            ),
        }

    return _get_job_results(query)


def install_license():
    """
    Install the license key(s).

    CLI Example:

    .. code-block:: bash

        salt '*' panos.install_license

    """
    query = {
        "type": "op",
        "cmd": "<request><license><install></install></license></request>",
    }

    return __proxy__["panos.call"](query)


def install_software(version=None):
    """
    Upgrade to a software package by version.

    Args:
        version(str): The version of the PANOS file to install.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.install_license 8.0.0

    """
    if not version:
        raise CommandExecutionError("Version option must not be none.")

    query = {
        "type": "op",
        "cmd": (
            "<request><system><software><install>"
            "<version>{}</version></install></software></system></request>".format(
                version
            )
        ),
    }

    return _get_job_results(query)


def reboot():
    """
    Reboot a running system.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.reboot

    """
    query = {
        "type": "op",
        "cmd": "<request><restart><system></system></restart></request>",
    }

    return __proxy__["panos.call"](query)


def refresh_fqdn_cache(force=False):
    """
    Force refreshes all FQDNs used in rules.

    force
        Forces all fqdn refresh

    CLI Example:

    .. code-block:: bash

        salt '*' panos.refresh_fqdn_cache
        salt '*' panos.refresh_fqdn_cache force=True

    """
    if not isinstance(force, bool):
        raise CommandExecutionError("Force option must be boolean.")

    if force:
        query = {
            "type": "op",
            "cmd": "<request><system><fqdn><refresh><force>yes</force></refresh></fqdn></system></request>",
        }
    else:
        query = {
            "type": "op",
            "cmd": (
                "<request><system><fqdn><refresh></refresh></fqdn></system></request>"
            ),
        }

    return __proxy__["panos.call"](query)


def remove_config_lock():
    """
    Release config lock previously held.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.remove_config_lock

    """
    query = {
        "type": "op",
        "cmd": "<request><config-lock><remove></remove></config-lock></request>",
    }

    return __proxy__["panos.call"](query)


def resolve_address(address=None, vsys=None):
    """
    Resolve address to ip address.
    Required version 7.0.0 or greater.

    address
        Address name you want to resolve.

    vsys
        The vsys name.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.resolve_address foo.bar.com
        salt '*' panos.resolve_address foo.bar.com vsys=2

    """
    _required_version = "7.0.0"
    if not __proxy__["panos.is_required_version"](_required_version):
        return (
            False,
            "The panos device requires version {} or greater for this command.".format(
                _required_version
            ),
        )

    if not address:
        raise CommandExecutionError("FQDN to resolve must be provided as address.")

    if not vsys:
        query = {
            "type": "op",
            "cmd": "<request><resolve><address>{}</address></resolve></request>".format(
                address
            ),
        }
    else:
        query = {
            "type": "op",
            "cmd": (
                "<request><resolve><vsys>{}</vsys><address>{}</address></resolve>"
                "</request>".format(vsys, address)
            ),
        }

    return __proxy__["panos.call"](query)


def save_device_config(filename=None):
    """
    Save device configuration to a named file.

    filename
        The filename to save the configuration to.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.save_device_config foo.xml

    """
    if not filename:
        raise CommandExecutionError("Filename must not be empty.")

    query = {
        "type": "op",
        "cmd": f"<save><config><to>{filename}</to></config></save>",
    }

    return __proxy__["panos.call"](query)


def save_device_state():
    """
    Save files needed to restore device to local disk.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.save_device_state

    """
    query = {"type": "op", "cmd": "<save><device-state></device-state></save>"}

    return __proxy__["panos.call"](query)


def set_authentication_profile(profile=None, deploy=False):
    """
    Set the authentication profile of the Palo Alto proxy minion. A commit will be required before this is processed.

    CLI Example:

    Args:
        profile (str): The name of the authentication profile to set.

        deploy (bool): If true then commit the full candidate configuration, if false only set pending change.

    .. code-block:: bash

        salt '*' panos.set_authentication_profile foo
        salt '*' panos.set_authentication_profile foo deploy=True

    """

    if not profile:
        raise CommandExecutionError("Profile name option must not be none.")

    ret = {}

    query = {
        "type": "config",
        "action": "set",
        "xpath": (
            "/config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/"
            "authentication-profile"
        ),
        "element": "<authentication-profile>{}</authentication-profile>".format(
            profile
        ),
    }

    ret.update(__proxy__["panos.call"](query))

    if deploy is True:
        ret.update(commit())

    return ret


def set_hostname(hostname=None, deploy=False):
    """
    Set the hostname of the Palo Alto proxy minion. A commit will be required before this is processed.

    CLI Example:

    Args:
        hostname (str): The hostname to set

        deploy (bool): If true then commit the full candidate configuration, if false only set pending change.

    .. code-block:: bash

        salt '*' panos.set_hostname newhostname
        salt '*' panos.set_hostname newhostname deploy=True

    """

    if not hostname:
        raise CommandExecutionError("Hostname option must not be none.")

    ret = {}

    query = {
        "type": "config",
        "action": "set",
        "xpath": (
            "/config/devices/entry[@name='localhost.localdomain']/deviceconfig/system"
        ),
        "element": f"<hostname>{hostname}</hostname>",
    }

    ret.update(__proxy__["panos.call"](query))

    if deploy is True:
        ret.update(commit())

    return ret


def set_management_icmp(enabled=True, deploy=False):
    """
    Enables or disables the ICMP management service on the device.

    CLI Example:

    Args:
        enabled (bool): If true the service will be enabled. If false the service will be disabled.

        deploy (bool): If true then commit the full candidate configuration, if false only set pending change.

    .. code-block:: bash

        salt '*' panos.set_management_icmp
        salt '*' panos.set_management_icmp enabled=False deploy=True

    """

    if enabled is True:
        value = "no"
    elif enabled is False:
        value = "yes"
    else:
        raise CommandExecutionError(
            "Invalid option provided for service enabled option."
        )

    ret = {}

    query = {
        "type": "config",
        "action": "set",
        "xpath": "/config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/service",
        "element": f"<disable-icmp>{value}</disable-icmp>",
    }

    ret.update(__proxy__["panos.call"](query))

    if deploy is True:
        ret.update(commit())

    return ret


def set_management_http(enabled=True, deploy=False):
    """
    Enables or disables the HTTP management service on the device.

    CLI Example:

    Args:
        enabled (bool): If true the service will be enabled. If false the service will be disabled.

        deploy (bool): If true then commit the full candidate configuration, if false only set pending change.

    .. code-block:: bash

        salt '*' panos.set_management_http
        salt '*' panos.set_management_http enabled=False deploy=True

    """

    if enabled is True:
        value = "no"
    elif enabled is False:
        value = "yes"
    else:
        raise CommandExecutionError(
            "Invalid option provided for service enabled option."
        )

    ret = {}

    query = {
        "type": "config",
        "action": "set",
        "xpath": "/config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/service",
        "element": f"<disable-http>{value}</disable-http>",
    }

    ret.update(__proxy__["panos.call"](query))

    if deploy is True:
        ret.update(commit())

    return ret


def set_management_https(enabled=True, deploy=False):
    """
    Enables or disables the HTTPS management service on the device.

    CLI Example:

    Args:
        enabled (bool): If true the service will be enabled. If false the service will be disabled.

        deploy (bool): If true then commit the full candidate configuration, if false only set pending change.

    .. code-block:: bash

        salt '*' panos.set_management_https
        salt '*' panos.set_management_https enabled=False deploy=True

    """

    if enabled is True:
        value = "no"
    elif enabled is False:
        value = "yes"
    else:
        raise CommandExecutionError(
            "Invalid option provided for service enabled option."
        )

    ret = {}

    query = {
        "type": "config",
        "action": "set",
        "xpath": "/config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/service",
        "element": f"<disable-https>{value}</disable-https>",
    }

    ret.update(__proxy__["panos.call"](query))

    if deploy is True:
        ret.update(commit())

    return ret


def set_management_ocsp(enabled=True, deploy=False):
    """
    Enables or disables the HTTP OCSP management service on the device.

    CLI Example:

    Args:
        enabled (bool): If true the service will be enabled. If false the service will be disabled.

        deploy (bool): If true then commit the full candidate configuration, if false only set pending change.

    .. code-block:: bash

        salt '*' panos.set_management_ocsp
        salt '*' panos.set_management_ocsp enabled=False deploy=True

    """

    if enabled is True:
        value = "no"
    elif enabled is False:
        value = "yes"
    else:
        raise CommandExecutionError(
            "Invalid option provided for service enabled option."
        )

    ret = {}

    query = {
        "type": "config",
        "action": "set",
        "xpath": "/config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/service",
        "element": f"<disable-http-ocsp>{value}</disable-http-ocsp>",
    }

    ret.update(__proxy__["panos.call"](query))

    if deploy is True:
        ret.update(commit())

    return ret


def set_management_snmp(enabled=True, deploy=False):
    """
    Enables or disables the SNMP management service on the device.

    CLI Example:

    Args:
        enabled (bool): If true the service will be enabled. If false the service will be disabled.

        deploy (bool): If true then commit the full candidate configuration, if false only set pending change.

    .. code-block:: bash

        salt '*' panos.set_management_snmp
        salt '*' panos.set_management_snmp enabled=False deploy=True

    """

    if enabled is True:
        value = "no"
    elif enabled is False:
        value = "yes"
    else:
        raise CommandExecutionError(
            "Invalid option provided for service enabled option."
        )

    ret = {}

    query = {
        "type": "config",
        "action": "set",
        "xpath": "/config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/service",
        "element": f"<disable-snmp>{value}</disable-snmp>",
    }

    ret.update(__proxy__["panos.call"](query))

    if deploy is True:
        ret.update(commit())

    return ret


def set_management_ssh(enabled=True, deploy=False):
    """
    Enables or disables the SSH management service on the device.

    CLI Example:

    Args:
        enabled (bool): If true the service will be enabled. If false the service will be disabled.

        deploy (bool): If true then commit the full candidate configuration, if false only set pending change.

    .. code-block:: bash

        salt '*' panos.set_management_ssh
        salt '*' panos.set_management_ssh enabled=False deploy=True

    """

    if enabled is True:
        value = "no"
    elif enabled is False:
        value = "yes"
    else:
        raise CommandExecutionError(
            "Invalid option provided for service enabled option."
        )

    ret = {}

    query = {
        "type": "config",
        "action": "set",
        "xpath": "/config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/service",
        "element": f"<disable-ssh>{value}</disable-ssh>",
    }

    ret.update(__proxy__["panos.call"](query))

    if deploy is True:
        ret.update(commit())

    return ret


def set_management_telnet(enabled=True, deploy=False):
    """
    Enables or disables the Telnet management service on the device.

    CLI Example:

    Args:
        enabled (bool): If true the service will be enabled. If false the service will be disabled.

        deploy (bool): If true then commit the full candidate configuration, if false only set pending change.

    .. code-block:: bash

        salt '*' panos.set_management_telnet
        salt '*' panos.set_management_telnet enabled=False deploy=True

    """

    if enabled is True:
        value = "no"
    elif enabled is False:
        value = "yes"
    else:
        raise CommandExecutionError(
            "Invalid option provided for service enabled option."
        )

    ret = {}

    query = {
        "type": "config",
        "action": "set",
        "xpath": "/config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/service",
        "element": f"<disable-telnet>{value}</disable-telnet>",
    }

    ret.update(__proxy__["panos.call"](query))

    if deploy is True:
        ret.update(commit())

    return ret


def set_ntp_authentication(
    target=None,
    authentication_type=None,
    key_id=None,
    authentication_key=None,
    algorithm=None,
    deploy=False,
):
    """
    Set the NTP authentication of the Palo Alto proxy minion. A commit will be required before this is processed.

    CLI Example:

    Args:
        target(str): Determines the target of the authentication. Valid options are primary, secondary, or both.

        authentication_type(str): The authentication type to be used. Valid options are symmetric, autokey, and none.

        key_id(int): The NTP authentication key ID.

        authentication_key(str): The authentication key.

        algorithm(str): The algorithm type to be used for a symmetric key. Valid options are md5 and sha1.

        deploy (bool): If true then commit the full candidate configuration, if false only set pending change.

    .. code-block:: bash

        salt '*' ntp.set_authentication target=both authentication_type=autokey
        salt '*' ntp.set_authentication target=primary authentication_type=none
        salt '*' ntp.set_authentication target=both authentication_type=symmetric key_id=15 authentication_key=mykey algorithm=md5
        salt '*' ntp.set_authentication target=both authentication_type=symmetric key_id=15 authentication_key=mykey algorithm=md5 deploy=True

    """
    ret = {}

    if target not in ["primary", "secondary", "both"]:
        raise salt.exceptions.CommandExecutionError(
            "Target option must be primary, secondary, or both."
        )

    if authentication_type not in ["symmetric", "autokey", "none"]:
        raise salt.exceptions.CommandExecutionError(
            "Type option must be symmetric, autokey, or both."
        )

    if authentication_type == "symmetric" and not authentication_key:
        raise salt.exceptions.CommandExecutionError(
            "When using symmetric authentication, authentication_key must be provided."
        )

    if authentication_type == "symmetric" and not key_id:
        raise salt.exceptions.CommandExecutionError(
            "When using symmetric authentication, key_id must be provided."
        )

    if authentication_type == "symmetric" and algorithm not in ["md5", "sha1"]:
        raise salt.exceptions.CommandExecutionError(
            "When using symmetric authentication, algorithm must be md5 or sha1."
        )

    if authentication_type == "symmetric":
        if target == "primary" or target == "both":
            query = {
                "type": "config",
                "action": "set",
                "xpath": (
                    "/config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/ntp-servers/"
                    "primary-ntp-server/authentication-type"
                ),
                "element": (
                    "<symmetric-key><algorithm><{0}><authentication-key>{1}</authentication-key></{0}>"
                    "</algorithm><key-id>{2}</key-id></symmetric-key>".format(
                        algorithm, authentication_key, key_id
                    )
                ),
            }
            ret.update({"primary_server": __proxy__["panos.call"](query)})

        if target == "secondary" or target == "both":
            query = {
                "type": "config",
                "action": "set",
                "xpath": (
                    "/config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/ntp-servers/"
                    "secondary-ntp-server/authentication-type"
                ),
                "element": (
                    "<symmetric-key><algorithm><{0}><authentication-key>{1}</authentication-key></{0}>"
                    "</algorithm><key-id>{2}</key-id></symmetric-key>".format(
                        algorithm, authentication_key, key_id
                    )
                ),
            }
            ret.update({"secondary_server": __proxy__["panos.call"](query)})
    elif authentication_type == "autokey":
        if target == "primary" or target == "both":
            query = {
                "type": "config",
                "action": "set",
                "xpath": (
                    "/config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/ntp-servers/"
                    "primary-ntp-server/authentication-type"
                ),
                "element": "<autokey/>",
            }
            ret.update({"primary_server": __proxy__["panos.call"](query)})

        if target == "secondary" or target == "both":
            query = {
                "type": "config",
                "action": "set",
                "xpath": (
                    "/config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/ntp-servers/"
                    "secondary-ntp-server/authentication-type"
                ),
                "element": "<autokey/>",
            }
            ret.update({"secondary_server": __proxy__["panos.call"](query)})
    elif authentication_type == "none":
        if target == "primary" or target == "both":
            query = {
                "type": "config",
                "action": "set",
                "xpath": (
                    "/config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/ntp-servers/"
                    "primary-ntp-server/authentication-type"
                ),
                "element": "<none/>",
            }
            ret.update({"primary_server": __proxy__["panos.call"](query)})

        if target == "secondary" or target == "both":
            query = {
                "type": "config",
                "action": "set",
                "xpath": (
                    "/config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/ntp-servers/"
                    "secondary-ntp-server/authentication-type"
                ),
                "element": "<none/>",
            }
            ret.update({"secondary_server": __proxy__["panos.call"](query)})

    if deploy is True:
        ret.update(commit())

    return ret


def set_ntp_servers(primary_server=None, secondary_server=None, deploy=False):
    """
    Set the NTP servers of the Palo Alto proxy minion. A commit will be required before this is processed.

    CLI Example:

    Args:
        primary_server(str): The primary NTP server IP address or FQDN.

        secondary_server(str): The secondary NTP server IP address or FQDN.

        deploy (bool): If true then commit the full candidate configuration, if false only set pending change.

    .. code-block:: bash

        salt '*' ntp.set_servers 0.pool.ntp.org 1.pool.ntp.org
        salt '*' ntp.set_servers primary_server=0.pool.ntp.org secondary_server=1.pool.ntp.org
        salt '*' ntp.ser_servers 0.pool.ntp.org 1.pool.ntp.org deploy=True

    """
    ret = {}

    if primary_server:
        query = {
            "type": "config",
            "action": "set",
            "xpath": (
                "/config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/ntp-servers/"
                "primary-ntp-server"
            ),
            "element": "<ntp-server-address>{}</ntp-server-address>".format(
                primary_server
            ),
        }
        ret.update({"primary_server": __proxy__["panos.call"](query)})

    if secondary_server:
        query = {
            "type": "config",
            "action": "set",
            "xpath": (
                "/config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/ntp-servers/"
                "secondary-ntp-server"
            ),
            "element": "<ntp-server-address>{}</ntp-server-address>".format(
                secondary_server
            ),
        }
        ret.update({"secondary_server": __proxy__["panos.call"](query)})

    if deploy is True:
        ret.update(commit())

    return ret


def set_permitted_ip(address=None, deploy=False):
    """
    Add an IPv4 address or network to the permitted IP list.

    CLI Example:

    Args:
        address (str): The IPv4 address or network to allow access to add to the Palo Alto device.

        deploy (bool): If true then commit the full candidate configuration, if false only set pending change.

    .. code-block:: bash

        salt '*' panos.set_permitted_ip 10.0.0.1
        salt '*' panos.set_permitted_ip 10.0.0.0/24
        salt '*' panos.set_permitted_ip 10.0.0.1 deploy=True

    """

    if not address:
        raise CommandExecutionError("Address option must not be empty.")

    ret = {}

    query = {
        "type": "config",
        "action": "set",
        "xpath": "/config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/permitted-ip",
        "element": f"<entry name='{address}'></entry>",
    }

    ret.update(__proxy__["panos.call"](query))

    if deploy is True:
        ret.update(commit())

    return ret


def set_timezone(tz=None, deploy=False):
    """
    Set the timezone of the Palo Alto proxy minion. A commit will be required before this is processed.

    CLI Example:

    Args:
        tz (str): The name of the timezone to set.

        deploy (bool): If true then commit the full candidate configuration, if false only set pending change.

    .. code-block:: bash

        salt '*' panos.set_timezone UTC
        salt '*' panos.set_timezone UTC deploy=True

    """

    if not tz:
        raise CommandExecutionError("Timezone name option must not be none.")

    ret = {}

    query = {
        "type": "config",
        "action": "set",
        "xpath": "/config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/timezone",
        "element": f"<timezone>{tz}</timezone>",
    }

    ret.update(__proxy__["panos.call"](query))

    if deploy is True:
        ret.update(commit())

    return ret


def shutdown():
    """
    Shutdown a running system.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.shutdown

    """
    query = {
        "type": "op",
        "cmd": "<request><shutdown><system></system></shutdown></request>",
    }

    return __proxy__["panos.call"](query)


def test_fib_route(ip=None, vr="vr1"):
    """
    Perform a route lookup within active route table (fib).

    ip (str): The destination IP address to test.

    vr (str): The name of the virtual router to test.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.test_fib_route 4.2.2.2
        salt '*' panos.test_fib_route 4.2.2.2 my-vr

    """

    xpath = "<test><routing><fib-lookup>"

    if ip:
        xpath += f"<ip>{ip}</ip>"

    if vr:
        xpath += f"<virtual-router>{vr}</virtual-router>"

    xpath += "</fib-lookup></routing></test>"

    query = {"type": "op", "cmd": xpath}

    return __proxy__["panos.call"](query)


def test_security_policy(
    sourcezone=None,
    destinationzone=None,
    source=None,
    destination=None,
    protocol=None,
    port=None,
    application=None,
    category=None,
    vsys="1",
    allrules=False,
):
    """
    Checks which security policy as connection will match on the device.

    sourcezone (str): The source zone matched against the connection.

    destinationzone (str): The destination zone matched against the connection.

    source (str): The source address. This must be a single IP address.

    destination (str): The destination address. This must be a single IP address.

    protocol (int): The protocol number for the connection. This is the numerical representation of the protocol.

    port (int): The port number for the connection.

    application (str): The application that should be matched.

    category (str): The category that should be matched.

    vsys (int): The numerical representation of the VSYS ID.

    allrules (bool): Show all potential match rules until first allow rule.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.test_security_policy sourcezone=trust destinationzone=untrust protocol=6 port=22
        salt '*' panos.test_security_policy sourcezone=trust destinationzone=untrust protocol=6 port=22 vsys=2

    """

    xpath = "<test><security-policy-match>"

    if sourcezone:
        xpath += f"<from>{sourcezone}</from>"

    if destinationzone:
        xpath += f"<to>{destinationzone}</to>"

    if source:
        xpath += f"<source>{source}</source>"

    if destination:
        xpath += f"<destination>{destination}</destination>"

    if protocol:
        xpath += f"<protocol>{protocol}</protocol>"

    if port:
        xpath += f"<destination-port>{port}</destination-port>"

    if application:
        xpath += f"<application>{application}</application>"

    if category:
        xpath += f"<category>{category}</category>"

    if allrules:
        xpath += "<show-all>yes</show-all>"

    xpath += "</security-policy-match></test>"

    query = {"type": "op", "vsys": f"vsys{vsys}", "cmd": xpath}

    return __proxy__["panos.call"](query)


def unlock_admin(username=None):
    """
    Unlocks a locked administrator account.

    username
        Username of the administrator.

    CLI Example:

    .. code-block:: bash

        salt '*' panos.unlock_admin username=bob

    """
    if not username:
        raise CommandExecutionError("Username option must not be none.")

    query = {
        "type": "op",
        "cmd": (
            "<set><management-server><unlock><admin>{}</admin></unlock></management-server>"
            "</set>".format(username)
        ),
    }

    return __proxy__["panos.call"](query)
