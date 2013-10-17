# -*- coding: utf-8 -*-
'''
Module for viewing and modifying sysctl parameters
'''

# Import python libs
import logging
import os
import re

# Import salt libs
import salt.utils
from salt._compat import string_types
from salt.exceptions import CommandExecutionError
from salt.modules.systemd import _sd_booted

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'sysctl'

# TODO: Add unpersist() to remove either a sysctl or sysctl/value combo from
# the config


def __virtual__():
    '''
    Only run on Linux systems
    '''
    if __grains__['kernel'] != 'Linux':
        return False
    global _sd_booted
    _sd_booted = salt.utils.namespaced_function(_sd_booted, globals())
    return __virtualname__


def default_config():
    '''
    Linux hosts using systemd 207 or later ignore ``/etc/sysctl.conf`` and only
    load from ``/etc/sysctl.d/*.conf``. This function will do the proper checks
    and return a default config file which will be valid for the Minion. Hosts
    running systemd >= 207 will use ``/etc/sysctl.d/99-salt.conf``.

    CLI Example:

    .. code-block:: bash

        salt -G 'kernel:Linux' sysctl.default_config
    '''
    if _sd_booted():
        for line in __salt__['cmd.run_stdout'](
            'systemctl --version'
        ).splitlines():
            if line.startswith('systemd '):
                version = line.split()[-1]
                try:
                    if int(version) >= 207:
                        return '/etc/sysctl.d/99-salt.conf'
                except ValueError:
                    log.error(
                        'Unexpected non-numeric systemd version {0!r} '
                        'detected'.format(version)
                    )
                break

    return '/etc/sysctl.conf'


def show():
    '''
    Return a list of sysctl parameters for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' sysctl.show
    '''
    cmd = 'sysctl -a'
    ret = {}
    for line in __salt__['cmd.run_stdout'](cmd).splitlines():
        if not line or ' = ' not in line:
            continue
        comps = line.split(' = ', 1)
        ret[comps[0]] = comps[1]
    return ret


def get(name):
    '''
    Return a single sysctl parameter for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' sysctl.get net.ipv4.ip_forward
    '''
    cmd = 'sysctl -n {0}'.format(name)
    out = __salt__['cmd.run'](cmd)
    return out


def assign(name, value):
    '''
    Assign a single sysctl parameter for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' sysctl.assign net.ipv4.ip_forward 1
    '''
    value = str(value)
    sysctl_file = '/proc/sys/{0}'.format(name.replace('.', '/'))
    if not os.path.exists(sysctl_file):
        raise CommandExecutionError('sysctl {0} does not exist'.format(name))

    ret = {}
    cmd = 'sysctl -w {0}="{1}"'.format(name, value)
    data = __salt__['cmd.run_all'](cmd)
    out = data['stdout']

    # Example:
    #    # sysctl -w net.ipv4.tcp_rmem="4096 87380 16777216"
    #    net.ipv4.tcp_rmem = 4096 87380 16777216
    regex = re.compile(r'^{0}\s+=\s+{1}$'.format(re.escape(name), re.escape(value)))

    if not regex.match(out):
        if data['retcode'] != 0 and data['stderr']:
            error = data['stderr']
        else:
            error = out
        raise CommandExecutionError('sysctl -w failed: {0}'.format(error))
    new_name, new_value = out.split(' = ', 1)
    ret[new_name] = new_value
    return ret


def persist(name, value, config=None):
    '''
    Assign and persist a simple sysctl parameter for this minion. If ``config``
    is not specified, a sensible default will be chosen using
    :mod:`sysctl.default_config <salt.modules.linux_sysctl.default_config>`.

    CLI Example:

    .. code-block:: bash

        salt '*' sysctl.persist net.ipv4.ip_forward 1
    '''
    if config is None:
        config = default_config()
    running = show()
    edited = False
    # If the sysctl.conf is not present, add it
    if not os.path.isfile(config):
        try:
            with salt.utils.fopen(config, 'w+') as _fh:
                _fh.write('#\n# Kernel sysctl configuration\n#\n')
        except (IOError, OSError):
            msg = 'Could not write to file: {0}'
            raise CommandExecutionError(msg.format(config))

    # Read the existing sysctl.conf
    nlines = []
    try:
        with salt.utils.fopen(config, 'r') as _fh:
            # Use readlines because this should be a small file
            # and it seems unnecessary to indent the below for
            # loop since it is a fairly large block of code.
            config_data = _fh.readlines()
    except (IOError, OSError):
        msg = 'Could not read from file: {0}'
        raise CommandExecutionError(msg.format(config))

    for line in config_data:
        if line.startswith('#'):
            nlines.append(line)
            continue
        if '=' not in line:
            nlines.append(line)
            continue

        # Strip trailing whitespace and split the k,v
        comps = [i.strip() for i in line.split('=', 1)]

        # On Linux procfs, files such as /proc/sys/net/ipv4/tcp_rmem or any
        # other sysctl with whitespace in it consistently uses 1 tab.  Lets
        # allow our users to put a space or tab between multi-value sysctls
        # and have salt not try to set it every single time.
        if isinstance(comps[1], string_types) and ' ' in comps[1]:
            comps[1] = re.sub(r'\s+', '\t', comps[1])

        # Do the same thing for the value 'just in case'
        if isinstance(value, string_types) and ' ' in value:
            value = re.sub(r'\s+', '\t', value)

        if len(comps) < 2:
            nlines.append(line)
            continue
        if name == comps[0]:
            # This is the line to edit
            if str(comps[1]) == str(value):
                # It is correct in the config, check if it is correct in /proc
                if name in running:
                    if str(running[name]) != str(value):
                        assign(name, value)
                        return 'Updated'
                return 'Already set'
            nlines.append('{0} = {1}\n'.format(name, value))
            edited = True
            continue
        else:
            nlines.append(line)
    if not edited:
        nlines.append('{0} = {1}\n'.format(name, value))
    try:
        with salt.utils.fopen(config, 'w+') as _fh:
            _fh.writelines(nlines)
    except (IOError, OSError):
        msg = 'Could not write to file: {0}'
        raise CommandExecutionError(msg.format(config))

    assign(name, value)
    return 'Updated'
