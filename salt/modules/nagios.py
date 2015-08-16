# -*- coding: utf-8 -*-
'''
Run nagios plugins/checks from salt and get the return as data.
'''

# Import python libs
from __future__ import absolute_import
import os
import stat
import logging

# Import 3rd-party libs
import salt.ext.six as six

log = logging.getLogger(__name__)

PLUGINDIR = '/usr/lib/nagios/plugins/'


def __virtual__():
    '''
    Only load if nagios-plugins are installed
    '''
    if os.path.isdir('/usr/lib/nagios/'):
        return 'nagios'
    return False


def _execute_cmd(plugin, args='', run_type='cmd.retcode'):
    '''
    Execute nagios plugin if it's in the directory with salt command specified in run_type
    '''
    data = {}

    all_plugins = list_plugins()
    if plugin in all_plugins:
        data = __salt__[run_type](
                '{0}{1} {2}'.format(PLUGINDIR, plugin, args),
                python_shell=False)

    return data


def _execute_pillar(pillar_name, run_type):
    '''
    Run one or more nagios plugins from pillar data and get the result of run_type
    The pillar have to be in this format:
    ------
    webserver:
        Ping_google:
            - check_icmp: 8.8.8.8
            - check_icmp: google.com
        Load:
            - check_load: -w 0.8 -c 1
        APT:
            - check_apt
    -------
    '''
    groups = __salt__['pillar.get'](pillar_name)

    data = {}
    for group in groups:
        data[group] = {}
        commands = groups[group]
        for command in commands:
            # Check if is a dict to get the arguments
            # in command if not set the arguments to empty string
            if isinstance(command, dict):
                plugin = next(six.iterkeys(command))
                args = command[plugin]
            else:
                plugin = command
                args = ''
            command_key = _format_dict_key(args, plugin)
            data[group][command_key] = run_type(plugin, args)
    return data


def _format_dict_key(args, plugin):
    key_name = plugin
    args_key = args.replace(' ', '')
    if args != '':
        args_key = '_' + args_key
        key_name = plugin + args_key

    return key_name


def run(plugin, args=''):
    '''
    Run nagios plugin and return all the data execution with cmd.run

    '''
    data = _execute_cmd(plugin, args, 'cmd.run')

    return data


def retcode(plugin, args='', key_name=None):
    '''
    Run one nagios plugin and return retcode of the execution

    CLI Example:

    .. code-block:: bash

        salt '*' nagios.run check_apt
        salt '*' nagios.run check_icmp '8.8.8.8'
    '''
    data = {}

    # Remove all the spaces, the key must not have any space
    if key_name is None:
        key_name = _format_dict_key(args, plugin)

    data[key_name] = {}

    status = _execute_cmd(plugin, args, 'cmd.retcode')
    data[key_name]['status'] = status

    return data


def run_all(plugin, args=''):
    '''
    Run nagios plugin and return all the data execution with cmd.run_all
    '''
    data = _execute_cmd(plugin, args, 'cmd.run_all')
    return data


def retcode_pillar(pillar_name):
    '''
    Run one or more nagios plugins from pillar data and get the result of cmd.retcode
    The pillar have to be in this format::

        ------
        webserver:
            Ping_google:
                - check_icmp: 8.8.8.8
                - check_icmp: google.com
            Load:
                - check_load: -w 0.8 -c 1
            APT:
                - check_apt
        -------

    webserver is the role to check, the next keys are the group and the items
    the check with the arguments if needed

    You must to group different checks(one o more) and always it will return
    the highest value of all the checks

    CLI Example:

    .. code-block:: bash

        salt '*' nagios.retcode webserver
    '''
    groups = __salt__['pillar.get'](pillar_name)

    check = {}
    data = {}

    for group in groups:
        commands = groups[group]
        for command in commands:
            # Check if is a dict to get the arguments
            # in command if not set the arguments to empty string
            if isinstance(command, dict):
                plugin = next(six.iterkeys(command))
                args = command[plugin]
            else:
                plugin = command
                args = ''

            check.update(retcode(plugin, args, group))

            current_value = 0
            new_value = int(check[group]['status'])
            if group in data:
                current_value = int(data[group]['status'])

            if (new_value > current_value) or (group not in data):

                if group not in data:
                    data[group] = {}
                data[group]['status'] = new_value

    return data


def run_pillar(pillar_name):
    '''
    Run one or more nagios plugins from pillar data and get the result of cmd.run
    The pillar have to be in this format::

        ------
        webserver:
            Ping_google:
                - check_icmp: 8.8.8.8
                - check_icmp: google.com
            Load:
                - check_load: -w 0.8 -c 1
            APT:
                - check_apt
        -------

    webserver is the role to check, the next keys are the group and the items
    the check with the arguments if needed

    You have to group different checks in a group

    CLI Example:

    .. code-block:: bash

        salt '*' nagios.run webserver
    '''
    data = _execute_pillar(pillar_name, run)

    return data


def run_all_pillar(pillar_name):
    '''
    Run one or more nagios plugins from pillar data and get the result of cmd.run_all
    The pillar have to be in this format::

        ------
        webserver:
            Ping_google:
                - check_icmp: 8.8.8.8
                - check_icmp: google.com
            Load:
                - check_load: -w 0.8 -c 1
            APT:
                - check_apt
        -------

    webserver is the role to check, the next keys are the group and the items
    the check with the arguments if needed

    You have to group different checks in a group

    CLI Example:

    .. code-block:: bash

        salt '*' nagios.run webserver
    '''
    data = _execute_pillar(pillar_name, run_all)
    return data


def list_plugins():
    '''
    List all the nagios plugins

    CLI Example:

    .. code-block:: bash

        salt '*' nagios.list_plugins
    '''
    plugin_list = os.listdir(PLUGINDIR)
    ret = []
    for plugin in plugin_list:
        # Check if execute bit
        stat_f = os.path.join(PLUGINDIR, plugin)
        execute_bit = stat.S_IXUSR & os.stat(stat_f)[stat.ST_MODE]
        if execute_bit:
            ret.append(plugin)
    return ret
