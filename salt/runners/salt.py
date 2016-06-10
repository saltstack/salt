# -*- coding: utf-8 -*-
'''
Runner to call execution modules

.. versionadded:: Carbon
'''
# import python libs
from __future__ import absolute_import
from __future__ import print_function
import logging

# import salt libs
from salt.loader import minion_mods

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


def cmd(fun, args=None, kwargs=None):
    '''
    Execute fun with the given args and kwargs
    Parameter fun should be a Salt module function name.

    CLI example:

    .. code-block:: bash

        salt-run salt.cmd test.ping
        salt-run salt.cmd test.arg args='[1, 2, 3]', kwargs='{"a": 1}'
    '''
    log.debug('Called salt.cmd runner with minion function %s', fun)

    args = args or []
    kwargs = kwargs or {}

    return minion_mods(__opts__).get(fun)(*args, **kwargs)  # pylint: disable=undefined-variable
