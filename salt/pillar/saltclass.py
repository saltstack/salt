"""
SaltClass Pillar Module
=======================

.. code-block:: yaml

    ext_pillar:
      - saltclass:
        - path: /srv/saltclass

For additional configuration instructions, see the :mod:`saltclass <salt.tops.saltclass>` module
"""

import logging

import salt.utils.saltclass as sc

log = logging.getLogger(__name__)


def __virtual__():
    """
    This module has no external dependencies
    """
    return True


def ext_pillar(minion_id, pillar, *args, **kwargs):
    """
    Compile pillar data
    """
    # Node definitions path will be retrieved from args (or set to default),
    # then added to 'salt_data' dict that is passed to the 'get_pillars'
    # function. The dictionary contains:
    #     - __opts__
    #     - __salt__
    #     - __grains__
    #     - __pillar__
    #     - minion_id
    #     - path
    #
    # If successful, the function will return a pillar dict for minion_id.

    # If path has not been set, make a default
    for i in args:
        if "path" not in i:
            path = "/srv/saltclass"
            args[i]["path"] = path
            log.warning("path variable unset, using default: %s", path)
        else:
            path = i["path"]

    # Create a dict that will contain our salt dicts to pass it to reclass
    salt_data = {
        "__opts__": __opts__,
        "__salt__": __salt__,
        "__grains__": __grains__,
        "__pillar__": pillar,
        "minion_id": minion_id,
        "path": path,
    }

    return sc.get_pillars(minion_id, salt_data)
