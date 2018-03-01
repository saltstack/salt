# -*- coding: utf-8 -*-
'''
Module for configuring Windows Firewall using ``netsh``
'''
from __future__ import absolute_import, unicode_literals, print_function

# Import Python libs
import re

# Import Salt libs
import salt.utils.platform
from salt.exceptions import CommandExecutionError

# Define the module's virtual name
__virtualname__ = 'firewall'


def __virtual__():
    '''
    Only works on Windows systems
    '''
    if not salt.utils.platform.is_windows():
        return False, "Module win_firewall: module only available on Windows"

    return __virtualname__


def get_config():
    '''
    Get the status of all the firewall profiles

    Returns:
        dict: A dictionary of all profiles on the system

    Raises:
        CommandExecutionError: If the command fails

    CLI Example:

    .. code-block:: bash

        salt '*' firewall.get_config
    '''
    profiles = {}
    curr = None

    cmd = ['netsh', 'advfirewall', 'show', 'allprofiles']
    ret = __salt__['cmd.run_all'](cmd, python_shell=False, ignore_retcode=True)
    if ret['retcode'] != 0:
        raise CommandExecutionError(ret['stdout'])

    # There may be some problems with this depending on how `netsh` is localized
    # It's looking for lines that contain `Profile Settings` or start with
    # `State` which may be different in different localizations
    for line in ret['stdout'].splitlines():
        if not curr:
            tmp = re.search('(.*) Profile Settings:', line)
            if tmp:
                curr = tmp.group(1)
        elif line.startswith('State'):
            profiles[curr] = line.split()[1] == 'ON'
            curr = None

    return profiles


def disable(profile='allprofiles'):
    '''
    Disable firewall profile

    Args:
        profile (Optional[str]): The name of the profile to disable. Default is
            ``allprofiles``. Valid options are:

            - allprofiles
            - domainprofile
            - privateprofile
            - publicprofile

    Returns:
        bool: True if successful

    Raises:
        CommandExecutionError: If the command fails

    CLI Example:

    .. code-block:: bash

        salt '*' firewall.disable
    '''
    cmd = ['netsh', 'advfirewall', 'set', profile, 'state', 'off']
    ret = __salt__['cmd.run_all'](cmd, python_shell=False, ignore_retcode=True)
    if ret['retcode'] != 0:
        raise CommandExecutionError(ret['stdout'])

    return True


def enable(profile='allprofiles'):
    '''
    .. versionadded:: 2015.5.0

    Enable firewall profile

    Args:
        profile (Optional[str]): The name of the profile to enable. Default is
            ``allprofiles``. Valid options are:

            - allprofiles
            - domainprofile
            - privateprofile
            - publicprofile

    Returns:
        bool: True if successful

    Raises:
        CommandExecutionError: If the command fails

    CLI Example:

    .. code-block:: bash

        salt '*' firewall.enable
    '''
    cmd = ['netsh', 'advfirewall', 'set', profile, 'state', 'on']
    ret = __salt__['cmd.run_all'](cmd, python_shell=False, ignore_retcode=True)
    if ret['retcode'] != 0:
        raise CommandExecutionError(ret['stdout'])

    return True


def get_rule(name='all'):
    '''
    .. versionadded:: 2015.5.0

    Display all matching rules as specified by name

    Args:
        name (Optional[str]): The full name of the rule. ``all`` will return all
            rules. Default is ``all``

    Returns:
        dict: A dictionary of all rules or rules that match the name exactly

    Raises:
        CommandExecutionError: If the command fails

    CLI Example:

    .. code-block:: bash

        salt '*' firewall.get_rule 'MyAppPort'
    '''
    cmd = ['netsh', 'advfirewall', 'firewall', 'show', 'rule',
           'name={0}'.format(name)]
    ret = __salt__['cmd.run_all'](cmd, python_shell=False, ignore_retcode=True)
    if ret['retcode'] != 0:
        raise CommandExecutionError(ret['stdout'])

    return {name: ret['stdout']}


