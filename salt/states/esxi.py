# -*- coding: utf-8 -*-
'''
Manage VMware ESXi Hosts.

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
:doc:`ESXi Proxy Minion Tutorial </topics/tutorials/esxi_proxy_minion>` for
configuration examples, dependency installation instructions, how to run remote
execution functions against ESXi hosts via a Salt Proxy Minion, and a larger state
example.

'''
# Import Python Libs
from __future__ import absolute_import
import logging

# Import Salt Libs
import salt.utils
from salt.exceptions import CommandExecutionError

# Get Logging Started
log = logging.getLogger(__name__)


def __virtual__():
    return 'esxi.cmd' in __salt__


def coredump_configured(name, enabled, dump_ip, host_vnic='vmk0', dump_port=6500):
    '''
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

    '''
    ret = {'name': name,
           'result': False,
           'changes': {},
           'comment': ''}
    esxi_cmd = 'esxi.cmd'
    enabled_msg = 'ESXi requires that the core dump must be enabled ' \
                  'before any other parameters may be set.'
    host = __pillar__['proxy']['host']

    current_config = __salt__[esxi_cmd]('get_coredump_network_config').get(host)
    error = current_config.get('Error')
    if error:
        ret['comment'] = 'Error: {0}'.format(error)
        return ret

    current_config = current_config.get('Coredump Config')
    current_enabled = current_config.get('enabled')

    # Configure coredump enabled state, if there are changes.
    if current_enabled != enabled:
        enabled_changes = {'enabled': {'old': current_enabled, 'new': enabled}}
        # Only run the command if not using test=True
        if not __opts__['test']:
            response = __salt__[esxi_cmd]('coredump_network_enable',
                                          enabled=enabled).get(host)
            error = response.get('Error')
            if error:
                ret['comment'] = 'Error: {0}'.format(error)
                return ret

            # Allow users to disable core dump, but then return since
            # nothing else can be set if core dump is disabled.
            if not enabled:
                ret['result'] = True
                ret['comment'] = enabled_msg
                ret['changes'].update(enabled_changes)
                return ret

        ret['changes'].update(enabled_changes)

    elif not enabled:
        # If current_enabled and enabled match, but are both False,
        # We must return before configuring anything. This isn't a
        # failure as core dump may be disabled intentionally.
        ret['result'] = True
        ret['comment'] = enabled_msg
        return ret

    # Test for changes with all remaining configurations. The changes flag is used
    # To detect changes, and then set_coredump_network_config is called one time.
    changes = False
    current_ip = current_config.get('ip')
    if current_ip != dump_ip:
        ret['changes'].update({'dump_ip':
                              {'old': current_ip,
                               'new': dump_ip}})
        changes = True

    current_vnic = current_config.get('host_vnic')
    if current_vnic != host_vnic:
        ret['changes'].update({'host_vnic':
                              {'old': current_vnic,
                               'new': host_vnic}})
        changes = True

    current_port = current_config.get('port')
    if current_port != str(dump_port):
        ret['changes'].update({'dump_port':
                              {'old': current_port,
                               'new': str(dump_port)}})
        changes = True

    # Only run the command if not using test=True and changes were detected.
    if not __opts__['test'] and changes is True:
        response = __salt__[esxi_cmd]('set_coredump_network_config',
                                      dump_ip=dump_ip,
                                      host_vnic=host_vnic,
                                      dump_port=dump_port).get(host)
        if response.get('success') is False:
            msg = response.get('stderr')
            if not msg:
                msg = response.get('stdout')
            ret['comment'] = 'Error: {0}'.format(msg)
            return ret

    ret['result'] = True
    if ret['changes'] == {}:
        ret['comment'] = 'Core Dump configuration is already in the desired state.'
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Core dump configuration will change.'

    return ret


def password_present(name, password):
    '''
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
    '''
    ret = {'name': name,
           'result': True,
           'changes': {'old': 'unknown',
                       'new': '********'},
           'comment': 'Host password was updated.'}
    esxi_cmd = 'esxi.cmd'

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Host password will change.'
        return ret
    else:
        try:
            __salt__[esxi_cmd]('update_host_password',
                               new_password=password)
        except CommandExecutionError as err:
            ret['result'] = False
            ret['comment'] = 'Error: {0}'.format(err)
            return ret

    return ret


