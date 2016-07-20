# -*- coding: utf-8 -*-
'''
Manage VMware vCenter servers and ESXi hosts.

.. versionadded:: 2015.8.4

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

The 5.5.0.2014.1.1 is a known stable version that this original vSphere Execution
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

    Be aware that some functionality in this execution module may depend on the
    type of license attached to a vCenter Server or ESXi host(s).

    For example, certain services are only available to manipulate service state
    or policies with a VMware vSphere Enterprise or Enterprise Plus license, while
    others are available with a Standard license. The ``ntpd`` service is restricted
    to an Enterprise Plus license, while ``ssh`` is available via the Standard
    license.

    Please see the `vSphere Comparison`_ page for more information.

.. _vSphere Comparison: https://www.vmware.com/products/vsphere/compare


About
=====

This execution module was designed to be able to handle connections both to a
vCenter Server, as well as to an ESXi host. It utilizes the pyVmomi Python
library and the ESXCLI package to run remote execution functions against either
the defined vCenter server or the ESXi host.

Whether or not the function runs against a vCenter Server or an ESXi host depends
entirely upon the arguments passed into the function. Each function requires a
``host`` location, ``username``, and ``password``. If the credentials provided
apply to a vCenter Server, then the function will be run against the vCenter
Server. For example, when listing hosts using vCenter credentials, you'll get a
list of hosts associated with that vCenter Server:

.. code-block:: bash

    # salt my-minion vsphere.list_hosts <vcenter-ip> <vcenter-user> <vcenter-password>
    my-minion:
    - esxi-1.example.com
    - esxi-2.example.com

However, some functions should be used against ESXi hosts, not vCenter Servers.
Functionality such as getting a host's coredump network configuration should be
performed against a host and not a vCenter server. If the authentication information
you're using is against a vCenter server and not an ESXi host, you can provide the
host name that is associated with the vCenter server in the command, as a list, using
the ``host_names`` or ``esxi_host`` kwarg. For example:

.. code-block:: bash

    # salt my-minion vsphere.get_coredump_network_config <vcenter-ip> <vcenter-user> \
        <vcenter-password> esxi_hosts='[esxi-1.example.com, esxi-2.example.com]'
    my-minion:
    ----------
        esxi-1.example.com:
            ----------
            Coredump Config:
                ----------
                enabled:
                    False
        esxi-2.example.com:
            ----------
            Coredump Config:
                ----------
                enabled:
                    True
                host_vnic:
                    vmk0
                ip:
                    coredump-location.example.com
                port:
                    6500

You can also use these functions against an ESXi host directly by establishing a
connection to an ESXi host using the host's location, username, and password. If ESXi
connection credentials are used instead of vCenter credentials, the ``host_names`` and
``esxi_hosts`` arguments are not needed.

.. code-block:: bash

    # salt my-minion vsphere.get_coredump_network_config esxi-1.example.com root <host-password>
    local:
    ----------
        10.4.28.150:
            ----------
            Coredump Config:
                ----------
                enabled:
                    True
                host_vnic:
                    vmk0
                ip:
                    coredump-location.example.com
                port:
                    6500
'''

# Import Python Libs
from __future__ import absolute_import
import datetime
import logging

# Import Salt Libs
import salt.ext.six as six
import salt.utils
import salt.utils.vmware
import salt.utils.http
from salt.exceptions import CommandExecutionError

# Import Third Party Libs
try:
    from pyVmomi import vim, vmodl
    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False

log = logging.getLogger(__name__)

__virtualname__ = 'vsphere'
__proxyenabled__ = ['esxi']


def __virtual__():
    if not HAS_PYVMOMI:
        return False, 'Missing dependency: The vSphere module requires the pyVmomi Python module.'

    esx_cli = salt.utils.which('esxcli')
    if not esx_cli:
        return False, 'Missing dependency: The vSphere module requires ESXCLI.'

    return __virtualname__


def esxcli_cmd(host, username, password, cmd_str, protocol=None, port=None, esxi_hosts=None):
    '''
    Run an ESXCLI command directly on the host or list of hosts.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    cmd_str
        The ESXCLI command to run. Note: This should not include the ``-s``, ``-u``,
        ``-p``, ``-h``, ``--protocol``, or ``--portnumber`` arguments that are
         frequently passed when using a bare ESXCLI command from the command line.
         Those arguments are handled by this function via the other args and kwargs.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    esxi_hosts
        If ``host`` is a vCenter host, then use esxi_hosts to execute this function
        on a list of one or more ESXi machines.

    CLI Example:

    .. code-block:: bash

        # Used for ESXi host connection information
        salt '*' vsphere.esxcli_cmd my.esxi.host root bad-password \
            'system coredump network get'

        # Used for connecting to a vCenter Server
        salt '*' vsphere.esxcli_cmd my.vcenter.location root bad-password \
            'system coredump network get' esxi_hosts='[esxi-1.host.com, esxi-2.host.com]'
    '''
    ret = {}
    if esxi_hosts:
        if not isinstance(esxi_hosts, list):
            raise CommandExecutionError('\'esxi_hosts\' must be a list.')

        for esxi_host in esxi_hosts:
            response = salt.utils.vmware.esxcli(host, username, password, cmd_str,
                                                protocol=protocol, port=port,
                                                esxi_host=esxi_host)
            if response['retcode'] != 0:
                ret.update({esxi_host: {'Error': response.get('stdout')}})
            else:
                ret.update({esxi_host: response})
    else:
        # Handles a single host or a vCenter connection when no esxi_hosts are provided.
        response = salt.utils.vmware.esxcli(host, username, password, cmd_str,
                                            protocol=protocol, port=port)
        if response['retcode'] != 0:
            ret.update({host: {'Error': response.get('stdout')}})
        else:
            ret.update({host: response})

    return ret


def get_coredump_network_config(host, username, password, protocol=None, port=None, esxi_hosts=None):
    '''
    Retrieve information on ESXi or vCenter network dump collection and
    format it into a dictionary.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    esxi_hosts
        If ``host`` is a vCenter host, then use esxi_hosts to execute this function
        on a list of one or more ESXi machines.

    :return: A dictionary with the network configuration, or, if getting
             the network config failed, a an error message retrieved from the
             standard cmd.run_all dictionary, per host.

    CLI Example:

    .. code-block:: bash

        # Used for ESXi host connection information
        salt '*' vsphere.get_coredump_network_config my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.get_coredump_network_config my.vcenter.location root bad-password \
            esxi_hosts='[esxi-1.host.com, esxi-2.host.com]'

    '''
    cmd = 'system coredump network get'
    ret = {}
    if esxi_hosts:
        if not isinstance(esxi_hosts, list):
            raise CommandExecutionError('\'esxi_hosts\' must be a list.')

        for esxi_host in esxi_hosts:
            response = salt.utils.vmware.esxcli(host, username, password, cmd,
                                                protocol=protocol, port=port,
                                                esxi_host=esxi_host)
            if response['retcode'] != 0:
                ret.update({esxi_host: {'Error': response.get('stdout')}})
            else:
                # format the response stdout into something useful
                ret.update({esxi_host: {'Coredump Config': _format_coredump_stdout(response)}})
    else:
        # Handles a single host or a vCenter connection when no esxi_hosts are provided.
        response = salt.utils.vmware.esxcli(host, username, password, cmd,
                                            protocol=protocol, port=port)
        if response['retcode'] != 0:
            ret.update({host: {'Error': response.get('stdout')}})
        else:
            # format the response stdout into something useful
            stdout = _format_coredump_stdout(response)
            ret.update({host: {'Coredump Config': stdout}})

    return ret


def coredump_network_enable(host, username, password, enabled, protocol=None, port=None, esxi_hosts=None):
    '''
    Enable or disable ESXi core dump collection. Returns ``True`` if coredump is enabled
    and returns ``False`` if core dump is not enabled. If there was an error, the error
    will be the value printed in the ``Error`` key dictionary for the given host.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    enabled
        Python True or False to enable or disable coredumps.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    esxi_hosts
        If ``host`` is a vCenter host, then use esxi_hosts to execute this function
        on a list of one or more ESXi machines.

    CLI Example:

    .. code-block:: bash

        # Used for ESXi host connection information
        salt '*' vsphere.coredump_network_enable my.esxi.host root bad-password True

        # Used for connecting to a vCenter Server
        salt '*' vsphere.coredump_network_enable my.vcenter.location root bad-password True \
            esxi_hosts='[esxi-1.host.com, esxi-2.host.com]'
    '''
    if enabled:
        enable_it = 1
    else:
        enable_it = 0
    cmd = 'system coredump network set -e {0}'.format(enable_it)

    ret = {}
    if esxi_hosts:
        if not isinstance(esxi_hosts, list):
            raise CommandExecutionError('\'esxi_hosts\' must be a list.')

        for esxi_host in esxi_hosts:
            response = salt.utils.vmware.esxcli(host, username, password, cmd,
                                                protocol=protocol, port=port,
                                                esxi_host=esxi_host)
            if response['retcode'] != 0:
                ret.update({esxi_host: {'Error': response.get('stdout')}})
            else:
                ret.update({esxi_host: {'Coredump Enabled': enabled}})

    else:
        # Handles a single host or a vCenter connection when no esxi_hosts are provided.
        response = salt.utils.vmware.esxcli(host, username, password, cmd,
                                            protocol=protocol, port=port)
        if response['retcode'] != 0:
            ret.update({host: {'Error': response.get('stdout')}})
        else:
            ret.update({host: {'Coredump Enabled': enabled}})

    return ret


