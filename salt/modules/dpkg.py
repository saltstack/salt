# -*- coding: utf-8 -*-
'''
Support for DEB packages
'''
from __future__ import absolute_import

# Import python libs
import logging

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'lowpkg'


def __virtual__():
    '''
    Confirm this module is on a Debian based system
    '''
    return __virtualname__ if __grains__['os_family'] == 'Debian' else False


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
