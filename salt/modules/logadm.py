# -*- coding: utf-8 -*-
'''
Module for managing Solaris logadm based log rotations.
'''
from __future__ import absolute_import

# Import python libs
import logging

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)
default_conf = '/etc/logadm.conf'


def __virtual__():
    '''
    Only work on Solaris based systems
    '''
    if 'Solaris' in __grains__['os_family']:
        return True
    return False


def _parse_conf(conf_file=default_conf):
    '''
    Parse a logadm configuration file.
    '''
    ret = {}
    # ret = []
    with salt.utils.fopen(conf_file, 'r') as ifile:
        for line in ifile:
            line = line.strip()
            if not line:
                continue
            if line.startswith('#'):
                continue
            splitline = line.split(' ', 1)
            ret[splitline[0]] = splitline[1]
    return ret


def show_conf(conf_file=default_conf):
    '''
    Show parsed configuration

    CLI Example:

    .. code-block:: bash

        salt '*' logadm.show_conf
    '''
    return _parse_conf(conf_file)


def rotate(name,
           pattern=False,
           count=False,
           age=False,
           size=False,
           copy=True,
           conf_file=default_conf):
    '''
    Set up pattern for logging.

    CLI Example:

    .. code-block:: bash

      salt '*' logadm.rotate myapplog pattern='/var/log/myapp/*.log' count=7
    '''
    command = "logadm -f {0} -w {1}".format(conf_file, name)
    if count:
        command += " -C {0}".format(count)
    if age:
        command += " -A {0}".format(age)
    if copy:
        command += " -c"
    if size:
        command += " -s {0}".format(size)
    if pattern:
        command += " {0}".format(pattern)

    result = __salt__['cmd.run_all'](command, python_shell=False)
    if result['retcode'] != 0:
        return dict(Error='Failed in adding log', Output=result['stderr'])

    return dict(Result='Success')


def remove(name, conf_file=default_conf):
    '''
    Remove log pattern from logadm

    CLI Example:

    .. code-block:: bash

      salt '*' logadm.remove myapplog
    '''
    command = "logadm -f {0} -r {1}".format(conf_file, name)
    result = __salt__['cmd.run_all'](command, python_shell=False)
    if result['retcode'] != 0:
        return dict(
            Error='Failure in removing log. Possibly already removed?',
            Output=result['stderr']
        )
    return dict(Result='Success')
