"""
Decorators for salt.utils.path
"""

import functools

import salt.utils.path
from salt.exceptions import CommandNotFoundError


def which(exe):
    """
    Decorator wrapper for salt.utils.path.which
    """

    def wrapper(function):
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            if salt.utils.path.which(exe) is None:
                raise CommandNotFoundError(
                    "The '{}' binary was not found in $PATH.".format(exe)
                )
            return function(*args, **kwargs)

        return wrapped

    return wrapper


def which_bin(exes):
    """
    Decorator wrapper for salt.utils.path.which_bin
    """

    def wrapper(function):
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            if salt.utils.path.which_bin(exes) is None:
                raise CommandNotFoundError(
                    "None of provided binaries({}) were found in $PATH.".format(
                        ["'{}'".format(exe) for exe in exes]
                    )
                )
            return function(*args, **kwargs)

        return wrapped

    return wrapper
