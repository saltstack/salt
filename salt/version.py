# -*- coding: utf-8 -*-
'''
Set up the version of Salt
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import re
import sys
import platform
import warnings

# linux_distribution deprecated in py3.7
try:
    from platform import linux_distribution as _deprecated_linux_distribution

    def linux_distribution(**kwargs):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return _deprecated_linux_distribution(**kwargs)
except ImportError:
    from distro import linux_distribution

# pylint: disable=invalid-name,redefined-builtin
# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import map

# Don't rely on external packages in this module since it's used at install time
if sys.version_info[0] == 3:
    MAX_SIZE = sys.maxsize
    string_types = (str,)
else:
    MAX_SIZE = sys.maxint
    string_types = (six.string_types,)
# pylint: enable=invalid-name,redefined-builtin

# ----- ATTENTION --------------------------------------------------------------------------------------------------->
#
# ALL major version bumps, new release codenames, MUST be defined in the SaltStackVersion.NAMES dictionary, i.e.:
#
#    class SaltStackVersion(object):
#
#        NAMES = {
#            'Hydrogen': (2014, 1),   # <- This is the tuple to bump versions
#            ( ... )
#        }
#
#
# ONLY UPDATE CODENAMES AFTER BRANCHING
#
# As an example, The Helium codename must only be properly defined with "(2014, 7)" after Hydrogen, "(2014, 1)", has
# been branched out into it's own branch.
#
# ALL OTHER VERSION INFORMATION IS EXTRACTED FROM THE GIT TAGS
#
# <---- ATTENTION ----------------------------------------------------------------------------------------------------


class SaltStackVersion(object):
    '''
    Handle SaltStack versions class.

    Knows how to parse ``git describe`` output, knows about release candidates
    and also supports version comparison.
    '''

    __slots__ = ('name', 'major', 'minor', 'bugfix', 'mbugfix', 'pre_type', 'pre_num', 'noc', 'sha')

    git_describe_regex = re.compile(
        r'(?:[^\d]+)?(?P<major>[\d]{1,4})'
        r'\.(?P<minor>[\d]{1,2})'
        r'(?:\.(?P<bugfix>[\d]{0,2}))?'
        r'(?:\.(?P<mbugfix>[\d]{0,2}))?'
        r'(?:(?P<pre_type>rc|a|b|alpha|beta|nb)(?P<pre_num>[\d]{1}))?'
        r'(?:(?:.*)-(?P<noc>(?:[\d]+|n/a))-(?P<sha>[a-z0-9]{8}))?'
    )
    git_sha_regex = r'(?P<sha>[a-z0-9]{7})'
    if six.PY2:
        git_sha_regex = git_sha_regex.decode(__salt_system_encoding__)
    git_sha_regex = re.compile(git_sha_regex)

    # Salt versions after 0.17.0 will be numbered like:
    #   <4-digit-year>.<month>.<bugfix>
    #
    # Since the actual version numbers will only be know on release dates, the
    # periodic table element names will be what's going to be used to name
    # versions and to be able to mention them.

    NAMES = {
        # Let's keep at least 3 version names uncommented counting from the
        # latest release so we can map deprecation warnings to versions.


        # pylint: disable=E8203
        # ----- Please refrain from fixing PEP-8 E203 and E265 ----->
        # The idea is to keep this readable.
        # -----------------------------------------------------------
        'Hydrogen'      : (2014, 1),
        'Helium'        : (2014, 7),
        'Lithium'       : (2015, 5),
        'Beryllium'     : (2015, 8),
        'Boron'         : (2016, 3),
        'Carbon'        : (2016, 11),
        'Nitrogen'      : (2017, 7),
        'Oxygen'        : (2018, 3),
        'Fluorine'      : (2019, 2),
        'Neon'          : (MAX_SIZE - 99, 0),
        'Sodium'        : (MAX_SIZE - 98, 0),
        'Magnesium'     : (MAX_SIZE - 97, 0),
        # pylint: disable=E8265
        #'Aluminium'    : (MAX_SIZE - 96, 0),
        #'Silicon'      : (MAX_SIZE - 95, 0),
        #'Phosphorus'   : (MAX_SIZE - 94, 0),
        #'Sulfur'       : (MAX_SIZE - 93, 0),
        #'Chlorine'     : (MAX_SIZE - 92, 0),
        #'Argon'        : (MAX_SIZE - 91, 0),
        #'Potassium'    : (MAX_SIZE - 90, 0),
        #'Calcium'      : (MAX_SIZE - 89, 0),
        #'Scandium'     : (MAX_SIZE - 88, 0),
        #'Titanium'     : (MAX_SIZE - 87, 0),
        #'Vanadium'     : (MAX_SIZE - 86, 0),
        #'Chromium'     : (MAX_SIZE - 85, 0),
        #'Manganese'    : (MAX_SIZE - 84, 0),
        #'Iron'         : (MAX_SIZE - 83, 0),
        #'Cobalt'       : (MAX_SIZE - 82, 0),
        #'Nickel'       : (MAX_SIZE - 81, 0),
        #'Copper'       : (MAX_SIZE - 80, 0),
        #'Zinc'         : (MAX_SIZE - 79, 0),
        #'Gallium'      : (MAX_SIZE - 78, 0),
        #'Germanium'    : (MAX_SIZE - 77, 0),
        #'Arsenic'      : (MAX_SIZE - 76, 0),
        #'Selenium'     : (MAX_SIZE - 75, 0),
        #'Bromine'      : (MAX_SIZE - 74, 0),
        #'Krypton'      : (MAX_SIZE - 73, 0),
        #'Rubidium'     : (MAX_SIZE - 72, 0),
        #'Strontium'    : (MAX_SIZE - 71, 0),
        #'Yttrium'      : (MAX_SIZE - 70, 0),
        #'Zirconium'    : (MAX_SIZE - 69, 0),
        #'Niobium'      : (MAX_SIZE - 68, 0),
        #'Molybdenum'   : (MAX_SIZE - 67, 0),
        #'Technetium'   : (MAX_SIZE - 66, 0),
        #'Ruthenium'    : (MAX_SIZE - 65, 0),
        #'Rhodium'      : (MAX_SIZE - 64, 0),
        #'Palladium'    : (MAX_SIZE - 63, 0),
        #'Silver'       : (MAX_SIZE - 62, 0),
        #'Cadmium'      : (MAX_SIZE - 61, 0),
        #'Indium'       : (MAX_SIZE - 60, 0),
        #'Tin'          : (MAX_SIZE - 59, 0),
        #'Antimony'     : (MAX_SIZE - 58, 0),
        #'Tellurium'    : (MAX_SIZE - 57, 0),
        #'Iodine'       : (MAX_SIZE - 56, 0),
        #'Xenon'        : (MAX_SIZE - 55, 0),
        #'Caesium'      : (MAX_SIZE - 54, 0),
        #'Barium'       : (MAX_SIZE - 53, 0),
        #'Lanthanum'    : (MAX_SIZE - 52, 0),
        #'Cerium'       : (MAX_SIZE - 51, 0),
        #'Praseodymium' : (MAX_SIZE - 50, 0),
        #'Neodymium'    : (MAX_SIZE - 49, 0),
        #'Promethium'   : (MAX_SIZE - 48, 0),
        #'Samarium'     : (MAX_SIZE - 47, 0),
        #'Europium'     : (MAX_SIZE - 46, 0),
        #'Gadolinium'   : (MAX_SIZE - 45, 0),
        #'Terbium'      : (MAX_SIZE - 44, 0),
        #'Dysprosium'   : (MAX_SIZE - 43, 0),
        #'Holmium'      : (MAX_SIZE - 42, 0),
        #'Erbium'       : (MAX_SIZE - 41, 0),
        #'Thulium'      : (MAX_SIZE - 40, 0),
        #'Ytterbium'    : (MAX_SIZE - 39, 0),
        #'Lutetium'     : (MAX_SIZE - 38, 0),
        #'Hafnium'      : (MAX_SIZE - 37, 0),
        #'Tantalum'     : (MAX_SIZE - 36, 0),
        #'Tungsten'     : (MAX_SIZE - 35, 0),
        #'Rhenium'      : (MAX_SIZE - 34, 0),
        #'Osmium'       : (MAX_SIZE - 33, 0),
        #'Iridium'      : (MAX_SIZE - 32, 0),
        #'Platinum'     : (MAX_SIZE - 31, 0),
        #'Gold'         : (MAX_SIZE - 30, 0),
        #'Mercury'      : (MAX_SIZE - 29, 0),
        #'Thallium'     : (MAX_SIZE - 28, 0),
        #'Lead'         : (MAX_SIZE - 27, 0),
        #'Bismuth'      : (MAX_SIZE - 26, 0),
        #'Polonium'     : (MAX_SIZE - 25, 0),
        #'Astatine'     : (MAX_SIZE - 24, 0),
        #'Radon'        : (MAX_SIZE - 23, 0),
        #'Francium'     : (MAX_SIZE - 22, 0),
        #'Radium'       : (MAX_SIZE - 21, 0),
        #'Actinium'     : (MAX_SIZE - 20, 0),
        #'Thorium'      : (MAX_SIZE - 19, 0),
        #'Protactinium' : (MAX_SIZE - 18, 0),
        #'Uranium'      : (MAX_SIZE - 17, 0),
        #'Neptunium'    : (MAX_SIZE - 16, 0),
        #'Plutonium'    : (MAX_SIZE - 15, 0),
        #'Americium'    : (MAX_SIZE - 14, 0),
        #'Curium'       : (MAX_SIZE - 13, 0),
        #'Berkelium'    : (MAX_SIZE - 12, 0),
        #'Californium'  : (MAX_SIZE - 11, 0),
        #'Einsteinium'  : (MAX_SIZE - 10, 0),
        #'Fermium'      : (MAX_SIZE - 9, 0),
        #'Mendelevium'  : (MAX_SIZE - 8, 0),
        #'Nobelium'     : (MAX_SIZE - 7, 0),
        #'Lawrencium'   : (MAX_SIZE - 6, 0),
        #'Rutherfordium': (MAX_SIZE - 5, 0),
        #'Dubnium'      : (MAX_SIZE - 4, 0),
        #'Seaborgium'   : (MAX_SIZE - 3, 0),
        #'Bohrium'      : (MAX_SIZE - 2, 0),
        #'Hassium'      : (MAX_SIZE - 1, 0),
        #'Meitnerium'   : (MAX_SIZE - 0, 0),
        # <---- Please refrain from fixing PEP-8 E203 and E265 ------
        # pylint: enable=E8203,E8265
    }

    LNAMES = dict((k.lower(), v) for (k, v) in iter(NAMES.items()))
    VNAMES = dict((v, k) for (k, v) in iter(NAMES.items()))
    RMATCH = dict((v[:2], k) for (k, v) in iter(NAMES.items()))

    def __init__(self,              # pylint: disable=C0103
                 major,
                 minor,
                 bugfix=0,
                 mbugfix=0,
                 pre_type=None,
                 pre_num=None,
                 noc=0,
                 sha=None):

        if isinstance(major, string_types):
            major = int(major)

        if isinstance(minor, string_types):
            minor = int(minor)

        if bugfix is None:
            bugfix = 0
        elif isinstance(bugfix, string_types):
            bugfix = int(bugfix)

        if mbugfix is None:
            mbugfix = 0
        elif isinstance(mbugfix, string_types):
            mbugfix = int(mbugfix)

        if pre_type is None:
            pre_type = ''
        if pre_num is None:
            pre_num = 0
        elif isinstance(pre_num, string_types):
            pre_num = int(pre_num)

        if noc is None:
            noc = 0
        elif isinstance(noc, string_types) and noc == 'n/a':
            noc = -1
        elif isinstance(noc, string_types):
            noc = int(noc)

        self.major = major
        self.minor = minor
        self.bugfix = bugfix
        self.mbugfix = mbugfix
        self.pre_type = pre_type
        self.pre_num = pre_num
        self.name = self.VNAMES.get((major, minor), None)
        self.noc = noc
        self.sha = sha

    @classmethod
    def parse(cls, version_string):
        if version_string.lower() in cls.LNAMES:
            return cls.from_name(version_string)
        vstr = version_string.decode() if isinstance(version_string, bytes) else version_string
        match = cls.git_describe_regex.match(vstr)
        if not match:
            raise ValueError(
                'Unable to parse version string: \'{0}\''.format(version_string)
            )
        return cls(*match.groups())

    @classmethod
    def from_name(cls, name):
        if name.lower() not in cls.LNAMES:
            raise ValueError(
                'Named version \'{0}\' is not known'.format(name)
            )
        return cls(*cls.LNAMES[name.lower()])

    @classmethod
    def from_last_named_version(cls):
        return cls.from_name(
            cls.VNAMES[
                max([version_info for version_info in
                     cls.VNAMES if
                     version_info[0] < (MAX_SIZE - 200)])
            ]
        )

    @classmethod
    def next_release(cls):
        return cls.from_name(
            cls.VNAMES[
                min([version_info for version_info in
                     cls.VNAMES if
                     version_info > cls.from_last_named_version().info])
            ]
        )

    @property
    def sse(self):
        # Higher than 0.17, lower than first date based
        return 0 < self.major < 2014

    @property
    def info(self):
        return (
            self.major,
            self.minor,
            self.bugfix,
            self.mbugfix
        )

    @property
    def pre_info(self):
        return (
            self.major,
            self.minor,
            self.bugfix,
            self.mbugfix,
            self.pre_type,
            self.pre_num
        )

    @property
    def noc_info(self):
        return (
            self.major,
            self.minor,
            self.bugfix,
            self.mbugfix,
            self.pre_type,
            self.pre_num,
            self.noc
        )

    @property
    def full_info(self):
        return (
            self.major,
            self.minor,
            self.bugfix,
            self.mbugfix,
            self.pre_type,
            self.pre_num,
            self.noc,
            self.sha
        )

    @property
    def string(self):
        version_string = '{0}.{1}.{2}'.format(
            self.major,
            self.minor,
            self.bugfix
        )
        if self.mbugfix:
            version_string += '.{0}'.format(self.mbugfix)
        if self.pre_type:
            version_string += '{0}{1}'.format(self.pre_type, self.pre_num)
        if self.noc and self.sha:
            noc = self.noc
            if noc < 0:
                noc = 'n/a'
            version_string += '-{0}-{1}'.format(noc, self.sha)
        return version_string

    @property
    def formatted_version(self):
        if self.name and self.major > 10000:
            version_string = self.name
            if self.sse:
                version_string += ' Enterprise'
            version_string += ' (Unreleased)'
            return version_string
        version_string = self.string
        if self.sse:
            version_string += ' Enterprise'
        if (self.major, self.minor) in self.RMATCH:
            version_string += ' ({0})'.format(self.RMATCH[(self.major, self.minor)])
        return version_string

    def __str__(self):
        return self.string

    def __compare__(self, other, method):
        if not isinstance(other, SaltStackVersion):
            if isinstance(other, string_types):
                other = SaltStackVersion.parse(other)
            elif isinstance(other, (list, tuple)):
                other = SaltStackVersion(*other)
            else:
                raise ValueError(
                    'Cannot instantiate Version from type \'{0}\''.format(
                        type(other)
                    )
                )

        if (self.pre_type and other.pre_type) or (not self.pre_type and not other.pre_type):
            # Both either have or don't have pre-release information, regular compare is ok
            return method(self.noc_info, other.noc_info)

        if self.pre_type and not other.pre_type:
            # We have pre-release information, the other side doesn't
            other_noc_info = list(other.noc_info)
            other_noc_info[4] = 'zzzzz'
            return method(self.noc_info, tuple(other_noc_info))

        if not self.pre_type and other.pre_type:
            # The other side has pre-release informatio, we don't
            noc_info = list(self.noc_info)
            noc_info[4] = 'zzzzz'
            return method(tuple(noc_info), other.noc_info)

    def __lt__(self, other):
        return self.__compare__(other, lambda _self, _other: _self < _other)

    def __le__(self, other):
        return self.__compare__(other, lambda _self, _other: _self <= _other)

    def __eq__(self, other):
        return self.__compare__(other, lambda _self, _other: _self == _other)

    def __ne__(self, other):
        return self.__compare__(other, lambda _self, _other: _self != _other)

    def __ge__(self, other):
        return self.__compare__(other, lambda _self, _other: _self >= _other)

    def __gt__(self, other):
        return self.__compare__(other, lambda _self, _other: _self > _other)

    def __repr__(self):
        parts = []
        if self.name:
            parts.append('name=\'{0}\''.format(self.name))
        parts.extend([
            'major={0}'.format(self.major),
            'minor={0}'.format(self.minor),
            'bugfix={0}'.format(self.bugfix)
        ])
        if self.mbugfix:
            parts.append('minor-bugfix={0}'.format(self.mbugfix))
        if self.pre_type:
            parts.append('{0}={1}'.format(self.pre_type, self.pre_num))
        noc = self.noc
        if noc == -1:
            noc = 'n/a'
        if noc and self.sha:
            parts.extend([
                'noc={0}'.format(noc),
                'sha={0}'.format(self.sha)
            ])
        return '<{0} {1}>'.format(self.__class__.__name__, ' '.join(parts))


# ----- Hardcoded Salt Codename Version Information ----------------------------------------------------------------->
#
#   There's no need to do anything here. The last released codename will be picked up
# --------------------------------------------------------------------------------------------------------------------
__saltstack_version__ = SaltStackVersion.from_last_named_version()
# <---- Hardcoded Salt Version Information ---------------------------------------------------------------------------


# ----- Dynamic/Runtime Salt Version Information -------------------------------------------------------------------->
def __discover_version(saltstack_version):
    # This might be a 'python setup.py develop' installation type. Let's
    # discover the version information at runtime.
    import os
    import subprocess

    if 'SETUP_DIRNAME' in globals():
        # This is from the exec() call in Salt's setup.py
        cwd = SETUP_DIRNAME  # pylint: disable=E0602
        if not os.path.exists(os.path.join(cwd, '.git')):
            # This is not a Salt git checkout!!! Don't even try to parse...
            return saltstack_version
    else:
        cwd = os.path.abspath(os.path.dirname(__file__))
        if not os.path.exists(os.path.join(os.path.dirname(cwd), '.git')):
            # This is not a Salt git checkout!!! Don't even try to parse...
            return saltstack_version

    try:
        kwargs = dict(
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd
        )

        if not sys.platform.startswith('win'):
            # Let's not import `salt.utils` for the above check
            kwargs['close_fds'] = True

        process = subprocess.Popen(
            ['git', 'describe', '--tags', '--first-parent', '--match', 'v[0-9]*', '--always'], **kwargs)

        out, err = process.communicate()

        if process.returncode != 0:
            # The git version running this might not support --first-parent
            # Revert to old command
            process = subprocess.Popen(
                ['git', 'describe', '--tags', '--match', 'v[0-9]*', '--always'], **kwargs)
            out, err = process.communicate()
        if six.PY3:
            out = out.decode()
            err = err.decode()
        out = out.strip()
        err = err.strip()

        if not out or err:
            return saltstack_version

        try:
            return SaltStackVersion.parse(out)
        except ValueError:
            if not SaltStackVersion.git_sha_regex.match(out):
                raise

            # We only define the parsed SHA and set NOC as ??? (unknown)
            saltstack_version.sha = out.strip()
            saltstack_version.noc = -1

    except OSError as os_err:
        if os_err.errno != 2:
            # If the errno is not 2(The system cannot find the file
            # specified), raise the exception so it can be catch by the
            # developers
            raise
    return saltstack_version


def __get_version(saltstack_version):
    '''
    If we can get a version provided at installation time or from Git, use
    that instead, otherwise we carry on.
    '''
    try:
        # Try to import the version information provided at install time
        from salt._version import __saltstack_version__  # pylint: disable=E0611,F0401
        return __saltstack_version__
    except ImportError:
        return __discover_version(saltstack_version)


# Get additional version information if available
__saltstack_version__ = __get_version(__saltstack_version__)
# This function has executed once, we're done with it. Delete it!
del __get_version
# <---- Dynamic/Runtime Salt Version Information ---------------------------------------------------------------------


# ----- Common version related attributes - NO NEED TO CHANGE ------------------------------------------------------->
__version_info__ = __saltstack_version__.info
__version__ = __saltstack_version__.string
# <---- Common version related attributes - NO NEED TO CHANGE --------------------------------------------------------


def salt_information():
    '''
    Report version of salt.
    '''
    yield 'Salt', __version__


def dependency_information(include_salt_cloud=False):
    '''
    Report versions of library dependencies.
    '''
    libs = [
        ('Python', None, sys.version.rsplit('\n')[0].strip()),
        ('Jinja2', 'jinja2', '__version__'),
        ('M2Crypto', 'M2Crypto', 'version'),
        ('msgpack-python', 'msgpack', 'version'),
        ('msgpack-pure', 'msgpack_pure', 'version'),
        ('pycrypto', 'Crypto', '__version__'),
        ('pycryptodome', 'Cryptodome', 'version_info'),
        ('PyYAML', 'yaml', '__version__'),
        ('PyZMQ', 'zmq', '__version__'),
        ('ZMQ', 'zmq', 'zmq_version'),
        ('Mako', 'mako', '__version__'),
        ('Tornado', 'tornado', 'version'),
        ('timelib', 'timelib', 'version'),
        ('dateutil', 'dateutil', '__version__'),
        ('pygit2', 'pygit2', '__version__'),
        ('libgit2', 'pygit2', 'LIBGIT2_VERSION'),
        ('smmap', 'smmap', '__version__'),
        ('cffi', 'cffi', '__version__'),
        ('pycparser', 'pycparser', '__version__'),
        ('gitdb', 'gitdb', '__version__'),
        ('gitpython', 'git', '__version__'),
        ('python-gnupg', 'gnupg', '__version__'),
        ('mysql-python', 'MySQLdb', '__version__'),
        ('cherrypy', 'cherrypy', '__version__'),
        ('docker-py', 'docker', '__version__'),
    ]

    if include_salt_cloud:
        libs.append(
            ('Apache Libcloud', 'libcloud', '__version__'),
        )

    for name, imp, attr in libs:
        if imp is None:
            yield name, attr
            continue
        try:
            imp = __import__(imp)
            version = getattr(imp, attr)
            if callable(version):
                version = version()
            if isinstance(version, (tuple, list)):
                version = '.'.join(map(str, version))
            yield name, version
        except Exception:
            yield name, None


def system_information():
    '''
    Report system versions.
    '''
    def system_version():
        '''
        Return host system version.
        '''
        lin_ver = linux_distribution()
        mac_ver = platform.mac_ver()
        win_ver = platform.win32_ver()

        if lin_ver[0]:
            return ' '.join(lin_ver)
        elif mac_ver[0]:
            if isinstance(mac_ver[1], (tuple, list)) and ''.join(mac_ver[1]):
                return ' '.join([mac_ver[0], '.'.join(mac_ver[1]), mac_ver[2]])
            else:
                return ' '.join([mac_ver[0], mac_ver[2]])
        elif win_ver[0]:
            return ' '.join(win_ver)
        else:
            return ''

    if platform.win32_ver()[0]:
        # Get the version and release info based on the Windows Operating
        # System Product Name. As long as Microsoft maintains a similar format
        # this should be future proof
        import win32api  # pylint: disable=3rd-party-module-not-gated
        import win32con  # pylint: disable=3rd-party-module-not-gated

        # Get the product name from the registry
        hkey = win32con.HKEY_LOCAL_MACHINE
        key = 'SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion'
        value_name = 'ProductName'
        reg_handle = win32api.RegOpenKey(hkey, key)

        # Returns a tuple of (product_name, value_type)
        product_name, _ = win32api.RegQueryValueEx(reg_handle, value_name)

        version = 'Unknown'
        release = ''
        if 'Server' in product_name:
            for item in product_name.split(' '):
                # If it's all digits, then it's version
                if re.match(r'\d+', item):
                    version = item
                # If it starts with R and then numbers, it's the release
                # ie: R2
                if re.match(r'^R\d+$', item):
                    release = item
            release = '{0}Server{1}'.format(version, release)
        else:
            for item in product_name.split(' '):
                # If it's a number, decimal number, Thin or Vista, then it's the
                # version
                if re.match(r'^(\d+(\.\d+)?)|Thin|Vista$', item):
                    version = item
            release = version

        _, ver, sp, extra = platform.win32_ver()
        version = ' '.join([release, ver, sp, extra])
    else:
        version = system_version()
        release = platform.release()

    system = [
        ('system', platform.system()),
        ('dist', ' '.join(linux_distribution(full_distribution_name=False))),
        ('release', release),
        ('machine', platform.machine()),
        ('version', version),
        ('locale', __salt_system_encoding__),
    ]

    for name, attr in system:
        yield name, attr
        continue


def versions_information(include_salt_cloud=False):
    '''
    Report the versions of dependent software.
    '''
    salt_info = list(salt_information())
    lib_info = list(dependency_information(include_salt_cloud))
    sys_info = list(system_information())

    return {'Salt Version': dict(salt_info),
            'Dependency Versions': dict(lib_info),
            'System Versions': dict(sys_info)}


def versions_report(include_salt_cloud=False):
    '''
    Yield each version properly formatted for console output.
    '''
    ver_info = versions_information(include_salt_cloud)

    lib_pad = max(len(name) for name in ver_info['Dependency Versions'])
    sys_pad = max(len(name) for name in ver_info['System Versions'])
    padding = max(lib_pad, sys_pad) + 1

    fmt = '{0:>{pad}}: {1}'
    info = []
    for ver_type in ('Salt Version', 'Dependency Versions', 'System Versions'):
        info.append('{0}:'.format(ver_type))
        # List dependencies in alphabetical, case insensitive order
        for name in sorted(ver_info[ver_type], key=lambda x: x.lower()):
            ver = fmt.format(name,
                             ver_info[ver_type][name] or 'Not Installed',
                             pad=padding)
            info.append(ver)
        info.append(' ')

    for line in info:
        yield line


def msi_conformant_version():
    '''
    An msi installer uninstalls/replaces a lower "internal version" of itself.
    "internal version" is ivMAJOR.ivMINOR.ivBUILD with max values 255.255.65535.
    Using the build nr allows continuous integration of the installer.
    "Display version" is indipendent and free format: Year.Month.Bugfix as in Salt 2016.11.3.
    Calculation of the internal version fields:
        ivMAJOR = 'short year' (2 digits).
        ivMINOR = 20*(month-1) + Bugfix
            Combine Month and Bugfix to free ivBUILD for the build number
            This limits Bugfix < 20.
            The msi automatically replaces only 19 bugfixes of a month, one must uninstall manually.
        ivBUILD = git commit count (noc)
            noc for tags is 0, representing the final word, translates to the highest build number (65535).

    Examples:
      git checkout    Display version      Internal version    Remark
      develop         2016.11.0-742        16.200.742          The develop branch has bugfix 0
      2016.11         2016.11.2-78         16.202.78
      2016.11         2016.11.9-88         16.209.88
      2018.8          2018.3.2-1306        18.42.1306
      v2016.11.0      2016.11.0            16.200.65535        Tags have noc 0
      v2016.11.2      2016.11.2            16.202.65535

    '''
    short_year = int(six.text_type(__saltstack_version__.major)[2:])
    month = __saltstack_version__.minor
    bugfix = __saltstack_version__.bugfix
    if bugfix > 19:
        bugfix = 19
    noc = __saltstack_version__.noc
    if noc == 0:
        noc = 65535
    return '{}.{}.{}'.format(short_year, 20*(month-1)+bugfix, noc)


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 'msi':
        # Building the msi requires an msi-conformant version
        print(msi_conformant_version())
    else:
        print(__version__)