def set_coredump_network_config(host,
                                username,
                                password,
                                dump_ip,
                                protocol=None,
                                port=None,
                                host_vnic='vmk0',
                                dump_port=6500,
                                esxi_hosts=None):
    '''

    Set the network parameters for a network coredump collection.
    Note that ESXi requires that the dumps first be enabled (see
    `coredump_network_enable`) before these parameters may be set.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    dump_ip
        IP address of host that will accept the dump.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    esxi_hosts
        If ``host`` is a vCenter host, then use esxi_hosts to execute this function
        on a list of one or more ESXi machines.

    host_vnic
        Host VNic port through which to communicate. Defaults to ``vmk0``.

    dump_port
        TCP port to use for the dump, defaults to ``6500``.

    :return: A standard cmd.run_all dictionary with a `success` key added, per host.
             `success` will be True if the set succeeded, False otherwise.

    CLI Example:

    .. code-block:: bash

        # Used for ESXi host connection information
        salt '*' vsphere.set_coredump_network_config my.esxi.host root bad-password 'dump_ip.host.com'

        # Used for connecting to a vCenter Server
        salt '*' vsphere.set_coredump_network_config my.vcenter.location root bad-password 'dump_ip.host.com' \
            esxi_hosts='[esxi-1.host.com, esxi-2.host.com]'
    '''
    cmd = 'system coredump network set -v {0} -i {1} -o {2}'.format(host_vnic,
                                                                    dump_ip,
                                                                    dump_port)
    ret = {}
    if esxi_hosts:
        if not isinstance(esxi_hosts, list):
            raise CommandExecutionError('\'esxi_hosts\' must be a list.')

        for esxi_host in esxi_hosts:
            response = salt.utils.vmware.esxcli(host, username, password, cmd,
                                                protocol=protocol, port=port,
                                                esxi_host=esxi_host)
            if response['retcode'] != 0:
                response['success'] = False
            else:
                response['success'] = True

            # Update the cmd.run_all dictionary for each particular host.
            ret.update({esxi_host: response})
    else:
        # Handles a single host or a vCenter connection when no esxi_hosts are provided.
        response = salt.utils.vmware.esxcli(host, username, password, cmd,
                                            protocol=protocol, port=port)
        if response['retcode'] != 0:
            response['success'] = False
        else:
            response['success'] = True
        ret.update({host: response})

    return ret


def get_firewall_status(host, username, password, protocol=None, port=None, esxi_hosts=None):
    '''
    Show status of all firewall rule sets.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    esxi_hosts
        If ``host`` is a vCenter host, then use esxi_hosts to execute this function
        on a list of one or more ESXi machines.

    :return: Nested dictionary with two toplevel keys ``rulesets`` and ``success``
             ``success`` will be True or False depending on query success
             ``rulesets`` will list the rulesets and their statuses if ``success``
             was true, per host.

    CLI Example:

    .. code-block:: bash

        # Used for ESXi host connection information
        salt '*' vsphere.get_firewall_status my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.get_firewall_status my.vcenter.location root bad-password \
            esxi_hosts='[esxi-1.host.com, esxi-2.host.com]'
    '''
    cmd = 'network firewall ruleset list'

    ret = {}
    if esxi_hosts:
        if not isinstance(esxi_hosts, list):
            raise CommandExecutionError('\'esxi_hosts\' must be a list.')

        for esxi_host in esxi_hosts:
            response = salt.utils.vmware.esxcli(host, username, password, cmd,
                                                protocol=protocol, port=port,
                                                esxi_host=esxi_host)
            if response['retcode'] != 0:
                ret.update({esxi_host: {'Error': response['stdout'],
                                        'success': False,
                                        'rulesets': None}})
            else:
                # format the response stdout into something useful
                ret.update({esxi_host: _format_firewall_stdout(response)})
    else:
        # Handles a single host or a vCenter connection when no esxi_hosts are provided.
        response = salt.utils.vmware.esxcli(host, username, password, cmd,
                                            protocol=protocol, port=port)
        if response['retcode'] != 0:
            ret.update({host: {'Error': response['stdout'],
                               'success': False,
                               'rulesets': None}})
        else:
            # format the response stdout into something useful
            ret.update({host: _format_firewall_stdout(response)})

    return ret


def enable_firewall_ruleset(host,
                            username,
                            password,
                            ruleset_enable,
                            ruleset_name,
                            protocol=None,
                            port=None,
                            esxi_hosts=None):
    '''
    Enable or disable an ESXi firewall rule set.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    ruleset_enable
        True to enable the ruleset, false to disable.

    ruleset_name
        Name of ruleset to target.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    esxi_hosts
        If ``host`` is a vCenter host, then use esxi_hosts to execute this function
        on a list of one or more ESXi machines.

    :return: A standard cmd.run_all dictionary, per host.

    CLI Example:

    .. code-block:: bash

        # Used for ESXi host connection information
        salt '*' vsphere.enable_firewall_ruleset my.esxi.host root bad-password True 'syslog'

        # Used for connecting to a vCenter Server
        salt '*' vsphere.enable_firewall_ruleset my.vcenter.location root bad-password True 'syslog' \
            esxi_hosts='[esxi-1.host.com, esxi-2.host.com]'
    '''
    cmd = 'network firewall ruleset set --enabled {0} --ruleset-id={1}'.format(
        ruleset_enable, ruleset_name
    )

    ret = {}
    if esxi_hosts:
        if not isinstance(esxi_hosts, list):
            raise CommandExecutionError('\'esxi_hosts\' must be a list.')

        for esxi_host in esxi_hosts:
            response = salt.utils.vmware.esxcli(host, username, password, cmd,
                                                protocol=protocol, port=port,
                                                esxi_host=esxi_host)
            ret.update({esxi_host: response})
    else:
        # Handles a single host or a vCenter connection when no esxi_hosts are provided.
        response = salt.utils.vmware.esxcli(host, username, password, cmd,
                                            protocol=protocol, port=port)
        ret.update({host: response})

    return ret


def syslog_service_reload(host, username, password, protocol=None, port=None, esxi_hosts=None):
    '''
    Reload the syslog service so it will pick up any changes.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    esxi_hosts
        If ``host`` is a vCenter host, then use esxi_hosts to execute this function
        on a list of one or more ESXi machines.

    :return: A standard cmd.run_all dictionary.  This dictionary will at least
             have a `retcode` key.  If `retcode` is 0 the command was successful.

    CLI Example:

    .. code-block:: bash

        # Used for ESXi host connection information
        salt '*' vsphere.syslog_service_reload my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.syslog_service_reload my.vcenter.location root bad-password \
            esxi_hosts='[esxi-1.host.com, esxi-2.host.com]'
    '''
    cmd = 'system syslog reload'

    ret = {}
    if esxi_hosts:
        if not isinstance(esxi_hosts, list):
            raise CommandExecutionError('\'esxi_hosts\' must be a list.')

        for esxi_host in esxi_hosts:
            response = salt.utils.vmware.esxcli(host, username, password, cmd,
                                                protocol=protocol, port=port,
                                                esxi_host=esxi_host)
            ret.update({esxi_host: response})
    else:
        # Handles a single host or a vCenter connection when no esxi_hosts are provided.
        response = salt.utils.vmware.esxcli(host, username, password, cmd,
                                            protocol=protocol, port=port)
        ret.update({host: response})

    return ret


def set_syslog_config(host,
                      username,
                      password,
                      syslog_config,
                      config_value,
                      protocol=None,
                      port=None,
                      firewall=True,
                      reset_service=True,
                      esxi_hosts=None):
    '''
    Set the specified syslog configuration parameter. By default, this function will
    reset the syslog service after the configuration is set.

    host
        ESXi or vCenter host to connect to.

    username
        User to connect as, usually root.

    password
        Password to connect with.

    syslog_config
        Name of parameter to set (corresponds to the command line switch for
        esxcli without the double dashes (--))

        Valid syslog_config values are ``logdir``, ``loghost``, ``default-rotate`,
        ``default-size``, ``default-timeout``, and ``logdir-unique``.

    config_value
        Value for the above parameter. For ``loghost``, URLs or IP addresses to
        use for logging. Multiple log servers can be specified by listing them,
        comma-separated, but without spaces before or after commas.

        (reference: https://blogs.vmware.com/vsphere/2012/04/configuring-multiple-syslog-servers-for-esxi-5.html)

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    firewall
        Enable the firewall rule set for syslog. Defaults to ``True``.

    reset_service
        After a successful parameter set, reset the service. Defaults to ``True``.

    esxi_hosts
        If ``host`` is a vCenter host, then use esxi_hosts to execute this function
        on a list of one or more ESXi machines.

    :return: Dictionary with a top-level key of 'success' which indicates
             if all the parameters were reset, and individual keys
             for each parameter indicating which succeeded or failed, per host.

    CLI Example:

    .. code-block:: bash

        # Used for ESXi host connection information
        salt '*' vsphere.set_syslog_config my.esxi.host root bad-password \
            loghost ssl://localhost:5432,tcp://10.1.0.1:1514

        # Used for connecting to a vCenter Server
        salt '*' vsphere.set_syslog_config my.vcenter.location root bad-password \
            loghost ssl://localhost:5432,tcp://10.1.0.1:1514 \
            esxi_hosts='[esxi-1.host.com, esxi-2.host.com]'

    '''
    ret = {}

    # First, enable the syslog firewall ruleset, for each host, if needed.
    if firewall and syslog_config == 'loghost':
        if esxi_hosts:
            if not isinstance(esxi_hosts, list):
                raise CommandExecutionError('\'esxi_hosts\' must be a list.')

            for esxi_host in esxi_hosts:
                response = enable_firewall_ruleset(host, username, password,
                                                   ruleset_enable=True, ruleset_name='syslog',
                                                   protocol=protocol, port=port,
                                                   esxi_hosts=[esxi_host]).get(esxi_host)
                if response['retcode'] != 0:
                    ret.update({esxi_host: {'enable_firewall': {'message': response['stdout'],
                                                                'success': False}}})
                else:
                    ret.update({esxi_host: {'enable_firewall': {'success': True}}})
        else:
            # Handles a single host or a vCenter connection when no esxi_hosts are provided.
            response = enable_firewall_ruleset(host, username, password,
                                               ruleset_enable=True, ruleset_name='syslog',
                                               protocol=protocol, port=port).get(host)
            if response['retcode'] != 0:
                ret.update({host: {'enable_firewall': {'message': response['stdout'],
                                                       'success': False}}})
            else:
                ret.update({host: {'enable_firewall': {'success': True}}})

    # Set the config value on each esxi_host, if provided.
    if esxi_hosts:
        if not isinstance(esxi_hosts, list):
            raise CommandExecutionError('\'esxi_hosts\' must be a list.')

        for esxi_host in esxi_hosts:
            response = _set_syslog_config_helper(host, username, password, syslog_config,
                                                 config_value, protocol=protocol, port=port,
                                                 reset_service=reset_service, esxi_host=esxi_host)
            # Ensure we don't overwrite any dictionary data already set
            # By updating the esxi_host directly.
            if ret.get(esxi_host) is None:
                ret.update({esxi_host: {}})
            ret[esxi_host].update(response)

    else:
        # Handles a single host or a vCenter connection when no esxi_hosts are provided.
        response = _set_syslog_config_helper(host, username, password, syslog_config,
                                             config_value, protocol=protocol, port=port,
                                             reset_service=reset_service)
        # Ensure we don't overwrite any dictionary data already set
        # By updating the host directly.
        if ret.get(host) is None:
            ret.update({host: {}})
        ret[host].update(response)

    return ret


