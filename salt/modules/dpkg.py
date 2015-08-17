# -*- coding: utf-8 -*-
'''
Support for DEB packages
'''
from __future__ import absolute_import

# Import python libs
import logging
import os

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError, SaltInvocationError

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'lowpkg'


def __virtual__():
    '''
    Confirm this module is on a Debian based system
    '''
    return __virtualname__ if __grains__['os_family'] == 'Debian' else False


def bin_pkg_info(path, saltenv='base'):
    '''
    .. versionadded:: 2015.8.0

    Parses RPM metadata and returns a dictionary of information about the
    package (name, version, etc.).

    path
        Path to the file. Can either be an absolute path to a file on the
        minion, or a salt fileserver URL (e.g. ``salt://path/to/file.rpm``).
        If a salt fileserver URL is passed, the file will be cached to the
        minion so that it can be examined.

    saltenv : base
        Salt fileserver envrionment from which to retrieve the package. Ignored
        if ``path`` is a local file path on the minion.

    CLI Example:

    .. code-block:: bash

        salt '*' lowpkg.bin_pkg_info /root/foo-1.2.3-1ubuntu1_all.deb
        salt '*' lowpkg.bin_pkg_info salt://foo-1.2.3-1ubuntu1_all.deb
    '''
    # If the path is a valid protocol, pull it down using cp.cache_file
    if __salt__['config.valid_fileproto'](path):
        newpath = __salt__['cp.cache_file'](path, saltenv)
        if not newpath:
            raise CommandExecutionError(
                'Unable to retrieve {0} from saltenv \'{1}\''
                .format(path, saltenv)
            )
        path = newpath
    else:
        if not os.path.exists(path):
            raise CommandExecutionError(
                '{0} does not exist on minion'.format(path)
            )
        elif not os.path.isabs(path):
            raise SaltInvocationError(
                '{0} does not exist on minion'.format(path)
            )

    cmd = ['dpkg', '-I', path]
    result = __salt__['cmd.run_all'](cmd, output_loglevel='trace')
    if result['retcode'] != 0:
        msg = 'Unable to get info for ' + path
        if result['stderr']:
            msg += ': ' + result['stderr']
        raise CommandExecutionError(msg)

    ret = {}
    for line in result['stdout'].splitlines():
        line = line.strip()
        if line.startswith('Package:'):
            ret['name'] = line.split()[-1]
        elif line.startswith('Version:'):
            ret['version'] = line.split()[-1]
        elif line.startswith('Architecture:'):
            ret['arch'] = line.split()[-1]

    missing = [x for x in ('name', 'version', 'arch') if x not in ret]
    if missing:
        raise CommandExecutionError(
            'Unable to get {0} for {1}'.format(', '.join(missing), path)
        )

    if __grains__.get('cpuarch', '') == 'x86_64':
        osarch = __grains__.get('osarch', '')
        arch = ret['arch']
        if arch != 'all' and osarch == 'amd64' and osarch != arch:
            ret['name'] += ':{0}'.format(arch)

    return ret


def unpurge(*packages):
    '''
    Change package selection for each package specified to 'install'

    CLI Example:

    .. code-block:: bash

        salt '*' lowpkg.unpurge curl
    '''
    if not packages:
        return {}
    old = __salt__['pkg.list_pkgs'](purge_desired=True)
    ret = {}
    __salt__['cmd.run'](
        ['dpkg', '--set-selections'],
        stdin=r'\n'.join(['{0} install'.format(x) for x in packages]),
        python_shell=False,
        output_loglevel='trace'
    )
    __context__.pop('pkg.list_pkgs', None)
    new = __salt__['pkg.list_pkgs'](purge_desired=True)
    return salt.utils.compare_dicts(old, new)


def list_pkgs(*packages):
    '''
    List the packages currently installed in a dict::

        {'<package_name>': '<version>'}

    External dependencies::

        Virtual package resolution requires aptitude. Because this function
        uses dpkg, virtual packages will be reported as not installed.

    CLI Example:

    .. code-block:: bash

        salt '*' lowpkg.list_pkgs
        salt '*' lowpkg.list_pkgs httpd
    '''
    pkgs = {}
    cmd = 'dpkg -l {0}'.format(' '.join(packages))
    out = __salt__['cmd.run_all'](cmd, python_shell=False)
    if out['retcode'] != 0:
        msg = 'Error:  ' + out['stderr']
        log.error(msg)
        return msg
    out = out['stdout']

    for line in out.splitlines():
        if line.startswith('ii '):
            comps = line.split()
            pkgs[comps[1]] = comps[2]
    return pkgs


def file_list(*packages):
    '''
    List the files that belong to a package. Not specifying any packages will
    return a list of _every_ file on the system's package database (not
    generally recommended).

    CLI Examples:

    .. code-block:: bash

        salt '*' lowpkg.file_list httpd
        salt '*' lowpkg.file_list httpd postfix
        salt '*' lowpkg.file_list
    '''
    errors = []
    ret = set([])
    pkgs = {}
    cmd = 'dpkg -l {0}'.format(' '.join(packages))
    out = __salt__['cmd.run_all'](cmd, python_shell=False)
    if out['retcode'] != 0:
        msg = 'Error:  ' + out['stderr']
        log.error(msg)
        return msg
    out = out['stdout']

    for line in out.splitlines():
        if line.startswith('ii '):
            comps = line.split()
            pkgs[comps[1]] = {'version': comps[2],
                              'description': ' '.join(comps[3:])}
        if 'No packages found' in line:
            errors.append(line)
    for pkg in pkgs:
        files = []
        cmd = 'dpkg -L {0}'.format(pkg)
        for line in __salt__['cmd.run'](cmd, python_shell=False).splitlines():
            files.append(line)
        fileset = set(files)
        ret = ret.union(fileset)
    return {'errors': errors, 'files': list(ret)}


def file_dict(*packages):
    '''
    List the files that belong to a package, grouped by package. Not
    specifying any packages will return a list of _every_ file on the system's
    package database (not generally recommended).

    CLI Examples:

    .. code-block:: bash

        salt '*' lowpkg.file_list httpd
        salt '*' lowpkg.file_list httpd postfix
        salt '*' lowpkg.file_list
    '''
    errors = []
    ret = {}
    pkgs = {}
    cmd = 'dpkg -l {0}'.format(' '.join(packages))
    out = __salt__['cmd.run_all'](cmd, python_shell=False)
    if out['retcode'] != 0:
        msg = 'Error:  ' + out['stderr']
        log.error(msg)
        return msg
    out = out['stdout']

    for line in out.splitlines():
        if line.startswith('ii '):
            comps = line.split()
            pkgs[comps[1]] = {'version': comps[2],
                              'description': ' '.join(comps[3:])}
        if 'No packages found' in line:
            errors.append(line)
    for pkg in pkgs:
        files = []
        cmd = 'dpkg -L {0}'.format(pkg)
        for line in __salt__['cmd.run'](cmd, python_shell=False).splitlines():
            files.append(line)
        ret[pkg] = files
    return {'errors': errors, 'packages': ret}
