"""
An engine that listens for libvirt events and resends them to the salt event bus.

The minimal configuration is the following and will listen to all events on the
local hypervisor and send them with a tag starting with ``salt/engines/libvirt_events``:

.. code-block:: yaml

    engines:
        - libvirt_events

Note that the automatically-picked libvirt connection will depend on the value
of ``uri_default`` in ``/etc/libvirt/libvirt.conf``. To force using another
connection like the local LXC libvirt driver, set the ``uri`` property as in the
following example configuration.

.. code-block:: yaml

    engines:
        - libvirt_events:
            uri: lxc:///
            tag_prefix: libvirt
            filters:
                - domain/lifecycle
                - domain/reboot
                - pool

Filters is a list of event types to relay to the event bus. Items in this list
can be either one of the main types (``domain``, ``network``, ``pool``,
``nodedev``, ``secret``), ``all`` or a more precise filter. These can be done
with values like <main_type>/<subtype>. The possible values are in the
CALLBACK_DEFS constant. If the filters list contains ``all``, all
events will be relayed.

Be aware that the list of events increases with libvirt versions, for example
network events have been added in libvirt 1.2.1 and storage events in 2.0.0.

Running the engine on non-root
------------------------------

Running this engine as non-root requires a special attention, which is surely
the case for the master running as user `salt`. The engine is likely to fail
to connect to libvirt with an error like this one:

    [ERROR   ] authentication unavailable: no polkit agent available to authenticate action 'org.libvirt.unix.monitor'


To fix this, the user running the engine, for example the salt-master, needs
to have the rights to connect to libvirt in the machine polkit config.
A polkit rule like the following one will allow `salt` user to connect to libvirt:

.. code-block:: javascript

    polkit.addRule(function(action, subject) {
        if (action.id.indexOf("org.libvirt") == 0 &&
            subject.user == "salt") {
            return polkit.Result.YES;
        }
    });

:depends: libvirt 1.0.0+ python binding

.. versionadded:: 2019.2.0
"""

import logging
import urllib.parse

import salt.utils.event

log = logging.getLogger(__name__)


try:
    import libvirt
except ImportError:
    libvirt = None  # pylint: disable=invalid-name


def __virtual__():
    """
    Only load if libvirt python binding is present
    """
    if libvirt is None:
        msg = "libvirt module not found"
    elif libvirt.getVersion() < 1000000:
        msg = "libvirt >= 1.0.0 required"
    else:
        msg = ""
    return not bool(msg), msg


REGISTER_FUNCTIONS = {
    "domain": "domainEventRegisterAny",
    "network": "networkEventRegisterAny",
    "pool": "storagePoolEventRegisterAny",
    "nodedev": "nodeDeviceEventRegisterAny",
    "secret": "secretEventRegisterAny",
}

# Handle either BLOCK_JOB or BLOCK_JOB_2, but prefer the latter
if hasattr(libvirt, "VIR_DOMAIN_EVENT_ID_BLOCK_JOB_2"):
    BLOCK_JOB_ID = "VIR_DOMAIN_EVENT_ID_BLOCK_JOB_2"
else:
    BLOCK_JOB_ID = "VIR_DOMAIN_EVENT_ID_BLOCK_JOB"

CALLBACK_DEFS = {
    "domain": (
        ("lifecycle", None),
        ("reboot", None),
        ("rtc_change", None),
        ("watchdog", None),
        ("graphics", None),
        ("io_error", "VIR_DOMAIN_EVENT_ID_IO_ERROR_REASON"),
        ("control_error", None),
        ("disk_change", None),
        ("tray_change", None),
        ("pmwakeup", None),
        ("pmsuspend", None),
        ("balloon_change", None),
        ("pmsuspend_disk", None),
        ("device_removed", None),
        ("block_job", BLOCK_JOB_ID),
        ("tunable", None),
        ("agent_lifecycle", None),
        ("device_added", None),
        ("migration_iteration", None),
        ("job_completed", None),
        ("device_removal_failed", None),
        ("metadata_change", None),
        ("block_threshold", None),
    ),
    "network": (("lifecycle", None),),
    "pool": (
        ("lifecycle", "VIR_STORAGE_POOL_EVENT_ID_LIFECYCLE"),
        ("refresh", "VIR_STORAGE_POOL_EVENT_ID_REFRESH"),
    ),
    "nodedev": (
        ("lifecycle", "VIR_NODE_DEVICE_EVENT_ID_LIFECYCLE"),
        ("update", "VIR_NODE_DEVICE_EVENT_ID_UPDATE"),
    ),
    "secret": (("lifecycle", None), ("value_changed", None)),
}


