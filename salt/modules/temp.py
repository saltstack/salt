# -*- coding: utf-8 -*-
"""
Simple module for creating temporary directories and files

This is a thin wrapper around Pythons tempfile module

.. versionadded:: 2015.8.0

"""
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import tempfile

log = logging.getLogger(__name__)


def dir(suffix="", prefix="tmp", parent=None):
    """
    Create a temporary directory

    CLI Example:

    .. code-block:: bash

        salt '*' temp.dir
        salt '*' temp.dir prefix='mytemp-' parent='/var/run/'
    """
    return tempfile.mkdtemp(suffix, prefix, parent)


def file(suffix="", prefix="tmp", parent=None):
    """
    Create a temporary file

    CLI Example:

    .. code-block:: bash

        salt '*' temp.file
        salt '*' temp.file prefix='mytemp-' parent='/var/run/'
    """
    fh_, tmp_ = tempfile.mkstemp(suffix, prefix, parent)
    os.close(fh_)
    return tmp_
