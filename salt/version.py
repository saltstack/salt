# -*- coding: utf-8 -*-
'''
Set up the version of Salt
'''

# Import python libs
import re
import sys

# Import salt libs
try:
    from salt._compat import string_types
except ImportError:
    if sys.version_info[0] == 3:
        string_types = str
    else:
        string_types = basestring

# ----- ATTENTION ----------------------------------------------------------->
#
# For version bumps, please update `__saltstack_version__` below
#
# <---- ATTENTION ------------------------------------------------------------


class SaltStackVersion(object):
    '''
    Handle SaltStack versions class.

    Knows how to parse ``git describe`` output, knows about release candidates
    and also supports version comparison.
    '''

    __slots__ = ('name', 'major', 'minor', 'bugfix', 'rc', 'noc', 'sha')

    git_describe_regex = re.compile(
        r'(?:[^\d]+)?(?P<major>[\d]{1,4})\.(?P<minor>[\d]{1,2})'
        r'(?:\.(?P<bugfix>[\d]{0,2}))?(?:rc(?P<rc>[\d]{1}))?'
        r'(?:(?:.*)-(?P<noc>[\d]+)-(?P<sha>[a-z0-9]{8}))?'
    )

    # Salt versions after 0.17.0 will be numbered like:
    #   <2-digit-year>.<month>.<bugfix>
    #
    # Since the actual version numbers will only be know on release dates, the
    # periodic table element names will be what's going to be used to name
    # versions and to be able to mention them.

    NAMES = {
        # Let's keep at least 3 version names uncommented counting from the
        # latest release so we can map deprecation warnings to versions.


        # ----- Please refrain from fixing PEP-8 E203 ----------------------->
        # The idea is keep this readable
        # --------------------------------------------------------------------
        'Hydrogen': (sys.maxint - 108, 0, 0, 0),
        'Helium': (sys.maxint - 107, 0, 0, 0),
        'Lithium': (sys.maxint - 106, 0, 0, 0),
        'Beryllium': (sys.maxint - 105, 0, 0, 0),
        'Boron': (sys.maxint - 104, 0, 0, 0),
        #'Carbon'       : (sys.maxint - 103, 0, 0, 0),
        #'Nitrogen'     : (sys.maxint - 102, 0, 0, 0),
        #'Oxygen'       : (sys.maxint - 101, 0, 0, 0),
        #'Fluorine'     : (sys.maxint - 100, 0, 0, 0),
        #'Neon'         : (sys.maxint - 99 , 0, 0, 0),
        #'Sodium'       : (sys.maxint - 98 , 0, 0, 0),
        #'Magnesium'    : (sys.maxint - 97 , 0, 0, 0),
        #'Aluminium'    : (sys.maxint - 96 , 0, 0, 0),
        #'Silicon'      : (sys.maxint - 95 , 0, 0, 0),
        #'Phosphorus'   : (sys.maxint - 94 , 0, 0, 0),
        #'Sulfur'       : (sys.maxint - 93 , 0, 0, 0),
        #'Chlorine'     : (sys.maxint - 92 , 0, 0, 0),
        #'Argon'        : (sys.maxint - 91 , 0, 0, 0),
        #'Potassium'    : (sys.maxint - 90 , 0, 0, 0),
        #'Calcium'      : (sys.maxint - 89 , 0, 0, 0),
        #'Scandium'     : (sys.maxint - 88 , 0, 0, 0),
        #'Titanium'     : (sys.maxint - 87 , 0, 0, 0),
        #'Vanadium'     : (sys.maxint - 86 , 0, 0, 0),
        #'Chromium'     : (sys.maxint - 85 , 0, 0, 0),
        #'Manganese'    : (sys.maxint - 84 , 0, 0, 0),
        #'Iron'         : (sys.maxint - 83 , 0, 0, 0),
        #'Cobalt'       : (sys.maxint - 82 , 0, 0, 0),
        #'Nickel'       : (sys.maxint - 81 , 0, 0, 0),
        #'Copper'       : (sys.maxint - 80 , 0, 0, 0),
        #'Zinc'         : (sys.maxint - 79 , 0, 0, 0),
        #'Gallium'      : (sys.maxint - 78 , 0, 0, 0),
        #'Germanium'    : (sys.maxint - 77 , 0, 0, 0),
        #'Arsenic'      : (sys.maxint - 76 , 0, 0, 0),
        #'Selenium'     : (sys.maxint - 75 , 0, 0, 0),
        #'Bromine'      : (sys.maxint - 74 , 0, 0, 0),
        #'Krypton'      : (sys.maxint - 73 , 0, 0, 0),
        #'Rubidium'     : (sys.maxint - 72 , 0, 0, 0),
        #'Strontium'    : (sys.maxint - 71 , 0, 0, 0),
        #'Yttrium'      : (sys.maxint - 70 , 0, 0, 0),
        #'Zirconium'    : (sys.maxint - 69 , 0, 0, 0),
        #'Niobium'      : (sys.maxint - 68 , 0, 0, 0),
        #'Molybdenum'   : (sys.maxint - 67 , 0, 0, 0),
        #'Technetium'   : (sys.maxint - 66 , 0, 0, 0),
        #'Ruthenium'    : (sys.maxint - 65 , 0, 0, 0),
        #'Rhodium'      : (sys.maxint - 64 , 0, 0, 0),
        #'Palladium'    : (sys.maxint - 63 , 0, 0, 0),
        #'Silver'       : (sys.maxint - 62 , 0, 0, 0),
        #'Cadmium'      : (sys.maxint - 61 , 0, 0, 0),
        #'Indium'       : (sys.maxint - 60 , 0, 0, 0),
        #'Tin'          : (sys.maxint - 59 , 0, 0, 0),
        #'Antimony'     : (sys.maxint - 58 , 0, 0, 0),
        #'Tellurium'    : (sys.maxint - 57 , 0, 0, 0),
        #'Iodine'       : (sys.maxint - 56 , 0, 0, 0),
        #'Xenon'        : (sys.maxint - 55 , 0, 0, 0),
        #'Caesium'      : (sys.maxint - 54 , 0, 0, 0),
        #'Barium'       : (sys.maxint - 53 , 0, 0, 0),
        #'Lanthanum'    : (sys.maxint - 52 , 0, 0, 0),
        #'Cerium'       : (sys.maxint - 51 , 0, 0, 0),
        #'Praseodymium' : (sys.maxint - 50 , 0, 0, 0),
        #'Neodymium'    : (sys.maxint - 49 , 0, 0, 0),
        #'Promethium'   : (sys.maxint - 48 , 0, 0, 0),
        #'Samarium'     : (sys.maxint - 47 , 0, 0, 0),
        #'Europium'     : (sys.maxint - 46 , 0, 0, 0),
        #'Gadolinium'   : (sys.maxint - 45 , 0, 0, 0),
        #'Terbium'      : (sys.maxint - 44 , 0, 0, 0),
        #'Dysprosium'   : (sys.maxint - 43 , 0, 0, 0),
        #'Holmium'      : (sys.maxint - 42 , 0, 0, 0),
        #'Erbium'       : (sys.maxint - 41 , 0, 0, 0),
        #'Thulium'      : (sys.maxint - 40 , 0, 0, 0),
        #'Ytterbium'    : (sys.maxint - 39 , 0, 0, 0),
        #'Lutetium'     : (sys.maxint - 38 , 0, 0, 0),
        #'Hafnium'      : (sys.maxint - 37 , 0, 0, 0),
        #'Tantalum'     : (sys.maxint - 36 , 0, 0, 0),
        #'Tungsten'     : (sys.maxint - 35 , 0, 0, 0),
        #'Rhenium'      : (sys.maxint - 34 , 0, 0, 0),
        #'Osmium'       : (sys.maxint - 33 , 0, 0, 0),
        #'Iridium'      : (sys.maxint - 32 , 0, 0, 0),
        #'Platinum'     : (sys.maxint - 31 , 0, 0, 0),
        #'Gold'         : (sys.maxint - 30 , 0, 0, 0),
        #'Mercury'      : (sys.maxint - 29 , 0, 0, 0),
        #'Thallium'     : (sys.maxint - 28 , 0, 0, 0),
        #'Lead'         : (sys.maxint - 27 , 0, 0, 0),
        #'Bismuth'      : (sys.maxint - 26 , 0, 0, 0),
        #'Polonium'     : (sys.maxint - 25 , 0, 0, 0),
        #'Astatine'     : (sys.maxint - 24 , 0, 0, 0),
        #'Radon'        : (sys.maxint - 23 , 0, 0, 0),
        #'Francium'     : (sys.maxint - 22 , 0, 0, 0),
        #'Radium'       : (sys.maxint - 21 , 0, 0, 0),
        #'Actinium'     : (sys.maxint - 20 , 0, 0, 0),
        #'Thorium'      : (sys.maxint - 19 , 0, 0, 0),
        #'Protactinium' : (sys.maxint - 18 , 0, 0, 0),
        #'Uranium'      : (sys.maxint - 17 , 0, 0, 0),
        #'Neptunium'    : (sys.maxint - 16 , 0, 0, 0),
        #'Plutonium'    : (sys.maxint - 15 , 0, 0, 0),
        #'Americium'    : (sys.maxint - 14 , 0, 0, 0),
        #'Curium'       : (sys.maxint - 13 , 0, 0, 0),
        #'Berkelium'    : (sys.maxint - 12 , 0, 0, 0),
        #'Californium'  : (sys.maxint - 11 , 0, 0, 0),
        #'Einsteinium'  : (sys.maxint - 10 , 0, 0, 0),
        #'Fermium'      : (sys.maxint - 9  , 0, 0, 0),
        #'Mendelevium'  : (sys.maxint - 8  , 0, 0, 0),
        #'Nobelium'     : (sys.maxint - 7  , 0, 0, 0),
        #'Lawrencium'   : (sys.maxint - 6  , 0, 0, 0),
        #'Rutherfordium': (sys.maxint - 5  , 0, 0, 0),
        #'Dubnium'      : (sys.maxint - 4  , 0, 0, 0),
        #'Seaborgium'   : (sys.maxint - 3  , 0, 0, 0),
        #'Bohrium'      : (sys.maxint - 2  , 0, 0, 0),
        #'Hassium'      : (sys.maxint - 1  , 0, 0, 0),
        #'Meitnerium'   : (sys.maxint - 0  , 0, 0, 0),
        # <---- Please refrain from fixing PEP-8 E203 ------------------------
    }

    LNAMES = dict((k.lower(), v) for (k, v) in NAMES.iteritems())
    VNAMES = dict((v, k) for (k, v) in NAMES.iteritems())

    def __init__(self,              # pylint: disable=C0103
                 major,
                 minor,
                 bugfix=0,
                 rc=0,              # pylint: disable=C0103
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

        if rc is None:
            rc = 0
        elif isinstance(rc, string_types):
            rc = int(rc)

        if noc is None:
            noc = 0
        elif isinstance(noc, string_types):
            noc = int(noc)

        self.major = major
        self.minor = minor
        self.bugfix = bugfix
        self.rc = rc  # pylint: disable=C0103
        self.name = self.VNAMES.get((major, minor, bugfix, rc), None)
        self.noc = noc
        self.sha = sha

    @classmethod
    def parse(cls, version_string):
        if version_string.lower() in cls.LNAMES:
            return cls.from_name(version_string)
        match = cls.git_describe_regex.match(version_string)
        if not match:
            raise ValueError(
                'Unable to parse version string: {0!r}'.format(version_string)
            )
        return cls(*match.groups())

    @classmethod
    def from_name(cls, name):
        if name.lower() not in cls.LNAMES:
            raise ValueError(
                'Named version {0!r} is not known'.format(name)
            )
        return cls(*cls.LNAMES[name.lower()])

    @property
    def info(self):
        return (
            self.major,
            self.minor,
            self.bugfix
        )

    @property
    def rc_info(self):
        return (
            self.major,
            self.minor,
            self.bugfix,
            self.rc
        )

    @property
    def noc_info(self):
        return (
            self.major,
            self.minor,
            self.bugfix,
            self.rc,
            self.noc
        )

    @property
    def full_info(self):
        return (
            self.major,
            self.minor,
            self.bugfix,
            self.rc,
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
        if self.rc:
            version_string += 'rc{0}'.format(self.rc)
        if self.noc and self.sha:
            version_string += '-{0}-{1}'.format(self.noc, self.sha)
        return version_string

    @property
    def formatted_version(self):
        if self.name and self.major > 10000:
            return '{0} (Unreleased)'.format(self.name)
        elif self.name:
            return '{0} ({1})'.format(self.name, self.string)
        return self.string

    def __str__(self):
        return self.string

    def __cmp__(self, other):
        if not isinstance(other, SaltStackVersion):
            if isinstance(other, string_types):
                other = SaltStackVersion.parse(other)
            elif isinstance(other, (list, tuple)):
                other = SaltStackVersion(*other)
            else:
                raise ValueError(
                    'Cannot instantiate Version from type {0!r}'.format(
                        type(other)
                    )
                )

        if (self.rc and other.rc) or (not self.rc and not other.rc):
            # Both have rc information, regular compare is ok
            return cmp(self.noc_info, other.noc_info)

        # RC's are always lower versions than non RC's
        if self.rc > 0 and other.rc <= 0:
            noc_info = list(self.noc_info)
            noc_info[3] = -1
            return cmp(tuple(noc_info), other.noc_info)

        if self.rc <= 0 and other.rc > 0:
            other_noc_info = list(other.noc_info)
            other_noc_info[3] = -1
            return cmp(self.noc_info, tuple(other_noc_info))

    def __repr__(self):
        parts = []
        if self.name:
            parts.append('name={0!r}'.format(self.name))
        parts.extend([
            'major={0}'.format(self.major),
            'minor={0}'.format(self.minor),
            'bugfix={0}'.format(self.bugfix)
        ])
        if self.rc:
            parts.append('rc={0}'.format(self.rc))
        return '<{0} {1}>'.format(self.__class__.__name__, ' '.join(parts))


# ----- Hardcoded Salt Version Information ---------------------------------->
#
# Please bump version information for __saltstack_version__ on new releases
# ----------------------------------------------------------------------------
__saltstack_version__ = SaltStackVersion(2014, 1, 0, 1)
__version_info__ = __saltstack_version__.info
__version__ = __saltstack_version__.string
# <---- Hardcoded Salt Version Information -----------------------------------


# ----- Dynamic/Runtime Salt Version Information ---------------------------->
def __get_version(version, version_info):
    '''
    If we can get a version provided at installation time or from Git, use
    that instead, otherwise we carry on.
    '''
    try:
        # Try to import the version information provided at install time
        from salt._version import __version__, __version_info__  # pylint: disable=E0611
        return __version__, __version_info__
    except ImportError:
        pass

    # This might be a 'python setup.py develop' installation type. Let's
    # discover the version information at runtime.
    import os
    import warnings
    import subprocess

    if 'SETUP_DIRNAME' in globals():
        # This is from the exec() call in Salt's setup.py
        cwd = SETUP_DIRNAME  # pylint: disable=E0602
        if not os.path.exists(os.path.join(cwd, '.git')):
            # This is not a Salt git checkout!!! Don't even try to parse...
            return version, version_info
    else:
        cwd = os.path.abspath(os.path.dirname(__file__))
        if not os.path.exists(os.path.join(os.path.dirname(cwd), '.git')):
            # This is not a Salt git checkout!!! Don't even try to parse...
            return version, version_info

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
                ['git', 'describe', '--tags', '--match', 'v[0-9]*'], **kwargs)
        out, err = process.communicate()
        out = out.strip()
        err = err.strip()

        if not out or err:
            return version, version_info

        parsed_version = SaltStackVersion.parse(out)

        if parsed_version.info > version_info:
            warnings.warn(
                'The parsed version info, `{0}`, is bigger than the one '
                'defined in the file, `{1}`. Missing version bump?'.format(
                    parsed_version.info,
                    version_info
                ),
                UserWarning,
                stacklevel=2
            )
            return version, version_info
        elif parsed_version.info < version_info:
            warnings.warn(
                'The parsed version info, `{0}`, is lower than the one '
                'defined in the file, `{1}`.'
                'In order to get the proper salt version with the git hash '
                'you need to update salt\'s local git tags. Something like: '
                '\'git fetch --tags\' or \'git fetch --tags upstream\' if '
                'you followed salt\'s contribute documentation. The version '
                'string WILL NOT include the git hash.'.format(
                    parsed_version.info,
                    version_info
                ),
                UserWarning,
                stacklevel=2
            )
            return version, version_info
        return parsed_version.string, parsed_version.info
    except OSError as os_err:
        if os_err.errno != 2:
            # If the errno is not 2(The system cannot find the file
            # specified), raise the exception so it can be catch by the
            # developers
            raise
    return version, version_info


# Get additional version information if available
__version__, __version_info__ = __get_version(__version__, __version_info__)
# This function has executed once, we're done with it. Delete it!
del __get_version
# <---- Dynamic/Runtime Salt Version Information -----------------------------


def versions_information(include_salt_cloud=False):
    '''
    Report on all of the versions for dependent software
    '''
    libs = [
        ('Salt', None, __version__),
        ('Python', None, sys.version.rsplit('\n')[0].strip()),
        ('Jinja2', 'jinja2', '__version__'),
        ('M2Crypto', 'M2Crypto', 'version'),
        ('msgpack-python', 'msgpack', 'version'),
        ('msgpack-pure', 'msgpack_pure', 'version'),
        ('pycrypto', 'Crypto', '__version__'),
        ('PyYAML', 'yaml', '__version__'),
        ('PyZMQ', 'zmq', '__version__'),
        ('ZMQ', 'zmq', 'zmq_version')
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
        except ImportError:
            yield name, None


def versions_report(include_salt_cloud=False):
    '''
    Yield each library properly formatted for a console clean output.
    '''
    libs = list(versions_information(include_salt_cloud=include_salt_cloud))

    padding = max(len(lib[0]) for lib in libs) + 1

    fmt = '{0:>{pad}}: {1}'

    for name, version in libs:
        yield fmt.format(name, version or 'Not Installed', pad=padding)


if __name__ == '__main__':
    print(__version__)
