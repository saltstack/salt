# -*- coding: utf-8 -*-
'''
SaltClass Pillar Module

.. code-block:: yaml

  ext_pillar:
    - saltclass:
      - path: /srv/saltclass

'''

# import python libs
from __future__ import absolute_import, print_function, unicode_literals
import salt.utils.saltclass as sc
import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''
    This module has no external dependencies
    '''
    return True


def ext_pillar(minion_id, pillar, *args, **kwargs):
    '''
    Node definitions path will be retrieved from args - or set to default -
    then added to 'salt_data' dict that is passed to the 'get_pillars' function.
    'salt_data' dict is a convenient way to pass all the required datas to the function
    It contains:
        - __opts__
        - __salt__
        - __grains__
        - __pillar__
        - minion_id
        - path

    If successfull the function will return a pillar dict for minion_id
    '''
    # If path has not been set, make a default
    for i in args:
        if 'path' not in i:
            path = '/srv/saltclass'
            args[i]['path'] = path
            log.warning('path variable unset, using default: %s', path)
        else:
            path = i['path']

    # Create a dict that will contain our salt dicts to pass it to reclass
    salt_data = {
        '__opts__': __opts__,
        '__salt__': __salt__,
        '__grains__': __grains__,
        '__pillar__': pillar,
        'minion_id': minion_id,
        'path': path
    }

    return sc.get_pillars(minion_id, salt_data)
