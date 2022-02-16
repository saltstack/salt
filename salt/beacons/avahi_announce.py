"""
Beacon to announce via avahi (zeroconf)

.. versionadded:: 2016.11.0

Dependencies
============

- python-avahi
- dbus-python

"""

import logging
import time

import salt.utils.beacons
import salt.utils.stringutils

try:
    import avahi

    HAS_PYAVAHI = True
except ImportError:
    HAS_PYAVAHI = False

try:
    import dbus
    from dbus import DBusException

    BUS = dbus.SystemBus()
    SERVER = dbus.Interface(
        BUS.get_object(avahi.DBUS_NAME, avahi.DBUS_PATH_SERVER),
        avahi.DBUS_INTERFACE_SERVER,
    )
    GROUP = dbus.Interface(
        BUS.get_object(avahi.DBUS_NAME, SERVER.EntryGroupNew()),
        avahi.DBUS_INTERFACE_ENTRY_GROUP,
    )
    HAS_DBUS = True
except (ImportError, NameError):
    HAS_DBUS = False
except DBusException:
    HAS_DBUS = False

log = logging.getLogger(__name__)

__virtualname__ = "avahi_announce"

LAST_GRAINS = {}


def __virtual__():
    if HAS_PYAVAHI:
        if HAS_DBUS:
            return __virtualname__
        err_msg = "The 'python-dbus' dependency is missing."
        log.error("Unable to load %s beacon: %s", __virtualname__, err_msg)
        return False, err_msg

    err_msg = "The 'python-avahi' dependency is missing."
    log.error("Unable to load %s beacon: %s", __virtualname__, err_msg)
    return False, err_msg


def validate(config):
    """
    Validate the beacon configuration
    """

    _config = salt.utils.beacons.list_to_dict(config)

    if not isinstance(config, list):
        return False, "Configuration for avahi_announce beacon must be a list."

    elif not all(x in _config for x in ("servicetype", "port", "txt")):
        return (
            False,
            "Configuration for avahi_announce beacon must contain servicetype, port and txt items.",
        )
    return True, "Valid beacon configuration."


def _enforce_txt_record_maxlen(key, value):
    """
    Enforces the TXT record maximum length of 255 characters.
    TXT record length includes key, value, and '='.

    :param str key: Key of the TXT record
    :param str value: Value of the TXT record

    :rtype: str
    :return: The value of the TXT record. It may be truncated if it exceeds
             the maximum permitted length. In case of truncation, '...' is
             appended to indicate that the entire value is not present.
    """
    # Add 1 for '=' separator between key and value
    if len(key) + len(value) + 1 > 255:
        # 255 - 3 ('...') - 1 ('=') = 251
        return value[: 251 - len(key)] + "..."
    return value