def add_rule(name, localport, protocol='tcp', action='allow', dir='in',
             remoteip='any'):
    '''
    .. versionadded:: 2015.5.0

    Add a new inbound or outbound rule to the firewall policy

    Args:

        name (str): The name of the rule. Must be unique and cannot be "all".
            Required.

        localport (int): The port the rule applies to. Must be a number between
            0 and 65535. Can be a range. Can specify multiple ports separated by
            commas. Required.

        protocol (Optional[str]): The protocol. Can be any of the following:

            - A number between 0 and 255
            - icmpv4
            - icmpv6
            - tcp
            - udp
            - any

        action (Optional[str]): The action the rule performs. Can be any of the
            following:

            - allow
            - block
            - bypass

        dir (Optional[str]): The direction. Can be ``in`` or ``out``.

        remoteip (Optional [str]): The remote IP. Can be any of the following:

            - any
            - localsubnet
            - dns
            - dhcp
            - wins
            - defaultgateway
            - Any valid IPv4 address (192.168.0.12)
            - Any valid IPv6 address (2002:9b3b:1a31:4:208:74ff:fe39:6c43)
            - Any valid subnet (192.168.1.0/24)
            - Any valid range of IP addresses (192.168.0.1-192.168.0.12)
            - A list of valid IP addresses

            Can be combinations of the above separated by commas.

    Returns:
        bool: True if successful

    Raises:
        CommandExecutionError: If the command fails

    CLI Example:

    .. code-block:: bash

        salt '*' firewall.add_rule 'test' '8080' 'tcp'
        salt '*' firewall.add_rule 'test' '1' 'icmpv4'
        salt '*' firewall.add_rule 'test_remote_ip' '8000' 'tcp' 'allow' 'in' '192.168.0.1'
    '''
    cmd = ['netsh', 'advfirewall', 'firewall', 'add', 'rule',
           'name={0}'.format(name),
           'protocol={0}'.format(protocol),
           'dir={0}'.format(dir),
           'action={0}'.format(action),
           'remoteip={0}'.format(remoteip)]

    if protocol is None \
            or ('icmpv4' not in protocol and 'icmpv6' not in protocol):
        cmd.append('localport={0}'.format(localport))

    ret = __salt__['cmd.run_all'](cmd, python_shell=False, ignore_retcode=True)
    if ret['retcode'] != 0:
        raise CommandExecutionError(ret['stdout'])

    return True


def delete_rule(name=None,
                localport=None,
                protocol=None,
                dir=None,
                remoteip=None):
    '''
    .. versionadded:: 2015.8.0

    Delete an existing firewall rule identified by name and optionally by ports,
    protocols, direction, and remote IP.

    Args:

        name (str): The name of the rule to delete. If the name ``all`` is used
            you must specify additional parameters.

        localport (Optional[str]): The port of the rule. If protocol is not
            specified, protocol will be set to ``tcp``

        protocol (Optional[str]): The protocol of the rule. Default is ``tcp``
            when ``localport`` is specified

        dir (Optional[str]): The direction of the rule.

        remoteip (Optional[str]): The remote IP of the rule.

    Returns:
        bool: True if successful

    Raises:
        CommandExecutionError: If the command fails

    CLI Example:

    .. code-block:: bash

        # Delete incoming tcp port 8080 in the rule named 'test'
        salt '*' firewall.delete_rule 'test' '8080' 'tcp' 'in'

        # Delete the incoming tcp port 8000 from 192.168.0.1 in the rule named
        # 'test_remote_ip`
        salt '*' firewall.delete_rule 'test_remote_ip' '8000' 'tcp' 'in' '192.168.0.1'

        # Delete all rules for local port 80:
        salt '*' firewall.delete_rule all 80 tcp

        # Delete a rule called 'allow80':
        salt '*' firewall.delete_rule allow80
    '''
    cmd = ['netsh', 'advfirewall', 'firewall', 'delete', 'rule']
    if name:
        cmd.append('name={0}'.format(name))
    if protocol:
        cmd.append('protocol={0}'.format(protocol))
    if dir:
        cmd.append('dir={0}'.format(dir))
    if remoteip:
        cmd.append('remoteip={0}'.format(remoteip))

    if protocol is None \
            or ('icmpv4' not in protocol and 'icmpv6' not in protocol):
        if localport:
            if not protocol:
                cmd.append('protocol=tcp')
            cmd.append('localport={0}'.format(localport))

    ret = __salt__['cmd.run_all'](cmd, python_shell=False, ignore_retcode=True)
    if ret['retcode'] != 0:
        raise CommandExecutionError(ret['stdout'])

    return True


def rule_exists(name):
    '''
    .. versionadded:: 2016.11.6

    Checks if a firewall rule exists in the firewall policy

    Args:
        name (str): The name of the rule

    Returns:
        bool: True if exists, otherwise False

    CLI Example:

    .. code-block:: bash

        # Is there a rule named RemoteDesktop
        salt '*' firewall.rule_exists RemoteDesktop
    '''
    try:
        get_rule(name)
        return True
    except CommandExecutionError:
        return False
