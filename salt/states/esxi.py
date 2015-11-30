# -*- coding: utf-8 -*-
'''
Manage VMware ESXi Hosts.

.. versionadded:: 2015.8.4
'''
# Import Python Libs
from __future__ import absolute_import
import logging

# Get Logging Started
log = logging.getLogger(__name__)


def __virtual__():
    return 'esxi.cmd' in __salt__


def ntp_configured(name,
                   ntp_service,
                   ntp_servers=None,
                   ntp_service_policy=None,
                   ntp_service_restart=False):
    '''
    Ensures a host's NTP server configuration such as setting NTP servers, ensuring the
    NTP daemon is running or stopped, or restarting the NTP daemon for the ESXi host.

    name
        Name of the state.

    ntp_service
        Ensures the running state of the ntp deamon for the host. Boolean value where
        ``True`` indicates that ntpd should be running and ``False`` indicates that it
        should be stopped.

    ntp_servers
        A list of servers that should be added to the ESXi host's NTP configuration.

    ntp_service_policy
        The policy to set for the NTP service.

    ntp_service_restart
        If set to ``True``, the ntp daemon will be restarted, regardless of its previous
        running state. Default is ``False``.

    Example:

    .. code-block:: yaml

        configure-host-ntp:
          esxi.ntp_configured:
            - ntp_service: True
            - ntp_servers: [192.174.1.100, 192.174.1.200]
            - ntp_service_policy: 'automatic'
            - ntp_service_restart: True

    '''
    ret = {'name': name,
           'result': False,
           'changes': {},
           'comment': ''}
    esxi_cmd = 'esxi.cmd'
    host = __pillar__['proxy']['host']

    ntp_config = __salt__[esxi_cmd]('get_ntp_config').get(host)
    ntp_running = __salt__[esxi_cmd]('get_service_running')(service_running='ntpd').get(host)
    error = ntp_running.get('Error')
    if error:
        ret['comment'] = 'Error: {0}'.format(error)
        return ret

    # Configure NTP Servers for the Host
    if ntp_servers and set(ntp_servers) != set(ntp_config):
        # Only run the command if not using test=True
        if not __opts__['test']:
            response = __salt__[esxi_cmd]('set_ntp_config')(ntp_servers=ntp_servers).get(host)
            error = response.get('Error')
            if error:
                ret['comment'] = 'Error: {0}'.format(error)
                return ret
        # Set changes dictionary for ntp_servers
        ret['changes'].update({'ntp_servers':
                              {'old': ntp_config,
                               'new': ntp_servers}})

    # Configure ntp_service state
    if ntp_service != ntp_running:
        # Only run the command if not using test=True
        if not __opts__['test']:
            # Start ntdp if ntp_service=True
            if ntp_running is True:
                response = __salt__[esxi_cmd]('ntp_start')().get(host)
                error = response.get('Error')
                if error:
                    ret['comment'] = 'Error: {0}'.format(error)
                    return ret
            # Stop ntpd if ntp_service=False
            else:
                response = __salt__[esxi_cmd]('ntp_stop')().get(host)
                error = response.get('Error')
                if error:
                    ret['comment'] = 'Error: {0}'.format(error)
                    return ret
        ret['changes'].update({'ntp_service':
                              {'old': ntp_running,
                               'new': ntp_service}})

    # Configure ntp_service_policy
    if ntp_service_policy:
        current_service_policy = __salt__[esxi_cmd]('get_service_policy')(service_name='ntpd').get(host)
        error = current_service_policy.get('Error')
        if error:
            ret['comment'] = 'Error: {0}'.format(error)
            return ret

        if ntp_service_policy != current_service_policy:
            # Only run the command if not using test=True
            if not __opts__['test']:
                response = __salt__[esxi_cmd]('set_service_policy')(service_name='ntpd',
                                                                    service_policy=ntp_service_policy).get(host)
                error = response.get('Error')
                if error:
                    ret['comment'] = 'Error: {0}'.format(error)
                    return ret
            ret['changes'].update({'ntp_service_policy':
                                  {'old': current_service_policy,
                                   'new': ntp_service_policy}})

    # Restart ntp_service if ntp_service_restart=True
    if ntp_service_restart:
        # Only run the command if not using test=True
        if not __opts__['test']:
            response = __salt__[esxi_cmd]('ntp_restart')().get(host)
            error = response.get('Error')
            if error:
                ret['comment'] = 'Error: {0}'.format(error)
                return ret
        ret['changes'].update({'ntp_service_restart':
                              {'old': ntp_running,
                               'new': 'NTP Deamon Restarted.'}})

    ret['result'] = True
    if ret['changes'] == {}:
        ret['comment'] = 'NTP is already in the desired state.'
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'NTP state will change.'

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
            - vsan_enabled: True
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

    # Configure VSAN Enabled state, if changed.
    if enabled != current_vsan_enabled:
        # Only run the command if not using test=True
        if not __opts__['test']:
            # Enable VSAN if enabled=True
            if enabled is True:
                response = __salt__[esxi_cmd]('vsan_enable')().get(host)
                error = response.get('Error')
                if error:
                    ret['comment'] = 'Error: {0}'.format(error)
                    return ret
            # Disable VSAN if enabled=False
            else:
                response = __salt__[esxi_cmd]('vsan_disable')().get(host)
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
            ret['changes'].update({'add_disks_to_vsan':
                                  {'old': '',
                                   'new': disks}})

            # Only run the command if not using test=True
            if not __opts__['test']:
                response = __salt__[esxi_cmd]('vsan_add_disks')().get(host)
                error = response.get('Error')
                if error:
                    ret['comment'] = 'Error: {0}'.format(error)
                    return ret

    ret['result'] = True
    if ret['changes'] == {}:
        ret['comment'] = 'VSAN configuration is already in the desired state.'
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'VSAN configuration will change.'

    return ret