def get_syslog_config(host, username, password, protocol=None, port=None, esxi_hosts=None):
    '''
    Retrieve the syslog configuration.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    esxi_hosts
        If ``host`` is a vCenter host, then use esxi_hosts to execute this function
        on a list of one or more ESXi machines.

    :return: Dictionary with keys and values corresponding to the
             syslog configuration, per host.

    CLI Example:

    .. code-block:: bash

        # Used for ESXi host connection information
        salt '*' vsphere.get_syslog_config my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.get_syslog_config my.vcenter.location root bad-password \
            esxi_hosts='[esxi-1.host.com, esxi-2.host.com]'
    '''
    cmd = 'system syslog config get'

    ret = {}
    if esxi_hosts:
        if not isinstance(esxi_hosts, list):
            raise CommandExecutionError('\'esxi_hosts\' must be a list.')

        for esxi_host in esxi_hosts:
            response = salt.utils.vmware.esxcli(host, username, password, cmd,
                                                protocol=protocol, port=port,
                                                esxi_host=esxi_host)
            # format the response stdout into something useful
            ret.update({esxi_host: _format_syslog_config(response)})
    else:
        # Handles a single host or a vCenter connection when no esxi_hosts are provided.
        response = salt.utils.vmware.esxcli(host, username, password, cmd,
                                            protocol=protocol, port=port)
        # format the response stdout into something useful
        ret.update({host: _format_syslog_config(response)})

    return ret


def reset_syslog_config(host,
                        username,
                        password,
                        protocol=None,
                        port=None,
                        syslog_config=None,
                        esxi_hosts=None):
    '''
    Reset the syslog service to its default settings.

    Valid syslog_config values are ``logdir``, ``loghost``, ``logdir-unique``,
    ``default-rotate``, ``default-size``, ``default-timeout``,
    or ``all`` for all of these.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    syslog_config
        List of parameters to reset, provided as a comma-delimited string, or 'all' to
        reset all syslog configuration parameters. Required.

    esxi_hosts
        If ``host`` is a vCenter host, then use esxi_hosts to execute this function
        on a list of one or more ESXi machines.

    :return: Dictionary with a top-level key of 'success' which indicates
             if all the parameters were reset, and individual keys
             for each parameter indicating which succeeded or failed, per host.

    CLI Example:

    ``syslog_config`` can be passed as a quoted, comma-separated string, e.g.

    .. code-block:: bash

        # Used for ESXi host connection information
        salt '*' vsphere.reset_syslog_config my.esxi.host root bad-password \
            syslog_config='logdir,loghost'

        # Used for connecting to a vCenter Server
        salt '*' vsphere.reset_syslog_config my.vcenter.location root bad-password \
            syslog_config='logdir,loghost' esxi_hosts='[esxi-1.host.com, esxi-2.host.com]'
    '''
    if not syslog_config:
        raise CommandExecutionError('The \'reset_syslog_config\' function requires a '
                                    '\'syslog_config\' setting.')

    valid_resets = ['logdir', 'loghost', 'default-rotate',
                    'default-size', 'default-timeout', 'logdir-unique']
    cmd = 'system syslog config set --reset='
    if ',' in syslog_config:
        resets = [ind_reset.strip() for ind_reset in syslog_config.split(',')]
    elif syslog_config == 'all':
        resets = valid_resets
    else:
        resets = [syslog_config]

    ret = {}
    if esxi_hosts:
        if not isinstance(esxi_hosts, list):
            raise CommandExecutionError('\'esxi_hosts\' must be a list.')

        for esxi_host in esxi_hosts:
            response_dict = _reset_syslog_config_params(host, username, password,
                                                        cmd, resets, valid_resets,
                                                        protocol=protocol, port=port,
                                                        esxi_host=esxi_host)
            ret.update({esxi_host: response_dict})
    else:
        # Handles a single host or a vCenter connection when no esxi_hosts are provided.
        response_dict = _reset_syslog_config_params(host, username, password,
                                                    cmd, resets, valid_resets,
                                                    protocol=protocol, port=port)
        ret.update({host: response_dict})

    return ret


def upload_ssh_key(host, username, password, ssh_key=None, ssh_key_file=None,
                   protocol=None, port=None, certificate_verify=False):
    '''
    Upload an ssh key for root to an ESXi host via http PUT.
    This function only works for ESXi, not vCenter.
    Only one ssh key can be uploaded for root.  Uploading a second key will
    replace any existing key.

    :param host: The location of the ESXi Host
    :param username: Username to connect as
    :param password: Password for the ESXi web endpoint
    :param ssh_key: Public SSH key, will be added to authorized_keys on ESXi
    :param ssh_key_file: File containing the SSH key.  Use 'ssh_key' or
                         ssh_key_file, but not both.
    :param protocol: defaults to https, can be http if ssl is disabled on ESXi
    :param port: defaults to 443 for https
    :param certificate_verify: If true require that the SSL connection present
                               a valid certificate
    :return: Dictionary with a 'status' key, True if upload is successful.
             If upload is unsuccessful, 'status' key will be False and
             an 'Error' key will have an informative message.

    CLI Example:

    .. code-block:: bash

        salt '*' vsphere.upload_ssh_key my.esxi.host root bad-password ssh_key_file='/etc/salt/my_keys/my_key.pub'

    '''
    if protocol is None:
        protocol = 'https'
    if port is None:
        port = 443

    url = '{0}://{1}:{2}/host/ssh_root_authorized_keys'.format(protocol,
                                                               host,
                                                               port)
    ret = {}
    result = None
    try:
        if ssh_key:
            result = salt.utils.http.query(url,
                                           status=True,
                                           text=True,
                                           method='PUT',
                                           username=username,
                                           password=password,
                                           data=ssh_key,
                                           verify_ssl=certificate_verify)
        elif ssh_key_file:
            result = salt.utils.http.query(url,
                                           status=True,
                                           text=True,
                                           method='PUT',
                                           username=username,
                                           password=password,
                                           data_file=ssh_key_file,
                                           data_render=False,
                                           verify_ssl=certificate_verify)
        if result.get('status') == 200:
            ret['status'] = True
        else:
            ret['status'] = False
            ret['Error'] = result['error']
    except Exception as msg:
        ret['status'] = False
        ret['Error'] = msg

    return ret


def get_ssh_key(host,
                username,
                password,
                protocol=None,
                port=None,
                certificate_verify=False):
    '''
    Retrieve the authorized_keys entry for root.
    This function only works for ESXi, not vCenter.

    :param host: The location of the ESXi Host
    :param username: Username to connect as
    :param password: Password for the ESXi web endpoint
    :param protocol: defaults to https, can be http if ssl is disabled on ESXi
    :param port: defaults to 443 for https
    :param certificate_verify: If true require that the SSL connection present
                               a valid certificate
    :return: True if upload is successful

    CLI Example:

    .. code-block:: bash

        salt '*' vsphere.get_ssh_key my.esxi.host root bad-password certificate_verify=True

    '''
    if protocol is None:
        protocol = 'https'
    if port is None:
        port = 443

    url = '{0}://{1}:{2}/host/ssh_root_authorized_keys'.format(protocol,
                                                               host,
                                                               port)
    ret = {}
    try:
        result = salt.utils.http.query(url,
                                       status=True,
                                       text=True,
                                       method='GET',
                                       username=username,
                                       password=password,
                                       verify_ssl=certificate_verify)
        if result.get('status') == 200:
            ret['status'] = True
            ret['key'] = result['text']
        else:
            ret['status'] = False
            ret['Error'] = result['error']
    except Exception as msg:
        ret['status'] = False
        ret['Error'] = msg

    return ret


def get_host_datetime(host, username, password, protocol=None, port=None, host_names=None):
    '''
    Get the date/time information for a given host or list of host_names.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to tell
        vCenter the hosts for which to get date/time information.

        If host_names is not provided, the date/time information will be retrieved for the
        ``host`` location instead. This is useful for when service instance connection
        information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.get_host_datetime my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.get_host_datetime my.vcenter.location root bad-password \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)
    ret = {}
    for host_name in host_names:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        date_time_manager = _get_date_time_mgr(host_ref)
        date_time = date_time_manager.QueryDateTime()
        ret.update({host_name: date_time})

    return ret


def get_ntp_config(host, username, password, protocol=None, port=None, host_names=None):
    '''
    Get the NTP configuration information for a given host or list of host_names.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to tell
        vCenter the hosts for which to get ntp configuration information.

        If host_names is not provided, the NTP configuration will be retrieved for the
        ``host`` location instead. This is useful for when service instance connection
        information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.get_ntp_config my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.get_ntp_config my.vcenter.location root bad-password \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)
    ret = {}
    for host_name in host_names:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        ntp_config = host_ref.configManager.dateTimeSystem.dateTimeInfo.ntpConfig.server
        ret.update({host_name: ntp_config})

    return ret


