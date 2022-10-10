#!/usr/bin/env python

import sys


def main():
    print(
        "\nruntests.py support has been removed from Salt. Please try `nox -e"
        " 'pytest-3(coverage=True)'` "
        "or `nox -e 'pytest-3(coverage=True)' -- --help` to know more about the"
        " supported CLI flags.\n"
        "For more information, please check"
        " https://docs.saltproject.io/en/latest/topics/development/tests/index.html#running-the-tests",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
