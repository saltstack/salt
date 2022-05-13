"""
Beacon that fires events on vm state changes

.. code-block:: yaml

    ## minimal
    # - check for vm changes every 1 second (salt default)
    # - does not send events at startup
    beacons:
      vmadm: []

    ## standard
    # - check for vm changes every 60 seconds
    # - send create event at startup for all vms
    beacons:
      vmadm:
        - interval: 60
        - startup_create_event: True
"""
import logging

import salt.utils.beacons

__virtualname__ = "vmadm"

VMADM_STATE = {
    "first_run": True,
    "vms": [],
}

log = logging.getLogger(__name__)


def __virtual__():
    """
    Provides vmadm beacon on SmartOS
    """
    if "vmadm.list" in __salt__:
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
        vcfg_msg = "Configuration for vmadm beacon must be a list!"

    return vcfg_ret, vcfg_msg


def beacon(config):
    """
    Poll vmadm for changes
    """
    ret = []

    # NOTE: lookup current images
    current_vms = __salt__["vmadm.list"](
        keyed=True,
        order="uuid,state,alias,hostname,dns_domain",
    )

    # NOTE: apply configuration
    if VMADM_STATE["first_run"]:
        log.info("Applying configuration for vmadm beacon")

        config = salt.utils.beacons.list_to_dict(config)

        if "startup_create_event" not in config or not config["startup_create_event"]:
            VMADM_STATE["vms"] = current_vms

    # NOTE: create events
    for uuid in current_vms:
        event = {}
        if uuid not in VMADM_STATE["vms"]:
            event["tag"] = "created/{}".format(uuid)
            for label in current_vms[uuid]:
                if label == "state":
                    continue
                event[label] = current_vms[uuid][label]

        if event:
            ret.append(event)

    # NOTE: deleted events
    for uuid in VMADM_STATE["vms"]:
        event = {}
        if uuid not in current_vms:
            event["tag"] = "deleted/{}".format(uuid)
            for label in VMADM_STATE["vms"][uuid]:
                if label == "state":
                    continue
                event[label] = VMADM_STATE["vms"][uuid][label]

        if event:
            ret.append(event)

    # NOTE: state change events
    for uuid in current_vms:
        event = {}
        if (
            VMADM_STATE["first_run"]
            or uuid not in VMADM_STATE["vms"]
            or current_vms[uuid].get("state", "unknown")
            != VMADM_STATE["vms"][uuid].get("state", "unknown")
        ):
            event["tag"] = "{}/{}".format(
                current_vms[uuid].get("state", "unknown"), uuid
            )
            for label in current_vms[uuid]:
                if label == "state":
                    continue
                event[label] = current_vms[uuid][label]

        if event:
            ret.append(event)

    # NOTE: update stored state
    VMADM_STATE["vms"] = current_vms

    # NOTE: disable first_run
    if VMADM_STATE["first_run"]:
        VMADM_STATE["first_run"] = False

    return ret


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
