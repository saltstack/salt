import logging

import salt.utils.event

log = logging.getLogger(__name__)


def rebuild_index():
    """
    Trigger a full rebuild of the PKI mmap index on the master.

    CLI Example:

    .. code-block:: bash

        salt-run pki.rebuild_index
    """
    if not __opts__.get("pki_index_enabled", False):
        return "PKI index is not enabled in configuration."

    with salt.utils.event.get_master_event(
        __opts__, __opts__["sock_dir"], listen=True
    ) as event:
        event.fire_event({}, "salt/pki/index/rebuild")

        # Wait for completion event
        res = event.get_event(wait=30, tag="salt/pki/index/rebuild/complete")
        if res and res.get("data", {}).get("result"):
            return "PKI index rebuild successful."
        return "PKI index rebuild failed or timed out."
