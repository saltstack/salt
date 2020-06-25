# -*- coding: utf-8 -*-
"""
.. versionadded:: 2015.5.0

Salt-ssh wrapper functions for the publish module.

Publish will never actually execute on the minions, so we just create new
salt-ssh calls and return the data from them.

No access control is needed because calls cannot originate from the minions.
"""
# Import python libs
from __future__ import absolute_import, print_function

import copy
import logging

# Import salt libs
import salt.client.ssh
import salt.runner
import salt.utils.args

log = logging.getLogger(__name__)


def _publish(
    tgt,
    fun,
    arg=None,
    tgt_type="glob",
    returner="",
    timeout=None,
    form="clean",
    roster=None,
):
    """
    Publish a command "from the minion out to other minions". In reality, the
    minion does not execute this function, it is executed by the master. Thus,
    no access control is enabled, as minions cannot initiate publishes
    themselves.

    Salt-ssh publishes will default to whichever roster was used for the
    initiating salt-ssh call, and can be overridden using the ``roster``
    argument

    Returners are not currently supported

    The arguments sent to the minion publish function are separated with
    commas. This means that for a minion executing a command with multiple
    args it will look like this::

        salt-ssh system.example.com publish.publish '*' user.add 'foo,1020,1020'

    CLI Example:

    .. code-block:: bash

        salt-ssh system.example.com publish.publish '*' cmd.run 'ls -la /tmp'
    """
    if fun.startswith("publish."):
        log.info("Cannot publish publish calls. Returning {}")
        return {}

    # TODO: implement returners? Do they make sense for salt-ssh calls?
    if returner:
        log.warning("Returners currently not supported in salt-ssh publish")

    # Make sure args have been processed
    if arg is None:
        arg = []
    elif not isinstance(arg, list):
        arg = [salt.utils.args.yamlify_arg(arg)]
    else:
        arg = [salt.utils.args.yamlify_arg(x) for x in arg]
    if len(arg) == 1 and arg[0] is None:
        arg = []

    # Set up opts for the SSH object
    opts = copy.deepcopy(__context__["master_opts"])
    minopts = copy.deepcopy(__opts__)
    opts.update(minopts)
    if roster:
        opts["roster"] = roster
    if timeout:
        opts["timeout"] = timeout
    opts["argv"] = [fun] + arg
    opts["selected_target_option"] = tgt_type
    opts["tgt"] = tgt
    opts["arg"] = arg

    # Create the SSH object to handle the actual call
    ssh = salt.client.ssh.SSH(opts)

    # Run salt-ssh to get the minion returns
    rets = {}
    for ret in ssh.run_iter():
        rets.update(ret)

    if form == "clean":
        cret = {}
        for host in rets:
            if "return" in rets[host]:
                cret[host] = rets[host]["return"]
            else:
                cret[host] = rets[host]
        return cret
    else:
        return rets


def publish(tgt, fun, arg=None, tgt_type="glob", returner="", timeout=5, roster=None):
    """
    Publish a command "from the minion out to other minions". In reality, the
    minion does not execute this function, it is executed by the master. Thus,
    no access control is enabled, as minions cannot initiate publishes
    themselves.


    Salt-ssh publishes will default to whichever roster was used for the
    initiating salt-ssh call, and can be overridden using the ``roster``
    argument

    Returners are not currently supported

    The tgt_type argument is used to pass a target other than a glob into
    the execution, the available options are:

    - glob
    - pcre

    .. versionchanged:: 2017.7.0
        The ``expr_form`` argument has been renamed to ``tgt_type``, earlier
        releases must use ``expr_form``.

    The arguments sent to the minion publish function are separated with
    commas. This means that for a minion executing a command with multiple
    args it will look like this:

    .. code-block:: bash

        salt-ssh system.example.com publish.publish '*' user.add 'foo,1020,1020'
        salt-ssh system.example.com publish.publish '127.0.0.1' network.interfaces '' roster=scan

    CLI Example:

    .. code-block:: bash

        salt-ssh system.example.com publish.publish '*' cmd.run 'ls -la /tmp'


    .. admonition:: Attention

        If you need to pass a value to a function argument and that value
        contains an equal sign, you **must** include the argument name.
        For example:

        .. code-block:: bash

            salt-ssh '*' publish.publish test.kwarg arg='cheese=spam'

        Multiple keyword arguments should be passed as a list.

        .. code-block:: bash

            salt-ssh '*' publish.publish test.kwarg arg="['cheese=spam','spam=cheese']"



    """
    return _publish(
        tgt,
        fun,
        arg=arg,
        tgt_type=tgt_type,
        returner=returner,
        timeout=timeout,
        form="clean",
        roster=roster,
    )


def full_data(tgt, fun, arg=None, tgt_type="glob", returner="", timeout=5, roster=None):
    """
    Return the full data about the publication, this is invoked in the same
    way as the publish function

    CLI Example:

    .. code-block:: bash

        salt-ssh system.example.com publish.full_data '*' cmd.run 'ls -la /tmp'

    .. admonition:: Attention

        If you need to pass a value to a function argument and that value
        contains an equal sign, you **must** include the argument name.
        For example:

        .. code-block:: bash

            salt-ssh '*' publish.full_data test.kwarg arg='cheese=spam'

    """
    return _publish(
        tgt,
        fun,
        arg=arg,
        tgt_type=tgt_type,
        returner=returner,
        timeout=timeout,
        form="full",
        roster=roster,
    )


def runner(fun, arg=None, timeout=5):
    """
    Execute a runner on the master and return the data from the runnr function

    CLI Example:

    .. code-block:: bash

        salt-ssh '*' publish.runner jobs.lookup_jid 20140916125524463507
    """
    # Form args as list
    if not isinstance(arg, list):
        arg = [salt.utils.args.yamlify_arg(arg)]
    else:
        arg = [salt.utils.args.yamlify_arg(x) for x in arg]
    if len(arg) == 1 and arg[0] is None:
        arg = []

    # Create and run the runner
    runner = salt.runner.RunnerClient(__opts__["__master_opts__"])
    return runner.cmd(fun, arg)
