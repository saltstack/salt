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

Example output::

    {'myminion': {'foo': {'list': ['Hello', 'World'], 'bar': 'baz', 'dictionary': {'abc': 123, 'def': 456}}}}
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt libs
import salt.utils.locales


def output(data):
    '''
    Rather basic....
    '''
    return salt.utils.locales.sdecode(str(data))
