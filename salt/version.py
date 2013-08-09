'''
Set up the version of Salt
'''

# Import python libs
import sys


__version_info__ = (0, 16, 3)
__version__ = '.'.join(map(str, __version_info__))

GIT_DESCRIBE_REGEX = (
    r'(?P<major>[\d]{1,2})\.(?P<minor>[\d]{1,2})(?:\.(?P<bugfix>[\d]{0,2}))?'
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
        cwd = os.path.abspath(os.path.dirname(__file__))
    except NameError:
        # We're most likely being frozen and __file__ triggered this NameError
        # Let's work around that
        import inspect
        cwd = os.path.abspath(
            os.path.dirname(inspect.getsourcefile(__get_version))
        )

    try:
        kwargs = dict(
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd
        )

        if not sys.platform.startswith('win'):
            # Let's not import `salt.utils` for the above check
            kwargs['close_fds'] = True

        process = subprocess.Popen(['git', 'describe', '--tags'], **kwargs)
        out, err = process.communicate()
        out = out.strip()
        err = err.strip()

        if not out or err:
            return version, version_info

        match = re.search(GIT_DESCRIBE_REGEX, out)
        if not match:
            return version, version_info

        parsed_version = '{0}.{1}.{2}'.format(
            match.group('major'),
            match.group('minor'),
            match.group('bugfix') or '0'
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
            int(g) for g in [h or '0' for h in match.groups()[:3]]
                    if g.isdigit()
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
                'The parsed version info, `{0}`, is lower than the one '
                'defined in the file, `{1}`.'
                'In order to get the proper salt version with the git hash '
                'you need to update salt\'s local git tags. Something like: '
                '\'git fetch --tags\' or \'git fetch --tags upstream\' if '
                'you followed salt\'s contribute documentation. The version '
                'string WILL NOT include the git hash.'.format(
                    parsed_version_info,
                    version_info
                ),
                UserWarning,
                stacklevel=2
            )
            return version, version_info
        return parsed_version, parsed_version_info
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
