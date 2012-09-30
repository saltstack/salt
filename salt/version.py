import sys

__version_info__ = (0, 10, 3)
__version__ = '.'.join(map(str, __version_info__))


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
