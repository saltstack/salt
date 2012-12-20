'''
Set up the version of Salt
'''

# Import python libs
import sys
import os
import subprocess

__version_info__ = (0, 11, 0)
__version__ = '.'.join(map(str, __version_info__))


# If we can get a version from Git use that instead, otherwise carry on
try:
    from salt.utils import which

    git = which('git')
    if git:
        p = subprocess.Popen(
            [git, 'describe'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
            cwd=os.path.abspath(os.path.dirname(__file__))
        )
        out, err = p.communicate()
        if out:
            parsed_version = '{0}'.format(out.strip().lstrip('v'))
            parsed_version_info = tuple(
                [int(i) for i in parsed_version.split('-', 1)[0].split('.')]
            )
            if parsed_version_info != __version_info__:
                msg = ('In order to get the proper salt version with the git '
                       'hash you need to update salt\'s local git tags. '
                       'Something like: \'git fetch --tags\' or '
                       '\'git fetch --tags upstream\' if you followed '
                       'salt\'s contribute documentation. The version string '
                       'WILL NOT include the git hash.')
                from salt import log
                if log.is_console_configured():
                    import logging
                    logging.getLogger(__name__).warning(msg)
                else:
                    sys.stderr.write('WARNING: {0}\n'.format(msg))
            else:
                __version__ = parsed_version
                __version_info__ = parsed_version_info
except Exception:
    pass


def versions_report():
    libs = (
        ("Jinja2", "jinja2", "__version__"),
        ("M2Crypto", "M2Crypto", "version"),
        ("msgpack-python", "msgpack", "version"),
        ("msgpack-pure", "msgpack_pure", "version"),
        ("pycrypto", "Crypto", "__version__"),
        ("PyYAML", "yaml", "__version__"),
        ("PyZMQ", "zmq", "__version__"),
    )

    padding = len(max([lib[0] for lib in libs], key=len)) + 1

    fmt = '{0:>{pad}}: {1}'

    yield fmt.format("Salt", __version__, pad=padding)

    yield fmt.format(
        "Python", sys.version.rsplit('\n')[0].strip(), pad=padding
    )

    for name, imp, attr in libs:
        try:
            imp = __import__(imp)
            version = getattr(imp, attr)
            if not isinstance(version, basestring):
                version = '.'.join(map(str, version))
            yield fmt.format(name, version, pad=padding)
        except ImportError:
            yield fmt.format(name, "not installed", pad=padding)


if __name__ == '__main__':
    print(__version__)
