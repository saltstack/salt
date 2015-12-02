# -*- coding: utf-8 -*-
'''
Manage VMware ESXi Hosts.

.. versionadded:: 2015.8.4
'''
# Import Python Libs
from __future__ import absolute_import
import logging

# Import Salt Libs
import salt.utils
import salt.ext.six as six
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
        any other parameters may be set.

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
            - dump_ip: 'my-coredump-ip.example.com`

    '''
    ret = {'name': name,
           'result': False,
           'changes': {},
           'comment': ''}
    esxi_cmd = 'esxi.cmd'
    enabled_msg = 'ESXi requires that the core dump must be enabled ' \
                  'before any other parameters may be set.'

    current_config = __salt__[esxi_cmd]('get_coredump_network_config')
    if isinstance(current_config, six.string_types):
        ret['comment'] = 'Error: {0}'.format(current_config)
        return ret
    elif ret.get('stderr'):
        ret['comment'] = 'Error: {0}'.format(ret.get('stderr'))
        return ret
    else:
        current_enabled = current_config.get('enabled')

    if current_enabled != enabled:
        ret['changes'].update({'enabled':
                              {'old': current_enabled,
                               'new': enabled}})
        # Only run the command if not using test=True
        if not __opts__['test']:
            ret = __salt__[esxi_cmd]('coredump_network_enable')(enabled=enabled)
            if ret['retcode'] != 0:
                ret['comment'] = 'Error: {0}'.format(ret['stderr'])
                return ret

            # Allow users to disable core dump, but then return since
            # nothing else can be set if core dump is disabled.
            if not enabled:
                ret['result'] = True
                ret['comment'] = enabled_msg
                return ret

    elif not enabled:
        # If current_enabled and enabled match, but are both False,
        # We must return before configuring anything. This isn't a
        # failure as core dump may be disabled intentionally.
        ret['result'] = True
        ret['comment'] = enabled_msg
        return ret

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
    if current_port != dump_port:
        ret['changes'].update({'dump_port':
                              {'old': current_port,
                               'new': dump_port}})
        changes = True

    # Only run the command if not using test=True and changes were detected.
    if not __opts__['test'] and changes is True:
        ret = __salt__[esxi_cmd]('set_coredump_network_config')(dump_ip=dump_ip,
                                                                host_vnic=host_vnic,
                                                                dump_port=dump_port)
        if ret.get('success') is False:
            ret['comment'] = 'Error {0}'.format(ret.get('stderr'))
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
            - user: 'root'
            - password: 'new-bad-password'
    '''
    ret = {'name': name,
           'result': True,
           'changes': {'old': 'unknown',
                       'new': '********'},
           'comment': 'Host password was updated.'}
    esxi_cmd = 'esxi.cmd'
    host = __pillar__['proxy']['host']

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Host password will change.'
        return ret
    else:
        try:
            __salt__[esxi_cmd]('update_host_password')(new_password=password).get(host)
        except CommandExecutionError as err:
            ret['result'] = False
            ret['comment'] = 'Error: {0}'.format(err)
            return ret

    return ret


def ntp_configured(name,
                   ntp_service,
                   ntp_servers=None,
                   ntp_service_policy=None,
                   update_datetime=False,
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

    update_datetime
        If set to ``True``, the date/time on the given host will be updated to UTC.
        Default setting is ``False``. This option should be used with caution since
        network delays and execution delays can result in time skews.

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
    ntp_running = __salt__[esxi_cmd]('get_service_running')(service_name='ntpd').get(host)
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

        In order to update SSH keys, the SSH service must be enabled.

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

    ssh_running = __salt__[esxi_cmd]('get_service_running')(service_name='SSH').get(host)
    error = ssh_running.get('Error')
    if error:
        ret['comment'] = 'Error: {0}'.format(error)
        return ret

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

    # If uploading an SSH key or SSH key file, see if there's a current
    # SSH key and compare the current key to the key set in the state.
    current_ssh_key, ssh_key_changed = None, False
    if ssh_key or ssh_key_file:
        current_ssh_key = __salt__[esxi_cmd]('get_ssh_key')(
            certificate_verify=certificate_verify
        ).get(host)
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

    syslog_config
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
        List of parameters to reset. Only runs if ``reset_syslog_config`` is set
        to ``True``. If ``reset_syslog_config`` is set to ``True``, but no syslog
        configs are listed in ``reset_configs``, then ``reset_configs`` will be
        to ``all`` by default.

        See ``syslog_configs`` parameter above for a list of valid syslog_config
        values.

    Example:

    .. code-block:: yaml

        configure-host-syslog:
          esxi.syslog_configured:
            - syslog_config:
              - loghost: ssl://localhost:5432,tcp://10.1.0.1:1514
              - default-timeout: 120
            - firewall: True
            - reset_service: True
            - reset_syslog_config: True
            - reset_configs:
              - loghost
              - default-timeout
    '''
    ret = {'name': name,
           'result': False,
           'changes': {},
           'comment': ''}
    esxi_cmd = 'esxi.cmd'

    if reset_syslog_config:
        if not reset_configs:
            reset_configs = 'all'
        # Only run the command if not using test=True
        if not __opts__['test']:
            reset = __salt__[esxi_cmd]('reset_syslog_config')(syslog_config=reset_configs)
            for key, val in reset.iteritems():
                if not val.get('success'):
                    msg = val.get('message')
                    if not msg:
                        msg = 'There was an error resetting a syslog config. ' \
                              'Please check debug logs.'
                    ret['comment'] = 'Error: {0}'.format(msg)
                    return ret

        ret['changes'].update({'reset_syslog_config':
                              {'old': '',
                               'new': reset_configs}})

    current_firewall = __salt__[esxi_cmd]('get_firewall_status')
    if not current_firewall.get('success'):
        ret['comment'] = 'There was an error obtaining firewall statuses. ' \
                         'Please check debug logs.'
        return ret

    current_firewall = current_firewall.get('rulesets').get('syslog')
    if current_firewall != firewall:
        # Only run the command if not using test=True
        if not __opts__['test']:
            enabled = __salt__[esxi_cmd]('enable_firewall_ruleset')(ruleset_enable=firewall,
                                                                    ruleset_name='syslog')
            if enabled.get('retcode') != 0:
                err = enabled.get('stderr')
                out = enabled.get('stdout')
                ret['comment'] = 'Error: {0}'.format(err if err else out)
                return ret

        ret['changes'].update({'firewall':
                              {'old': current_firewall,
                               'new': firewall}})

    current_syslog_config = __salt__[esxi_cmd]('get_syslog_config')
    for key, val in syslog_configs.iteritems():
        # The output of get_syslog_config has different keys than the keys
        # Used to set syslog_config values. We need to look them up first.
        try:
            lookup_key = _lookup_syslog_config(key)
        except KeyError:
            ret['comment'] = '\'{0}\' is not a valid config variable.'.format(key)
            return ret

        current_val = current_syslog_config[lookup_key]
        if current_val != val:
            # Only run the command if not using test=True
            if not __opts__['test']:
                response = __salt__[esxi_cmd]('set_syslog_config')(syslog_config=key,
                                                                   config_value=val,
                                                                   firewall=firewall,
                                                                   reset_service=reset_service)
                success = response.get('success')
                if not success:
                    msg = response.get('message')
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
