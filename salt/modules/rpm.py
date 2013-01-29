'''
Support for rpm

:depends:   - rpmUtils Python module
'''

# Import python libs
import os
import logging

# Import third party libs
try:
    from rpmUtils.arch import getBaseArch
    HAS_RPMDEPS = True
except (ImportError, AttributeError):
    HAS_RPMDEPS = False

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Confine this module to rpm based systems
    '''
    if not HAS_RPMDEPS:
        return False

    # Work only on RHEL/Fedora based distros with python 2.6 or greater
    # TODO: Someone decide if we can just test os_family and pythonversion
    os_grain = __grains__['os']
    os_family = __grains__['os_family']
    try:
        os_major = int(__grains__['osrelease'].split('.')[0])
    except ValueError:
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


def verify(*package):
    '''
    Runs an rpm -Va on a system, and returns the results in a dict

    CLI Example::

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
            del(fdict['mismatch'])
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

    CLI Examples::

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