def get_service_policy(host, username, password, service_name, protocol=None, port=None, host_names=None):
    '''
    Get the service name's policy for a given host or list of hosts.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    service_name
        The name of the service for which to retrieve the policy. Supported service names are:
          - DCUI
          - TSM
          - SSH
          - lbtd
          - lsassd
          - lwiod
          - netlogond
          - ntpd
          - sfcbd-watchdog
          - snmpd
          - vprobed
          - vpxa
          - xorg

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to tell
        vCenter the hosts for which to get service policy information.

        If host_names is not provided, the service policy information will be retrieved
        for the ``host`` location instead. This is useful for when service instance
        connection information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.get_service_policy my.esxi.host root bad-password 'ssh'

        # Used for connecting to a vCenter Server
        salt '*' vsphere.get_service_policy my.vcenter.location root bad-password 'ntpd' \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    valid_services = ['DCUI', 'TSM', 'SSH', 'ssh', 'lbtd', 'lsassd', 'lwiod', 'netlogond',
                      'ntpd', 'sfcbd-watchdog', 'snmpd', 'vprobed', 'vpxa', 'xorg']
    host_names = _check_hosts(service_instance, host, host_names)

    ret = {}
    for host_name in host_names:
        # Check if the service_name provided is a valid one.
        # If we don't have a valid service, return. The service will be invalid for all hosts.
        if service_name not in valid_services:
            ret.update({host_name: {'Error': '{0} is not a valid service name.'.format(service_name)}})
            return ret

        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        services = host_ref.configManager.serviceSystem.serviceInfo.service

        # Don't require users to know that VMware lists the ssh service as TSM-SSH
        if service_name == 'SSH' or service_name == 'ssh':
            temp_service_name = 'TSM-SSH'
        else:
            temp_service_name = service_name

        # Loop through services until we find a matching name
        for service in services:
            if service.key == temp_service_name:
                ret.update({host_name:
                           {service_name: service.policy}})
                # We've found a match - break out of the loop so we don't overwrite the
                # Updated host_name value with an error message.
                break
            else:
                msg = 'Could not find service \'{0}\' for host \'{1}\'.'.format(service_name,
                                                                                host_name)
                ret.update({host_name: {'Error': msg}})

        # If we made it this far, something else has gone wrong.
        if ret.get(host_name) is None:
            msg = '\'vsphere.get_service_policy\' failed for host {0}.'.format(host_name)
            log.debug(msg)
            ret.update({host_name: {'Error': msg}})

    return ret


def get_service_running(host, username, password, service_name, protocol=None, port=None, host_names=None):
    '''
    Get the service name's running state for a given host or list of hosts.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    service_name
        The name of the service for which to retrieve the policy. Supported service names are:
          - DCUI
          - TSM
          - SSH
          - lbtd
          - lsassd
          - lwiod
          - netlogond
          - ntpd
          - sfcbd-watchdog
          - snmpd
          - vprobed
          - vpxa
          - xorg

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to tell
        vCenter the hosts for which to get the service's running state.

        If host_names is not provided, the service's running state will be retrieved
        for the ``host`` location instead. This is useful for when service instance
        connection information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.get_service_running my.esxi.host root bad-password 'ssh'

        # Used for connecting to a vCenter Server
        salt '*' vsphere.get_service_running my.vcenter.location root bad-password 'ntpd' \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    valid_services = ['DCUI', 'TSM', 'SSH', 'ssh', 'lbtd', 'lsassd', 'lwiod', 'netlogond',
                      'ntpd', 'sfcbd-watchdog', 'snmpd', 'vprobed', 'vpxa', 'xorg']
    host_names = _check_hosts(service_instance, host, host_names)

    ret = {}
    for host_name in host_names:
        # Check if the service_name provided is a valid one.
        # If we don't have a valid service, return. The service will be invalid for all hosts.
        if service_name not in valid_services:
            ret.update({host_name: {'Error': '{0} is not a valid service name.'.format(service_name)}})
            return ret

        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        services = host_ref.configManager.serviceSystem.serviceInfo.service

        # Don't require users to know that VMware lists the ssh service as TSM-SSH
        if service_name == 'SSH' or service_name == 'ssh':
            temp_service_name = 'TSM-SSH'
        else:
            temp_service_name = service_name

        # Loop through services until we find a matching name
        for service in services:
            if service.key == temp_service_name:
                ret.update({host_name:
                           {service_name: service.running}})
                # We've found a match - break out of the loop so we don't overwrite the
                # Updated host_name value with an error message.
                break
            else:
                msg = 'Could not find service \'{0}\' for host \'{1}\'.'.format(service_name,
                                                                                host_name)
                ret.update({host_name: {'Error': msg}})

        # If we made it this far, something else has gone wrong.
        if ret.get(host_name) is None:
            msg = '\'vsphere.get_service_running\' failed for host {0}.'.format(host_name)
            log.debug(msg)
            ret.update({host_name: {'Error': msg}})

    return ret


def get_vmotion_enabled(host, username, password, protocol=None, port=None, host_names=None):
    '''
    Get the VMotion enabled status for a given host or a list of host_names. Returns ``True``
    if VMotion is enabled, ``False`` if it is not enabled.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to
        tell vCenter which hosts to check if VMotion is enabled.

        If host_names is not provided, the VMotion status will be retrieved for the
        ``host`` location instead. This is useful for when service instance
        connection information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.get_vmotion_enabled my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.get_vmotion_enabled my.vcenter.location root bad-password \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)
    ret = {}
    for host_name in host_names:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        vmotion_vnic = host_ref.configManager.vmotionSystem.netConfig.selectedVnic
        if vmotion_vnic:
            ret.update({host_name: {'VMotion Enabled': True}})
        else:
            ret.update({host_name: {'VMotion Enabled': False}})

    return ret


def get_vsan_enabled(host, username, password, protocol=None, port=None, host_names=None):
    '''
    Get the VSAN enabled status for a given host or a list of host_names. Returns ``True``
    if VSAN is enabled, ``False`` if it is not enabled, and ``None`` if a VSAN Host Config
    is unset, per host.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to
        tell vCenter which hosts to check if VSAN enabled.

        If host_names is not provided, the VSAN status will be retrieved for the
        ``host`` location instead. This is useful for when service instance
        connection information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.get_vsan_enabled my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.get_vsan_enabled my.vcenter.location root bad-password \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)
    ret = {}
    for host_name in host_names:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        vsan_config = host_ref.config.vsanHostConfig

        # We must have a VSAN Config in place get information about VSAN state.
        if vsan_config is None:
            msg = 'VSAN System Config Manager is unset for host \'{0}\'.'.format(host_name)
            log.debug(msg)
            ret.update({host_name: {'Error': msg}})
        else:
            ret.update({host_name: {'VSAN Enabled': vsan_config.enabled}})

    return ret


def get_vsan_eligible_disks(host, username, password, protocol=None, port=None, host_names=None):
    '''
    Returns a list of VSAN-eligible disks for a given host or list of host_names.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to
        tell vCenter which hosts to check if any VSAN-eligible disks are available.

        If host_names is not provided, the VSAN-eligible disks will be retrieved
        for the ``host`` location instead. This is useful for when service instance
        connection information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.get_vsan_eligible_disks my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.get_vsan_eligible_disks my.vcenter.location root bad-password \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)
    response = _get_vsan_eligible_disks(service_instance, host, host_names)

    ret = {}
    for host_name, value in response.iteritems():
        error = value.get('Error')
        if error:
            ret.update({host_name: {'Error': error}})
            continue

        disks = value.get('Eligible')
        # If we have eligible disks, it will be a list of disk objects
        if disks and isinstance(disks, list):
            disk_names = []
            # We need to return ONLY the disk names, otherwise
            # MessagePack can't deserialize the disk objects.
            for disk in disks:
                disk_names.append(disk.canonicalName)
            ret.update({host_name: {'Eligible': disk_names}})
        else:
            # If we have disks, but it's not a list, it's actually a
            # string message that we're passing along.
            ret.update({host_name: {'Eligible': disks}})

    return ret


def system_info(host, username, password, protocol=None, port=None):
    '''
    Return system information about a VMware environment.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    CLI Example:

    .. code-block:: bash

        salt '*' vsphere.system_info 1.2.3.4 root bad-password
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    return salt.utils.vmware.get_inventory(service_instance).about.__dict__


def list_datacenters(host, username, password, protocol=None, port=None):
    '''
    Returns a list of datacenters for the the specified host.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    .. code-block:: bash

        salt '*' vsphere.list_datacenters 1.2.3.4 root bad-password
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    return salt.utils.vmware.list_datacenters(service_instance)


def list_clusters(host, username, password, protocol=None, port=None):
    '''
    Returns a list of clusters for the the specified host.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    .. code-block:: bash

        salt '*' vsphere.list_clusters 1.2.3.4 root bad-password
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    return salt.utils.vmware.list_clusters(service_instance)


def list_datastore_clusters(host, username, password, protocol=None, port=None):
    '''
    Returns a list of datastore clusters for the the specified host.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    .. code-block:: bash

        salt '*' vsphere.list_datastore_clusters 1.2.3.4 root bad-password
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    return salt.utils.vmware.list_datastore_clusters(service_instance)


def list_datastores(host, username, password, protocol=None, port=None):
    '''
    Returns a list of datastores for the the specified host.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    .. code-block:: bash

        salt '*' vsphere.list_datastores 1.2.3.4 root bad-password
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    return salt.utils.vmware.list_datastores(service_instance)


def list_hosts(host, username, password, protocol=None, port=None):
    '''
    Returns a list of hosts for the the specified VMware environment.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    .. code-block:: bash

        salt '*' vsphere.list_hosts 1.2.3.4 root bad-password
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    return salt.utils.vmware.list_hosts(service_instance)


def list_resourcepools(host, username, password, protocol=None, port=None):
    '''
    Returns a list of resource pools for the the specified host.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    .. code-block:: bash

        salt '*' vsphere.list_resourcepools 1.2.3.4 root bad-password
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    return salt.utils.vmware.list_resourcepools(service_instance)


