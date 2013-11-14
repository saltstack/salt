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

    __slots__ = ('major', 'minor', 'bugfix', 'rc', 'noc', 'sha')

    git_describe_regex = re.compile(
        r'(?:[^\d]+)?(?P<major>[\d]{1,2})\.(?P<minor>[\d]{1,2})'
        r'(?:\.(?P<bugfix>[\d]{0,2}))?(?:rc(?P<rc>[\d]{1}))?'
        r'(?:(?:.*)-(?P<noc>[\d]+)-(?P<sha>[a-z0-9]{8}))?'
    )

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
        self.noc = noc
        self.sha = sha

    @classmethod
    def parse(cls, version_string):
        match = cls.git_describe_regex.match(version_string)
        if not match:
            raise ValueError(
                'Unable to parse version string: {0!r}'.format(version_string)
            )
        return cls(*match.groups())

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


# ----- Hardcoded Salt Version Information ---------------------------------->
#
# Please bump version information for __saltstack_version__ on new releases
# ----------------------------------------------------------------------------
__saltstack_version__ = SaltStackVersion(0, 17, 2)
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

    try:
        cwd = os.path.abspath(os.path.dirname(__file__))
    except NameError:
        # We're most likely being frozen and __file__ triggered this NameError
        # Let's work around that
        import inspect
        cwd = os.path.abspath(
            os.path.dirname(inspect.getsourcefile(__get_version))
        )

    if __file__ == 'setup.py':
        # This is from the exec() call in Salt's setup.py
        if not os.path.exists(os.path.join(cwd, '.git')):
            # This is not a Salt git checkout!!! Don't even try to parse...
            return version, version_info

    elif not os.path.exists(os.path.join(os.path.dirname(cwd), '.git')):
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


def versions_information():
    '''
    Report on all of the versions for dependent software
    '''
    libs = (
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


def versions_report():
    '''
    Yield each library properly formatted for a console clean output.
    '''
    libs = list(versions_information())

    padding = max(len(lib[0]) for lib in libs) + 1

    fmt = '{0:>{pad}}: {1}'

    for name, version in libs:
        yield fmt.format(name, version or 'Not Installed', pad=padding)


if __name__ == '__main__':
    print(__version__)
