'''
Support for Gentoolkit

'''

import salt.utils

HAS_GENTOOLKIT = False

# Import third party libs
try:
    from gentoolkit.eclean.search import DistfilesSearch
    from gentoolkit.eclean.cli import parseSize, parseTime
    HAS_GENTOOLKIT = True
except ImportError:
    pass

def __virtual__():
    '''
    Only work on Gentoo systems with gentoolkit installed
    '''
    if __grains__['os'] == 'Gentoo' and HAS_GENTOOLKIT:
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

def eclean_dist(destructive=False, package_names=False, size_limit=0,
                time_limit=0, fetch_restricted=False):
    '''
    Clean obsolete portage sources

    destructive
        Only keep minimum for reinstallation

    package_names
        Protect all versions of installed packages. Only meaningful if used
        with destructive=True

    size_limit <size>
        Don't delete distfiles bigger than <size>.
        <size> is a size specification: "10M" is "ten megabytes",
        "200K" is "two hundreds kilobytes", etc. Units are: G, M, K and B.

    time_limit <time>
        Don't delete distfiles files modified since <time>
        <time> is an amount of time: "1y" is "one year", "2w" is
        "two weeks", etc. Units are: y (years), m (months), w (weeks),
        d (days) and h (hours).

    fetch_restricted
        Protect fetch-restricted files. Only meaningful if used with
        destructive=True

    CLI Example::
        salt '*' gentoolkit.eclean_dist destructive=True
    '''

    dfs = DistfilesSearch(lambda x: None)
    search_kwargs = dict()
    search_kwargs['destructive'] = destructive
    search_kwargs['package_names'] = package_names
    search_kwargs['fetch_restricted'] = fetch_restricted
    if time_limit is not 0:
        search_kwargs['time_limit'] = parseTime(time_limit)
    if size_limit is not 0:
        search_kwargs['size_limit'] = parseSize(size_limit)
    cleaned, saved, deprecated  = dfs.findDistfiles(**search_kwargs)

    ret = {'cleaned': cleaned, 'saved': saved, 'deprecated': deprecated}

    cmd = 'eclean-dist --quiet --pretend'
    if destructive:
        cmd += ' --destructive'
    if package_names:
        cmd += ' --package-names'
    if size_limit is not 0:
        cmd += ' --size-limit={0}'.format(size_limit)
    if time_limit is not 0:
        cmd += ' --time-limit={0}'.format(time_limit)
    if fetch_restricted:
        cmd += ' --fetch-restricted'
    if __salt__['cmd.retcode'](cmd) == 0:
        return ret
    return dict()
