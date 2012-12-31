'''
Support for Gentoolkit

'''

import os

HAS_GENTOOLKIT = False

# Import third party libs
try:
    from gentoolkit.eclean import search, clean, cli, exclude as excludemod
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

def _pretty_size(size):
    '''
    Print sizes in a similar fashion as eclean
    '''
    units = [' G', ' M', ' K', ' B']
    while len(units) and size >= 1000:
        size = size / 1024.0
        units.pop()
    return '{0}{1}'.format(round(size,1), units[-1])

def _parse_exclude(exclude_file):
    '''
    Parse an exclude file.

    Return a dict as defined in gentoolkit.eclean.exclude.parseExcludeFile
    '''
    if os.path.isfile(exclude_file):
        exclude = excludemod.parseExcludeFile(exclude_file, lambda x: None)
    else:
        exclude = dict()
    return exclude

def eclean_dist(destructive=False, package_names=False, size_limit=0,
                time_limit=0, fetch_restricted=False,
                exclude_file='/etc/eclean/distfiles.exclude'):
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

    exclude_file
        Path to exclusion file. Default is /etc/eclean/distfiles.exclude
        This is the same default eclean-dist uses. Use None if this file
        exists and you want to ignore.

    Return a dict containing the cleaned, saved, and deprecated dists::

        {'cleaned': {<dist file>: <size>},
         'deprecated': {<package>: <dist file>},
         'saved': {<package>: <dist file>},
         'total_cleaned': <size>}

    CLI Example::
        salt '*' gentoolkit.eclean_dist destructive=True
    '''
    try:
        exclude = None
        if exclude_file is not None:
            exclude = _parse_exclude(exclude_file)

        if time_limit is not 0:
            time_limit = cli.parseTime(time_limit)
        if size_limit is not 0:
            size_limit = cli.parseSize(size_limit)

        clean_size=0
        engine = search.DistfilesSearch(lambda x: None)
        clean_me, saved, deprecated = engine.findDistfiles(
            destructive=destructive, package_names=package_names,
            size_limit=size_limit, time_limit=time_limit,
            fetch_restricted=fetch_restricted, exclude=exclude)

        cleaned = dict()
        def _eclean_progress_controller(size, key, *args):
            cleaned[key] = _pretty_size(size)
            return True

        if clean_me:
            cleaner = clean.CleanUp(_eclean_progress_controller)
            clean_size = cleaner.clean_dist(clean_me)

        ret = {'cleaned': cleaned, 'saved': saved, 'deprecated': deprecated,
               'total_cleaned': _pretty_size(clean_size)}
    except excludemod.ParseExcludeFileException as e:
        ret = {e: 'Invalid exclusion file: {0}'.format(exclude_file)}
    finally:
        return ret

def eclean_pkg(destructive=False, package_names=False, time_limit=0,
               exclude_file='/etc/eclean/packages.exclude'):
    '''
    Clean obsolete binary packages

    destructive
        Only keep minimum for reinstallation

    package_names
        Protect all versions of installed packages. Only meaningful if used
        with destructive=True

    time_limit <time>
        Don't delete distfiles files modified since <time>
        <time> is an amount of time: "1y" is "one year", "2w" is
        "two weeks", etc. Units are: y (years), m (months), w (weeks),
        d (days) and h (hours).

    exclude_file
        Path to exclusion file. Default is /etc/eclean/packages.exclude
        This is the same default eclean-pkg uses. Use None if this file
        exists and you want to ignore.

    Return a dict containing the cleaned binary packages::

        {'cleaned': {<dist file>: <size>},
         'total_cleaned': <size>}

    CLI Example::
        salt '*' gentoolkit.eclean_pkg destructive=True
    '''
    try:
        exclude = None
        if exclude_file is not None:
            exclude = _parse_exclude(exclude_file)

        if time_limit is not 0:
            time_limit = cli.parseTime(time_limit)

        clean_size=0
        # findPackages requires one arg, but does nothing with it.
        # So we will just pass None in for the required arg
        clean_me = search.findPackages(None, destructive=destructive,
                                       package_names=package_names,
                                       time_limit=time_limit, exclude=exclude,
                                       pkgdir=search.pkgdir)

        cleaned = dict()
        def _eclean_progress_controller(size, key, *args):
            cleaned[key] = _pretty_size(size)
            return True

        if clean_me:
            cleaner = clean.CleanUp(_eclean_progress_controller)
            clean_size = cleaner.clean_pkgs(clean_me, search.pkgdir)

        ret = {'cleaned': cleaned,
               'total_cleaned': _pretty_size(clean_size)}
    except excludemod.ParseExcludeFileException as e:
        ret = {e: 'Invalid exclusion file: {0}'.format(exclude_file)}
    finally:
        return ret
