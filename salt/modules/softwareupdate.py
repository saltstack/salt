# -*- coding: utf-8 -*-
'''
Support for the softwareupdate command on MacOS.
'''
from __future__ import absolute_import


# Import python libs
import re
import os

# import salt libs
import salt.utils

__virtualname__ = 'softwareupdate'


def __virtual__():
    '''
    Only for MacOS
    '''
    return __virtualname__ if __grains__['os'] == 'MacOS' else False


def _get_upgradable(rec=False, restart=False):
    '''
    Utility function to get all upgradable packages.

    Sample return date:
    { 'updatename': '1.2.3-45', ... }
    '''
    cmd = 'softwareupdate --list'
    out = __salt__['cmd.run_stdout'](cmd, python_shell=False)
    # rexp parses lines that look like the following:
    #    * Safari6.1.2MountainLion-6.1.2
    #         Safari (6.1.2), 51679K [recommended]
    #    - iCal-1.0.2
    #         iCal, 1.0.2, 6520K
    rexp = re.compile('(?m)^   [*|-] '
                      r'([^ ].*)[\r\n].*\(([^\)]+)')

    if salt.utils.is_true(rec):
        # rexp parses lines that look like the following:
        #    * Safari6.1.2MountainLion-6.1.2
        #         Safari (6.1.2), 51679K [recommended]
        rexp = re.compile('(?m)^   [*] '
                          r'([^ ].*)[\r\n].*\(([^\)]+)')

    keys = ['name', 'version']
    _get = lambda l, k: l[keys.index(k)]

    upgrades = rexp.findall(out)

    ret = {}
    for line in upgrades:
        name = _get(line, 'name')
        version_num = _get(line, 'version')
        ret[name] = version_num

    if not salt.utils.is_true(restart):
        return ret

    # rexp parses lines that look like the following:
    #    * Safari6.1.2MountainLion-6.1.2
    #         Safari (6.1.2), 51679K [recommended] [restart]
    rexp1 = re.compile('(?m)^   [*|-] '
                       r'([^ ].*)[\r\n].*restart*')

    restart_upgrades = rexp1.findall(out)
    ret_restart = {}
    for update in ret:
        if update in restart_upgrades:
            ret_restart[update] = ret[update]

    return ret_restart


def list_upgrades(rec=False, restart=False):
    '''
    List all available updates.

    rec
       Return only the recommended updates.

    restart
       Return only the updates that require a restart.

    CLI Example:

    .. code-block:: bash

       salt '*' softwareupdate.list_upgrades
    '''

    return _get_upgradable(rec, restart)


def ignore(*updates):
    '''
    Ignore a specific program update. When an update is ignored the '-' and
    version number at the end will be omitted, so "SecUpd2014-001-1.0" becomes
    "SecUpd2014-001". It will be removed automatically if present. An update
    is successfully ignored when it no longer shows up after list_upgrades.

    CLI Example:

    .. code-block:: bash

       salt '*' softwareupdate.ignore <update-name>
       salt '*' softwareupdate.ignore "<update with whitespace>"
       salt '*' softwareupdate.ignore <update1> <update2> <update3>
    '''
    if len(updates) == 0:
        return ''

    # remove everything after and including the '-' in the updates
    # name.
    to_ignore = []
    for name in updates:
        to_ignore.append(name.rsplit('-', 1)[0])

    for name in to_ignore:
        cmd = ['softwareupdate', '--ignore', name]
        __salt__['cmd.run_stdout'](cmd, python_shell=False)

    return list_ignored()


def list_ignored():
    '''
    List all upgrades that has been ignored. Ignored updates are shown
    without the '-' and version number at the end, this is how the
    softwareupdate command works.

    CLI Example:

    .. code-block:: bash

       salt '*' softwareupdate.list_ignored
    '''
    cmd = 'softwareupdate --list --ignore'
    out = __salt__['cmd.run_stdout'](cmd, python_shell=False)

    # rep parses lines that look like the following:
    #     "Safari6.1.2MountainLion-6.1.2",
    # or:
    #     Safari6.1.2MountainLion-6.1.2
    rexp = re.compile('(?m)^    ["]?'
                      r'([^,|\s].*[^"|\n|,])[,|"]?')

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
    cmd = 'softwareupdate --reset-ignored'
    ignored_updates = list_ignored()

    if ignored_updates:
        __salt__['cmd.run_stdout'](cmd, python_shell=False)
        ret = ignored_updates
    else:
        ret = None

    return ret


