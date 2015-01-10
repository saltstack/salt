# -*- coding: utf-8 -*-
'''
Execute chef in server or solo mode
'''
from __future__ import absolute_import

# Import Python libs
import logging
import os

# Import Salt libs
import salt.utils
import salt.utils.decorators as decorators

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if chef is installed
    '''
    if not salt.utils.which('chef-client'):
        return False
    return True


def _default_logfile(exe_name):

    if salt.utils.is_windows():
        logfile = salt.utils.path_join(
            os.environ['TMP'],
            '{0}.log'.format(exe_name)
        )
    else:
        logfile = salt.utils.path_join(
            '/var/log',
            '{0}.log'.format(exe_name)
        )

    return logfile


@decorators.which('chef-client')
def client(whyrun=False,
           localmode=False,
           logfile=_default_logfile('chef-client'),
           **kwargs):
    '''
    Execute a chef client run and return a dict with the stderr, stdout,
    return code, and pid.

    CLI Example:

    .. code-block:: bash

        salt '*' chef.client server=https://localhost

    server
        The chef server URL

    client_key
        Set the client key file location

    config
        The configuration file to use

    config-file-jail
        Directory under which config files are allowed to be loaded
        (no client.rb or knife.rb outside this path will be loaded).

    environment
        Set the Chef Environment on the node

    group
        Group to set privilege to

    json-attributes
        Load attributes from a JSON file or URL

    localmode
        Point chef-client at local repository if True

    log_level
        Set the log level (debug, info, warn, error, fatal)

    logfile
        Set the log file location

    node-name
        The node name for this client

    override-runlist
        Replace current run list with specified items for a single run

    pid
        Set the PID file location, defaults to /tmp/chef-client.pid

    run-lock-timeout
        Set maximum duration to wait for another client run to finish,
        default is indefinitely.

    runlist
        Permanently replace current run list with specified items

    user
        User to set privilege to

    validation_key
        Set the validation key file location, used for registering new clients

    whyrun
        Enable whyrun mode when set to True

    '''
    args = ['chef-client',
            '--no-color',
            '--once',
            '--logfile "{0}"'.format(logfile),
            '--format doc']

    if whyrun:
        args.append('--why-run')

    if localmode:
        args.append('--local-mode')

    return _exec_cmd(*args, **kwargs)


@decorators.which('chef-solo')
def solo(whyrun=False,
         logfile=_default_logfile('chef-solo'),
         **kwargs):
    '''
    Execute a chef solo run and return a dict with the stderr, stdout,
    return code, and pid.

    CLI Example:

    .. code-block:: bash

        salt '*' chef.solo override-runlist=test

    config
        The configuration file to use

    environment
        Set the Chef Environment on the node

    group
        Group to set privilege to

    json-attributes
        Load attributes from a JSON file or URL

    log_level
        Set the log level (debug, info, warn, error, fatal)

    logfile
        Set the log file location

    node-name
        The node name for this client

    override-runlist
        Replace current run list with specified items for a single run

    recipe-url
        Pull down a remote gzipped tarball of recipes and untar it to
        the cookbook cache

    run-lock-timeout
        Set maximum duration to wait for another client run to finish,
        default is indefinitely.

    user
        User to set privilege to

    whyrun
        Enable whyrun mode when set to True
    '''
    args = ['chef-solo',
            '--no-color',
            '--logfile "{0}"'.format(logfile),
            '--format doc']

    args = ['chef-solo', '--no-color', '--logfile {0}'.format(logfile)]

    if whyrun:
        args.append('--why-run')

    return _exec_cmd(*args, **kwargs)


def _exec_cmd(*args, **kwargs):

    # Compile the command arguments
    cmd_args = ' '.join(args)
    cmd_kwargs = ''.join([
         ' --{0} {1}'.format(k, v)
         for k, v in kwargs.items() if not k.startswith('__')]
    )
    cmd_exec = '{0}{1}'.format(cmd_args, cmd_kwargs)
    log.debug('Chef command: {0}'.format(cmd_exec))

    return __salt__['cmd.run_all'](cmd_exec, python_shell=False)
