# -*- coding: utf-8 -*-
"""
Module for running arbitrary tests
"""
from __future__ import absolute_import

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
