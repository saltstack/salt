"""
Module for running arbitrary tests
"""


def jinja_error():
    """

    CLI Example:

    .. code-block:: bash

        salt '*' salttest.jinja_error
    """
    raise Exception("hehehe")