def list_networks(host, username, password, protocol=None, port=None):
    '''
    Returns a list of networks for the the specified host.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    .. code-block:: bash

        salt '*' vsphere.list_networks 1.2.3.4 root bad-password
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    return salt.utils.vmware.list_networks(service_instance)


def list_vms(host, username, password, protocol=None, port=None):
    '''
    Returns a list of VMs for the the specified host.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    .. code-block:: bash

        salt '*' vsphere.list_vms 1.2.3.4 root bad-password
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    return salt.utils.vmware.list_vms(service_instance)


def list_folders(host, username, password, protocol=None, port=None):
    '''
    Returns a list of folders for the the specified host.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    .. code-block:: bash

        salt '*' vsphere.list_folders 1.2.3.4 root bad-password
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    return salt.utils.vmware.list_folders(service_instance)


def list_dvs(host, username, password, protocol=None, port=None):
    '''
    Returns a list of distributed virtual switches for the the specified host.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    .. code-block:: bash

        salt '*' vsphere.list_dvs 1.2.3.4 root bad-password
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    return salt.utils.vmware.list_dvs(service_instance)


def list_vapps(host, username, password, protocol=None, port=None):
    '''
    Returns a list of vApps for the the specified host.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    .. code-block:: bash

        salt '*' vsphere.list_vapps 1.2.3.4 root bad-password
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    return salt.utils.vmware.list_vapps(service_instance)


def list_ssds(host, username, password, protocol=None, port=None, host_names=None):
    '''
    Returns a list of SSDs for the given host or list of host_names.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to
        tell vCenter the hosts for which to retrieve SSDs.

        If host_names is not provided, SSDs will be retrieved for the
        ``host`` location instead. This is useful for when service instance
        connection information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.list_ssds my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.list_ssds my.vcenter.location root bad-password \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)
    ret = {}
    names = []
    for host_name in host_names:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        disks = _get_host_ssds(host_ref)
        for disk in disks:
            names.append(disk.canonicalName)
        ret.update({host_name: names})

    return ret


def list_non_ssds(host, username, password, protocol=None, port=None, host_names=None):
    '''
    Returns a list of Non-SSD disks for the given host or list of host_names.

    .. note::

        In the pyVmomi StorageSystem, ScsiDisks may, or may not have an ``ssd`` attribute.
        This attribute indicates if the ScsiDisk is SSD backed. As this option is optional,
        if a relevant disk in the StorageSystem does not have ``ssd = true``, it will end
        up in the ``non_ssds`` list here.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to
        tell vCenter the hosts for which to retrieve Non-SSD disks.

        If host_names is not provided, Non-SSD disks will be retrieved for the
        ``host`` location instead. This is useful for when service instance
        connection information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.list_non_ssds my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.list_non_ssds my.vcenter.location root bad-password \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)
    ret = {}
    names = []
    for host_name in host_names:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        disks = _get_host_non_ssds(host_ref)
        for disk in disks:
            names.append(disk.canonicalName)
        ret.update({host_name: names})

    return ret


def set_ntp_config(host, username, password, ntp_servers, protocol=None, port=None, host_names=None):
    '''
    Set NTP configuration for a given host of list of host_names.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    ntp_servers
        A list of servers that should be added to and configured for the specified
        host's NTP configuration.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to tell
        vCenter which hosts to configure ntp servers.

        If host_names is not provided, the NTP servers will be configured for the
        ``host`` location instead. This is useful for when service instance connection
        information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.ntp_configure my.esxi.host root bad-password '[192.174.1.100, 192.174.1.200]'

        # Used for connecting to a vCenter Server
        salt '*' vsphere.ntp_configure my.vcenter.location root bad-password '[192.174.1.100, 192.174.1.200]' \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    if not isinstance(ntp_servers, list):
        raise CommandExecutionError('\'ntp_servers\' must be a list.')

    # Get NTP Config Object from ntp_servers
    ntp_config = vim.HostNtpConfig(server=ntp_servers)

    # Get DateTimeConfig object from ntp_config
    date_config = vim.HostDateTimeConfig(ntpConfig=ntp_config)

    host_names = _check_hosts(service_instance, host, host_names)
    ret = {}
    for host_name in host_names:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        date_time_manager = _get_date_time_mgr(host_ref)
        log.debug('Configuring NTP Servers \'{0}\' for host \'{1}\'.'.format(ntp_servers, host_name))

        try:
            date_time_manager.UpdateDateTimeConfig(config=date_config)
        except vim.fault.HostConfigFault as err:
            msg = 'vsphere.ntp_configure_servers failed: {0}'.format(err)
            log.debug(msg)
            ret.update({host_name: {'Error': msg}})
            continue

        ret.update({host_name: {'NTP Servers': ntp_config}})
    return ret


def service_start(host,
                  username,
                  password,
                  service_name,
                  protocol=None,
                  port=None,
                  host_names=None):
    '''
    Start the named service for the given host or list of hosts.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    service_name
        The name of the service for which to set the policy. Supported service names are:
          - DCUI
          - TSM
          - SSH
          - lbtd
          - lsassd
          - lwiod
          - netlogond
          - ntpd
          - sfcbd-watchdog
          - snmpd
          - vprobed
          - vpxa
          - xorg

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to tell
        vCenter the hosts for which to start the service.

        If host_names is not provided, the service will be started for the ``host``
        location instead. This is useful for when service instance connection information
        is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.service_start my.esxi.host root bad-password 'ntpd'

        # Used for connecting to a vCenter Server
        salt '*' vsphere.service_start my.vcenter.location root bad-password 'ntpd' \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)
    valid_services = ['DCUI', 'TSM', 'SSH', 'ssh', 'lbtd', 'lsassd', 'lwiod', 'netlogond',
                      'ntpd', 'sfcbd-watchdog', 'snmpd', 'vprobed', 'vpxa', 'xorg']
    ret = {}

    # Don't require users to know that VMware lists the ssh service as TSM-SSH
    if service_name == 'SSH' or service_name == 'ssh':
        temp_service_name = 'TSM-SSH'
    else:
        temp_service_name = service_name

    for host_name in host_names:
        # Check if the service_name provided is a valid one.
        # If we don't have a valid service, return. The service will be invalid for all hosts.
        if service_name not in valid_services:
            ret.update({host_name: {'Error': '{0} is not a valid service name.'.format(service_name)}})
            return ret

        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        service_manager = _get_service_manager(host_ref)
        log.debug('Starting the \'{0}\' service on {1}.'.format(service_name, host_name))

        # Start the service
        try:
            service_manager.StartService(id=temp_service_name)
        except vim.fault.HostConfigFault as err:
            msg = '\'vsphere.service_start\' failed for host {0}: {1}'.format(host_name, err)
            log.debug(msg)
            ret.update({host_name: {'Error': msg}})
            continue
        # Some services are restricted by the vSphere License Level.
        except vim.fault.RestrictedVersion as err:
            log.debug(err)
            ret.update({host_name: {'Error': err}})
            continue

        ret.update({host_name: {'Service Started': True}})

    return ret


def service_stop(host,
                 username,
                 password,
                 service_name,
                 protocol=None,
                 port=None,
                 host_names=None):
    '''
    Stop the named service for the given host or list of hosts.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    service_name
        The name of the service for which to set the policy. Supported service names are:
          - DCUI
          - TSM
          - SSH
          - lbtd
          - lsassd
          - lwiod
          - netlogond
          - ntpd
          - sfcbd-watchdog
          - snmpd
          - vprobed
          - vpxa
          - xorg

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to tell
        vCenter the hosts for which to stop the service.

        If host_names is not provided, the service will be stopped for the ``host``
        location instead. This is useful for when service instance connection information
        is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.service_stop my.esxi.host root bad-password 'ssh'

        # Used for connecting to a vCenter Server
        salt '*' vsphere.service_stop my.vcenter.location root bad-password 'ssh' \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)
    valid_services = ['DCUI', 'TSM', 'SSH', 'ssh', 'lbtd', 'lsassd', 'lwiod', 'netlogond',
                      'ntpd', 'sfcbd-watchdog', 'snmpd', 'vprobed', 'vpxa', 'xorg']
    ret = {}

    # Don't require users to know that VMware lists the ssh service as TSM-SSH
    if service_name == 'SSH' or service_name == 'ssh':
        temp_service_name = 'TSM-SSH'
    else:
        temp_service_name = service_name

    for host_name in host_names:
        # Check if the service_name provided is a valid one.
        # If we don't have a valid service, return. The service will be invalid for all hosts.
        if service_name not in valid_services:
            ret.update({host_name: {'Error': '{0} is not a valid service name.'.format(service_name)}})
            return ret

        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        service_manager = _get_service_manager(host_ref)
        log.debug('Stopping the \'{0}\' service on {1}.'.format(service_name, host_name))

        # Stop the service.
        try:
            service_manager.StopService(id=temp_service_name)
        except vim.fault.HostConfigFault as err:
            msg = '\'vsphere.service_stop\' failed for host {0}: {1}'.format(host_name, err)
            log.debug(msg)
            ret.update({host_name: {'Error': msg}})
            continue
        # Some services are restricted by the vSphere License Level.
        except vim.fault.RestrictedVersion as err:
            log.debug(err)
            ret.update({host_name: {'Error': err}})
            continue

        ret.update({host_name: {'Service Stopped': True}})

    return ret


