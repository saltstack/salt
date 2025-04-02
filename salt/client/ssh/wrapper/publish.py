"""
.. versionadded:: 2015.5.0

Salt-ssh wrapper functions for the publish module.

Publish will never actually execute on the minions, so we just create new
salt-ssh calls and return the data from them.

No access control is needed because calls cannot originate from the minions.

.. versionchanged:: 3007.0

    In addition to SSH minions, this module can now also target regular ones.
"""

import copy
import logging
import time

import salt.client.ssh
import salt.daemons.masterapi
import salt.runner
import salt.utils.args
import salt.utils.json

log = logging.getLogger(__name__)


def _parse_args(arg):
    """
    yamlify `arg` and ensure its outermost datatype is a list
    """
    yaml_args = salt.utils.args.yamlify_arg(arg)

    if yaml_args is None:
        return []
    elif not isinstance(yaml_args, list):
        return [yaml_args]
    else:
        return yaml_args


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
        # yamlify_arg does not operate on non-strings, which we need to JSON-encode
        arg = [salt.utils.json.dumps(salt.utils.args.yamlify_arg(arg))]
    else:
        arg = [
            salt.utils.json.dumps(y)
            for y in (salt.utils.args.yamlify_arg(x) for x in arg)
        ]
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
    for host in rets:
        if "return" in rets[host]:
            # The regular publish return just contains `ret`,
            # at least make it accessible like this as well
            rets[host]["ret"] = rets[host]["return"]
    return rets


def _publish_regular(
    tgt,
    fun,
    arg=None,
    tgt_type="glob",
    returner="",
    timeout=5,
    form="clean",
    wait=False,
):
    if fun.startswith("publish."):
        log.info("Cannot publish publish calls. Returning {}")
        return {}

    arg = _parse_args(arg)
    masterapi = salt.daemons.masterapi.RemoteFuncs(__context__["master_opts"])

    log.info("Publishing '%s'", fun)
    load = {
        "cmd": "minion_pub",
        "fun": fun,
        "arg": arg,
        "tgt": tgt,
        "tgt_type": tgt_type,
        "ret": returner,
        "tmo": timeout,
        "form": form,
        "id": __opts__["id"],
        "no_parse": __opts__.get("no_parse", []),
    }
    peer_data = masterapi.minion_pub(load)
    if not peer_data:
        return {}
    # CLI args are passed as strings, re-cast to keep time.sleep happy
    if wait:
        loop_interval = 0.3
        matched_minions = set(peer_data["minions"])
        returned_minions = set()
        loop_counter = 0
        while returned_minions ^ matched_minions:
            load = {
                "cmd": "pub_ret",
                "id": __opts__["id"],
                "jid": peer_data["jid"],
            }
            ret = masterapi.pub_ret(load)
            returned_minions = set(ret.keys())

            end_loop = False
            if returned_minions >= matched_minions:
                end_loop = True
            elif (loop_interval * loop_counter) > timeout:
                if not returned_minions:
                    return {}
                end_loop = True

            if end_loop:
                if form == "clean":
                    cret = {}
                    for host in ret:
                        cret[host] = ret[host]["ret"]
                    return cret
                else:
                    return ret
            loop_counter = loop_counter + 1
            time.sleep(loop_interval)
    else:
        time.sleep(float(timeout))
        load = {
            "cmd": "pub_ret",
            "id": __opts__["id"],
            "jid": peer_data["jid"],
        }
        ret = masterapi.pub_ret(load)
        if form == "clean":
            cret = {}
            for host in ret:
                cret[host] = ret[host]["ret"]
            return cret
        else:
            return ret
    return ret


def publish(
    tgt,
    fun,
    arg=None,
    tgt_type="glob",
    returner="",
    timeout=5,
    roster=None,
    ssh_minions=True,
    regular_minions=False,
):
    """
    Publish a command from the minion out to other minions. In reality, the
    minion does not execute this function, it is executed by the master. Thus,
    no access control is enabled, as minions cannot initiate publishes
    themselves.

    Salt-ssh publishes will default to whichever roster was used for the
    initiating salt-ssh call, and can be overridden using the ``roster``
    argument.

    Returners are not currently supported

    The tgt_type argument is used to pass a target other than a glob into
    the execution, the available options for SSH minions are:

    - glob
    - pcre
    - nodegroup
    - range

    Regular minions support all usual ones.

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


    tgt
        The target specification.

    fun
        The execution module to run.

    arg
        A list of arguments to pass to the module.

    tgt_type
        The matcher to use. Defaults to ``glob``.

    returner
        A returner to use.

    timeout
        Timeout in seconds. Defaults to 5.

    roster
        Override the roster for SSH minion targets. Defaults to the one
        used for initiating the salt-ssh call.

    ssh_minions
        .. versionadded:: 3007.0
        Include SSH minions in the possible targets. Defaults to true.

    regular_minions
        .. versionadded:: 3007.0
        Include regular minions in the possible targets. Defaults to false.
    """
    rets = {}
    if regular_minions:
        rets.update(
            _publish_regular(
                tgt,
                fun,
                arg=arg,
                tgt_type=tgt_type,
                returner=returner,
                timeout=timeout,
                form="clean",
                wait=True,
            )
        )
    if ssh_minions:
        rets.update(
            _publish(
                tgt,
                fun,
                arg=arg,
                tgt_type=tgt_type,
                returner=returner,
                timeout=timeout,
                form="clean",
                roster=roster,
            )
        )
    return rets


def full_data(
    tgt,
    fun,
    arg=None,
    tgt_type="glob",
    returner="",
    timeout=5,
    roster=None,
    ssh_minions=True,
    regular_minions=False,
):
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
    rets = {}
    if regular_minions:
        rets.update(
            _publish_regular(
                tgt,
                fun,
                arg=arg,
                tgt_type=tgt_type,
                returner=returner,
                timeout=timeout,
                form="full",
                wait=True,
            )
        )
    if ssh_minions:
        rets.update(
            _publish(
                tgt,
                fun,
                arg=arg,
                tgt_type=tgt_type,
                returner=returner,
                timeout=timeout,
                form="full",
                roster=roster,
            )
        )
    return rets


def runner(fun, arg=None, timeout=5):
    """
    Execute a runner on the master and return the data from the runner function

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
