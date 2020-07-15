# -*- coding: utf-8 -*-
"""
DSON Renderer for Salt

This renderer is intended for demonstration purposes. Information on the DSON
spec can be found `here`__.

.. __: http://vpzomtrrfrt.github.io/DSON/

This renderer requires `Dogeon`__ (installable via pip)

.. __: https://github.com/soasme/dogeon
"""

from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging

# Import salt libs
from salt.ext import six

try:
    import dson
except ImportError:
    dson = None


log = logging.getLogger(__name__)


def __virtual__():
    if dson is None:
        return (False, "The dogeon Python package is not installed")
    return True


def render(dson_input, saltenv="base", sls="", **kwargs):
    """
    Accepts DSON data as a string or as a file object and runs it through the
    JSON parser.

    :rtype: A Python data structure
    """
    if not isinstance(dson_input, six.string_types):
        dson_input = dson_input.read()

    log.debug("DSON input = %s", dson_input)

    if dson_input.startswith("#!"):
        dson_input = dson_input[(dson_input.find("\n") + 1) :]
    if not dson_input.strip():
        return {}
    return dson.loads(dson_input)