def ntp_configured(name,
                   service_running,
                   ntp_servers=None,
                   service_policy=None,
                   service_restart=False,
                   update_datetime=False):
    '''
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

    '''
    ret = {'name': name,
           'result': False,
           'changes': {},
           'comment': ''}
    esxi_cmd = 'esxi.cmd'
    host = __pillar__['proxy']['host']
    ntpd = 'ntpd'

    ntp_config = __salt__[esxi_cmd]('get_ntp_config').get(host)
    ntp_running = __salt__[esxi_cmd]('get_service_running',
                                     service_name=ntpd).get(host)
    error = ntp_running.get('Error')
    if error:
        ret['comment'] = 'Error: {0}'.format(error)
        return ret
    ntp_running = ntp_running.get(ntpd)

    # Configure NTP Servers for the Host
    if ntp_servers and set(ntp_servers) != set(ntp_config):
        # Only run the command if not using test=True
        if not __opts__['test']:
            response = __salt__[esxi_cmd]('set_ntp_config',
                                          ntp_servers=ntp_servers).get(host)
            error = response.get('Error')
            if error:
                ret['comment'] = 'Error: {0}'.format(error)
                return ret
        # Set changes dictionary for ntp_servers
        ret['changes'].update({'ntp_servers':
                              {'old': ntp_config,
                               'new': ntp_servers}})

    # Configure service_running state
    if service_running != ntp_running:
        # Only run the command if not using test=True
        if not __opts__['test']:
            # Start ntdp if service_running=True
            if ntp_running is True:
                response = __salt__[esxi_cmd]('service_start',
                                              service_name=ntpd).get(host)
                error = response.get('Error')
                if error:
                    ret['comment'] = 'Error: {0}'.format(error)
                    return ret
            # Stop ntpd if service_running=False
            else:
                response = __salt__[esxi_cmd]('service_stop',
                                              service_name=ntpd).get(host)
                error = response.get('Error')
                if error:
                    ret['comment'] = 'Error: {0}'.format(error)
                    return ret
        ret['changes'].update({'service_running':
                              {'old': ntp_running,
                               'new': service_running}})

    # Configure service_policy
    if service_policy:
        current_service_policy = __salt__[esxi_cmd]('get_service_policy',
                                                    service_name=ntpd).get(host)
        error = current_service_policy.get('Error')
        if error:
            ret['comment'] = 'Error: {0}'.format(error)
            return ret
        current_service_policy = current_service_policy.get(ntpd)

        if service_policy != current_service_policy:
            # Only run the command if not using test=True
            if not __opts__['test']:
                response = __salt__[esxi_cmd]('set_service_policy',
                                              service_name=ntpd,
                                              service_policy=service_policy).get(host)
                error = response.get('Error')
                if error:
                    ret['comment'] = 'Error: {0}'.format(error)
                    return ret
            ret['changes'].update({'service_policy':
                                  {'old': current_service_policy,
                                   'new': service_policy}})

    # Update datetime, if requested.
    if update_datetime:
        # Only run the command if not using test=True
        if not __opts__['test']:
            response = __salt__[esxi_cmd]('update_host_datetime').get(host)
            error = response.get('Error')
            if error:
                ret['comment'] = 'Error: {0}'.format(error)
                return ret
        ret['changes'].update({'update_datetime':
                              {'old': '',
                               'new': 'Host datetime was updated.'}})

    # Restart ntp_service if service_restart=True
    if service_restart:
        # Only run the command if not using test=True
        if not __opts__['test']:
            response = __salt__[esxi_cmd]('service_restart',
                                          service_name=ntpd).get(host)
            error = response.get('Error')
            if error:
                ret['comment'] = 'Error: {0}'.format(error)
                return ret
        ret['changes'].update({'service_restart':
                              {'old': '',
                               'new': 'NTP Daemon Restarted.'}})

    ret['result'] = True
    if ret['changes'] == {}:
        ret['comment'] = 'NTP is already in the desired state.'
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'NTP state will change.'

    return ret


