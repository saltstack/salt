"""
Digicert Pillar Certificates

This module will only return pillar data if the ``digicert`` runner module has
already been used to create certificates.

To configure this module, set ``digicert`` to ``True`` in the ``ext_pillar``
section of your ``master`` configuration file:

.. code-block:: yaml

    ext_pillar:
      - digicert: True
"""

import logging

import salt.cache
import salt.syspaths as syspaths

__virtualname__ = "digicert"
log = logging.getLogger(__name__)


def __virtual__():
    """
    No special requirements outside of Salt itself
    """
    return __virtualname__


def ext_pillar(minion_id, pillar, conf):
    """
    Return an existing set of certificates
    """
    cache = salt.cache.Cache(__opts__, syspaths.CACHE_DIR)

    ret = {}
    dns_names = cache.fetch("digicert/minions", minion_id)

    for dns_name in dns_names:
        data = cache.fetch("digicert/domains", dns_name)
        ret[dns_name] = data
        del ret[dns_name]["csr"]
    return {"digicert": ret}