def _compute_subprefix(attr):
    """
    Get the part before the first '_' or the end of attr including
    the potential '_'
    """
    return "".join((attr.split("_")[0], "_" if len(attr.split("_")) > 1 else ""))


def _get_libvirt_enum_string(prefix, value):
    """
    Convert the libvirt enum integer value into a human readable string.

    :param prefix: start of the libvirt attribute to look for.
    :param value: integer to convert to string
    """
    attributes = [
        attr[len(prefix) :] for attr in libvirt.__dict__ if attr.startswith(prefix)
    ]

    # Filter out the values starting with a common base as they match another enum
    prefixes = [_compute_subprefix(p) for p in attributes]
    counts = {p: prefixes.count(p) for p in prefixes}
    sub_prefixes = [
        p
        for p, count in counts.items()
        if count > 1 or (p.endswith("_") and p[:-1] in prefixes)
    ]
    filtered = [
        attr for attr in attributes if _compute_subprefix(attr) not in sub_prefixes
    ]

    for candidate in filtered:
        if value == getattr(libvirt, "".join((prefix, candidate))):
            name = candidate.lower().replace("_", " ")
            return name
    return "unknown"


def _get_domain_event_detail(event, detail):
    """
    Convert event and detail numeric values into a tuple of human readable strings
    """
    event_name = _get_libvirt_enum_string("VIR_DOMAIN_EVENT_", event)
    if event_name == "unknown":
        return event_name, "unknown"

    prefix = "VIR_DOMAIN_EVENT_{}_".format(event_name.upper())
    detail_name = _get_libvirt_enum_string(prefix, detail)

    return event_name, detail_name


def _salt_send_event(opaque, conn, data):
    """
    Convenience function adding common data to the event and sending it
    on the salt event bus.

    :param opaque: the opaque data that is passed to the callback.
                   This is a dict with 'prefix', 'object' and 'event' keys.
    :param conn: libvirt connection
    :param data: additional event data dict to send
    """
    tag_prefix = opaque["prefix"]
    object_type = opaque["object"]
    event_type = opaque["event"]

    # Prepare the connection URI to fit in the tag
    # qemu+ssh://user@host:1234/system -> qemu+ssh/user@host:1234/system
    uri = urllib.parse.urlparse(conn.getURI())
    uri_tag = [uri.scheme]
    if uri.netloc:
        uri_tag.append(uri.netloc)
    path = uri.path.strip("/")
    if path:
        uri_tag.append(path)
    uri_str = "/".join(uri_tag)

    # Append some common data
    all_data = {"uri": conn.getURI()}
    all_data.update(data)

    tag = "/".join((tag_prefix, uri_str, object_type, event_type))

    # Actually send the event in salt
    if __opts__.get("__role") == "master":
        salt.utils.event.get_master_event(__opts__, __opts__["sock_dir"]).fire_event(
            all_data, tag
        )
    else:
        __salt__["event.send"](tag, all_data)


def _salt_send_domain_event(opaque, conn, domain, event, event_data):
    """
    Helper function send a salt event for a libvirt domain.

    :param opaque: the opaque data that is passed to the callback.
                   This is a dict with 'prefix', 'object' and 'event' keys.
    :param conn: libvirt connection
    :param domain: name of the domain related to the event
    :param event: name of the event
    :param event_data: additional event data dict to send
    """
    data = {
        "domain": {
            "name": domain.name(),
            "id": domain.ID(),
            "uuid": domain.UUIDString(),
        },
        "event": event,
    }
    data.update(event_data)
    _salt_send_event(opaque, conn, data)


def _domain_event_lifecycle_cb(conn, domain, event, detail, opaque):
    """
    Domain lifecycle events handler
    """
    event_str, detail_str = _get_domain_event_detail(event, detail)

    _salt_send_domain_event(
        opaque,
        conn,
        domain,
        opaque["event"],
        {"event": event_str, "detail": detail_str},
    )


def _domain_event_reboot_cb(conn, domain, opaque):
    """
    Domain reboot events handler
    """
    _salt_send_domain_event(opaque, conn, domain, opaque["event"], {})


