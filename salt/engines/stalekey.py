#!/usr/bin/python

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

import salt.utils.minions
import salt.config
import salt.key
import salt.wheel
import msgpack
import os
import time
import logging

log = logging.getLogger(__name__)


def __virtual__():
    opts = salt.config.master_config('/etc/salt/master')
    if not opts['minion_data_cache']:
        return (False, 'stalekey engine requires minion_data_cache to be enabled')


def _get_keys(opts):
    keys = salt.key.get_key(opts)
    minions = keys.all_keys()
    return minions['minions']


def start(interval=3600, expire=604800):
    opts = salt.config.master_config('/etc/salt/master')
    ck = salt.utils.minions.CkMinions(opts)
    presence_file = '{0}/minions/presence.p'.format(opts['cachedir'])
    wheel = salt.wheel.WheelClient(opts)

    while True:
        log.debug('Checking for present minions')
        minions = {}
        if os.path.exists(presence_file):
            try:
                with open(presence_file, 'r') as f:
                    minions = msgpack.load(f)
            except IOError as e:
                log.error('Could not open presence file {0}: {1}'.format(presence_file, e))
                time.sleep(interval)
                continue

        minion_keys = _get_keys(opts)
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
        for m, seen in minions.iteritems():
            if now - expire > seen:
                stale_keys.append(m)

        if len(stale_keys):
            for k in stale_keys:
                log.info('Removing stale key for {0}'.format(k))
            wheel.cmd('key.delete', stale_keys)
            del(minions[k])

        try:
            with open(presence_file, 'w') as f:
                msgpack.dump(minions, f)
        except IOError as e:
            log.error('Could not write to presence file {0}: {1}'.format(presence_file, e))
        time.sleep(interval)
