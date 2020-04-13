# -*- coding: utf-8 -*-
"""
Add all extra minion data to the pillar.

:codeauthor: Alexandru.Bleotu@morganstanley.ms.com

One can filter on the keys to include in the pillar by using the ``include``
parameter. For subkeys the ':' notation is supported (i.e. 'key:subkey')
The keyword ``<all>`` includes all keys.

Complete example in etc/salt/master
=====================================

.. code-block:: yaml

    ext_pillar:
      - extra_minion_data_in_pillar:
          include: *

    ext_pillar:
      - extra_minion_data_in_pillar:
          include:
              - key1
              - key2:subkey2

    ext_pillar:
      - extra_minion_data_in_pillar:
          include: <all>

"""


from __future__ import absolute_import, print_function, unicode_literals

import logging

# Set up logging
log = logging.getLogger(__name__)

__virtualname__ = "extra_minion_data_in_pillar"


def __virtual__():
    return __virtualname__


def ext_pillar(minion_id, pillar, include, extra_minion_data=None):
    def get_subtree(key, source_dict):
        """
        Returns a subtree corresponfing to the specified key.

        key
            Key. Supports the ':' notation (e.g. 'key:subkey')

        source_dict
            Source dictionary
        """
        ret_dict = aux_dict = {}
        subtree = source_dict
        subkeys = key.split(":")
        # Build an empty intermediate subtree following the subkeys
        for subkey in subkeys[:-1]:
            # The result will be built in aux_dict
            aux_dict[subkey] = {}
            aux_dict = aux_dict[subkey]
            if subkey not in subtree:
                # The subkey is not in
                return {}
            subtree = subtree[subkey]
        if subkeys[-1] not in subtree:
            # Final subkey is not in subtree
            return {}
        # Assign the subtree value to the result
        aux_dict[subkeys[-1]] = subtree[subkeys[-1]]
        return ret_dict

    log.trace("minion_id = %s", minion_id)
    log.trace("include = %s", include)
    log.trace("extra_minion_data = %s", extra_minion_data)
    data = {}

    if not extra_minion_data:
        return {}
    if include in ["*", "<all>"]:
        return extra_minion_data
    data = {}
    for key in include:
        data.update(get_subtree(key, extra_minion_data))
    return data