def ssh_configured(name,
                   enabled,
                   ssh_key=None,
                   ssh_key_file=None,
                   certificate_verify=False,
                   ssh_service_restart=False):
    '''
    Manage the SSH configuration for a host including whether or not SSH is enabled and
    running, or the presence of a given SSH key. Note: Only one ssh key can be uploaded
    for root. Uploading a second key will replace any existing key.

    name
        Name of the state.

    enabled
        Ensures whether or not the SSH service should be enabled and running on a host
        as a boolean value where ``True`` indicates that SSH should be enabled and
        running and ``False`` indicates that SSH should be disabled and stopped.

    ssh_key
        Public SSH key to added to the authorized_keys file on the ESXi host. You can
        use ``ssh_key`` or ``ssh_key_file``, but not both.

    ssh_key_file
        File containing the public SSH key to be added to the authorized_keys file on
        the ESXi host. You can use ``ssh_key_file`` or ``ssh_key``, but not both.

    certificate_verify
        If set to ``True``, the SSL connection must present a valid certificate.
        Default is ``False``.

    ssh_service_restart
        If set to ``True``, the SSH service will be restarted, regardless of its
        previous running state. Default is ``False``.

    Example:

    .. code-block:: yaml

        configure-host-ssh:
          esxi.ssh_configured:
            - enabled: True
            - ssh_key_file: /etc/salt/ssh_keys/my_key.pub
            - certificate_verify: True

    '''
    ret = {'name': name,
           'result': False,
           'changes': {},
           'comment': ''}
    esxi_cmd = 'esxi.cmd'
    host = __pillar__['proxy']['host']

    ssh_running = __salt__[esxi_cmd]('get_service_running')(service_running='SSH').get(host)
    error = ssh_running.get('Error')
    if error:
        ret['comment'] = 'Error: {0}'.format(error)
        return ret

    # If uploading an SSH key or SSH key file, see if there's a current
    # SSH key and compare the current key to the key set in the state.
    # TODO: Figure out how to compare keys properly
    current_ssh_key, ssh_key_changed = None, None
    if ssh_key or ssh_key_file:
        current_ssh_key = __salt__[esxi_cmd]('get_ssh_key')(
            certificate_verify=certificate_verify
        ).get(host)
        error = current_ssh_key.get('Error')
        if error:
            ret['comment'] = 'Error: {0}'.format(error)
            return ret
        current_ssh_key = current_ssh_key.get('key')

    # Configure SSH enabled state, if changed.
    if enabled != ssh_running:
        # Only actually run the command if not using test=True
        if not __opts__['test']:
            # Enable SSH if enabled=True
            if enabled is True:
                enable = __salt__[esxi_cmd]('ssh_enable')().get(host)
                error = enable.get('Error')
                if error:
                    ret['comment'] = 'Error: {0}'.format(error)
                    return ret
            # Disable SSH if enabled=False
            else:
                disable = __salt__[esxi_cmd]('ssh_disable')().get(host)
                error = disable.get('Error')
                if error:
                    ret['comment'] = 'Error: {0}'.format(error)
                    return ret

        ret['changes'].update({'SSH Enabled':
                              {'old': ssh_running,
                               'new': enabled}})

    # Upload SSH key, if changed.
    if ssh_key_changed:
        if not __opts__['test']:
            # Upload key
            response = __salt__[esxi_cmd]('upload_ssh_key')(ssh_key=ssh_key,
                                                            ssh_key_file=ssh_key_file,
                                                            certificate_verify=certificate_verify).get(host)
            error = response.get('Error')
            if error:
                ret['comment'] = 'Error: {0}'.format(error)
                return ret
        ret['changes'].update({'SSH Key':
                              {'old': current_ssh_key,
                               'new': ssh_key if ssh_key else ssh_key_file}})

    # Restart ssh_service if ssh_service_restart=True
    if ssh_service_restart:
        # Only run the command if not using test=True
        if not __opts__['test']:
            response = __salt__[esxi_cmd]('ssh_restart')().get(host)
            error = response.get('Error')
            if error:
                ret['comment'] = 'Error: {0}'.format(error)
                return ret
        ret['changes'].update({'ssh_service_restart':
                              {'old': ssh_running,
                               'new': 'SSH service restarted.'}})

    ret['result'] = True
    if ret['changes'] == {}:
        ret['comment'] = 'SSH service is already in the desired state.'
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'SSH service state will change.'

    return ret
