# -*- coding: utf-8 -*-
"""
Output Module
=============

.. versionadded:: 2018.3.0

Execution module that processes JSON serializable data
and returns string having the format as processed by the outputters.

Although this does not bring much value on the CLI, it turns very handy
in applications that require human readable data rather than Python objects.

For example, inside a Jinja template:

.. code-block:: jinja

    {{ salt.out.string_format(complex_object, out='highstate') }}
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging

# Import salt modules
import salt.output

log = logging.getLogger(__name__)


__virtualname__ = "out"
__proxyenabled__ = ["*"]


def __virtual__():
    return __virtualname__


def out_format(data, out="nested", opts=None, **kwargs):
    """
    Return the formatted outputter string for the Python object.

    data
        The JSON serializable object.

    out: ``nested``
        The name of the output to use to transform the data. Default: ``nested``.

    opts
        Dictionary of configuration options. Default: ``__opts__``.

    kwargs
        Arguments to sent to the outputter module.

    CLI Example:

    .. code-block:: bash

        salt '*' out.out_format "{'key': 'value'}"
    """
    if not opts:
        opts = __opts__
    return salt.output.out_format(data, out, opts=opts, **kwargs)


def string_format(data, out="nested", opts=None, **kwargs):
    """
    Return the outputter formatted string, removing the ANSI escape sequences.

    data
        The JSON serializable object.

    out: ``nested``
        The name of the output to use to transform the data. Default: ``nested``.

    opts
        Dictionary of configuration options. Default: ``__opts__``.

    kwargs
        Arguments to sent to the outputter module.

    CLI Example:

    .. code-block:: bash

        salt '*' out.string_format "{'key': 'value'}" out=table
    """
    if not opts:
        opts = __opts__
    return salt.output.string_format(data, out, opts=opts, **kwargs)


def html_format(data, out="nested", opts=None, **kwargs):
    """
    Return the formatted string as HTML.

    data
        The JSON serializable object.

    out: ``nested``
        The name of the output to use to transform the data. Default: ``nested``.

    opts
        Dictionary of configuration options. Default: ``__opts__``.

    kwargs
        Arguments to sent to the outputter module.

    CLI Example:

    .. code-block:: bash

        salt '*' out.html_format "{'key': 'value'}" out=yaml
    """
    if not opts:
        opts = __opts__
    return salt.output.html_format(data, out, opts=opts, **kwargs)
