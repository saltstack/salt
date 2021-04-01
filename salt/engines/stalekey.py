"""
An engine that uses presence detection to keep track of which minions
have been recently connected and remove their keys if they have not been
connected for a certain period of time.

Requires that the :conf_master:`minion_data_cache` option be enabled.

.. versionadded:: 2017.7.0

:configuration:

    Example configuration:

    .. code-block:: yaml

        engines:
          - stalekey:
              interval: 3600
              expire: 86400

"""

import logging
import os
import time

import salt.config
import salt.key
import salt.utils.files
import salt.utils.minions
import salt.utils.msgpack
import salt.wheel

log = logging.getLogger(__name__)


def __virtual__():
    if not __opts__.get("minion_data_cache"):
        return (False, "stalekey engine requires minion_data_cache to be enabled")
    return True


def _get_keys():
    """
    Get the keys
    """
    with salt.key.get_key(__opts__) as keys:
        minions = keys.all_keys()
        return minions["minions"]


def _delete_keys(stale_keys, minions):
    """
    Delete the keys
    """
    wheel = salt.wheel.WheelClient(__opts__)
    for k in stale_keys:
        log.info("Removing stale key for %s", k)
        wheel.cmd("key.delete", [salt.utils.stringutils.to_unicode(k)])
        del minions[k]
    return minions


def _read_presence(presence_file):
    """
    Read minion data from presence file
    """
    error = False
    minions = {}
    if os.path.exists(presence_file):
        try:
            with salt.utils.files.fopen(presence_file, "rb") as f:
                _minions = salt.utils.msgpack.load(f)

                # ensure all keys are unicode, not bytes.
                for minion in _minions:
                    _minion = salt.utils.stringutils.to_unicode(minion)
                    minions[_minion] = _minions[minion]

        except OSError as e:
            error = True
            log.error("Could not open presence file %s: %s", presence_file, e)

    return error, minions


def _write_presence(presence_file, minions):
    """
    Write minion data to presence file
    """
    error = False
    try:
        with salt.utils.files.fopen(presence_file, "wb") as f:
            salt.utils.msgpack.dump(minions, f)
    except OSError as e:
        error = True
        log.error("Could not write to presence file %s: %s", presence_file, e)
    return error


def start(interval=3600, expire=604800):
    """
    Start the engine
    """
    ck = salt.utils.minions.CkMinions(__opts__)
    presence_file = "{}/presence.p".format(__opts__["cachedir"])
    wheel = salt.wheel.WheelClient(__opts__)

    while True:
        log.debug("Checking for present minions")
        minions = {}
        error, minions = _read_presence(presence_file)
        if error:
            time.sleep(interval)
            continue

        minion_keys = _get_keys()
        now = time.time()
        present = ck.connected_ids()

        # For our existing keys, check which are present
        for m in minion_keys:
            # If we have a key that's not in the presence file,
            # it may be a new minion # It could also mean this
            # is the first time this engine is running and no
            # presence file was found
            if m not in minions:
                minions[m] = now
            elif m in present:
                minions[m] = now

        log.debug("Finished checking for present minions")
        # Delete old keys
        stale_keys = []
        for m, seen in minions.items():
            if now - expire > seen:
                stale_keys.append(m)

        if stale_keys:
            minions = _delete_keys(stale_keys, minions)

        error = _write_presence(presence_file, minions)

        time.sleep(interval)
