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
import salt.utils.mac_utils
from salt.exceptions import CommandExecutionError, SaltInvocationError

__virtualname__ = 'softwareupdate'


def __virtual__():
    '''
    Only for MacOS
    '''
    if not salt.utils.is_darwin():
        return (False, 'The softwareupdate module could not be loaded: '
                       'module only works on MacOS systems.')

    return __virtualname__


def _get_available(recommended=False, restart=False):
    '''
    Utility function to get all available update packages.

    Sample return date:
    { 'updatename': '1.2.3-45', ... }
    '''
    cmd = ['softwareupdate', '--list']
    out = salt.utils.mac_utils.execute_return_result(cmd)

    # rexp parses lines that look like the following:
    #    * Safari6.1.2MountainLion-6.1.2
    #         Safari (6.1.2), 51679K [recommended]
    #    - iCal-1.0.2
    #         iCal, 1.0.2, 6520K
    rexp = re.compile('(?m)^   [*|-] '
                      r'([^ ].*)[\r\n].*\(([^\)]+)')

    if salt.utils.is_true(recommended):
        # rexp parses lines that look like the following:
        #    * Safari6.1.2MountainLion-6.1.2
        #         Safari (6.1.2), 51679K [recommended]
        rexp = re.compile('(?m)^   [*] '
                          r'([^ ].*)[\r\n].*\(([^\)]+)')

    keys = ['name', 'version']
    _get = lambda l, k: l[keys.index(k)]

    updates = rexp.findall(out)

    ret = {}
    for line in updates:
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

    restart_updates = rexp1.findall(out)
    ret_restart = {}
    for update in ret:
        if update in restart_updates:
            ret_restart[update] = ret[update]

    return ret_restart


def list_available(recommended=False, restart=False):
    '''
    List all available updates.

    :param bool recommended: Show only recommended updates.

    :param bool restart: Show only updates that require a restart.

    :return: Returns a dictionary containing the updates
    :rtype: dict

    CLI Example:

    .. code-block:: bash

       salt '*' softwareupdate.list_available
    '''
    return _get_available(recommended, restart)


def ignore(name):
    '''
    Ignore a specific program update. When an update is ignored the '-' and
    version number at the end will be omitted, so "SecUpd2014-001-1.0" becomes
    "SecUpd2014-001". It will be removed automatically if present. An update
    is successfully ignored when it no longer shows up after list_updates.

    :param name: The name of the update to add to the ignore list.
    :ptype: str

    :return: True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

       salt '*' softwareupdate.ignore <update-name>
    '''
    # remove everything after and including the '-' in the updates name.
    to_ignore = name.rsplit('-', 1)[0]

    cmd = ['softwareupdate', '--ignore', to_ignore]
    salt.utils.mac_utils.execute_return_success(cmd)

    return to_ignore in list_ignored()


def list_ignored():
    '''
    List all updates that have been ignored. Ignored updates are shown
    without the '-' and version number at the end, this is how the
    softwareupdate command works.

    :return: The list of ignored updates
    :rtype: list

    CLI Example:

    .. code-block:: bash

       salt '*' softwareupdate.list_ignored
    '''
    cmd = ['softwareupdate', '--list', '--ignore']
    out = salt.utils.mac_utils.execute_return_result(cmd)

    # rep parses lines that look like the following:
    #     "Safari6.1.2MountainLion-6.1.2",
    # or:
    #     Safari6.1.2MountainLion-6.1.2
    rexp = re.compile('(?m)^    ["]?'
                      r'([^,|\s].*[^"|\n|,])[,|"]?')

    return rexp.findall(out)


def reset_ignored():
    '''
    Make sure the ignored updates are not ignored anymore,
    returns a list of the updates that are no longer ignored.

    :return: True if the list was reset, Otherwise False
    :rtype: bool

    CLI Example:

    .. code-block:: bash

       salt '*' softwareupdate.reset_ignored
    '''
    cmd = ['softwareupdate', '--reset-ignored']
    salt.utils.mac_utils.execute_return_success(cmd)

    return list_ignored() == []


def schedule_enabled():
    '''
    Check the status of automatic update scheduling.

    :return: True if scheduling is enabled, False if disabled
        - ``True``: Automatic checking is on,
        - ``False``: Automatic checking is off,
    :rtype: bool

    CLI Example:

    .. code-block:: bash

       salt '*' softwareupdate.schedule_enabled
    '''
    cmd = ['softwareupdate', '--schedule']
    ret = salt.utils.mac_utils.execute_return_result(cmd)

    enabled = ret.split()[-1]

    return salt.utils.mac_utils.validate_enabled(enabled) == 'on'


def schedule_enable(enable):
    '''
    Enable/disable automatic update scheduling.

    :param enable: True/On/Yes/1 to turn on automatic updates. False/No/Off/0 to
    turn off automatic updates. If this value is empty, the current status will
    be returned.
    :type: bool str

    :return: True if scheduling is enabled, False if disabled
    :rtype: bool

    CLI Example:

    .. code-block:: bash

       salt '*' softwareupdate.schedule_enable on|off
    '''
    status = salt.utils.mac_utils.validate_enabled(enable)

    cmd = ['softwareupdate',
           '--schedule',
           salt.utils.mac_utils.validate_enabled(status)]
    salt.utils.mac_utils.execute_return_success(cmd)

    return salt.utils.mac_utils.validate_enabled(schedule_enabled()) == status


