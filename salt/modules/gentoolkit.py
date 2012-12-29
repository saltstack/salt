'''
Support for Gentoolkit

'''

import salt.utils

def __virtual__():
    '''
    Only work on Gentoo systems with gentoolkit installed
    '''
    if __grains__['os'] == 'Gentoo' and salt.utils.which('revdep-rebuild'):
        return 'gentoolkit'
    return False

def revdep_rebuild(lib=None):
    '''
    Fix up broken reverse dependencies

    lib
        Search for reverse dependencies for a particular library rather
        than every library on the system. It can be a full path to a
        library or basic regular expression.

    CLI Example::

        salt '*' gentoolkit.revdep_rebuild
    '''
    cmd = 'revdep-rebuild --quiet --no-progress'
    if lib is not None:
        cmd += ' --library={0}'.format(lib)
    return __salt__['cmd.retcode'](cmd) == 0

def eclean_dist(destructive=False, pkg_names=False, size=False, time=False, restricted=False):
    '''
    Clean obsolete portage sources

    destructive
        Only keep minimum for reinstallation

    pkg_names
        Protect all versions of installed packages. Only meaningful if used
        with destructive=True

    size <size>
        Don't delete distfiles bigger than <size>.
        <size> is a size specification: "10M" is "ten megabytes",
        "200K" is "two hundreds kilobytes", etc. Units are: G, M, K and B.

    time <time>
        Don't delete distfiles files modified since <time>
        <time> is an amount of time: "1y" is "one year", "2w" is
        "two weeks", etc. Units are: y (years), m (months), w (weeks),
        d (days) and h (hours).

    restricted
        Protect fetch-restricted files. Only meaningful if used with
        destructive=True

    CLI Example::
        salt '*' gentoolkit.eclean_dist destructive=True
    '''
    cmd = 'eclean-dist --quiet'
    if destructive:
        cmd += ' --destructive'
    if pkg_names:
        cmd += ' --package-names'
    if size:
        cmd += ' --size-limit={0}'.format(size)
    if time:
        cmd += ' --time-limit={0}'.format(time)
    if restricted:
        cmd += ' --fetch-restricted'
    return __salt__['cmd.retcode'](cmd) == 0