def service_restart(host,
                    username,
                    password,
                    service_name,
                    protocol=None,
                    port=None,
                    host_names=None):
    '''
    Restart the named service for the given host or list of hosts.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    service_name
        The name of the service for which to set the policy. Supported service names are:
          - DCUI
          - TSM
          - SSH
          - lbtd
          - lsassd
          - lwiod
          - netlogond
          - ntpd
          - sfcbd-watchdog
          - snmpd
          - vprobed
          - vpxa
          - xorg

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to tell
        vCenter the hosts for which to restart the service.

        If host_names is not provided, the service will be restarted for the ``host``
        location instead. This is useful for when service instance connection information
        is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.service_restart my.esxi.host root bad-password 'ntpd'

        # Used for connecting to a vCenter Server
        salt '*' vsphere.service_restart my.vcenter.location root bad-password 'ntpd' \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)
    valid_services = ['DCUI', 'TSM', 'SSH', 'ssh', 'lbtd', 'lsassd', 'lwiod', 'netlogond',
                      'ntpd', 'sfcbd-watchdog', 'snmpd', 'vprobed', 'vpxa', 'xorg']
    ret = {}

    # Don't require users to know that VMware lists the ssh service as TSM-SSH
    if service_name == 'SSH' or service_name == 'ssh':
        temp_service_name = 'TSM-SSH'
    else:
        temp_service_name = service_name

    for host_name in host_names:
        # Check if the service_name provided is a valid one.
        # If we don't have a valid service, return. The service will be invalid for all hosts.
        if service_name not in valid_services:
            ret.update({host_name: {'Error': '{0} is not a valid service name.'.format(service_name)}})
            return ret

        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        service_manager = _get_service_manager(host_ref)
        log.debug('Restarting the \'{0}\' service on {1}.'.format(service_name, host_name))

        # Restart the service.
        try:
            service_manager.RestartService(id=temp_service_name)
        except vim.fault.HostConfigFault as err:
            msg = '\'vsphere.service_restart\' failed for host {0}: {1}'.format(host_name, err)
            log.debug(msg)
            ret.update({host_name: {'Error': msg}})
            continue
        # Some services are restricted by the vSphere License Level.
        except vim.fault.RestrictedVersion as err:
            log.debug(err)
            ret.update({host_name: {'Error': err}})
            continue

        ret.update({host_name: {'Service Restarted': True}})

    return ret


def set_service_policy(host,
                       username,
                       password,
                       service_name,
                       service_policy,
                       protocol=None,
                       port=None,
                       host_names=None):
    '''
    Set the service name's policy for a given host or list of hosts.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    service_name
        The name of the service for which to set the policy. Supported service names are:
          - DCUI
          - TSM
          - SSH
          - lbtd
          - lsassd
          - lwiod
          - netlogond
          - ntpd
          - sfcbd-watchdog
          - snmpd
          - vprobed
          - vpxa
          - xorg

    service_policy
        The policy to set for the service. For example, 'automatic'.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to tell
        vCenter the hosts for which to set the service policy.

        If host_names is not provided, the service policy information will be retrieved
        for the ``host`` location instead. This is useful for when service instance
        connection information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.set_service_policy my.esxi.host root bad-password 'ntpd' 'automatic'

        # Used for connecting to a vCenter Server
        salt '*' vsphere.set_service_policy my.vcenter.location root bad-password 'ntpd' 'automatic' \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)
    valid_services = ['DCUI', 'TSM', 'SSH', 'ssh', 'lbtd', 'lsassd', 'lwiod', 'netlogond',
                      'ntpd', 'sfcbd-watchdog', 'snmpd', 'vprobed', 'vpxa', 'xorg']
    ret = {}

    for host_name in host_names:
        # Check if the service_name provided is a valid one.
        # If we don't have a valid service, return. The service will be invalid for all hosts.
        if service_name not in valid_services:
            ret.update({host_name: {'Error': '{0} is not a valid service name.'.format(service_name)}})
            return ret

        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        service_manager = _get_service_manager(host_ref)
        services = host_ref.configManager.serviceSystem.serviceInfo.service

        # Services are stored in a general list - we need loop through the list and find
        # service key that matches our service name.
        for service in services:
            service_key = None

            # Find the service key based on the given service_name
            if service.key == service_name:
                service_key = service.key
            elif service_name == 'ssh' or service_name == 'SSH':
                if service.key == 'TSM-SSH':
                    service_key = 'TSM-SSH'

            # If we have a service_key, we've found a match. Update the policy.
            if service_key:
                try:
                    service_manager.UpdateServicePolicy(id=service_key, policy=service_policy)
                except vim.fault.NotFound:
                    msg = 'The service name \'{0}\' was not found.'.format(service_name)
                    log.debug(msg)
                    ret.update({host_name: {'Error': msg}})
                    continue
                # Some services are restricted by the vSphere License Level.
                except vim.fault.HostConfigFault as err:
                    msg = '\'vsphere.set_service_policy\' failed for host {0}: {1}'.format(host_name, err)
                    log.debug(msg)
                    ret.update({host_name: {'Error': msg}})
                    continue

                ret.update({host_name: True})

            # If we made it this far, something else has gone wrong.
            if ret.get(host_name) is None:
                msg = 'Could not find service \'{0}\' for host \'{1}\'.'.format(service_name, host_name)
                log.debug(msg)
                ret.update({host_name: {'Error': msg}})

    return ret


def update_host_datetime(host, username, password, protocol=None, port=None, host_names=None):
    '''
    Update the date/time on the given host or list of host_names. This function should be
    used with caution since network delays and execution delays can result in time skews.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to
        tell vCenter which hosts should update their date/time.

        If host_names is not provided, the date/time will be updated for the ``host``
        location instead. This is useful for when service instance connection
        information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.update_date_time my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.update_date_time my.vcenter.location root bad-password \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)
    ret = {}
    for host_name in host_names:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        date_time_manager = _get_date_time_mgr(host_ref)
        try:
            date_time_manager.UpdateDateTime(datetime.datetime.utcnow())
        except vim.fault.HostConfigFault as err:
            msg = '\'vsphere.update_date_time\' failed for host {0}: {1}'.format(host_name, err)
            log.debug(msg)
            ret.update({host_name: {'Error': msg}})
            continue

        ret.update({host_name: {'Datetime Updated': True}})

    return ret


def update_host_password(host, username, password, new_password, protocol=None, port=None):
    '''
    Update the password for a given host.

    .. note:: Currently only works with connections to ESXi hosts. Does not work with vCenter servers.

    host
        The location of the ESXi host.

    username
        The username used to login to the ESXi host, such as ``root``.

    password
        The password used to login to the ESXi host.

    new_password
        The new password that will be updated for the provided username on the ESXi host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    CLI Example:

    .. code-block:: bash

        salt '*' vsphere.update_host_password my.esxi.host root original-bad-password new-bad-password

    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    # Get LocalAccountManager object
    account_manager = salt.utils.vmware.get_inventory(service_instance).accountManager

    # Create user account specification object and assign id and password attributes
    user_account = vim.host.LocalAccountManager.AccountSpecification()
    user_account.id = username
    user_account.password = new_password

    # Update the password
    try:
        account_manager.UpdateUser(user_account)
    except vmodl.fault.SystemError as err:
        raise CommandExecutionError(err.msg)
    except vim.fault.UserNotFound:
        raise CommandExecutionError('\'vsphere.update_host_password\' failed for host {0}: '
                                    'User was not found.'.format(host))
    # If the username and password already exist, we don't need to do anything.
    except vim.fault.AlreadyExists:
        pass

    return True


def vmotion_disable(host, username, password, protocol=None, port=None, host_names=None):
    '''
    Disable vMotion for a given host or list of host_names.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to
        tell vCenter which hosts should disable VMotion.

        If host_names is not provided, VMotion will be disabled for the ``host``
        location instead. This is useful for when service instance connection
        information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.vmotion_disable my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.vmotion_disable my.vcenter.location root bad-password \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)
    ret = {}
    for host_name in host_names:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        vmotion_system = host_ref.configManager.vmotionSystem

        # Disable VMotion for the host by removing the VNic selected to use for VMotion.
        try:
            vmotion_system.DeselectVnic()
        except vim.fault.HostConfigFault as err:
            msg = 'vsphere.vmotion_disable failed: {0}'.format(err)
            log.debug(msg)
            ret.update({host_name: {'Error': msg,
                                    'VMotion Disabled': False}})
            continue

        ret.update({host_name: {'VMotion Disabled': True}})

    return ret


def vmotion_enable(host, username, password, protocol=None, port=None, host_names=None, device='vmk0'):
    '''
    Enable vMotion for a given host or list of host_names.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to
        tell vCenter which hosts should enable VMotion.

        If host_names is not provided, VMotion will be enabled for the ``host``
        location instead. This is useful for when service instance connection
        information is used for a single ESXi host.

    device
        The device that uniquely identifies the VirtualNic that will be used for
        VMotion for each host. Defaults to ``vmk0``.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.vmotion_enable my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.vmotion_enable my.vcenter.location root bad-password \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)
    ret = {}
    for host_name in host_names:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        vmotion_system = host_ref.configManager.vmotionSystem

        # Enable VMotion for the host by setting the given device to provide the VNic to use for VMotion.
        try:
            vmotion_system.SelectVnic(device)
        except vim.fault.HostConfigFault as err:
            msg = 'vsphere.vmotion_disable failed: {0}'.format(err)
            log.debug(msg)
            ret.update({host_name: {'Error': msg,
                                    'VMotion Enabled': False}})
            continue

        ret.update({host_name: {'VMotion Enabled': True}})

    return ret


