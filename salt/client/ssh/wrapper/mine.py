"""
Wrapper function for mine operations for salt-ssh

.. versionadded:: 2015.5.0
.. versionchanged:: 3007.0

    In addition to mine returns from roster targets, this wrapper now supports
    accessing the regular mine as well.
"""

import copy
import logging

import salt.client.ssh
import salt.daemons.masterapi

log = logging.getLogger(__name__)


def get(
    tgt, fun, tgt_type="glob", roster="flat", ssh_minions=True, regular_minions=False
):
    """
    Get data from the mine based on the target, function and tgt_type

    This will actually run the function on all targeted SSH minions (like
    publish.publish), as salt-ssh clients can't update the mine themselves.

    We will look for mine_functions in the roster, pillar, and master config,
    in that order, looking for a match for the defined function.

    Targets can be matched based on any standard matching system that can be
    matched on the defined roster (in salt-ssh).

    Regular mine data will be fetched as usual and can be targeted as usual.

    CLI Example:

    .. code-block:: bash

        salt-ssh '*' mine.get '*' network.interfaces
        salt-ssh '*' mine.get 'myminion' network.interfaces roster=flat
        salt-ssh '*' mine.get '192.168.5.0' network.ipaddrs roster=scan
        salt-ssh myminion mine.get '*' network.interfaces ssh_minions=False regular_minions=True
        salt-ssh myminion mine.get '*' network.interfaces ssh_minions=True regular_minions=True

    tgt
        Target whose mine data to get.

    fun
        Function to get the mine data of. You can specify multiple functions
        to retrieve using either a list or a comma-separated string of functions.

    tgt_type
        Target type to use with ``tgt``. Defaults to ``glob``.
        See :ref:`targeting` for more information for regular minion targets, above
        for SSH ones.

    roster
        The roster module to use. Defaults to ``flat``.

    ssh_minions
        .. versionadded:: 3007.0
        Target minions from the roster. Defaults to true.

    regular_minions
        .. versionadded:: 3007.0
        Target regular minions of the master running salt-ssh. Defaults to false.
    """
    rets = {}
    if regular_minions:
        masterapi = salt.daemons.masterapi.RemoteFuncs(__context__["master_opts"])
        load = {
            "id": __opts__["id"],
            "fun": fun,
            "tgt": tgt,
            "tgt_type": tgt_type,
        }
        ret = masterapi._mine_get(load)
        rets.update(ret)

    if ssh_minions:
        # Set up opts for the SSH object
        opts = copy.deepcopy(__context__["master_opts"])
        minopts = copy.deepcopy(__opts__)
        opts.update(minopts)
        if roster:
            opts["roster"] = roster
        opts["argv"] = [fun]
        opts["selected_target_option"] = tgt_type
        opts["tgt"] = tgt
        opts["arg"] = []

        # Create the SSH object to handle the actual call
        ssh = salt.client.ssh.SSH(opts)

        # Run salt-ssh to get the minion returns
        mrets = {}
        for ret in ssh.run_iter(mine=True):
            mrets.update(ret)

        for host, data in mrets.items():
            if not isinstance(data, dict):
                log.error(
                    "Error executing mine func %s on %s: %s."
                    " Excluding minion from mine.",
                    fun,
                    host,
                    data,
                )
            elif "_error" in data:
                log.error(
                    "Error executing mine func %s on %s: %s."
                    " Excluding minion from mine. Full output in debug log.",
                    fun,
                    host,
                    data["_error"],
                )
                log.debug("Return was: %s", salt.utils.json.dumps(data))
            elif "return" not in data:
                log.error(
                    "Error executing mine func %s on %s: No return was specified."
                    " Excluding minion from mine. Full output in debug log.",
                    fun,
                    host,
                )
                log.debug("Return was: %s", salt.utils.json.dumps(data))
            else:
                rets[host] = data["return"]
    return rets
