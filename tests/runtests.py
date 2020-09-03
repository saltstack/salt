#!/usr/bin/env python

import sys


def main():
    print(
        """\nruntests.py support has been removed from Salt. Please try `nox -e '{0}'` """
        """or `nox -e '{0}' -- --help` to know more about the supported CLI flags.\n"""
        "For more information, please check https://docs.saltstack.com/en/latest/topics/development/tests/index.html#running-the-tests".format(
            "pytest-zeromq-3"
        ),
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
