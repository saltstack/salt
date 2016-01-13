'''
Manage Software Updates on Mac OS X 10.11+
'''

# Import python libs
from __future__ import absolute_import
import logging
import re

# Import 3rdp-party libs

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'updates'


def __virtual__():
    if not salt.utils.is_darwin():
        return False

    return __virtualname__


def _parse_packages(output):
    '''
    Parse package listing from `softwareupdate` tool.
    '''
    lines = output.splitlines()

    titles = [re.match('^\s*\*\s+(.*)', line).group(1) for line in lines if re.search('^\s*\*\s+', line)]
    descriptions = [re.match('^\t+(.*)', line).group(1) for line in lines if re.search('^\t+', line)]
    return dict(zip(titles, descriptions))


def scheduled():
    '''
    Determine the status of the automatic checking schedule

    :return: True if automatic checking is on, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' updates.scheduled
    '''
    cmd = '/usr/sbin/softwareupdate --schedule'
    out = __salt__['cmd.run'](cmd)

    if 'on' in out:
        return True
    else:
        return False


def schedule(enabled):
    '''
    Enable/Disable the automatic checking schedule.

    :param bool enabled: True to enable automatic checking, False to disable

    :return: True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' updates.schedule True
    '''
    if enabled:
        cmd = '/usr/sbin/softwareupdate --schedule on'
        out = __salt__['cmd.run'](cmd)
    else:
        cmd = '/usr/sbin/softwareupdate --schedule off'
        out = __salt__['cmd.run'](cmd)

    return enabled == scheduled()


def list():
    '''
    List available software updates. (Warning: can take a while to execute)

    :return: A dictionary containing a list of available updates
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' updates.list
    '''
    log.debug('Fetching available updates, this may take some time')
    cmd = '/usr/sbin/softwareupdate -l'
    out = __salt__['cmd.run'](cmd)

    packages = _parse_packages(out)

    if not packages:
        return 'No new software available'

    return packages


def download(name):
    '''
    Download the update specified in the name. Get the name from ``update.list``
    . (Warning: can take a while to execute depending on the size of the
    download)

    :param str name: The name of the update to download

    :return: The results of the command
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' updates.download 'OS X El Capitan Update 10.11.2'
    '''
    cmd = '/usr/sbin/softwareupdate -d {0}'.format(name)
    out = __salt__['cmd.run'](cmd)
    return out


def cancel_download(name):
    '''
    Cancel the download of the update specified in the name.

    :param str name: The name of the update to stop downloading

    :return: The results of the command
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' updates.cancel_download 'OS X El Capitan Update 10.11.2'
    '''
    cmd = '/usr/sbin/softwareupdate -e {0}'.format(name)
    out = __salt__['cmd.run'](cmd)
    return out


def install(name):
    '''
    Install the update specified in the name

    :param str name: The name of the update to install. Get the name using
    ``updates.list``.(Warning: this can take some time. The update must be
    downloaded and installed.)

    :return: The results of the command
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' updates.install 'iTunesXPatch-12.1.2'
    '''
    cmd = '/usr/sbin/softwareupdate -i {0}'.format(name)
    out = __salt__['cmd.run'](cmd)
    return out


def install_all():
    '''
    Install all pending software updates (Warning: this can take some time. Each
    update must be downloaded and installed.)

    :return: The results of the command
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' updates.install_all
    '''
    cmd = '/usr/sbin/softwareupdate -i -a'
    out = __salt__['cmd.run'](cmd)
    return out


def install_recommended():
    '''
    Install all recommended software updates (Warning: this can take some time.
    Each update must be downloaded and installed.)

    :return: The results of the command
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' updates.install_recommended
    '''
    cmd = '/usr/sbin/softwareupdate -i -r'
    out = __salt__['cmd.run'](cmd)
    return out


def list_ignored():
    '''
    List updates which have been ignored

    :return: A list of ignored updates
    :rtype: list

    CLI Example:

    .. code-block:: bash

        salt '*' updates.list_ignored
    '''
    cmd = '/usr/sbin/softwareupdate --ignore'
    out = __salt__['cmd.run'](cmd)

    ignored = []
    for line in out.splitlines():
        if re.search('^\s{4}"(.*)"', line):
            ignored.append(re.match('^\s{4}"(.*)"', line).group(1))

    return ignored


def clear_ignored():
    '''
    Clear the list of ignored updates

    :return: The results of the command
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' updates.clear_ignored
    '''
    cmd = '/usr/sbin/softwareupdate --reset-ignored'
    out = __salt__['cmd.run'](cmd)
    return out


def ignore(name):
    '''
    Ignore the update specified in the name

    :param str name: The name of the update to place on the ignore list

    :return: The results of the command
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' updates.ignore iTunesXPatch-12.1.2
    '''
    cmd = '/usr/sbin/softwareupdate --ignore {0}'.format(name)
    out = __salt__['cmd.run'](cmd)
    return out


def get_catalog():
    '''
    Get the current catalog being used for update lookups. Will return a url if
    a custom catalog has been specified. Otherwise the word 'Default' will be
    returned

    :return: The catalog being used for update lookups
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' updates.get_catalog
    '''
    cmd = 'defaults read /Library/Preferences/com.apple.SoftwareUpdate.plist ' \
          'CatalogURL'
    out = __salt__['cmd.run'](cmd)
    if 'does not exist' in out:
        return 'Default'
    return out


def set_catalog(url):
    '''
    Set the Software Update Catalog to the URL specified

    :param str url: The url to the update catalog

    :return: True if successfult, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' updates.set_url http://swupd.local:8888/index.sucatalog
    '''
    cmd = '/usr/sbin/softwareupdate --set-catalog {0}'.format(url)
    out = __salt__['cmd.run'](cmd)
    if url in out:
        return True
    else:
        return False


def reset_catalog():
    '''
    Reset the Software Update Catalog to the default.

    :return: True if successful, False if not
    :rtype: bool
    '''
    cmd = '/usr/sbin/softwareupdate --clear-catalog'
    out = __salt__['cmd.run'](cmd)
    return 'Default' == get_catalog()