def _domain_event_rtc_change_cb(conn, domain, utcoffset, opaque):
    """
    Domain RTC change events handler
    """
    _salt_send_domain_event(
        opaque, conn, domain, opaque["event"], {"utcoffset": utcoffset}
    )


def _domain_event_watchdog_cb(conn, domain, action, opaque):
    """
    Domain watchdog events handler
    """
    _salt_send_domain_event(
        opaque,
        conn,
        domain,
        opaque["event"],
        {"action": _get_libvirt_enum_string("VIR_DOMAIN_EVENT_WATCHDOG_", action)},
    )


def _domain_event_io_error_cb(conn, domain, srcpath, devalias, action, reason, opaque):
    """
    Domain I/O Error events handler
    """
    _salt_send_domain_event(
        opaque,
        conn,
        domain,
        opaque["event"],
        {
            "srcPath": srcpath,
            "dev": devalias,
            "action": _get_libvirt_enum_string("VIR_DOMAIN_EVENT_IO_ERROR_", action),
            "reason": reason,
        },
    )


def _domain_event_graphics_cb(
    conn, domain, phase, local, remote, auth, subject, opaque
):
    """
    Domain graphics events handler
    """
    prefix = "VIR_DOMAIN_EVENT_GRAPHICS_"

    def get_address(addr):
        """
        transform address structure into event data piece
        """
        return {
            "family": _get_libvirt_enum_string(
                "{}_ADDRESS_".format(prefix), addr["family"]
            ),
            "node": addr["node"],
            "service": addr["service"],
        }

    _salt_send_domain_event(
        opaque,
        conn,
        domain,
        opaque["event"],
        {
            "phase": _get_libvirt_enum_string(prefix, phase),
            "local": get_address(local),
            "remote": get_address(remote),
            "authScheme": auth,
            "subject": [{"type": item[0], "name": item[1]} for item in subject],
        },
    )


def _domain_event_control_error_cb(conn, domain, opaque):
    """
    Domain control error events handler
    """
    _salt_send_domain_event(opaque, conn, domain, opaque["event"], {})


def _domain_event_disk_change_cb(conn, domain, old_src, new_src, dev, reason, opaque):
    """
    Domain disk change events handler
    """
    _salt_send_domain_event(
        opaque,
        conn,
        domain,
        opaque["event"],
        {
            "oldSrcPath": old_src,
            "newSrcPath": new_src,
            "dev": dev,
            "reason": _get_libvirt_enum_string("VIR_DOMAIN_EVENT_DISK_", reason),
        },
    )


def _domain_event_tray_change_cb(conn, domain, dev, reason, opaque):
    """
    Domain tray change events handler
    """
    _salt_send_domain_event(
        opaque,
        conn,
        domain,
        opaque["event"],
        {
            "dev": dev,
            "reason": _get_libvirt_enum_string("VIR_DOMAIN_EVENT_TRAY_CHANGE_", reason),
        },
    )


def _domain_event_pmwakeup_cb(conn, domain, reason, opaque):
    """
    Domain wakeup events handler
    """
    _salt_send_domain_event(
        opaque, conn, domain, opaque["event"], {"reason": "unknown"}  # currently unused
    )


def _domain_event_pmsuspend_cb(conn, domain, reason, opaque):
    """
    Domain suspend events handler
    """
    _salt_send_domain_event(
        opaque, conn, domain, opaque["event"], {"reason": "unknown"}  # currently unused
    )


def _domain_event_balloon_change_cb(conn, domain, actual, opaque):
    """
    Domain balloon change events handler
    """
    _salt_send_domain_event(opaque, conn, domain, opaque["event"], {"actual": actual})


def _domain_event_pmsuspend_disk_cb(conn, domain, reason, opaque):
    """
    Domain disk suspend events handler
    """
    _salt_send_domain_event(
        opaque, conn, domain, opaque["event"], {"reason": "unknown"}  # currently unused
    )


def _domain_event_block_job_cb(conn, domain, disk, job_type, status, opaque):
    """
    Domain block job events handler
    """
    _salt_send_domain_event(
        opaque,
        conn,
        domain,
        opaque["event"],
        {
            "disk": disk,
            "type": _get_libvirt_enum_string("VIR_DOMAIN_BLOCK_JOB_TYPE_", job_type),
            "status": _get_libvirt_enum_string("VIR_DOMAIN_BLOCK_JOB_", status),
        },
    )


