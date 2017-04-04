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
option_toggles = {
    '-c': 'copy_and_truncate',
    '-l': 'localtime',
    '-N': 'skip_missing',
}
option_flags = {
    '-A': ['age', None],
    '-C': ['count', 10],
    '-a': ['post_command', None],
    '-b': ['pre_command', None],
    '-e': ['mail_addr', None],
    '-E': ['expire_command', None],
    '-g': ['group', None],
    '-m': ['mode', None],
    '-M': ['rename_command', "/bin/mv $file$nfile"],
    '-o': ['owner', None],
    '-p': ['period', None],
    '-P': ['timestmp', None],
    '-R': ['old_created_command', None],
    '-s': ['size', None],
    '-S': ['max_size', None],
    '-t': ['template', None],
    '-T': ['pattern', None],
    '-w': ['entryname', None],
    '-z': ['compress_count', None],
}


def __virtual__():
    '''
    Only work on Solaris based systems
    '''
    if 'Solaris' in __grains__['os_family']:
        return True
    return (False, 'The logadm execution module cannot be loaded: only available on Solaris.')


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


def show_conf(conf_file=default_conf, name=None):
    '''
    Show configuration

    .. versionchanged:: Nitrogen

    conf_file : string
        path to logadm.conf, defaults to /etc/logadm.conf
    name : string
        optional show only a single entry

    CLI Example:

    .. code-block:: bash

        salt '*' logadm.show_conf
        salt '*' logadm.show_conf log_file=/var/log/syslog
    '''
    cfg = _parse_conf(conf_file)

    if name and name in cfg:
        return {name: cfg[name]}
    elif name:
        return {name: 'not found in {}'.format(conf_file)}
    else:
        return cfg


def list_conf(conf_file=default_conf, name=None):
    '''
    Show parsed configuration

    .. versionadded:: Nitrogen

    conf_file : string
        path to logadm.conf, defaults to /etc/logadm.conf
    name : string
        optional show only a single entry

    CLI Example:

    .. code-block:: bash

        salt '*' logadm.list_conf
        salt '*' logadm.list_conf log_file=/var/log/syslog
    '''
    cfg = show_conf(conf_file, name)
    cfg_parsed = []

    ## parse all options
    for log in cfg:
        log_cfg = {}
        options = cfg[log].split()  # FIXME: brakes quotations
        if len(options) == 0:
            continue

        # handle toggle options
        for opt in option_toggles:
            log_cfg[option_toggles[opt]] = opt in options
            if opt in options:
                options.remove(opt)

        # handle flag options
        for opt in option_flags:
            if opt in options:
                opt_val = None
                if len(options) > options.index(opt):
                    opt_val = options[options.index(opt)+1]
                log_cfg[option_flags[opt][0]] = opt_val
                options.remove(opt)
                if opt_val:
                    options.remove(opt_val)
            else:
                log_cfg[option_flags[opt][0]] = option_flags[opt][1]

        # handle log file
        if log.startswith('/'):
            log_cfg['log_file'] = log
        else:
            log_cfg['entryname'] = log
            if options[0].startswith('/'):
                log_cfg['log_file'] = options[0]
                del options[0]

        # handle unknown options
        log_cfg['aditional_options'] = " ".join(options) if len(options) else None

        cfg_parsed.append(log_cfg)

    return cfg_parsed


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
