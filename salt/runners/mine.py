"""
A runner to access data from the salt mine
"""

import salt.daemons.masterapi


def get(tgt, fun, tgt_type="glob"):
    """
    Gathers the data from the specified minions' mine, pass in the target,
    function to look up and the target type

    CLI Example:

    .. code-block:: bash

        salt-run mine.get '*' network.interfaces
    """
    masterapi = salt.daemons.masterapi.RemoteFuncs(__opts__)
    load = {
        "id": __opts__["id"],
        "fun": fun,
        "tgt": tgt,
        "tgt_type": tgt_type,
    }
    ret = masterapi._mine_get(load)
    return ret


def update(tgt, tgt_type="glob", clear=False, mine_functions=None):
    """
    .. versionadded:: 2017.7.0

    Update the mine data on a certain group of minions.

    tgt
        Which minions to target for the execution.

    tgt_type: ``glob``
        The type of ``tgt``.

    clear: ``False``
        Boolean flag specifying whether updating will clear the existing
        mines, or will update. Default: ``False`` (update).

    mine_functions
        Update the mine data on certain functions only.
        This feature can be used when updating the mine for functions
        that require refresh at different intervals than the rest of
        the functions specified under ``mine_functions`` in the
        minion/master config or pillar.

    CLI Example:

    .. code-block:: bash

        salt-run mine.update '*'
        salt-run mine.update 'juniper-edges' tgt_type='nodegroup'
    """
    ret = __salt__["salt.execute"](
        tgt,
        "mine.update",
        tgt_type=tgt_type,
        clear=clear,
        mine_functions=mine_functions,
    )
    return ret
