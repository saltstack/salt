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
    if salt.utils.is_darwin():
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
    Determine whether the automatic checking schedule is on.
    Returns True or False
    CLI Example:
    .. code-block:: bash
        salt '*' swupd.scheduled
    '''
    out = __salt__['cmd.run']('/usr/sbin/softwareupdate --schedule')

    if re.search('on', out):
        return True
    else:
        return False


def schedule(enabled):
    '''
    Enable/Disable the automatic checking schedule.
    CLI Example:
    .. code-block:: bash
        salt '*' swupd.schedule True
    '''
    if enabled:
        out = __salt__['cmd.run']('/usr/sbin/softwareupdate --schedule on')
    else:
        out = __salt__['cmd.run']('/usr/sbin/softwareupdate --schedule off')

    return out


def list():
    '''
    List available software updates. (Warning: can take a while to execute)
    CLI Example:
    .. code-block:: bash
        salt '*' swupd.list
    '''
    log.debug('Fetching available updates, this may take some time')
    out = __salt__['cmd.run']('/usr/sbin/softwareupdate -l')

    packages = _parse_packages(out)

    return packages


def install(label):
    '''
    Install a specific update by its label.
    CLI Example:
    .. code-block:: bash
        salt '*' swupd.install 'iTunesXPatch-12.1.2'
    '''
    out = __salt__['cmd.run']('/usr/sbin/softwareupdate -i {0}'.format(label))
    return out


def install_all():
    '''
    Install all pending software updates
    CLI Example:
    .. code-block:: bash
        salt '*' swupd.install_all
    '''
    out = __salt__['cmd.run']('/usr/sbin/softwareupdate -i -a')
    return out


def install_recommended():
    '''
    Install recommended software updates
    CLI Example:
    .. code-block:: bash
        salt '*' swupd.install_all
    '''
    out = __salt__['cmd.run']('/usr/sbin/softwareupdate -i -r')
    return out


def list_ignored():
    '''
    List updates which have been ignored
    CLI Example:
    .. code-block:: bash
        salt '*' swupd.list_ignored
    '''
    out = __salt__['cmd.run']('/usr/sbin/softwareupdate --ignore')
    ignored = []

    for line in out.splitlines():
        if re.search('^\s{4}"(.*)"', line):
            ignored.append(re.match('^\s{4}"(.*)"', line).group(1))

    return ignored


def clear_ignored():
    '''
    Clear the list of ignored updates
    CLI Example:
    .. code-block:: bash
        salt '*' swupd.clear_ignored
    '''
    out = __salt__['cmd.run']('/usr/sbin/softwareupdate --reset-ignored')
    return out


def ignore(label):
    '''
    Ignore a specific update by label
    CLI Example:
    .. code-block:: bash
        salt '*' swupd.ignore iTunesXPatch-12.1.2
    '''
    out = __salt__['cmd.run']('/usr/sbin/softwareupdate --ignore {0}'.format(label))
    return out


def set_catalog_url(catalog_url):
    '''
    Set the Software Update Catalog URL
    CLI Example:
    .. code-block:: bash
        salt '*' swupd.set_url http://swupd.local:8888/index.sucatalog
    '''
    out = __salt__['cmd.run']('/usr/sbin/softwareupdate --set-catalog {0}'.format(catalog_url))
    return out
