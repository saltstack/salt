'''
Manage PHP pecl extensions.
'''

# Import python libs
import re


__opts__ = {}
__pillar__ = {}

def _pecl(command):
    cmdline = 'pecl {0}'.format(command)

    ret = __salt__['cmd.run_all'](cmdline)

    if ret['retcode'] == 0:
        return ret['stdout']
    else:
        return False


def install(pecls):
    '''
    Installs one or several pecl extensions.

    pecls
        The pecl extensions to install.
    '''
    return _pecl('install {0}'.format(pecls))


def uninstall(pecls):
    '''
    Uninstall one or several pecl extensions.

    pecls
        The pecl extensions to uninstall.
    '''
    return _pecl('uninstall {0}'.format(pecls))


def update(pecls):
    '''
    Update one or several pecl exntesions.

    pecls
        The pecl extensions to update.
    '''
    return _pecl('install -U {0}'.format(pecls))


def list():
    '''
    List installed pecl extensions.
    '''

    lines = _pecl('list').splitlines()
    lines.pop(0)
    lines.pop(0)
    lines.pop(0)

    pecls = {}
    for line in lines:
        m = re.match('^([^ ]+)[ ]+([^ ]+)[ ]+([^ ]+)', line)
        if m:
            pecls[m.group(1)] = [m.group(2), m.group(3)]

    return pecls



