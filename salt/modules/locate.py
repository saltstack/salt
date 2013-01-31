'''
Module for using the locate utilities
'''

# Import python libs
import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only work on posix-like systems
    '''
    # Disable on these platorms, specific service modules exist:
    disable = [
        'Windows',
        ]
    if __grains__['os'] in disable:
        return False
    return 'locate'


def version():
    '''
    Returns the version of locate

    CLI Example::

        salt '*' locate.version
    '''
    cmd = 'locate -V'
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def stats():
    '''
    Returns statistics about the locate database

    CLI Example::

        salt '*' locate.stats
    '''
    ret = {}
    cmd = 'locate -S'
    out = __salt__['cmd.run'](cmd).splitlines()
    for line in out:
        comps = line.strip().split()
        if line.startswith('Database'):
            ret['database'] = comps[1].replace(':', '')
            continue
        ret[' '.join(comps[1:])] = comps[0]
    return ret


def updatedb():
    '''
    Updates the locate database

    CLI Example::

        salt '*' locate.updatedb
    '''
    cmd = 'updatedb'
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def locate(pattern, database='', limit=0, **kwargs):
    '''
    Performs a file lookup. Valid options (and their defaults) are::

        basename=False
        count=False
        existing=False
        follow=True
        ignore=False
        nofollow=False
        wholename=True
        regex=False
        database=<locate's default database>
        limit=<integer, not set by default>

    See the manpage for locate for further explanation of these options.

    CLI Example::

        salt '*' locate.locate
    '''
    options = ''
    toggles = {
        'basename': 'b',
        'count': 'c',
        'existing': 'e',
        'follow': 'L',
        'ignore': 'i',
        'nofollow': 'P',
        'wholename': 'w',
        }
    for option in kwargs:
        if bool(kwargs[option]) is True:
            options += toggles[option]
    if options:
        options = '-{0}'.format(options)
    if database:
        options += ' -d {0}'.format(database)
    if limit > 0:
        options += ' -l {0}'.format(limit)
    if 'regex' in kwargs and bool(kwargs['regex']) is True:
        options += ' --regex'
    cmd = 'locate {0} {1}'.format(options, pattern)
    out = __salt__['cmd.run'](cmd).splitlines()
    return out

