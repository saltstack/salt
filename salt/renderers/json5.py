# -*- coding: utf-8 -*-
"""
JSON5 Renderer for Salt

.. versionadded:: 2016.3.0

JSON5 is an unofficial extension to JSON. See http://json5.org/ for more
information.

This renderer requires the `json5 python bindings`__, installable via pip.

.. __: https://pypi.python.org/pypi/json5
"""

from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging

# Import salt libs
from salt.ext import six

try:
    import json5 as json

    HAS_JSON5 = True
except ImportError:
    HAS_JSON5 = False


log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "json5"


def __virtual__():
    if not HAS_JSON5:
        return (False, "json5 module not installed")
    return __virtualname__


def render(json_data, saltenv="base", sls="", **kws):
    """
    Accepts JSON as a string or as a file object and runs it through the JSON
    parser.

    :rtype: A Python data structure
    """
    if not isinstance(json_data, six.string_types):
        json_data = json_data.read()

    if json_data.startswith("#!"):
        json_data = json_data[(json_data.find("\n") + 1) :]
    if not json_data.strip():
        return {}
    return json.loads(json_data)
