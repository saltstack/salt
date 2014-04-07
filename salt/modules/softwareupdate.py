# -*- coding: utf-8 -*-
'''
Support for the softwareupdate command on MacOS.
'''


# Import python libs
import re

__virtualname__ = 'softwareupdate'


def __virtual__():
    '''
    Only for MacOS
    '''
    return __virtualname__ if __grains__['os'] == 'MacOS' else False


def _get_upgradable():
    '''
    Utility function to get upgradable packages.

    Sample return date:
    { 'updatename': '1.2.3-45', ... }
    '''
    cmd = 'softwareupdate --list'
    out = __salt__['cmd.run_stdout'](cmd, output_loglevel='debug')

    # rexp parses lines that look like the following:
    #    * Safari6.1.2MountainLion-6.1.2
    #    Safari (6.1.2), 51679K [recommended]
    rexp = re.compile('(?m)^   [*|-] '
                      r'([^ ].*)[\r\n].*\(([^\)]+)')

    keys = ['name', 'version']
    _get = lambda l, k: l[keys.index(k)]

    upgrades = rexp.findall(out)

    ret = {}
    for line in upgrades:
        name = _get(line, 'name')
        version_num = _get(line, 'version')
        ret[name] = version_num

    return ret


def list_upgrades():
    '''
    List all available program upgrades.

    CLI Example:

    .. code-block:: bash

       salt '*' softwareupdate.list_upgrades
    '''

    return _get_upgradable()


def ignore(*updates):
    '''
    Ignore a specific program update.

    CLI Example:

    .. code-block:: bash

       salt '*' softwareupdate.ignore <update-name>
       salt '*' softwareupdate.ignore "<update with whitespace>"
       salt '*' softwareupdate.ignore <update1> <update2> <update3>
    '''

    ret = []

    if len(updates) == 0:
        return ''

    for name in updates:
        cmd = ['softwareupdate', '--ignore', name]
        __salt__['cmd.run_stdout'](cmd, python_shell=False,
                                      output_loglevel='debug')

        all_ignored = list_ignored()

        if name in all_ignored:
            ret.append(name)

    return ret


def list_ignored():
    '''
    List all upgrades that has been ignored.

    CLI Example:

    .. code-block:: bash

       salt '*' softwareupdate.list_ignored
    '''
    cmd = 'softwareupdate --list --ignore'
    out = __salt__['cmd.run_stdout'](cmd, output_loglevel='debug')

    # rep parses lines that look like the following:
    #     "Safari6.1.2MountainLion-6.1.2",
    # or:
    #     Safari6.1.2MountainLion-6.1.2
    rexp = re.compile('(?m)^    ["]?'
                      r'([^,|\s|"].*[^"])[,|"]')

    ignored_updates = rexp.findall(out)

    if ignored_updates:
        ret = ignored_updates
    else:
        ret = None
    return ret


def reset_ignored():
    '''
    Make sure the ignored updates are not ignored anymore,
    returns a list of the updates that are no longer ignored.

    CLI Example:

    .. code-block:: bash

       salt '*' softwareupdate.reset_ignored
    '''
    cmd = 'softwareupdate', '--reset-ignored'
    ignored_updates = list_ignored()

    if ignored_updates:
        __salt__['cmd.run_stdout'](cmd, output_loglevel='debug')
        ret = ignored_updates
    else:
        ret = None

    return ret


def schedule(*status):
    '''
    Decide if automatic checking for upgrades should be on or off.
    If no argumentsare given it will return the current status.
    Appaend on or off to change the status.

    Return values:
    - ``True``: Automatic checking is now on,
    - ``False``: Automatic checking is now off,
    - ``None``: Invalid argument.

    CLI Example:

    .. code-block:: bash

       salt '*' softwareupdate.schedule
       salt '*' softwareupdate.schedule on|off
    '''
    if len(status) == 0:
        cmd = 'softwareupdate --schedule'
    elif str(status[0]) == 'True':
        cmd = 'softwareupdate --schedule on'
    elif str(status[0]) == 'False':
        cmd = 'softwareupdate --schedule off'
    else:
        return None

    out = __salt__['cmd.run_stdout'](cmd, output_loglevel='debug')

    current_status = out.split()[-1]
    if current_status == 'off':
        return False
    elif current_status == 'on':
        return True


def upgrade():
    '''
    Installs all available upgrades.

    Return values:
    - ``True``: The update was installed.
    - ``False``: The update was not installed.

    CLI Example:

    .. code-block:: bash

       salt '*' softwareupdate.upgrade
    '''
    ret = {}

    available_upgrades = list_upgrades()
    cmd = 'softwareupdate --install --all'

    __salt__['cmd.run_stdout'](cmd, output_loglevel='debug')

    upgrades_left = list_upgrades()

    for name in available_upgrades:
        if name not in upgrades_left:
            ret[name] = True
        else:
            ret[name] = False

    return ret


def install(*updates):
    '''
    Install a named upgrade.

    Return values:
    - ``True``: The update was installed.
    - ``False``: The update was not installed.
    - ``None``: There is no update avaliable with that name.

    CLI Example:

    .. code-block:: bash

       salt '*' softwareupdate.install <update name>
       salt '*' softwareupdate.install <update1> <update2> <update3>
    '''
    ret = {}

    if len(updates) == 0:
        return ''

    avaliable_upgrades = list_upgrades()

    for name in updates:
        cmd = ['softwareupdate', '--install', name]
        __salt__['cmd.run_stdout'](cmd, python_shell=False,
                                      output_loglevel='debug')

    upgrades_left = list_upgrades()

    for name in updates:
        if name not in avaliable_upgrades:
            ret[name] = None
        elif name not in upgrades_left:
            ret[name] = True
        else:
            ret[name] = False

    return ret


def upgrade_available(update):
    '''
    Check whether or not an upgrade is available with a given name.

    CLI Example:

    .. code-block:: bash

       salt '*' softwareupdate.upgrade_available <update name>
    '''

    return update in list_upgrades()
