# -*- coding: utf-8 -*-
"""
Python pretty-print (pprint)
============================

The python pretty-print system was once the default outputter. It simply
passes the return data through to ``pprint.pformat`` and prints the results.

CLI Example:

.. code-block:: bash

    salt '*' foo.bar --out=pprint

Example output:

.. code-block:: python

    {'saltmine': {'foo': {'bar': 'baz',
                          'dictionary': {'abc': 123, 'def': 456},
                          'list': ['Hello', 'World']}}}
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import pprint

# Import 3rd-party libs
from salt.ext import six

# Define the module's virtual name
__virtualname__ = "pprint"


def __virtual__():
    """
    Change the name to pprint
    """
    return __virtualname__


def output(data, **kwargs):  # pylint: disable=unused-argument
    """
    Print out via pretty print
    """
    if isinstance(data, Exception):
        data = six.text_type(data)
    if "output_indent" in __opts__ and __opts__["output_indent"] >= 0:
        return pprint.pformat(data, indent=__opts__["output_indent"])
    return pprint.pformat(data)
