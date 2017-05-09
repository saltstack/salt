# -*- coding: utf-8 -*-
'''
.. versionadded:: 2016.11.0

This runner makes Salt's
execution modules available
on the salt master.

.. _salt_salt_runner:

Salt's execution modules are normally available
on the salt minion. Use this runner to call
execution modules on the salt master.
Salt :ref:`execution modules <writing-execution-modules>`
are the functions called by the ``salt`` command.

Execution modules can be called with ``salt-run``:

.. code-block:: bash

    salt-run salt.cmd test.ping
    # call functions with arguments and keyword arguments
    salt-run salt.cmd test.arg 1 2 3 key=value a=1

Execution modules are also available to salt runners:

.. code-block:: python

    __salt__['salt.cmd'](fun=fun, args=args, kwargs=kwargs)

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
    Execute ``fun`` with the given ``args`` and ``kwargs``.
    Parameter ``fun`` should be the string :ref:`name <all-salt.modules>`
    of the execution module to call.

    Note that execution modules will be *loaded every time*
    this function is called.

    CLI example:

    .. code-block:: bash

        salt-run salt.cmd test.ping
        # call functions with arguments and keyword arguments
        salt-run salt.cmd test.arg 1 2 3 a=1
    '''
    log.debug('Called salt.cmd runner with minion function %s', fun)

    kws = dict((k, v) for k, v in kwargs.items() if not k.startswith('__'))

    # pylint: disable=undefined-variable
    return minion_mods(
        __opts__,
        utils=utils(__opts__)).get(fun)(*args, **kws)
