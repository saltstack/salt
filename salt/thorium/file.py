# -*- coding: utf-8 -*-
'''
Writes matches to disk to verify activity, helpful when testing

Normally this is used by giving the name of the file (without a path) that the
data will be saved to. If for instance you use ``foo`` as the name:

.. code-block: yaml

    foo:
      file.save

Then the file will be saved to:

.. code-block: bash

    <salt cachedir>/thorium/saves/foo

You may also provide an absolute path for the file to be saved to:

.. code-block:: yaml

    /tmp/foo.save:
        file.save

Files will be saved in JSON format. However, JSON does not support ``set()``s.
If you are saving a register entry that contains a ``set()``, then it will fail
to save to JSON format. However, you may pass data through a filter which makes
it JSON compliant:

.. code-block:: yaml

    foo:
      file.save:
        filter: True

Be warned that if you do this, then the file will be saved, but not in a format
that can be re-imported into Python.
'''

# import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Import salt libs
import salt.utils.data
import salt.utils.files
import salt.utils.json


def save(name, filter=False):
    '''
    Save the register to <salt cachedir>/thorium/saves/<name>, or to an
    absolute path.

    If an absolute path is specified, then the directory will be created
    non-recursively if it doesn't exist.

    USAGE:

    .. code-block:: yaml

        foo:
          file.save

        /tmp/foo:
          file.save
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': True}
    if name.startswith('/'):
        tgt_dir = os.path.dirname(name)
        fn_ = name
    else:
        tgt_dir = os.path.join(__opts__['cachedir'], 'thorium', 'saves')
        fn_ = os.path.join(tgt_dir, name)
    if not os.path.isdir(tgt_dir):
        os.makedirs(tgt_dir)
    with salt.utils.files.fopen(fn_, 'w+') as fp_:
        if filter is True:
            salt.utils.json.dump(salt.utils.data.simple_types_filter(__reg__), fp_)
        else:
            salt.utils.json.dump(__reg__, fp_)
    return ret
