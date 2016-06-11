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
from salt.loader import minion_mods, utils

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


def cmd(fun, *args, **kwargs):
    '''
    Execute fun with the given args and kwargs
    Parameter fun should be a Salt module function name.

    CLI example:

    .. code-block:: bash

        salt-run salt.cmd test.ping
        # call functions with arguments and keyword arguments
        salt-run salt.cmd test.arg 1 2 3 a=1
    '''
    log.debug('Called salt.cmd runner with minion function %s', fun)

    kws = {key: val for key, val in kwargs.iteritems()
           if not key.startswith('__')}

    # pylint: disable=undefined-variable
    return minion_mods(
        __opts__,
        utils=utils(__opts__)).get(fun)(*args, **kws)
