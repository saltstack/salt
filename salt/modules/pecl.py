'''
Manage PHP pecl extensions.
'''

# Import python libs
import re
import logging


__opts__ = {}
__pillar__ = {}

__func_alias__ = {
    'list_': 'list'
}

log = logging.getLogger(__name__)


def _pecl(command):
    '''
    Execute the command passed with pecl
    '''
    cmdline = 'pecl {0}'.format(command)

    ret = __salt__['cmd.run_all'](cmdline)

    if ret['retcode'] == 0:
        return ret['stdout']
    else:
        log.error('Problem running pecl. Is php-pear installed?')
        return ''


def install(pecls):
    '''
    Installs one or several pecl extensions.

    pecls
        The pecl extensions to install.

    CLI Example::

        salt '*' pecl.install fuse
    '''
    return _pecl('install {0}'.format(pecls))


def uninstall(pecls):
    '''
    Uninstall one or several pecl extensions.

    pecls
        The pecl extensions to uninstall.

    CLI Example::

        salt '*' pecl.uninstall fuse
    '''
    return _pecl('uninstall {0}'.format(pecls))


def update(pecls):
    '''
    Update one or several pecl extensions.

    pecls
        The pecl extensions to update.

    CLI Example::

        salt '*' pecl.update fuse
    '''
    return _pecl('install -U {0}'.format(pecls))


def list_():
    '''
    List installed pecl extensions.

    CLI Example::

        salt '*' pecl.list
    '''
    pecls = {}
    lines = _pecl('list').splitlines()
    lines.pop(0)
    # Only one line if no package installed:
    # (no packages installed from channel pecl.php.net)
    if not lines:
        return pecls

    lines.pop(0)
    lines.pop(0)

    for line in lines:
        match = re.match('^([^ ]+)[ ]+([^ ]+)[ ]+([^ ]+)', line)
        if match:
            pecls[match.group(1)] = [match.group(2), match.group(3)]

    return pecls
