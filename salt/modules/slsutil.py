# -*- coding: utf-8 -*-
'''
Utility functions for use with or in SLS files
'''
from __future__ import absolute_import

from salt.utils.dictupdate import merge, update

update.__doc__ = update.__doc__ + '''\

CLI Example:

.. code-block:: shell

    salt '*' slsutil.update '{foo: Foo}' '{bar: Bar}'

'''

merge.__doc__ = '''\
Merge a data structure into another by choosing a merge strategy

Strategies:

* aggregate
* list
* overwrite
* recurse
* smart

CLI Example:

.. code-block:: shell

    salt '*' slsutil.merge '{foo: Foo}' '{bar: Bar}'
'''
