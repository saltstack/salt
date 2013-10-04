# -*- coding: utf-8 -*-
'''
Support for DEB packages
'''

# Import python libs
import logging


log = logging.getLogger(__name__)


def __virtual__():
    '''
    Confirm this module is on a Debian based system
    '''
    return 'lowpkg' if __grains__['os_family'] == 'Debian' else False


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
    out = __salt__['cmd.run_all'](cmd)
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
    out = __salt__['cmd.run_all'](cmd)
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
    for pkg in pkgs.keys():
        files = []
        cmd = 'dpkg -L {0}'.format(pkg)
        for line in __salt__['cmd.run'](cmd).splitlines():
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
    out = __salt__['cmd.run_all'](cmd)
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
    for pkg in pkgs.keys():
        files = []
        cmd = 'dpkg -L {0}'.format(pkg)
        for line in __salt__['cmd.run'](cmd).splitlines():
            files.append(line)
        ret[pkg] = files
    return {'errors': errors, 'packages': ret}