def vmotion_configured(name, enabled, device='vmk0'):
    '''
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

    '''
    ret = {'name': name,
           'result': False,
           'changes': {},
           'comment': ''}
    esxi_cmd = 'esxi.cmd'
    host = __pillar__['proxy']['host']

    current_vmotion_enabled = __salt__[esxi_cmd]('get_vmotion_enabled').get(host)
    current_vmotion_enabled = current_vmotion_enabled.get('VMotion Enabled')

    # Configure VMotion Enabled state, if changed.
    if enabled != current_vmotion_enabled:
        # Only run the command if not using test=True
        if not __opts__['test']:
            # Enable VMotion if enabled=True
            if enabled is True:
                response = __salt__[esxi_cmd]('vmotion_enable',
                                              device=device).get(host)
                error = response.get('Error')
                if error:
                    ret['comment'] = 'Error: {0}'.format(error)
                    return ret
            # Disable VMotion if enabled=False
            else:
                response = __salt__[esxi_cmd]('vmotion_disable').get(host)
                error = response.get('Error')
                if error:
                    ret['comment'] = 'Error: {0}'.format(error)
                    return ret
        ret['changes'].update({'enabled':
                              {'old': current_vmotion_enabled,
                               'new': enabled}})

    ret['result'] = True
    if ret['changes'] == {}:
        ret['comment'] = 'VMotion configuration is already in the desired state.'
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'VMotion configuration will change.'

    return ret


def vsan_configured(name, enabled, add_disks_to_vsan=False):
    '''
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

    '''
    ret = {'name': name,
           'result': False,
           'changes': {},
           'comment': ''}
    esxi_cmd = 'esxi.cmd'
    host = __pillar__['proxy']['host']

    current_vsan_enabled = __salt__[esxi_cmd]('get_vsan_enabled').get(host)
    error = current_vsan_enabled.get('Error')
    if error:
        ret['comment'] = 'Error: {0}'.format(error)
        return ret
    current_vsan_enabled = current_vsan_enabled.get('VSAN Enabled')

    # Configure VSAN Enabled state, if changed.
    if enabled != current_vsan_enabled:
        # Only run the command if not using test=True
        if not __opts__['test']:
            # Enable VSAN if enabled=True
            if enabled is True:
                response = __salt__[esxi_cmd]('vsan_enable').get(host)
                error = response.get('Error')
                if error:
                    ret['comment'] = 'Error: {0}'.format(error)
                    return ret
            # Disable VSAN if enabled=False
            else:
                response = __salt__[esxi_cmd]('vsan_disable').get(host)
                error = response.get('Error')
                if error:
                    ret['comment'] = 'Error: {0}'.format(error)
                    return ret
        ret['changes'].update({'enabled':
                              {'old': current_vsan_enabled,
                               'new': enabled}})

    # Add any eligible disks to VSAN, if requested.
    if add_disks_to_vsan:
        current_eligible_disks = __salt__[esxi_cmd]('get_vsan_eligible_disks').get(host)
        error = current_eligible_disks.get('Error')
        if error:
            ret['comment'] = 'Error: {0}'.format(error)
            return ret

        disks = current_eligible_disks.get('Eligible')
        if disks and isinstance(disks, list):
            # Only run the command if not using test=True
            if not __opts__['test']:
                response = __salt__[esxi_cmd]('vsan_add_disks').get(host)
                error = response.get('Error')
                if error:
                    ret['comment'] = 'Error: {0}'.format(error)
                    return ret

            ret['changes'].update({'add_disks_to_vsan':
                                  {'old': '',
                                   'new': disks}})

    ret['result'] = True
    if ret['changes'] == {}:
        ret['comment'] = 'VSAN configuration is already in the desired state.'
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'VSAN configuration will change.'

    return ret


