# -*- coding: utf-8 -*-
'''
Support for rpm
'''

# Import python libs
import logging

# Import Salt libs
import salt.utils

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Confine this module to rpm based systems
    '''
    if not salt.utils.which('rpm'):
        return False

    # Work only on RHEL/Fedora based distros with python 2.6 or greater
    # TODO: Someone decide if we can just test os_family and pythonversion
    os_grain = __grains__['os']
    os_family = __grains__['os_family']
    try:
        os_major = int(__grains__['osrelease'].split('.')[0])
    except (AttributeError, ValueError):
        os_major = 0

    if os_grain == 'Amazon':
        return 'lowpkg'
    elif os_grain == 'Fedora':
        # Fedora <= 10 used Python 2.5 and below
        if os_major >= 11:
            return 'lowpkg'
    elif os_family == 'RedHat' and os_major >= 6:
        return 'lowpkg'
    return False


def list_pkgs(*packages):
    '''
    List the packages currently installed in a dict::

        {'<package_name>': '<version>'}

    CLI Example:

    .. code-block:: bash

        salt '*' lowpkg.list_pkgs
    '''
    errors = []
    pkgs = {}
    if not packages:
        cmd = 'rpm -qa --qf \'%{NAME} %{VERSION}\\n\''
    else:
        cmd = 'rpm -q --qf \'%{{NAME}} %{{VERSION}}\\n\' {0}'.format(
            ' '.join(packages)
        )
    for line in __salt__['cmd.run'](cmd).splitlines():
        if 'is not installed' in line:
            errors.append(line)
            continue
        comps = line.split()
        pkgs[comps[0]] = comps[1]
    return pkgs


def verify(*package):
    '''
    Runs an rpm -Va on a system, and returns the results in a dict

    CLI Example:

    .. code-block:: bash

        salt '*' lowpkg.verify
    '''
    ftypes = {'c': 'config',
              'd': 'doc',
              'g': 'ghost',
              'l': 'license',
              'r': 'readme'}
    ret = {}
    if package:
        packages = ' '.join(package)
        cmd = 'rpm -V {0}'.format(packages)
    else:
        cmd = 'rpm -Va'
    for line in __salt__['cmd.run'](cmd).split('\n'):
        fdict = {'mismatch': []}
        if 'missing' in line:
            line = ' ' + line
            fdict['missing'] = True
            del fdict['mismatch']
        fname = line[13:]
        if line[11:12] in ftypes:
            fdict['type'] = ftypes[line[11:12]]
        if line[0:1] == 'S':
            fdict['mismatch'].append('size')
        if line[1:2] == 'M':
            fdict['mismatch'].append('mode')
        if line[2:3] == '5':
            fdict['mismatch'].append('md5sum')
        if line[3:4] == 'D':
            fdict['mismatch'].append('device major/minor number')
        if line[4:5] == 'L':
            fdict['mismatch'].append('readlink path')
        if line[5:6] == 'U':
            fdict['mismatch'].append('user')
        if line[6:7] == 'G':
            fdict['mismatch'].append('group')
        if line[7:8] == 'T':
            fdict['mismatch'].append('mtime')
        if line[8:9] == 'P':
            fdict['mismatch'].append('capabilities')
        ret[fname] = fdict
    return ret


def file_list(*packages):
    '''
    List the files that belong to a package. Not specifying any packages will
    return a list of _every_ file on the system's rpm database (not generally
    recommended).

    CLI Examples:

    .. code-block:: bash

        salt '*' lowpkg.file_list httpd
        salt '*' lowpkg.file_list httpd postfix
        salt '*' lowpkg.file_list
    '''
    if not packages:
        cmd = 'rpm -qla'
    else:
        cmd = 'rpm -ql {0}'.format(' '.join(packages))
    ret = __salt__['cmd.run'](cmd).splitlines()
    return {'errors': [], 'files': ret}


def file_dict(*packages):
    '''
    List the files that belong to a package, sorted by group. Not specifying
    any packages will return a list of _every_ file on the system's rpm
    database (not generally recommended).

    CLI Examples:

    .. code-block:: bash

        salt '*' lowpkg.file_list httpd
        salt '*' lowpkg.file_list httpd postfix
        salt '*' lowpkg.file_list
    '''
    errors = []
    ret = {}
    pkgs = {}
    if not packages:
        cmd = 'rpm -qa --qf \'%{NAME} %{VERSION}\\n\''
    else:
        cmd = 'rpm -q --qf \'%{{NAME}} %{{VERSION}}\\n\' {0}'.format(
            ' '.join(packages)
        )
    for line in __salt__['cmd.run'](cmd).splitlines():
        if 'is not installed' in line:
            errors.append(line)
            continue
        comps = line.split()
        pkgs[comps[0]] = {'version': comps[1]}
    for pkg in pkgs.keys():
        files = []
        cmd = 'rpm -ql {0}'.format(pkg)
        for line in __salt__['cmd.run'](cmd).splitlines():
            files.append(line)
        ret[pkg] = files
    return {'errors': errors, 'packages': ret}
