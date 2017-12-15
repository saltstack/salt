# -*- coding: utf-8 -*-
'''
SaltClass master_tops Module

.. code-block:: yaml
  master_tops:
    saltclass:
      path: /srv/saltclass
'''

# import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

import salt.utils.saltclass as sc

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only run if properly configured
    '''
    if __opts__['master_tops'].get('saltclass'):
        return True
    return False


def top(**kwargs):
    '''
    Node definitions path will be retrieved from __opts__ - or set to default -
    then added to 'salt_data' dict that is passed to the 'get_tops' function.
    'salt_data' dict is a convenient way to pass all the required datas to the function
    It contains:
        - __opts__
        - empty __salt__
        - __grains__
        - empty __pillar__
        - minion_id
        - path

    If successfull the function will return a top dict for minion_id
    '''
    # If path has not been set, make a default
    _opts = __opts__['master_tops']['saltclass']
    if 'path' not in _opts:
        path = '/srv/saltclass'
        log.warning('path variable unset, using default: %s', path)
    else:
        path = _opts['path']

    # Create a dict that will contain our salt objects
    # to send to get_tops function
    if 'id' not in kwargs['opts']:
        log.warning('Minion id not found - Returning empty dict')
        return {}
    else:
        minion_id = kwargs['opts']['id']

    salt_data = {
        '__opts__': kwargs['opts'],
        '__salt__': {},
        '__grains__': kwargs['grains'],
        '__pillar__': {},
        'minion_id': minion_id,
        'path': path
    }

    return sc.get_tops(minion_id, salt_data)
