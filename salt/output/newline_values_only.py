# -*- coding: utf-8 -*-
'''
Display values only, separated by newlines
==========================================

.. versionadded:: 2015.5.0

This outputter is designed for Salt CLI return data. It will do the following
to the return dict:

1. Get just the values (ignoring the minion IDs).
2. Each value, if it is iterable, is split a separate line.
3. Each minion's values are separated by newlines.

This results in a single string of return data containing all the values from
the various minions.

.. warning::

    As noted above, this outputter will discard the minion ID. If the minion ID
    is important, then an outputter that returns the full return dictionary in
    a parsable format (such as :mod:`json <salt.output.json>`, :mod:`pprint,
    <salt.output.pprint>`, or :mod:`yaml <salt.output.yaml>`) may be more
    suitable.


Example 1
~~~~~~~~~

.. code-block:: bash

    salt '*' foo.bar --out=newline_values_only

Input
-----

.. code-block:: python

    {
        'myminion': ['127.0.0.1', '10.0.0.1'],
        'second-minion': ['127.0.0.1', '10.0.0.2']
    }

Output
------

.. code-block:: text

    127.0.0.1
    10.0.0.1
    127.0.0.1
    10.0.0.2

Example 2
~~~~~~~~~

.. code-block:: bash

    salt '*' foo.bar --out=newline_values_only

Input
-----

.. code-block:: python

    {
        'myminion': 8,
        'second-minion': 10
    }

Output
------

.. code-block:: python

    8
    10
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import 3rd-party libs
from salt.ext import six


def _get_values(data):
    # This should be able to be improved
    # by parsing kargs from command line
    # instantiation.
    # But I am not sure how to do it
    # just yet.
    # This would enable us to toggle
    # this functionality.
    values = []
    for _, minion_values in six.iteritems(data):
        if isinstance(minion_values, list):
            values.extend(minion_values)
        else:
            values.append(minion_values)
    return values


def _one_level_values(data):
    return '\n'.join(_string_list(_get_values(data)))


def _string_list(a_list):
    return [six.text_type(item) for item in a_list]


def output(data, **kwargs):  # pylint: disable=unused-argument
    '''
    Display modified ret data
    '''
    return _one_level_values(data)
