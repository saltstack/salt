"""
Beacon that fires events on image import/delete.

.. code-block:: yaml

    ## minimal
    # - check for new images every 1 second (salt default)
    # - does not send events at startup
    beacons:
      imgadm: []

    ## standard
    # - check for new images every 60 seconds
    # - send import events at startup for all images
    beacons:
      imgadm:
        - interval: 60
        - startup_import_event: True
"""

import logging

import salt.utils.beacons

__virtualname__ = "imgadm"

IMGADM_STATE = {
    "first_run": True,
    "images": [],
}

log = logging.getLogger(__name__)


def __virtual__():
    """
    Provides imgadm beacon on SmartOS
    """
    if "imgadm.list" in __salt__:
        return True
    else:
        err_msg = "Only available on SmartOS compute nodes."
        log.error("Unable to load %s beacon: %s", __virtualname__, err_msg)
        return False, err_msg


def validate(config):
    """
    Validate the beacon configuration
    """
    vcfg_ret = True
    vcfg_msg = "Valid beacon configuration"

    if not isinstance(config, list):
        vcfg_ret = False
        vcfg_msg = "Configuration for imgadm beacon must be a list!"

    return vcfg_ret, vcfg_msg


def beacon(config):
    """
    Poll imgadm and compare available images
    """
    ret = []

    # NOTE: lookup current images
    current_images = __salt__["imgadm.list"](verbose=True)

    # NOTE: apply configuration
    if IMGADM_STATE["first_run"]:
        log.info("Applying configuration for imgadm beacon")

        config = salt.utils.beacons.list_to_dict(config)

        if "startup_import_event" not in config or not config["startup_import_event"]:
            IMGADM_STATE["images"] = current_images

    # NOTE: import events
    for uuid in current_images:
        event = {}
        if uuid not in IMGADM_STATE["images"]:
            event["tag"] = f"imported/{uuid}"
            for label in current_images[uuid]:
                event[label] = current_images[uuid][label]

        if event:
            ret.append(event)

    # NOTE: delete events
    for uuid in IMGADM_STATE["images"]:
        event = {}
        if uuid not in current_images:
            event["tag"] = f"deleted/{uuid}"
            for label in IMGADM_STATE["images"][uuid]:
                event[label] = IMGADM_STATE["images"][uuid][label]

        if event:
            ret.append(event)

    # NOTE: update stored state
    IMGADM_STATE["images"] = current_images

    # NOTE: disable first_run
    if IMGADM_STATE["first_run"]:
        IMGADM_STATE["first_run"] = False

    return ret