def vsan_add_disks(host, username, password, protocol=None, port=None, host_names=None):
    '''
    Add any VSAN-eligible disks to the VSAN System for the given host or list of host_names.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to
        tell vCenter which hosts need to add any VSAN-eligible disks to the host's
        VSAN system.

        If host_names is not provided, VSAN-eligible disks will be added to the hosts's
        VSAN system for the ``host`` location instead. This is useful for when service
        instance connection information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.vsan_add_disks my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.vsan_add_disks my.vcenter.location root bad-password \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    host_names = _check_hosts(service_instance, host, host_names)
    response = _get_vsan_eligible_disks(service_instance, host, host_names)

    ret = {}
    for host_name, value in response.iteritems():
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        vsan_system = host_ref.configManager.vsanSystem

        # We must have a VSAN Config in place before we can manipulate it.
        if vsan_system is None:
            msg = 'VSAN System Config Manager is unset for host \'{0}\'. ' \
                  'VSAN configuration cannot be changed without a configured ' \
                  'VSAN System.'.format(host_name)
            log.debug(msg)
            ret.update({host_name: {'Error': msg}})
        else:
            eligible = value.get('Eligible')
            error = value.get('Error')

            if eligible and isinstance(eligible, list):
                # If we have eligible, matching disks, add them to VSAN.
                try:
                    task = vsan_system.AddDisks(eligible)
                    salt.utils.vmware.wait_for_task(task, host_name, 'Adding disks to VSAN', sleep_seconds=3)
                except vim.fault.InsufficientDisks as err:
                    log.debug(err.msg)
                    ret.update({host_name: {'Error': err.msg}})
                    continue
                except Exception as err:
                    msg = '\'vsphere.vsan_add_disks\' failed for host {0}: {1}'.format(host_name, err)
                    log.debug(msg)
                    ret.update({host_name: {'Error': msg}})
                    continue

                log.debug('Successfully added disks to the VSAN system for host \'{0}\'.'.format(host_name))
                # We need to return ONLY the disk names, otherwise Message Pack can't deserialize the disk objects.
                disk_names = []
                for disk in eligible:
                    disk_names.append(disk.canonicalName)
                ret.update({host_name: {'Disks Added': disk_names}})
            elif eligible and isinstance(eligible, six.string_types):
                # If we have a string type in the eligible value, we don't
                # have any VSAN-eligible disks. Pull the message through.
                ret.update({host_name: {'Disks Added': eligible}})
            elif error:
                # If we hit an error, populate the Error return dict for state functions.
                ret.update({host_name: {'Error': error}})
            else:
                # If we made it this far, we somehow have eligible disks, but they didn't
                # match the disk list and just got an empty list of matching disks.
                ret.update({host_name: {'Disks Added': 'No new VSAN-eligible disks were found to add.'}})

    return ret


def vsan_disable(host, username, password, protocol=None, port=None, host_names=None):
    '''
    Disable VSAN for a given host or list of host_names.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to
        tell vCenter which hosts should disable VSAN.

        If host_names is not provided, VSAN will be disabled for the ``host``
        location instead. This is useful for when service instance connection
        information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.vsan_disable my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.vsan_disable my.vcenter.location root bad-password \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    # Create a VSAN Configuration Object and set the enabled attribute to True
    vsan_config = vim.vsan.host.ConfigInfo()
    vsan_config.enabled = False

    host_names = _check_hosts(service_instance, host, host_names)
    ret = {}
    for host_name in host_names:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        vsan_system = host_ref.configManager.vsanSystem

        # We must have a VSAN Config in place before we can manipulate it.
        if vsan_system is None:
            msg = 'VSAN System Config Manager is unset for host \'{0}\'. ' \
                  'VSAN configuration cannot be changed without a configured ' \
                  'VSAN System.'.format(host_name)
            log.debug(msg)
            ret.update({host_name: {'Error': msg}})
        else:
            try:
                # Disable vsan on the host
                task = vsan_system.UpdateVsan_Task(vsan_config)
                salt.utils.vmware.wait_for_task(task, host_name, 'Disabling VSAN', sleep_seconds=3)
            except vmodl.fault.SystemError as err:
                log.debug(err.msg)
                ret.update({host_name: {'Error': err.msg}})
                continue
            except Exception as err:
                msg = '\'vsphere.vsan_disable\' failed for host {0}: {1}'.format(host_name, err)
                log.debug(msg)
                ret.update({host_name: {'Error': msg}})
                continue

            ret.update({host_name: {'VSAN Disabled': True}})

    return ret


