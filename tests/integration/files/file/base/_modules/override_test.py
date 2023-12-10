"""
Module for running arbitrary tests
"""

__virtualname__ = "test"


def __virtual__():
    return __virtualname__


def recho(text):
    """
    Return a reversed string

    CLI Example:

    .. code-block:: bash

        salt '*' test.recho 'foo bar baz quo qux'
    """
    return text[::-1]
