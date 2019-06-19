# -*- coding: utf-8 -*-
'''
Module for managing dnsmasq
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import os

# Import salt libs
import salt.utils.files
import salt.utils.platform
from salt.exceptions import CommandExecutionError

# Import 3rd-party libs
from salt.ext import six

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only work on POSIX-like systems.
    '''
    if salt.utils.platform.is_windows():
        return (
            False,
            'dnsmasq execution module cannot be loaded: only works on '
            'non-Windows systems.'
        )
    return True


def version():
    '''
    Shows installed version of dnsmasq.

    CLI Example:

    .. code-block:: bash

        salt '*' dnsmasq.version
    '''
    cmd = 'dnsmasq -v'
    out = __salt__['cmd.run'](cmd).splitlines()
    comps = out[0].split()
    return comps[2]


def fullversion():
    '''
    Shows installed version of dnsmasq and compile options.

    CLI Example:

    .. code-block:: bash

        salt '*' dnsmasq.fullversion
    '''
    cmd = 'dnsmasq -v'
    out = __salt__['cmd.run'](cmd).splitlines()
    comps = out[0].split()
    version_num = comps[2]
    comps = out[1].split()
    return {'version': version_num,
            'compile options': comps[3:]}


def set_config(config_file='/etc/dnsmasq.conf', follow=True, **kwargs):
    '''
    Sets a value or a set of values in the specified file. By default, if
    conf-dir is configured in this file, salt will attempt to set the option
    in any file inside the conf-dir where it has already been enabled. If it
    does not find it inside any files, it will append it to the main config
    file. Setting follow to False will turn off this behavior.

    If a config option currently appears multiple times (such as dhcp-host,
    which is specified at least once per host), the new option will be added
    to the end of the main config file (and not to any includes). If you need
    an option added to a specific include file, specify it as the config_file.

    :param string config_file: config file where settings should be updated / added.
    :param bool follow: attempt to set the config option inside any file within
        the ``conf-dir`` where it has already been enabled.
    :param kwargs: key value pairs that contain the configuration settings that you
        want set.

    CLI Examples:

    .. code-block:: bash

        salt '*' dnsmasq.set_config domain=mydomain.com
        salt '*' dnsmasq.set_config follow=False domain=mydomain.com
        salt '*' dnsmasq.set_config config_file=/etc/dnsmasq.conf domain=mydomain.com
    '''
    dnsopts = get_config(config_file)
    includes = [config_file]
    if follow is True and 'conf-dir' in dnsopts:
        for filename in os.listdir(dnsopts['conf-dir']):
            if filename.startswith('.'):
                continue
            if filename.endswith('~'):
                continue
            if filename.endswith('bak'):
                continue
            if filename.endswith('#') and filename.endswith('#'):
                continue
            includes.append('{0}/{1}'.format(dnsopts['conf-dir'], filename))

    ret_kwargs = {}
    for key in kwargs:
        # Filter out __pub keys as they should not be added to the config file
        # See Issue #34263 for more information
        if key.startswith('__'):
            continue
        ret_kwargs[key] = kwargs[key]

        if key in dnsopts:
            if isinstance(dnsopts[key], six.string_types):
                for config in includes:
                    __salt__['file.sed'](path=config,
                                         before='^{0}=.*'.format(key),
                                         after='{0}={1}'.format(key, kwargs[key]))
            else:
                __salt__['file.append'](config_file,
                                        '{0}={1}'.format(key, kwargs[key]))
        else:
            __salt__['file.append'](config_file,
                                    '{0}={1}'.format(key, kwargs[key]))
    return ret_kwargs


def get_config(config_file='/etc/dnsmasq.conf'):
    '''
    Dumps all options from the config file.

    config_file
        The location of the config file from which to obtain contents.
        Defaults to ``/etc/dnsmasq.conf``.

    CLI Examples:

    .. code-block:: bash

        salt '*' dnsmasq.get_config
        salt '*' dnsmasq.get_config config_file=/etc/dnsmasq.conf
    '''
    dnsopts = _parse_dnamasq(config_file)
    if 'conf-dir' in dnsopts:
        for filename in os.listdir(dnsopts['conf-dir']):
            if filename.startswith('.'):
                continue
            if filename.endswith('~'):
                continue
            if filename.endswith('#') and filename.endswith('#'):
                continue
            dnsopts.update(_parse_dnamasq('{0}/{1}'.format(dnsopts['conf-dir'],
                                                        filename)))
    return dnsopts


def _parse_dnamasq(filename):
    '''
    Generic function for parsing dnsmasq files including includes.
    '''
    fileopts = {}

    if not os.path.isfile(filename):
        raise CommandExecutionError(
            'Error: No such file \'{0}\''.format(filename)
        )

    with salt.utils.files.fopen(filename, 'r') as fp_:
        for line in fp_:
            line = salt.utils.stringutils.to_unicode(line)
            if not line.strip():
                continue
            if line.startswith('#'):
                continue
            if '=' in line:
                comps = line.split('=')
                if comps[0] in fileopts:
                    if isinstance(fileopts[comps[0]], six.string_types):
                        temp = fileopts[comps[0]]
                        fileopts[comps[0]] = [temp]
                    fileopts[comps[0]].append(comps[1].strip())
                else:
                    fileopts[comps[0]] = comps[1].strip()
            else:
                if 'unparsed' not in fileopts:
                    fileopts['unparsed'] = []
                fileopts['unparsed'].append(line)
    return fileopts
