# -*- coding: utf-8 -*-
'''
Support for rpm
'''
from __future__ import absolute_import

# Import python libs
import logging

# Import Salt libs
import salt.utils

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'lowpkg'


def __virtual__():
    '''
    Confine this module to rpm based systems
    '''
    if not salt.utils.which('rpm'):
        return False
    try:
        os_grain = __grains__['os'].lower()
        os_family = __grains__['os_family'].lower()
    except Exception:
        return False

    enabled = ('amazon', 'xcp', 'xenserver')

    if os_family in ['redhat', 'suse'] or os_grain in enabled:
        return __virtualname__
    return False


def list_pkgs(*packages):
    '''
    List the packages currently installed in a dict::

        {'<package_name>': '<version>'}

    CLI Example:

    .. code-block:: bash

        salt '*' lowpkg.list_pkgs
    '''
    pkgs = {}
    if not packages:
        cmd = 'rpm -qa --qf \'%{NAME} %{VERSION}\\n\''
    else:
        cmd = 'rpm -q --qf \'%{{NAME}} %{{VERSION}}\\n\' {0}'.format(
            ' '.join(packages)
        )
    out = __salt__['cmd.run'](cmd, python_shell=False, output_loglevel='trace')
    for line in out.splitlines():
        if 'is not installed' in line:
            continue
        comps = line.split()
        pkgs[comps[0]] = comps[1]
    return pkgs


def verify(*package, **kwargs):
    '''
    Runs an rpm -Va on a system, and returns the results in a dict

    Files with an attribute of config, doc, ghost, license or readme in the
    package header can be ignored using the ``ignore_types`` keyword argument

    CLI Example:

    .. code-block:: bash

        salt '*' lowpkg.verify
        salt '*' lowpkg.verify httpd
        salt '*' lowpkg.verify 'httpd postfix'
        salt '*' lowpkg.verify 'httpd postfix' ignore_types=['config','doc']
    '''
    ftypes = {'c': 'config',
              'd': 'doc',
              'g': 'ghost',
              'l': 'license',
              'r': 'readme'}
    ret = {}
    ignore_types = kwargs.get('ignore_types', [])
    if package:
        packages = ' '.join(package)
        cmd = 'rpm -V {0}'.format(packages)
    else:
        cmd = 'rpm -Va'
    out = __salt__['cmd.run'](
            cmd,
            python_shell=False,
            output_loglevel='trace',
            ignore_retcode=True)
    for line in out.splitlines():
        fdict = {'mismatch': []}
        if 'missing' in line:
            line = ' ' + line
            fdict['missing'] = True
            del fdict['mismatch']
        fname = line[13:]
        if line[11:12] in ftypes:
            fdict['type'] = ftypes[line[11:12]]
        if 'type' not in fdict or fdict['type'] not in ignore_types:
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
    ret = __salt__['cmd.run'](
            cmd,
            python_shell=False,
            output_loglevel='trace').splitlines()
    return {'errors': [], 'files': ret}


def file_dict(*packages):
    '''
    List the files that belong to a package, sorted by group. Not specifying
    any packages will return a list of _every_ file on the system's rpm
    database (not generally recommended).

    CLI Examples:

    .. code-block:: bash

        salt '*' lowpkg.file_dict httpd
        salt '*' lowpkg.file_dict httpd postfix
        salt '*' lowpkg.file_dict
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
    out = __salt__['cmd.run'](cmd, python_shell=False, output_loglevel='trace')
    for line in out.splitlines():
        if 'is not installed' in line:
            errors.append(line)
            continue
        comps = line.split()
        pkgs[comps[0]] = {'version': comps[1]}
    for pkg in pkgs:
        files = []
        cmd = 'rpm -ql {0}'.format(pkg)
        out = __salt__['cmd.run'](cmd, python_shell=False, output_loglevel='trace')
        for line in out.splitlines():
            files.append(line)
        ret[pkg] = files
    return {'errors': errors, 'packages': ret}


def owner(*paths):
    '''
    Return the name of the package that owns the file. Multiple file paths can
    be passed. If a single path is passed, a string will be returned,
    and if multiple paths are passed, a dictionary of file/package name pairs
    will be returned.

    If the file is not owned by a package, or is not present on the minion,
    then an empty string will be returned for that path.

    CLI Examples:

    .. code-block:: bash

        salt '*' lowpkg.owner /usr/bin/apachectl
        salt '*' lowpkg.owner /usr/bin/apachectl /etc/httpd/conf/httpd.conf
    '''
    if not paths:
        return ''
    ret = {}
    cmd = 'rpm -qf --queryformat "%{{NAME}}" {0!r}'
    for path in paths:
        ret[path] = __salt__['cmd.run_stdout'](cmd.format(path),
                                               output_loglevel='trace')
        if 'not owned' in ret[path].lower():
            ret[path] = ''
    if len(ret) == 1:
        return list(ret.values())[0]
    return ret