def _domain_event_device_removed_cb(conn, domain, dev, opaque):
    """
    Domain device removal events handler
    """
    _salt_send_domain_event(opaque, conn, domain, opaque["event"], {"dev": dev})


def _domain_event_tunable_cb(conn, domain, params, opaque):
    """
    Domain tunable events handler
    """
    _salt_send_domain_event(opaque, conn, domain, opaque["event"], {"params": params})


# pylint: disable=invalid-name
def _domain_event_agent_lifecycle_cb(conn, domain, state, reason, opaque):
    """
    Domain agent lifecycle events handler
    """
    _salt_send_domain_event(
        opaque,
        conn,
        domain,
        opaque["event"],
        {
            "state": _get_libvirt_enum_string(
                "VIR_CONNECT_DOMAIN_EVENT_AGENT_LIFECYCLE_STATE_", state
            ),
            "reason": _get_libvirt_enum_string(
                "VIR_CONNECT_DOMAIN_EVENT_AGENT_LIFECYCLE_REASON_", reason
            ),
        },
    )


def _domain_event_device_added_cb(conn, domain, dev, opaque):
    """
    Domain device addition events handler
    """
    _salt_send_domain_event(opaque, conn, domain, opaque["event"], {"dev": dev})


# pylint: disable=invalid-name
def _domain_event_migration_iteration_cb(conn, domain, iteration, opaque):
    """
    Domain migration iteration events handler
    """
    _salt_send_domain_event(
        opaque, conn, domain, opaque["event"], {"iteration": iteration}
    )


def _domain_event_job_completed_cb(conn, domain, params, opaque):
    """
    Domain job completion events handler
    """
    _salt_send_domain_event(opaque, conn, domain, opaque["event"], {"params": params})


def _domain_event_device_removal_failed_cb(conn, domain, dev, opaque):
    """
    Domain device removal failure events handler
    """
    _salt_send_domain_event(opaque, conn, domain, opaque["event"], {"dev": dev})


def _domain_event_metadata_change_cb(conn, domain, mtype, nsuri, opaque):
    """
    Domain metadata change events handler
    """
    _salt_send_domain_event(
        opaque,
        conn,
        domain,
        opaque["event"],
        {
            "type": _get_libvirt_enum_string("VIR_DOMAIN_METADATA_", mtype),
            "nsuri": nsuri,
        },
    )


def _domain_event_block_threshold_cb(
    conn, domain, dev, path, threshold, excess, opaque
):
    """
    Domain block threshold events handler
    """
    _salt_send_domain_event(
        opaque,
        conn,
        domain,
        opaque["event"],
        {"dev": dev, "path": path, "threshold": threshold, "excess": excess},
    )


def _network_event_lifecycle_cb(conn, net, event, detail, opaque):
    """
    Network lifecycle events handler
    """

    _salt_send_event(
        opaque,
        conn,
        {
            "network": {"name": net.name(), "uuid": net.UUIDString()},
            "event": _get_libvirt_enum_string("VIR_NETWORK_EVENT_", event),
            "detail": "unknown",  # currently unused
        },
    )


def _pool_event_lifecycle_cb(conn, pool, event, detail, opaque):
    """
    Storage pool lifecycle events handler
    """
    _salt_send_event(
        opaque,
        conn,
        {
            "pool": {"name": pool.name(), "uuid": pool.UUIDString()},
            "event": _get_libvirt_enum_string("VIR_STORAGE_POOL_EVENT_", event),
            "detail": "unknown",  # currently unused
        },
    )


def _pool_event_refresh_cb(conn, pool, opaque):
    """
    Storage pool refresh events handler
    """
    _salt_send_event(
        opaque,
        conn,
        {
            "pool": {"name": pool.name(), "uuid": pool.UUIDString()},
            "event": opaque["event"],
        },
    )


def _nodedev_event_lifecycle_cb(conn, dev, event, detail, opaque):
    """
    Node device lifecycle events handler
    """
    _salt_send_event(
        opaque,
        conn,
        {
            "nodedev": {"name": dev.name()},
            "event": _get_libvirt_enum_string("VIR_NODE_DEVICE_EVENT_", event),
            "detail": "unknown",  # currently unused
        },
    )


def _nodedev_event_update_cb(conn, dev, opaque):
    """
    Node device update events handler
    """
    _salt_send_event(
        opaque, conn, {"nodedev": {"name": dev.name()}, "event": opaque["event"]}
    )


