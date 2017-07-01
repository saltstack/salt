# -*- coding: utf-8 -*-
'''
Venafi Pillar Certificates

This module will only return pillar data if the ``venafi`` runner module has
already been used to create certificates.

To configure this module, set ``venafi`` to ``True`` in the ``ext_pillar``
section of your ``master`` configuration file:

.. code-block:: yaml

    ext_pillar:
      - venafi: True
'''
from __future__ import absolute_import
import logging
import salt.utils
import salt.cache
import salt.syspaths as syspaths

__virtualname__ = 'venafi'
log = logging.getLogger(__name__)


def __virtual__():
    '''
    No special requirements outside of Salt itself
    '''
    return __virtualname__


def ext_pillar(minion_id, pillar, conf):
    '''
    Return an existing set of certificates
    '''
    cache = salt.cache.Cache(__opts__, syspaths.CACHE_DIR)

    ret = {}
    dns_names = cache.fetch('venafi/minions', minion_id)
    for dns_name in dns_names:
        data = cache.fetch('venafi/domains', dns_name)
        ret[dns_name] = data
        del ret[dns_name]['csr']
    return {'venafi': ret}
