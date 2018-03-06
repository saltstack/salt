# -*- coding: utf-8 -*-
'''
Module for viewing and modifying sysctl parameters
'''
from __future__ import absolute_import

# Import python libs
import logging
import os
import re

# Import salt libs
import salt.ext.six as six
import salt.utils
from salt.ext.six import string_types
from salt.exceptions import CommandExecutionError
from salt.utils.odict import OrderedDict
import salt.utils.systemd
import string

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
        return (False, 'The linux_sysctl execution module cannot be loaded: only available on Linux systems.')
    return __virtualname__


def _check_systemd_salt_config():
    conf = '/etc/sysctl.d/99-salt.conf'
    if not os.path.exists(conf):
        sysctl_dir = os.path.split(conf)[0]
        if not os.path.exists(sysctl_dir):
            os.makedirs(sysctl_dir)
        try:
            with salt.utils.fopen(conf, 'w'):
                pass
        except (IOError, OSError):
            msg = 'Could not create file: {0}'
            raise CommandExecutionError(msg.format(conf))
    return conf


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
    if salt.utils.systemd.booted(__context__) \
            and salt.utils.systemd.version(__context__) >= 207:
        return _check_systemd_salt_config()
    return '/etc/sysctl.conf'


def show(config_file=False):
    '''
    Return a list of sysctl parameters for this minion

    config: Pull the data from the system configuration file
        instead of the live data.

    CLI Example:

    .. code-block:: bash

        salt '*' sysctl.show
    '''
    ret = {}
    if config_file:
        try:
            with salt.utils.fopen(config_file) as fp_:
                for line in fp_:
                    if not line.startswith('#') and '=' in line:
                        # search if we have some '=' instead of ' = ' separators
                        SPLIT = ' = '
                        if SPLIT not in line:
                            SPLIT = SPLIT.strip()
                        key, value = line.split(SPLIT, 1)
                        key = key.strip()
                        value = value.lstrip()
                        ret[key] = value
        except (OSError, IOError):
            log.error('Could not open sysctl file')
            return None
    else:
        cmd = 'sysctl -a'
        out = __salt__['cmd.run_stdout'](cmd, output_loglevel='trace')
        for line in out.splitlines():
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
    out = __salt__['cmd.run'](cmd, python_shell=False)
    return out


def assign(name, value=None, sysctls={}):
    '''
    Assign a single sysctl parameter for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' sysctl.assign net.ipv4.ip_forward 1
    '''
    ret = {}
    all_sysctls = ""

    if value is not None:
        sysctls[name] = value

    log.info(sysctls)
    for (name, value) in sysctls.items():
        value = str(value)
        trantab = ''.maketrans('./', '/.') if six.PY3 else string.maketrans('./', '/.')
        sysctl_file = '/proc/sys/{0}'.format(name.translate(trantab))
        if not os.path.exists(sysctl_file):
            raise CommandExecutionError('sysctl {0} does not exist'.format(name))
        all_sysctls += '{0}="{1}"'.format(name, value)

    cmd = 'sysctl -w {}'.format(all_sysctls)
    log.info(cmd)
    data = __salt__['cmd.run_all'](cmd, python_shell=False)
    out = data['stdout']
    err = data['stderr']

    # Example:
    #    # sysctl -w net.ipv4.tcp_rmem="4096 87380 16777216"
    #    net.ipv4.tcp_rmem = 4096 87380 16777216
    # regex = re.compile(r'^{0}\s+=\s+{1}$'.format(re.escape(name), re.escape(value)))

    # if not regex.match(out) or 'Invalid argument' in str(err):
    error = ""
    if 'Invalid argument' in str(err):
        if data['retcode'] != 0 and err:
            error += err
        else:
            error += out

    if error != "":
        raise CommandExecutionError('sysctl -w failed: {0}'.format(error))
    # new_name, new_value = out.split(' = ', 1)
    ret[name] = all_sysctls
    return ret


def persist(name=None, value=None, config=None, sysctls=[]):
    '''
    Assign and persist a simple sysctl parameter for this minion. If ``config``
    is not specified, a sensible default will be chosen using
    :mod:`sysctl.default_config <salt.modules.linux_sysctl.default_config>`.

    CLI Example:

    .. code-block:: bash

        salt '*' sysctl.persist net.ipv4.ip_forward 1

        salt '*' sysctl.persist sysctls='["net.ipv4.ip_forward":1, "net.ipv4.ip_forward_use_pmtu":1}'
    '''

    print(str(name), str(value))
    print(sysctls)

    if name and value:
        sysctls = [OrderedDict({name:value})]

    sysctls_data = {}

    for item in sysctls:
        sysctl_name = item.keys()[0]
        value = item[sysctl_name]
        sysctls_data[sysctl_name]= value

    if config is None:
        config = default_config()
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


        if len(comps) < 2:
            nlines.append(line)
            continue
        if comps[0] in sysctls_data:
            # This is the line to edit
            # Do the same thing for the value 'just in case'
            value = sysctls_data[comps[0]]

            if isinstance(value, string_types) and ' ' in value:
                value = re.sub(r'\s+', '\t', value)

            if str(comps[1]) == str(value):
                # It is correct in the config, check if it is correct in /proc
                if str(get(comps[0])) != str(value):
                    log.info("comps: {}, value: {}".format(str(get(comps[0])), str(value)))
                    # assign(comps[0], value)
                    nlines.append('{0} = {1}\n'.format(comps[0], sysctls_data[comps[0]]))
                    # sysctls_data.pop(comps[0])
                    edited = True
                    continue
                #     return 'Updated'
                else:
                    sysctls_data.pop(comps[0])
                    continue
                #     return 'Already set'

            nlines.append('{0} = {1}\n'.format(comps[0], sysctls_data[comps[0]]))
            edited = True
            continue
        else:
            nlines.append(line)

    if not edited:
        for (sysctl_name, value) in sysctls_data.items():
            nlines.append('{0} = {1}\n'.format(sysctl_name, value))
        return "Already set"

    if len(sysctls_data) == 0:
        return "Already set"

    try:
        with salt.utils.fopen(config, 'w+') as _fh:
            _fh.writelines(nlines)
    except (IOError, OSError):
        msg = 'Could not write to file: {0}'
        raise CommandExecutionError(msg.format(config))

    # for (name, value) in sysctls_data.items():
    assign(name, None, sysctls_data)
    return 'Updated'
