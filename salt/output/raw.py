# -*- coding: utf-8 -*-
'''
Display raw output data structure
=================================

This outputter simply displays the output as a python data structure, by
printing a string representation of it. It is similar to the :mod:`pprint
<salt.output.pprint>` outputter, only the data is not nicely
formatted/indented.

This was the original outputter used by Salt before the outputter system was
developed.

CLI Example:

.. code-block:: bash

    salt '*' foo.bar --out=raw

Example output:

.. code-block:: python

    salt '*' foo.bar --out=table
    {'myminion': {'foo': {'list': ['Hello', 'World'], 'bar': 'baz', 'dictionary': {'abc': 123, 'def': 456}}}}
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.utils.stringutils

# Import 3rd-party libs
from salt.ext import six


def output(data, **kwargs):  # pylint: disable=unused-argument
    '''
    Rather basic....
    '''
    if not isinstance(data, six.string_types):
        data = six.text_type(data)
    return salt.utils.stringutils.to_unicode(data)
