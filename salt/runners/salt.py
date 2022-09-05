"""
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

"""

import copy
import logging

import salt.client
import salt.loader
import salt.pillar
import salt.utils.args
from salt.exceptions import SaltClientError

log = logging.getLogger(__name__)


def cmd(fun, *args, **kwargs):
    """
    .. versionchanged:: 2018.3.0
        Added ``with_pillar`` argument

    Execute ``fun`` with the given ``args`` and ``kwargs``.  Parameter ``fun``
    should be the string :ref:`name <all-salt.modules>` of the execution module
    to call.

    .. note::
        Execution modules will be loaded *every time* this function is called.
        Additionally, keep in mind that since runners execute on the master,
        custom execution modules will need to be synced to the master using
        :py:func:`salt-run saltutil.sync_modules
        <salt.runners.saltutil.sync_modules>`, otherwise they will not be
        available.

    with_pillar : False
        If ``True``, pillar data will be compiled for the master

        .. note::
            To target the master in the pillar top file, keep in mind that the
            default ``id`` for the master is ``<hostname>_master``. This can be
            overridden by setting an ``id`` configuration parameter in the
            master config file.

    CLI Example:

    .. code-block:: bash

        salt-run salt.cmd test.ping
        # call functions with arguments and keyword arguments
        salt-run salt.cmd test.arg 1 2 3 a=1
        salt-run salt.cmd mymod.myfunc with_pillar=True
    """
    log.debug("Called salt.cmd runner with minion function %s", fun)

    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    with_pillar = kwargs.pop("with_pillar", False)

    opts = copy.deepcopy(__opts__)
    opts["grains"] = salt.loader.grains(opts)

    if with_pillar:
        opts["pillar"] = salt.pillar.get_pillar(
            opts,
            opts["grains"],
            opts["id"],
            saltenv=opts["saltenv"],
            pillarenv=opts.get("pillarenv"),
        ).compile_pillar()
    else:
        opts["pillar"] = {}

    functions = salt.loader.minion_mods(
        opts, utils=salt.loader.utils(opts), context=__context__
    )

    return (
        functions[fun](*args, **kwargs)
        if fun in functions
        else "'{}' is not available.".format(fun)
    )


def execute(
    tgt,
    fun,
    arg=(),
    timeout=None,
    tgt_type="glob",
    ret="",
    jid="",
    kwarg=None,
    **kwargs
):
    """
    .. versionadded:: 2017.7.0

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
    """
    with salt.client.get_local_client(__opts__["conf_file"]) as client:
        try:
            return client.cmd(
                tgt,
                fun,
                arg=arg,
                timeout=timeout or __opts__["timeout"],
                tgt_type=tgt_type,  # no warn_until, as this is introduced only in 2017.7.0
                ret=ret,
                jid=jid,
                kwarg=kwarg,
                **kwargs
            )
        except SaltClientError as client_error:
            log.error("Error while executing %s on %s (%s)", fun, tgt, tgt_type)
            log.error(client_error)
            return {}
