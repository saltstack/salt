import sys

__version_info__ = (0, 8, 4)
__version__ = '.'.join(map(str, __version_info__))


def versions_report():
    libs = (
        ("Salt", "salt", "__version__"),
        ("Apache Libcloud", "libcloud", "__version__"),
        ("PyYAML", "yaml", "__version__"),
    )

    padding = len(max([lib[0] for lib in libs], key=len)) + 1

    fmt = '{0:>{pad}}: {1}'

    yield fmt.format("Salt Cloud", __version__, pad=padding)

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