def vsan_enable(host, username, password, protocol=None, port=None, host_names=None):
    '''
    Enable VSAN for a given host or list of host_names.

    host
        The location of the host.

    username
        The username used to login to the host, such as ``root``.

    password
        The password used to login to the host.

    protocol
        Optionally set to alternate protocol if the host is not using the default
        protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the host is not using the default
        port. Default port is ``443``.

    host_names
        List of ESXi host names. When the host, username, and password credentials
        are provided for a vCenter Server, the host_names argument is required to
        tell vCenter which hosts should enable VSAN.

        If host_names is not provided, VSAN will be enabled for the ``host``
        location instead. This is useful for when service instance connection
        information is used for a single ESXi host.

    CLI Example:

    .. code-block:: bash

        # Used for single ESXi host connection information
        salt '*' vsphere.vsan_enable my.esxi.host root bad-password

        # Used for connecting to a vCenter Server
        salt '*' vsphere.vsan_enable my.vcenter.location root bad-password \
        host_names='[esxi-1.host.com, esxi-2.host.com]'
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    # Create a VSAN Configuration Object and set the enabled attribute to True
    vsan_config = vim.vsan.host.ConfigInfo()
    vsan_config.enabled = True

    host_names = _check_hosts(service_instance, host, host_names)
    ret = {}
    for host_name in host_names:
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        vsan_system = host_ref.configManager.vsanSystem

        # We must have a VSAN Config in place before we can manipulate it.
        if vsan_system is None:
            msg = 'VSAN System Config Manager is unset for host \'{0}\'. ' \
                  'VSAN configuration cannot be changed without a configured ' \
                  'VSAN System.'.format(host_name)
            log.debug(msg)
            ret.update({host_name: {'Error': msg}})
        else:
            try:
                # Enable vsan on the host
                task = vsan_system.UpdateVsan_Task(vsan_config)
                salt.utils.vmware.wait_for_task(task, host_name, 'Enabling VSAN', sleep_seconds=3)
            except vmodl.fault.SystemError as err:
                log.debug(err.msg)
                ret.update({host_name: {'Error': err.msg}})
                continue
            except vim.fault.VsanFault as err:
                msg = '\'vsphere.vsan_enable\' failed for host {0}: {1}'.format(host_name, err)
                log.debug(msg)
                ret.update({host_name: {'Error': msg}})
                continue

            ret.update({host_name: {'VSAN Enabled': True}})

    return ret


def _check_hosts(service_instance, host, host_names):
    '''
    Helper function that checks to see if the host provided is a vCenter Server or
    an ESXi host. If it's an ESXi host, returns a list of a single host_name.

    If a host reference isn't found, we're trying to find a host object for a vCenter
    server. Raises a CommandExecutionError in this case, as we need host references to
    check against.
    '''
    if not host_names:
        host_name = _get_host_ref(service_instance, host)
        if host_name:
            host_names = [host]
        else:
            raise CommandExecutionError('No host reference found. If connecting to a '
                                        'vCenter Server, a list of \'host_names\' must be '
                                        'provided.')
    elif not isinstance(host_names, list):
        raise CommandExecutionError('\'host_names\' must be a list.')

    return host_names


def _format_coredump_stdout(cmd_ret):
    '''
    Helper function to format the stdout from the get_coredump_network_config function.

    cmd_ret
        The return dictionary that comes from a cmd.run_all call.
    '''
    ret_dict = {}
    for line in cmd_ret['stdout'].splitlines():
        line = line.strip().lower()
        if line.startswith('enabled:'):
            enabled = line.split(':')
            if 'true' in enabled[1]:
                ret_dict['enabled'] = True
            else:
                ret_dict['enabled'] = False
                break
        if line.startswith('host vnic:'):
            host_vnic = line.split(':')
            ret_dict['host_vnic'] = host_vnic[1].strip()
        if line.startswith('network server ip:'):
            ip = line.split(':')
            ret_dict['ip'] = ip[1].strip()
        if line.startswith('network server port:'):
            ip_port = line.split(':')
            ret_dict['port'] = ip_port[1].strip()

    return ret_dict


def _format_firewall_stdout(cmd_ret):
    '''
    Helper function to format the stdout from the get_firewall_status function.

    cmd_ret
        The return dictionary that comes from a cmd.run_all call.
    '''
    ret_dict = {'success': True,
                'rulesets': {}}
    for line in cmd_ret['stdout'].splitlines():
        if line.startswith('Name'):
            continue
        if line.startswith('---'):
            continue
        ruleset_status = line.split()
        ret_dict['rulesets'][ruleset_status[0]] = bool(ruleset_status[1])

    return ret_dict


def _format_syslog_config(cmd_ret):
    '''
    Helper function to format the stdout from the get_syslog_config function.

    cmd_ret
        The return dictionary that comes from a cmd.run_all call.
    '''
    ret_dict = {'success': cmd_ret['retcode'] == 0}

    if cmd_ret['retcode'] != 0:
        ret_dict['message'] = cmd_ret['stdout']
    else:
        for line in cmd_ret['stdout'].splitlines():
            line = line.strip()
            cfgvars = line.split(': ')
            key = cfgvars[0].strip()
            value = cfgvars[1].strip()
            ret_dict[key] = value

    return ret_dict


def _get_date_time_mgr(host_reference):
    '''
    Helper function that returns a dateTimeManager object
    '''
    return host_reference.configManager.dateTimeSystem


def _get_host_ref(service_instance, host, host_name=None):
    '''
    Helper function that returns a host object either from the host location or the host_name.
    If host_name is provided, that is the host_object that will be returned.

    The function will first search for hosts by DNS Name. If no hosts are found, it will
    try searching by IP Address.
    '''
    search_index = salt.utils.vmware.get_inventory(service_instance).searchIndex

    # First, try to find the host reference by DNS Name.
    if host_name:
        host_ref = search_index.FindByDnsName(dnsName=host_name, vmSearch=False)
    else:
        host_ref = search_index.FindByDnsName(dnsName=host, vmSearch=False)

    # If we couldn't find the host by DNS Name, then try the IP Address.
    if host_ref is None:
        host_ref = search_index.FindByIp(ip=host, vmSearch=False)

    return host_ref


def _get_host_ssds(host_reference):
    '''
    Helper function that returns a list of ssd objects for a given host.
    '''
    return _get_host_disks(host_reference).get('SSDs')


def _get_host_non_ssds(host_reference):
    '''
    Helper function that returns a list of Non-SSD objects for a given host.
    '''
    return _get_host_disks(host_reference).get('Non-SSDs')


def _get_host_disks(host_reference):
    '''
    Helper function that returns a dictionary containing a list of SSD and Non-SSD disks.
    '''
    storage_system = host_reference.configManager.storageSystem
    disks = storage_system.storageDeviceInfo.scsiLun
    ssds = []
    non_ssds = []

    for disk in disks:
        try:
            has_ssd_attr = disk.ssd
        except AttributeError:
            has_ssd_attr = False
        if has_ssd_attr:
            ssds.append(disk)
        else:
            non_ssds.append(disk)

    return {'SSDs': ssds, 'Non-SSDs': non_ssds}


def _get_service_manager(host_reference):
    '''
    Helper function that returns a service manager object from a given host object.
    '''
    return host_reference.configManager.serviceSystem


def _get_vsan_eligible_disks(service_instance, host, host_names):
    '''
    Helper function that returns a dictionary of host_name keys with either a list of eligible
    disks that can be added to VSAN or either an 'Error' message or a message saying no
    eligible disks were found. Possible keys/values look like:

    return = {'host_1': {'Error': 'VSAN System Config Manager is unset ...'},
              'host_2': {'Eligible': 'The host xxx does not have any VSAN eligible disks.'},
              'host_3': {'Eligible': [disk1, disk2, disk3, disk4],
              'host_4': {'Eligible': []}}
    '''
    ret = {}
    for host_name in host_names:

        # Get VSAN System Config Manager, if available.
        host_ref = _get_host_ref(service_instance, host, host_name=host_name)
        vsan_system = host_ref.configManager.vsanSystem
        if vsan_system is None:
            msg = 'VSAN System Config Manager is unset for host \'{0}\'. ' \
                  'VSAN configuration cannot be changed without a configured ' \
                  'VSAN System.'.format(host_name)
            log.debug(msg)
            ret.update({host_name: {'Error': msg}})
            continue

        # Get all VSAN suitable disks for this host.
        suitable_disks = []
        query = vsan_system.QueryDisksForVsan()
        for item in query:
            if item.state == 'eligible':
                suitable_disks.append(item)

        # No suitable disks were found to add. Warn and move on.
        # This isn't an error as the state may run repeatedly after all eligible disks are added.
        if not suitable_disks:
            msg = 'The host \'{0}\' does not have any VSAN eligible disks.'.format(host_name)
            log.warning(msg)
            ret.update({host_name: {'Eligible': msg}})
            continue

        # Get disks for host and combine into one list of Disk Objects
        disks = _get_host_ssds(host_ref) + _get_host_non_ssds(host_ref)

        # Get disks that are in both the disks list and suitable_disks lists.
        matching = []
        for disk in disks:
            for suitable_disk in suitable_disks:
                if disk.canonicalName == suitable_disk.disk.canonicalName:
                    matching.append(disk)

        ret.update({host_name: {'Eligible': matching}})

    return ret


def _reset_syslog_config_params(host, username, password, cmd, resets, valid_resets,
                                protocol=None, port=None, esxi_host=None):
    '''
    Helper function for reset_syslog_config that resets the config and populates the return dictionary.
    '''
    ret_dict = {}
    all_success = True

    if not isinstance(resets, list):
        resets = [resets]

    for reset_param in resets:
        if reset_param in valid_resets:
            ret = salt.utils.vmware.esxcli(host, username, password, cmd + reset_param,
                                           protocol=protocol, port=port,
                                           esxi_host=esxi_host)
            ret_dict[reset_param] = {}
            ret_dict[reset_param]['success'] = ret['retcode'] == 0
            if ret['retcode'] != 0:
                all_success = False
                ret_dict[reset_param]['message'] = ret['stdout']
        else:
            all_success = False
            ret_dict[reset_param] = {}
            ret_dict[reset_param]['success'] = False
            ret_dict[reset_param]['message'] = 'Invalid syslog ' \
                                               'configuration parameter'

    ret_dict['success'] = all_success

    return ret_dict


def _set_syslog_config_helper(host, username, password, syslog_config, config_value,
                              protocol=None, port=None, reset_service=None, esxi_host=None):
    '''
    Helper function for set_syslog_config that sets the config and populates the return dictionary.
    '''
    cmd = 'system syslog config set --{0} {1}'.format(syslog_config, config_value)
    ret_dict = {}

    valid_resets = ['logdir', 'loghost', 'default-rotate',
                    'default-size', 'default-timeout', 'logdir-unique']
    if syslog_config not in valid_resets:
        ret_dict.update({'success': False,
                         'message': '\'{0}\' is not a valid config variable.'.format(syslog_config)})
        return ret_dict

    response = salt.utils.vmware.esxcli(host, username, password, cmd,
                                        protocol=protocol, port=port,
                                        esxi_host=esxi_host)

    # Update the return dictionary for success or error messages.
    if response['retcode'] != 0:
        ret_dict.update({syslog_config: {'success': False,
                                         'message': response['stdout']}})
    else:
        ret_dict.update({syslog_config: {'success': True}})

    # Restart syslog for each host, if desired.
    if reset_service:
        if esxi_host:
            host_name = esxi_host
            esxi_host = [esxi_host]
        else:
            host_name = host
        response = syslog_service_reload(host, username, password,
                                         protocol=protocol, port=port,
                                         esxi_hosts=esxi_host).get(host_name)
        ret_dict.update({'syslog_restart': {'success': response['retcode'] == 0}})

    return ret_dict


def add_host_to_dvs(host, username, password, vmknic_name, vmnic_name,
                    dvs_name, portgroup_name, protocol=None, port=None,
                    host_names=None):
    '''
    Adds an ESXi host to a vSphere Distributed Virtual Switch
    DOES NOT migrate the ESXi's physical and virtual NICs to the switch (yet)
    (please don't remove the commented code)
    '''
    service_instance = salt.utils.vmware.get_service_instance(host=host,
                                                              username=username,
                                                              password=password,
                                                              protocol=protocol,
                                                              port=port)
    dvs = salt.utils.vmware._get_dvs(service_instance, dvs_name)
    target_portgroup = salt.utils.vmware._get_dvs_portgroup(dvs,
                                                            portgroup_name)
    uplink_portgroup = salt.utils.vmware._get_dvs_uplink_portgroup(dvs,
                                                                   'DSwitch-DVUplinks-34')
    dvs_uuid = dvs.config.uuid
    host_names = _check_hosts(service_instance, host, host_names)

    ret = {}
    for host_name in host_names:
        # try:
        ret[host_name] = {}

        ret[host_name].update({'status': False,
                               'portgroup': portgroup_name,
                               'dvs': dvs_name})
        host_ref = _get_host_ref(service_instance, host, host_name)

        dvs_hostmember_config = vim.dvs.HostMember.ConfigInfo(
            host=host_ref
        )
        dvs_hostmember = vim.dvs.HostMember(
            config=dvs_hostmember_config
        )
        p_nics = salt.utils.vmware._get_pnics(host_ref)
        p_nic = [x for x in p_nics if x.device == 'vmnic0']
        v_nics = salt.utils.vmware._get_vnics(host_ref)
        v_nic = [x for x in v_nics if x.device == vmknic_name]
        v_nic_mgr = salt.utils.vmware._get_vnic_manager(host_ref)

        dvs_pnic_spec = vim.dvs.HostMember.PnicSpec(
            pnicDevice=vmnic_name,
            uplinkPortgroupKey=uplink_portgroup.key
        )
        pnic_backing = vim.dvs.HostMember.PnicBacking(
            pnicSpec=[dvs_pnic_spec]
        )
        dvs_hostmember_config_spec = vim.dvs.HostMember.ConfigSpec(
            host=host_ref,
            operation='add',
        )
        dvs_config = vim.DVSConfigSpec(
                configVersion=dvs.config.configVersion,
                host=[dvs_hostmember_config_spec])
        task = dvs.ReconfigureDvs_Task(spec=dvs_config)
        salt.utils.vmware.wait_for_task(task, host_name,
                                        'Adding host to the DVS',
                                        sleep_seconds=3)

        ret[host_name].update({'status': True})

    return ret
        # # host_network_config.proxySwitch[0].spec.backing.pnicSpec = dvs_pnic_spec
        #
        # network_system = host_ref.configManager.networkSystem
        #
        # host_network_config = network_system.networkConfig
        #
        #
        # orig_portgroup = network_system.networkInfo.portgroup[0]
        # host_portgroup_config = []
        # host_portgroup_config.append(vim.HostPortGroupConfig(
        #     changeOperation='remove',
        #     spec=orig_portgroup.spec
        # ))
        # # host_portgroup_config.append(vim.HostPortGroupConfig(
        # #     changeOperation='add',
        # #     spec=target_portgroup
        # #
        # # ))
        # dvs_port_connection = vim.DistributedVirtualSwitchPortConnection(
        #     portgroupKey=target_portgroup.key, switchUuid=dvs_uuid
        # )
        # host_vnic_spec = vim.HostVirtualNicSpec(
        #         distributedVirtualPort=dvs_port_connection
        # )
        # host_vnic_config = vim.HostVirtualNicConfig(
        #     changeOperation='add',
        #     device=vmknic_name,
        #     portgroup=target_portgroup.key,
        #     spec=host_vnic_spec
        # )
        # host_network_config.proxySwitch[0].spec.backing = pnic_backing
        # host_network_config.portgroup = host_portgroup_config
        # host_network_config.vnic = [host_vnic_config]
        # # host_network_config = vim.HostNetworkConfig(
        # #     portgroup=[host_portgroup_config],
        # #     vnic=[host_vnic_config]
        # # )
        # network_system.UpdateNetworkConfig(changeMode='modify',
        #                                    config=host_network_config)