def ssh_configured(name,
                   service_running,
                   ssh_key=None,
                   ssh_key_file=None,
                   service_policy=None,
                   service_restart=False,
                   certificate_verify=False):
    '''
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
        Default is ``False``.

    Example:

    .. code-block:: yaml

        configure-host-ssh:
          esxi.ssh_configured:
            - service_running: True
            - ssh_key_file: /etc/salt/ssh_keys/my_key.pub
            - service_policy: 'on'
            - service_restart: True
            - certificate_verify: True

    '''
    ret = {'name': name,
           'result': False,
           'changes': {},
           'comment': ''}
    esxi_cmd = 'esxi.cmd'
    host = __pillar__['proxy']['host']
    ssh = 'ssh'

    ssh_running = __salt__[esxi_cmd]('get_service_running',
                                     service_name=ssh).get(host)
    error = ssh_running.get('Error')
    if error:
        ret['comment'] = 'Error: {0}'.format(error)
        return ret
    ssh_running = ssh_running.get(ssh)

    # Configure SSH service_running state, if changed.
    if service_running != ssh_running:
        # Only actually run the command if not using test=True
        if not __opts__['test']:
            # Start SSH if service_running=True
            if service_running is True:
                enable = __salt__[esxi_cmd]('service_start',
                                            service_name=ssh).get(host)
                error = enable.get('Error')
                if error:
                    ret['comment'] = 'Error: {0}'.format(error)
                    return ret
            # Disable SSH if service_running=False
            else:
                disable = __salt__[esxi_cmd]('service_stop',
                                             service_name=ssh).get(host)
                error = disable.get('Error')
                if error:
                    ret['comment'] = 'Error: {0}'.format(error)
                    return ret

        ret['changes'].update({'service_running':
                              {'old': ssh_running,
                               'new': service_running}})

    # If uploading an SSH key or SSH key file, see if there's a current
    # SSH key and compare the current key to the key set in the state.
    current_ssh_key, ssh_key_changed = None, False
    if ssh_key or ssh_key_file:
        current_ssh_key = __salt__[esxi_cmd]('get_ssh_key',
                                             certificate_verify=certificate_verify)
        error = current_ssh_key.get('Error')
        if error:
            ret['comment'] = 'Error: {0}'.format(error)
            return ret
        current_ssh_key = current_ssh_key.get('key')
        if current_ssh_key:
            clean_current_key = _strip_key(current_ssh_key).split(' ')
            if not ssh_key:
                ssh_key = ''
                # Open ssh key file and read in contents to create one key string
                with salt.utils.fopen(ssh_key_file, 'r') as key_file:
                    for line in key_file:
                        if line.startswith('#'):
                            # Commented line
                            continue
                        ssh_key = ssh_key + line

            clean_ssh_key = _strip_key(ssh_key).split(' ')
            # Check that the first two list items of clean key lists are equal.
            if clean_current_key[0] != clean_ssh_key[0] or clean_current_key[1] != clean_ssh_key[1]:
                ssh_key_changed = True
        else:
            # If current_ssh_key is None, but we're setting a new key with
            # either ssh_key or ssh_key_file, then we need to flag the change.
            ssh_key_changed = True

    # Upload SSH key, if changed.
    if ssh_key_changed:
        if not __opts__['test']:
            # Upload key
            response = __salt__[esxi_cmd]('upload_ssh_key',
                                          ssh_key=ssh_key,
                                          ssh_key_file=ssh_key_file,
                                          certificate_verify=certificate_verify)
            error = response.get('Error')
            if error:
                ret['comment'] = 'Error: {0}'.format(error)
                return ret
        ret['changes'].update({'SSH Key':
                              {'old': current_ssh_key,
                               'new': ssh_key if ssh_key else ssh_key_file}})

    # Configure service_policy
    if service_policy:
        current_service_policy = __salt__[esxi_cmd]('get_service_policy',
                                                    service_name=ssh).get(host)
        error = current_service_policy.get('Error')
        if error:
            ret['comment'] = 'Error: {0}'.format(error)
            return ret
        current_service_policy = current_service_policy.get(ssh)

        if service_policy != current_service_policy:
            # Only run the command if not using test=True
            if not __opts__['test']:
                response = __salt__[esxi_cmd]('set_service_policy',
                                              service_name=ssh,
                                              service_policy=service_policy).get(host)
                error = response.get('Error')
                if error:
                    ret['comment'] = 'Error: {0}'.format(error)
                    return ret
            ret['changes'].update({'service_policy':
                                  {'old': current_service_policy,
                                   'new': service_policy}})

    # Restart ssh_service if service_restart=True
    if service_restart:
        # Only run the command if not using test=True
        if not __opts__['test']:
            response = __salt__[esxi_cmd]('service_restart',
                                          service_name=ssh).get(host)
            error = response.get('Error')
            if error:
                ret['comment'] = 'Error: {0}'.format(error)
                return ret
        ret['changes'].update({'service_restart':
                              {'old': '',
                               'new': 'SSH service restarted.'}})

    ret['result'] = True
    if ret['changes'] == {}:
        ret['comment'] = 'SSH service is already in the desired state.'
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'SSH service state will change.'

    return ret


