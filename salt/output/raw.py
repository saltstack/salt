"""
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

    salt '*' foo.bar --out=raw
    {'myminion': {'foo': {'list': ['Hello', 'World'], 'bar': 'baz', 'dictionary': {'abc': 123, 'def': 456}}}}
"""

import salt.utils.stringutils


def output(data, **kwargs):  # pylint: disable=unused-argument
    """
    Rather basic....
    """
    if not isinstance(data, str):
        data = str(data)
    return salt.utils.stringutils.to_unicode(data)
