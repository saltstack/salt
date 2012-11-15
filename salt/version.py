import sys

__version_info__ = (0, 10, 4)
__version__ = '.'.join(map(str, __version_info__))


# If we can get a version from Git use that instead, otherwise carry on
try:
    import os
    import subprocess
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
            __version__ = '{0}'.format(out.strip().lstrip('v'))
            __version_info__ = tuple(
                [int(i) for i in __version__.split('-', 1)[0].split('.')]
            )
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