def syslog_configured(name,
                      syslog_configs,
                      firewall=True,
                      reset_service=True,
                      reset_syslog_config=False,
                      reset_configs=None):
    '''
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
        Resets the syslog service to it's default settings. Defaults to ``False``.
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
    '''
    ret = {'name': name,
           'result': False,
           'changes': {},
           'comment': ''}
    esxi_cmd = 'esxi.cmd'
    host = __pillar__['proxy']['host']

    if reset_syslog_config:
        if not reset_configs:
            reset_configs = 'all'
        # Only run the command if not using test=True
        if not __opts__['test']:
            reset = __salt__[esxi_cmd]('reset_syslog_config',
                                       syslog_config=reset_configs).get(host)
            for key, val in reset.iteritems():
                if isinstance(val, bool):
                    continue
                if not val.get('success'):
                    msg = val.get('message')
                    if not msg:
                        msg = 'There was an error resetting a syslog config \'{0}\'.' \
                              'Please check debug logs.'.format(val)
                    ret['comment'] = 'Error: {0}'.format(msg)
                    return ret

        ret['changes'].update({'reset_syslog_config':
                              {'old': '',
                               'new': reset_configs}})

    current_firewall = __salt__[esxi_cmd]('get_firewall_status').get(host)
    error = current_firewall.get('Error')
    if error:
        ret['comment'] = 'Error: {0}'.format(error)
        return ret

    current_firewall = current_firewall.get('rulesets').get('syslog')
    if current_firewall != firewall:
        # Only run the command if not using test=True
        if not __opts__['test']:
            enabled = __salt__[esxi_cmd]('enable_firewall_ruleset',
                                         ruleset_enable=firewall,
                                         ruleset_name='syslog').get(host)
            if enabled.get('retcode') != 0:
                err = enabled.get('stderr')
                out = enabled.get('stdout')
                ret['comment'] = 'Error: {0}'.format(err if err else out)
                return ret

        ret['changes'].update({'firewall':
                              {'old': current_firewall,
                               'new': firewall}})

    current_syslog_config = __salt__[esxi_cmd]('get_syslog_config').get(host)
    for key, val in syslog_configs.iteritems():
        # The output of get_syslog_config has different keys than the keys
        # Used to set syslog_config values. We need to look them up first.
        try:
            lookup_key = _lookup_syslog_config(key)
        except KeyError:
            ret['comment'] = '\'{0}\' is not a valid config variable.'.format(key)
            return ret

        current_val = current_syslog_config[lookup_key]
        if str(current_val) != str(val):
            # Only run the command if not using test=True
            if not __opts__['test']:
                response = __salt__[esxi_cmd]('set_syslog_config',
                                              syslog_config=key,
                                              config_value=val,
                                              firewall=firewall,
                                              reset_service=reset_service).get(host)
                success = response.get(key).get('success')
                if not success:
                    msg = response.get(key).get('message')
                    if not msg:
                        msg = 'There was an error setting syslog config \'{0}\'. ' \
                              'Please check debug logs.'.format(key)
                    ret['comment'] = msg
                    return ret

            if not ret['changes'].get('syslog_config'):
                ret['changes'].update({'syslog_config': {}})
            ret['changes']['syslog_config'].update({key:
                                                   {'old': current_val,
                                                    'new': val}})

    ret['result'] = True
    if ret['changes'] == {}:
        ret['comment'] = 'Syslog is already in the desired state.'
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Syslog state will change.'

    return ret


def _lookup_syslog_config(config):
    '''
    Helper function that looks up syslog_config keys available from
    ``vsphere.get_syslog_config``.
    '''
    lookup = {'default-timeout': 'Default Network Retry Timeout',
              'logdir': 'Local Log Output',
              'default-size': 'Local Logging Default Rotation Size',
              'logdir-unique': 'Log To Unique Subdirectory',
              'default-rotate': 'Local Logging Default Rotations',
              'loghost': 'Remote Host'}

    return lookup.get(config)


def _strip_key(key_string):
    '''
    Strips an SSH key string of white space and line endings and returns the new string.

    key_string
        The string to be stripped.
    '''
    key_string.strip()
    key_string.replace('\n', '')
    key_string.replace('\r\n', '')
    return key_string
