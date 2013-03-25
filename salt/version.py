'''
Set up the version of Salt
'''

# Import python libs
import sys


__version_info__ = (0, 14, 0)
__version__ = '.'.join(map(str, __version_info__))

GIT_DESCRIBE_REGEX = (
    r'(?P<major>[\d]{1,2}).(?P<minor>[\d]{1,2}).(?P<bugfix>[\d]{1,2})'
    r'(?:(?:.*)-(?P<noc>[\d]+)-(?P<sha>[a-z0-9]{8}))?'
)


def __get_version(version, version_info):
    '''
    If we can get a version provided at installation time or from Git, use
    that instead, otherwise we carry on.
    '''
    try:
        # Try to import the version information provided at install time
        from salt._version import __version__, __version_info__
        return __version__, __version_info__
    except ImportError:
        pass

    # This might be a 'python setup.py develop' installation type. Let's
    # discover the version information at runtime.
    import os
    import re
    import warnings
    import subprocess

    try:
        kwargs = dict(
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.abspath(os.path.dirname(__file__))
        )

        if not sys.platform.startswith('win'):
            # Let's not import `salt.utils` for the above check
            kwargs['close_fds'] = True

        process = subprocess.Popen(['git', 'describe', '--tags'], **kwargs)
        out, err = process.communicate()

        if not out.strip() or err.strip():
            return version, version_info

        match = re.search(GIT_DESCRIBE_REGEX, out.strip())
        if not match:
            return version, version_info

        parsed_version = '{0}.{1}.{2}'.format(
            match.group('major'),
            match.group('minor'),
            match.group('bugfix')
        )

        if match.group('noc') is not None and match.group('sha') is not None:
            # This is not the exact point where a tag was created.
            # We have the extra information. Let's add it.
            parsed_version = '{0}-{1}-{2}'.format(
                parsed_version,
                match.group('noc'),
                match.group('sha')
            )

        parsed_version_info = tuple([
            int(g) for g in match.groups()[:3] if g.isdigit()
        ])

        if parsed_version_info > version_info:
            warnings.warn(
                'The parsed version info, `{0}`, is bigger than the one '
                'defined in the file, `{1}`. Missing version bump?'.format(
                    parsed_version_info,
                    version_info
                ),
                UserWarning,
                stacklevel=2
            )
            return version, version_info
        elif parsed_version_info < version_info:
            warnings.warn(
                'In order to get the proper salt version with the git hash '
                'you need to update salt\'s local git tags. Something like: '
                '\'git fetch --tags\' or \'git fetch --tags upstream\' if '
                'you followed salt\'s contribute documentation. The version '
                'string WILL NOT include the git hash.',
                UserWarning,
                stacklevel=2
            )
            return version, version_info
        return parsed_version, parsed_version_info
    except OSError, err:
        if err.errno != 2:
            # If the errno is not 2(The system cannot find the file
            # specified), raise the exception so it can be catch by the
            # developers
            raise
    return version, version_info


# Get additional version information if available
__version__, __version_info__ = __get_version(__version__, __version_info__)
# This function has executed once, we're done with it. Delete it!
del __get_version


def versions_report():
    '''
    Report on all of the versions for dependant software
    '''
    libs = (
        ('Jinja2', 'jinja2', '__version__'),
        ('M2Crypto', 'M2Crypto', 'version'),
        ('msgpack-python', 'msgpack', 'version'),
        ('msgpack-pure', 'msgpack_pure', 'version'),
        ('pycrypto', 'Crypto', '__version__'),
        ('PyYAML', 'yaml', '__version__'),
        ('PyZMQ', 'zmq', '__version__'),
    )

    padding = len(max([lib[0] for lib in libs], key=len)) + 1

    fmt = '{0:>{pad}}: {1}'

    yield fmt.format('Salt', __version__, pad=padding)

    yield fmt.format(
        'Python', sys.version.rsplit('\n')[0].strip(), pad=padding
    )

    for name, imp, attr in libs:
        try:
            imp = __import__(imp)
            version = getattr(imp, attr)
            if not isinstance(version, basestring):
                version = '.'.join(map(str, version))
            yield fmt.format(name, version, pad=padding)
        except ImportError:
            yield fmt.format(name, 'not installed', pad=padding)


if __name__ == '__main__':
    print(__version__)