def _secret_event_lifecycle_cb(conn, secret, event, detail, opaque):
    """
    Secret lifecycle events handler
    """
    _salt_send_event(
        opaque,
        conn,
        {
            "secret": {"uuid": secret.UUIDString()},
            "event": _get_libvirt_enum_string("VIR_SECRET_EVENT_", event),
            "detail": "unknown",  # currently unused
        },
    )


def _secret_event_value_changed_cb(conn, secret, opaque):
    """
    Secret value change events handler
    """
    _salt_send_event(
        opaque,
        conn,
        {"secret": {"uuid": secret.UUIDString()}, "event": opaque["event"]},
    )


def _cleanup(cnx):
    """
    Close the libvirt connection

    :param cnx: libvirt connection
    """
    log.debug("Closing libvirt connection: %s", cnx.getURI())
    cnx.close()


def _callbacks_cleanup(cnx, callback_ids):
    """
    Unregister all the registered callbacks

    :param cnx: libvirt connection
    :param callback_ids: dictionary mapping a libvirt object type to an ID list
                         of callbacks to deregister
    """
    for obj, ids in callback_ids.items():
        register_name = REGISTER_FUNCTIONS[obj]
        deregister_name = register_name.replace("Reg", "Dereg")
        deregister = getattr(cnx, deregister_name)
        for callback_id in ids:
            deregister(callback_id)


def _register_callback(cnx, tag_prefix, obj, event, real_id):
    """
    Helper function registering a callback

    :param cnx: libvirt connection
    :param tag_prefix: salt event tag prefix to use
    :param obj: the libvirt object name for the event. Needs to
                be one of the REGISTER_FUNCTIONS keys.
    :param event: the event type name.
    :param real_id: the libvirt name of an alternative event id to use or None

    :rtype integer value needed to deregister the callback
    """
    libvirt_name = real_id
    if real_id is None:
        libvirt_name = "VIR_{}_EVENT_ID_{}".format(obj, event).upper()

    if not hasattr(libvirt, libvirt_name):
        log.warning('Skipping "%s/%s" events: libvirt too old', obj, event)
        return None

    libvirt_id = getattr(libvirt, libvirt_name)
    callback_name = "_{}_event_{}_cb".format(obj, event)
    callback = globals().get(callback_name, None)
    if callback is None:
        log.error("Missing function %s in engine", callback_name)
        return None

    register = getattr(cnx, REGISTER_FUNCTIONS[obj])
    return register(
        None,
        libvirt_id,
        callback,
        {"prefix": tag_prefix, "object": obj, "event": event},
    )


def _append_callback_id(ids, obj, callback_id):
    """
    Helper function adding a callback ID to the IDs dict.
    The callback ids dict maps an object to event callback ids.

    :param ids: dict of callback IDs to update
    :param obj: one of the keys of REGISTER_FUNCTIONS
    :param callback_id: the result of _register_callback
    """
    if obj not in ids:
        ids[obj] = []
    ids[obj].append(callback_id)


def start(uri=None, tag_prefix="salt/engines/libvirt_events", filters=None):
    """
    Listen to libvirt events and forward them to salt.

    :param uri: libvirt URI to listen on.
                Defaults to None to pick the first available local hypervisor
    :param tag_prefix: the beginning of the salt event tag to use.
                       Defaults to 'salt/engines/libvirt_events'
    :param filters: the list of event of listen on. Defaults to 'all'
    """
    if filters is None:
        filters = ["all"]
    try:
        libvirt.virEventRegisterDefaultImpl()

        cnx = libvirt.openReadOnly(uri)
        log.debug("Opened libvirt uri: %s", cnx.getURI())

        callback_ids = {}
        all_filters = "all" in filters

        for obj, event_defs in CALLBACK_DEFS.items():
            for event, real_id in event_defs:
                event_filter = "/".join((obj, event))
                if (
                    event_filter not in filters
                    and obj not in filters
                    and not all_filters
                ):
                    continue
                registered_id = _register_callback(cnx, tag_prefix, obj, event, real_id)
                if registered_id:
                    _append_callback_id(callback_ids, obj, registered_id)

        exit_loop = False
        while not exit_loop:
            exit_loop = libvirt.virEventRunDefaultImpl() < 0

    except Exception as err:  # pylint: disable=broad-except
        log.exception(err)
    finally:
        _callbacks_cleanup(cnx, callback_ids)
        _cleanup(cnx)