def schedule(*status):
    '''
    Decide if automatic checking for upgrades should be on or off.
    If no arguments are given it will return the current status.
    Append on or off to change the status.

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

    out = __salt__['cmd.run_stdout'](cmd, python_shell=False)

    current_status = out.split()[-1]
    if current_status == 'off':
        return False
    elif current_status == 'on':
        return True


def upgrade(rec=False, restart=True):
    '''
    Install all available upgrades. Returns a dictionary containing the name
    of the update and the status of its installation.

    Return values:
    - ``True``: The update was installed.
    - ``False``: The update was not installed.

    rec
       If set to True, only install all the recommended updates.

    restart
       Set this to False if you do not want to install updates
       that require a restart.

    CLI Example:

    .. code-block:: bash

       salt '*' softwareupdate.upgrade
    '''
    if salt.utils.is_true(rec):
        to_upgrade = _get_upgradable(rec=True)
    else:
        to_upgrade = _get_upgradable()

    if not salt.utils.is_true(restart):
        restart_upgrades = _get_upgradable(restart=True)
        for update in restart_upgrades:
            if update in to_upgrade:
                del to_upgrade[update]

    for update in to_upgrade:
        cmd = ['softwareupdate', '--install', update]
        __salt__['cmd.run_stdout'](cmd, python_shell=False)

    ret = {}
    upgrades_left = _get_upgradable()
    for update in to_upgrade:
        if update not in upgrades_left:
            ret[update] = True
        else:
            ret[update] = False

    return ret


def install(*updates):
    '''
    Install a named upgrade. Returns a dictionary containing the name
    of the update and the status of its installation.

    Return values:
    - ``True``: The update was installed.
    - ``False``: The update was not installed.
    - ``None``: There is no update available with that name.

    CLI Example:

    .. code-block:: bash

       salt '*' softwareupdate.install <update-name>
       salt '*' softwareupdate.install "<update with whitespace>"
       salt '*' softwareupdate.install <update1> <update2> <update3>
    '''
    ret = {}

    if len(updates) == 0:
        return ''

    available_upgrades = _get_upgradable()

    for name in updates:
        cmd = ['softwareupdate', '--install', name]
        __salt__['cmd.run_stdout'](cmd, python_shell=False)

    upgrades_left = _get_upgradable()

    for name in updates:
        if name not in available_upgrades:
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

       salt '*' softwareupdate.upgrade_available <update-name>
       salt '*' softwareupdate.upgrade_available "<update with whitespace>"
    '''
    return update in _get_upgradable()


def list_downloads():
    '''
    Return a list of all updates that have been downloaded locally.

    CLI Example:

    .. code-block:: bash

       salt '*' softwareupdate.list_downloads
    '''
    outfiles = []
    for root, subFolder, files in os.walk('/Library/Updates'):
        for f in files:
            outfiles.append(os.path.join(root, f))

    dist_files = []
    for f in outfiles:
        if f.endswith('.dist'):
            dist_files.append(f)

    ret = []
    for update in _get_upgradable():
        for f in dist_files:
            with salt.utils.fopen(f) as fhr:
                if update.rsplit('-', 1)[0] in fhr.read():
                    ret.append(update)

    return ret


def download(*updates):
    '''
    Download a named update so that it can be installed later with
    the install or upgrade function. It returns a list of all updates
    that are now downloaded.

    CLI Example:

    .. code-block:: bash

       salt '*' softwareupdate.download <update name>
       salt '*' softwareupdate.download "<update with whitespace>"
       salt '*' softwareupdate.download <update1> <update2> <update3>
    '''
    for name in updates:
        cmd = ['softwareupdate', '--download', name]
        __salt__['cmd.run_stdout'](cmd, python_shell=False)

    return list_downloads()


def download_all(rec=False, restart=True):
    '''
    Download all available updates so that they can be installed later
    with the install or upgrade function. It returns a list of updates
    that are now downloaded.

    CLI Example:

    .. code-block:: bash

       salt '*' softwareupdate.download_all
    '''
    if salt.utils.is_true(rec):
        to_download = _get_upgradable(rec=True)
    else:
        to_download = _get_upgradable()

    if not salt.utils.is_true(restart):
        restart_upgrades = _get_upgradable(restart=True)
        for update in restart_upgrades:
            if update in to_download:
                del to_download[update]

    for name in to_download:
        cmd = ['softwareupdate', '--download', name]
        __salt__['cmd.run_stdout'](cmd, python_shell=False)

    return list_downloads()