def beacon(config):
    """
    Broadcast values via zeroconf

    If the announced values are static, it is advised to set run_once: True
    (do not poll) on the beacon configuration.

    The following are required configuration settings:

    - ``servicetype`` - The service type to announce
    - ``port`` - The port of the service to announce
    - ``txt`` - The TXT record of the service being announced as a dict. Grains
      can be used to define TXT values using one of following two formats:

      - ``grains.<grain_name>``
      - ``grains.<grain_name>[i]`` where i is an integer representing the
        index of the grain to use. If the grain is not a list, the index is
        ignored.

    The following are optional configuration settings:

    - ``servicename`` - Set the name of the service. Will use the hostname from
      the minion's ``host`` grain if this value is not set.
    - ``reset_on_change`` - If ``True`` and there is a change in TXT records
      detected, it will stop announcing the service and then restart announcing
      the service. This interruption in service announcement may be desirable
      if the client relies on changes in the browse records to update its cache
      of TXT records. Defaults to ``False``.
    - ``reset_wait`` - The number of seconds to wait after announcement stops
      announcing and before it restarts announcing in the case where there is a
      change in TXT records detected and ``reset_on_change`` is ``True``.
      Defaults to ``0``.
    - ``copy_grains`` - If ``True``, Salt will copy the grains passed into the
      beacon when it backs them up to check for changes on the next iteration.
      Normally, instead of copy, it would use straight value assignment. This
      will allow detection of changes to grains where the grains are modified
      in-place instead of completely replaced.  In-place grains changes are not
      currently done in the main Salt code but may be done due to a custom
      plug-in. Defaults to ``False``.

    Example Config

    .. code-block:: yaml

       beacons:
         avahi_announce:
           - run_once: True
           - servicetype: _demo._tcp
           - port: 1234
           - txt:
               ProdName: grains.productname
               SerialNo: grains.serialnumber
               Comments: 'this is a test'
    """
    ret = []
    changes = {}
    txt = {}

    global LAST_GRAINS

    config = salt.utils.beacons.list_to_dict(config)

    if "servicename" in config:
        servicename = config["servicename"]
    else:
        servicename = __grains__["host"]
        # Check for hostname change
        if LAST_GRAINS and LAST_GRAINS["host"] != servicename:
            changes["servicename"] = servicename

    if LAST_GRAINS and config.get("reset_on_change", False):
        # Check for IP address change in the case when we reset on change
        if LAST_GRAINS.get("ipv4", []) != __grains__.get("ipv4", []):
            changes["ipv4"] = __grains__.get("ipv4", [])
        if LAST_GRAINS.get("ipv6", []) != __grains__.get("ipv6", []):
            changes["ipv6"] = __grains__.get("ipv6", [])

    for item in config["txt"]:
        changes_key = "txt." + salt.utils.stringutils.to_unicode(item)
        if config["txt"][item].startswith("grains."):
            grain = config["txt"][item][7:]
            grain_index = None
            square_bracket = grain.find("[")
            if square_bracket != -1 and grain[-1] == "]":
                grain_index = int(grain[square_bracket + 1 : -1])
                grain = grain[:square_bracket]

            grain_value = __grains__.get(grain, "")
            if isinstance(grain_value, list):
                if grain_index is not None:
                    grain_value = grain_value[grain_index]
                else:
                    grain_value = ",".join(grain_value)
            txt[item] = _enforce_txt_record_maxlen(item, grain_value)
            if LAST_GRAINS and (
                LAST_GRAINS.get(grain, "") != __grains__.get(grain, "")
            ):
                changes[changes_key] = txt[item]
        else:
            txt[item] = _enforce_txt_record_maxlen(item, config["txt"][item])

        if not LAST_GRAINS:
            changes[changes_key] = txt[item]

    if changes:
        if not LAST_GRAINS:
            changes["servicename"] = servicename
            changes["servicetype"] = config["servicetype"]
            changes["port"] = config["port"]
            changes["ipv4"] = __grains__.get("ipv4", [])
            changes["ipv6"] = __grains__.get("ipv6", [])
            GROUP.AddService(
                avahi.IF_UNSPEC,
                avahi.PROTO_UNSPEC,
                dbus.UInt32(0),
                servicename,
                config["servicetype"],
                "",
                "",
                dbus.UInt16(config["port"]),
                avahi.dict_to_txt_array(txt),
            )
            GROUP.Commit()
        elif config.get("reset_on_change", False) or "servicename" in changes:
            # A change in 'servicename' requires a reset because we can only
            # directly update TXT records
            GROUP.Reset()
            reset_wait = config.get("reset_wait", 0)
            if reset_wait > 0:
                time.sleep(reset_wait)
            GROUP.AddService(
                avahi.IF_UNSPEC,
                avahi.PROTO_UNSPEC,
                dbus.UInt32(0),
                servicename,
                config["servicetype"],
                "",
                "",
                dbus.UInt16(config["port"]),
                avahi.dict_to_txt_array(txt),
            )
            GROUP.Commit()
        else:
            GROUP.UpdateServiceTxt(
                avahi.IF_UNSPEC,
                avahi.PROTO_UNSPEC,
                dbus.UInt32(0),
                servicename,
                config["servicetype"],
                "",
                avahi.dict_to_txt_array(txt),
            )

        ret.append({"tag": "result", "changes": changes})

    if config.get("copy_grains", False):
        LAST_GRAINS = __grains__.copy()
    else:
        LAST_GRAINS = __grains__

    return ret
