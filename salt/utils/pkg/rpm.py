# -*- coding: utf-8 -*-
'''
Common
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import salt libs
from salt._compat import subprocess

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

QUERYFORMAT = '%{NAME}_|-%{VERSION}_|-%{RELEASE}_|-%{ARCH}_|-%{REPOID}'


def _osarch():
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
        osarch = _osarch()
    return all(x in ARCHES_32 for x in (osarch, arch))


def parse_pkginfo(line, osarch=None):
    '''
    A small helper to parse an rpm/repoquery command's output. Returns a
    namedtuple
    '''
    # Importing `collections` here since this function is re-namespaced into
    # another module
    import collections
    pkginfo = collections.namedtuple(
        'PkgInfo',
        ('name', 'version', 'arch', 'repoid')
    )

    try:
        name, pkg_version, release, arch, repoid = line.split('_|-')
    # Handle unpack errors (should never happen with the queryformat we are
    # using, but can't hurt to be careful).
    except ValueError:
        return None

    if osarch is None:
        osarch = _osarch()

    if not check_32(arch):
        if arch not in (osarch, 'noarch'):
            name += '.{0}'.format(arch)
    if release:
        pkg_version += '-{0}'.format(release)

    return pkginfo(name, pkg_version, arch, repoid)
