# -*- coding: utf-8 -*-
'''
This runner makes Salt's
execution modules available
on the salt master.

.. versionadded:: 2016.11.0

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
import salt.client
from salt.loader import minion_mods, utils
from salt.exceptions import SaltClientError

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


def execute(tgt,
            fun,
            arg=(),
            timeout=None,
            tgt_type='glob',
            ret='',
            jid='',
            kwarg=None,
            **kwargs):
    '''
    .. versionadded:: Nitrogen

    Execute ``fun`` on all minions matched by ``tgt`` and ``tgt_type``.
    Parameter ``fun`` is the name of execution module function to call.

    This function should mainly be used as a helper for runner modules,
    in order to avoid redundant code.
    For example, when inside a runner one needs to execute a certain function
    on arbitrary groups of minions, only has to:

    .. code-block:: python

        ret1 = __salt__['salt.execute']('*', 'mod.fun')
        ret2 = __salt__['salt.execute']('my_nodegroup', 'mod2.fun2', tgt_type='nodegroup')

    It can also be used to schedule jobs directly on the master, for example:

    .. code-block:: yaml

        schedule:
            collect_bgp_stats:
                function: salt.execute
                args:
                    - edge-routers
                    - bgp.neighbors
                kwargs:
                    tgt_type: nodegroup
                days: 1
                returner: redis
    '''
    client = salt.client.get_local_client(__opts__['conf_file'])
    try:
        ret = client.cmd(tgt,
                         fun,
                         arg=arg,
                         timeout=timeout or __opts__['timeout'],
                         tgt_type=tgt_type,  # no warn_until, as this is introduced only in Nitrogen
                         ret=ret,
                         jid=jid,
                         kwarg=kwarg,
                         **kwargs)
    except SaltClientError as client_error:
        log.error('Error while executing {fun} on {tgt} ({tgt_type})'.format(fun=fun,
                                                                             tgt=tgt,
                                                                             tgt_type=tgt_type))
        log.error(client_error)
        return {}
    return ret
