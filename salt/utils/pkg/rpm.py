# -*- coding: utf-8 -*-
'''
Common functions for working with RPM packages
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import collections
import datetime
import logging
import subprocess

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import range  # pylint: disable=redefined-builtin

log = logging.getLogger(__name__)

# These arches compiled from the rpmUtils.arch python module source
ARCHES_64 = ('x86_64', 'athlon', 'amd64', 'ia32e', 'ia64', 'geode')
ARCHES_32 = ('i386', 'i486', 'i586', 'i686')
ARCHES_PPC = ('ppc', 'ppc64', 'ppc64iseries', 'ppc64pseries')
ARCHES_S390 = ('s390', 's390x')
ARCHES_SPARC = (
    'sparc', 'sparcv8', 'sparcv9', 'sparcv9v', 'sparc64', 'sparc64v'
)
ARCHES_ALPHA = (
    'alpha', 'alphaev4', 'alphaev45', 'alphaev5', 'alphaev56',
    'alphapca56', 'alphaev6', 'alphaev67', 'alphaev68', 'alphaev7'
)
ARCHES_ARM = ('armv5tel', 'armv5tejl', 'armv6l', 'armv7l')
ARCHES_SH = ('sh3', 'sh4', 'sh4a')

ARCHES = ARCHES_64 + ARCHES_32 + ARCHES_PPC + ARCHES_S390 + \
    ARCHES_ALPHA + ARCHES_ARM + ARCHES_SH

# EPOCHNUM can't be used until RHEL5 is EOL as it is not present
QUERYFORMAT = '%{NAME}_|-%{EPOCH}_|-%{VERSION}_|-%{RELEASE}_|-%{ARCH}_|-%{REPOID}_|-%{INSTALLTIME}'


def get_osarch():
    '''
    Get the os architecture using rpm --eval
    '''
    ret = subprocess.Popen(
        'rpm --eval "%{_host_cpu}"',
        shell=True,
        close_fds=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE).communicate()[0]
    return ret or 'unknown'


def check_32(arch, osarch=None):
    '''
    Returns True if both the OS arch and the passed arch are 32-bit
    '''
    if osarch is None:
        osarch = get_osarch()
    return all(x in ARCHES_32 for x in (osarch, arch))


def pkginfo(name, version, arch, repoid, install_date=None, install_date_time_t=None):
    '''
    Build and return a pkginfo namedtuple
    '''
    pkginfo_tuple = collections.namedtuple(
        'PkgInfo',
        ('name', 'version', 'arch', 'repoid', 'install_date',
         'install_date_time_t')
    )
    return pkginfo_tuple(name, version, arch, repoid, install_date,
                         install_date_time_t)


def resolve_name(name, arch, osarch=None):
    '''
    Resolve the package name and arch into a unique name referred to by salt.
    For example, on a 64-bit OS, a 32-bit package will be pkgname.i386.
    '''
    if osarch is None:
        osarch = get_osarch()

    if not check_32(arch, osarch) and arch not in (osarch, 'noarch'):
        name += '.{0}'.format(arch)
    return name


def parse_pkginfo(line, osarch=None):
    '''
    A small helper to parse an rpm/repoquery command's output. Returns a
    pkginfo namedtuple.
    '''
    try:
        name, epoch, version, release, arch, repoid, install_time = line.split('_|-')
    # Handle unpack errors (should never happen with the queryformat we are
    # using, but can't hurt to be careful).
    except ValueError:
        return None

    name = resolve_name(name, arch, osarch)
    if release:
        version += '-{0}'.format(release)
    if epoch not in ('(none)', '0'):
        version = ':'.join((epoch, version))

    if install_time not in ('(none)', '0'):
        install_date = datetime.datetime.utcfromtimestamp(int(install_time)).isoformat() + "Z"
        install_date_time_t = int(install_time)
    else:
        install_date = None
        install_date_time_t = None

    return pkginfo(name, version, arch, repoid, install_date, install_date_time_t)


def combine_comments(comments):
    '''
    Given a list of comments, strings, a single comment or a single string,
    return a single string of text containing all of the comments, prepending
    the '#' and joining with newlines as necessary.
    '''
    if not isinstance(comments, list):
        comments = [comments]
    for idx in range(len(comments)):
        if not isinstance(comments[idx], six.string_types):
            comments[idx] = six.text_type(comments[idx])
        comments[idx] = comments[idx].strip()
        if not comments[idx].startswith('#'):
            comments[idx] = '#' + comments[idx]
    return '\n'.join(comments)


def version_to_evr(verstring):
    '''
    Split the package version string into epoch, version and release.
    Return this as tuple.

    The epoch is always not empty. The version and the release can be an empty
    string if such a component could not be found in the version string.

    "2:1.0-1.2" => ('2', '1.0', '1.2)
    "1.0" => ('0', '1.0', '')
    "" => ('0', '', '')
    '''
    if verstring in [None, '']:
        return '0', '', ''

    idx_e = verstring.find(':')
    if idx_e != -1:
        try:
            epoch = six.text_type(int(verstring[:idx_e]))
        except ValueError:
            # look, garbage in the epoch field, how fun, kill it
            epoch = '0'  # this is our fallback, deal
    else:
        epoch = '0'
    idx_r = verstring.find('-')
    if idx_r != -1:
        version = verstring[idx_e + 1:idx_r]
        release = verstring[idx_r + 1:]
    else:
        version = verstring[idx_e + 1:]
        release = ''

    return epoch, version, release