def update_all(recommended=False, restart=True):
    '''
    Install all available updates. Returns a dictionary containing the name
    of the update and the status of its installation.

    :param bool recommended: If set to True, only install the recommended
    updates. If set to False (default) all updates are installed.

    :param bool restart: Set this to False if you do not want to install updates
    that require a restart. Default is True

    :return: A dictionary containing the updates that were installed and the
    status of its installation. If no updates were installed an empty dictionary
    is returned.
    :rtype: dict
    - ``True``: The update was installed.
    - ``False``: The update was not installed.

    CLI Example:

    .. code-block:: bash

       salt '*' softwareupdate.update_all
    '''
    to_update = _get_available(recommended, restart)

    if not to_update:
        return {}

    for _update in to_update:
        cmd = ['softwareupdate', '--install', _update]
        salt.utils.mac_utils.execute_return_success(cmd)

    ret = {}
    updates_left = _get_available()

    for _update in to_update:
        ret[_update] = True if _update not in updates_left else False

    return ret


def update(name):
    '''
    Install a named update.

    :param str name: The name of the of the update to install.

    :return: True if successfully updated, otherwise False
    :rtype: bool

    CLI Example:

    .. code-block:: bash

       salt '*' softwareupdate.update <update-name>
    '''
    if not update_available(name):
        raise SaltInvocationError('Update not available: {0}'.format(name))

    cmd = ['softwareupdate', '--install', name]
    salt.utils.mac_utils.execute_return_success(cmd)

    return not update_available(name)


def update_available(name):
    '''
    Check whether or not an update is available with a given name.

    :param str name: The name of the update to look for

    :return: True if available, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

       salt '*' softwareupdate.update_available <update-name>
       salt '*' softwareupdate.update_available "<update with whitespace>"
    '''
    return name in _get_available()


def list_downloads():
    '''
    Return a list of all updates that have been downloaded locally.

    :return: A list of updates that have been downloaded
    :rtype: list

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
    for update in _get_available():
        for f in dist_files:
            with salt.utils.fopen(f) as fhr:
                if update.rsplit('-', 1)[0] in fhr.read():
                    ret.append(update)

    return ret


def download(name):
    '''
    Download a named update so that it can be installed later with the
    ``update`` or ``update_all`` functions

    :param str name: The update to download.

    :return: True if successful, otherwise False
    :rtype: bool

    CLI Example:

    .. code-block:: bash

       salt '*' softwareupdate.download <update name>
    '''
    if not update_available(name):
        raise SaltInvocationError('Update not available: {0}'.format(name))

    if name in list_downloads():
        return True

    cmd = ['softwareupdate', '--download', name]
    salt.utils.mac_utils.execute_return_success(cmd)

    return name in list_downloads()


def download_all(recommended=False, restart=True):
    '''
    Download all available updates so that they can be installed later with the
    ``update`` or ``update_all`` functions. It returns a list of updates that
    are now downloaded.

    :param bool recommended: If set to True, only install the recommended
    updates. If set to False (default) all updates are installed.

    :param bool restart: Set this to False if you do not want to install updates
    that require a restart. Default is True

    :return: A list containing all downloaded updates on the system.
    :rtype: list

    CLI Example:

    .. code-block:: bash

       salt '*' softwareupdate.download_all
    '''
    to_download = _get_available(recommended, restart)

    for name in to_download:
        download(name)

    return list_downloads()


def get_catalog():
    '''
    .. versionadded:: 2016.3.0

    Get the current catalog being used for update lookups. Will return a url if
    a custom catalog has been specified. Otherwise the word 'Default' will be
    returned

    :return: The catalog being used for update lookups
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' softwareupdates.get_catalog
    '''
    cmd = ['defaults',
           'read',
           '/Library/Preferences/com.apple.SoftwareUpdate.plist']
    out = salt.utils.mac_utils.execute_return_result(cmd)

    if 'AppleCatalogURL' in out:
        cmd.append('AppleCatalogURL')
        out = salt.utils.mac_utils.execute_return_result(cmd)
        return out
    elif 'CatalogURL' in out:
        cmd.append('CatalogURL')
        out = salt.utils.mac_utils.execute_return_result(cmd)
        return out
    else:
        return 'Default'


def set_catalog(url):
    '''
    .. versionadded:: 2016.3.0

    Set the Software Update Catalog to the URL specified

    :param str url: The url to the update catalog

    :return: True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' softwareupdates.set_catalog http://swupd.local:8888/index.sucatalog
    '''
    # This command always returns an error code, though it completes
    # successfully. Success will be determined by making sure get_catalog
    # returns the passed url
    cmd = ['softwareupdate', '--set-catalog', url]

    try:
        salt.utils.mac_utils.execute_return_success(cmd)
    except CommandExecutionError as exc:
        pass

    return get_catalog() == url


def reset_catalog():
    '''
    .. versionadded:: 2016.3.0

    Reset the Software Update Catalog to the default.

    :return: True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' softwareupdates.reset_catalog
    '''
    # This command always returns an error code, though it completes
    # successfully. Success will be determined by making sure get_catalog
    # returns 'Default'
    cmd = ['softwareupdate', '--clear-catalog']

    try:
        salt.utils.mac_utils.execute_return_success(cmd)
    except CommandExecutionError as exc:
        pass

    return get_catalog() == 'Default'
