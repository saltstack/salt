# -*- coding: utf-8 -*-
'''
An engine that uses presence detection to keep track of which minions
have been recently connected and remove their keys if they have not been
connected for a certain period of time.

Requires that the minion_data_cache option be enabled.

.. versionadded: Nitrogen

:configuration:

    Example configuration
        engines:
          - stalekey:
              interval: 3600
              expire: 86400

'''
# Import python libs
from __future__ import absolute_import
import os
import time
import logging

# Import salt libs
import salt.utils.minions
import salt.config
import salt.key
import salt.wheel
import salt.utils

# Import 3rd-party libs
import salt.ext.six as six
import msgpack

log = logging.getLogger(__name__)


def __virtual__():
    if not __opts__.get('minion_data_cache'):
        return (False, 'stalekey engine requires minion_data_cache to be enabled')
    return True


def _get_keys():
    keys = salt.key.get_key(__opts__)
    minions = keys.all_keys()
    return minions['minions']


def start(interval=3600, expire=604800):
    ck = salt.utils.minions.CkMinions(__opts__)
    presence_file = '{0}/minions/presence.p'.format(__opts__['cachedir'])
    wheel = salt.wheel.WheelClient(__opts__)

    while True:
        log.debug('Checking for present minions')
        minions = {}
        if os.path.exists(presence_file):
            try:
                with salt.utils.fopen(presence_file, 'r') as f:
                    minions = msgpack.load(f)
            except IOError as e:
                log.error('Could not open presence file {0}: {1}'.format(presence_file, e))
                time.sleep(interval)
                continue

        minion_keys = _get_keys()
        now = time.time()
        present = ck.connected_ids()

        # For our existing keys, check which are present
        for m in minion_keys:
            # If we have a key that's not in the presence file, it may be a new minion
            # It could also mean this is the first time this engine is running and no
            # presence file was found
            if m not in minions:
                minions[m] = now
            elif m in present:
                minions[m] = now

        log.debug('Finished checking for present minions')
        # Delete old keys
        stale_keys = []
        for m, seen in six.iteritems(minions):
            if now - expire > seen:
                stale_keys.append(m)

        if len(stale_keys):
            for k in stale_keys:
                log.info('Removing stale key for {0}'.format(k))
            wheel.cmd('key.delete', stale_keys)
            del minions[k]

        try:
            with salt.utils.fopen(presence_file, 'w') as f:
                msgpack.dump(minions, f)
        except IOError as e:
            log.error('Could not write to presence file {0}: {1}'.format(presence_file, e))
        time.sleep(interval)
