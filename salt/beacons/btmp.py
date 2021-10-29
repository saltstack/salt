"""
Beacon to fire events at failed login of users

.. versionadded:: 2015.5.0

Example Configuration
=====================

.. code-block:: yaml

    # Fire events on all failed logins
    beacons:
      btmp: []

    # Matching on user name, using a default time range
    beacons:
      btmp:
        - users:
            gareth:
        - defaults:
            time_range:
                start: '8am'
                end: '4pm'

    # Matching on user name, overriding the default time range
    beacons:
      btmp:
        - users:
            gareth:
                time_range:
                    start: '8am'
                    end: '4pm'
        - defaults:
            time_range:
                start: '8am'
                end: '4pm'

    # Matching on group name, overriding the default time range
    beacons:
      btmp:
        - groups:
            users:
                time_range:
                    start: '8am'
                    end: '4pm'
        - defaults:
            time_range:
                start: '8am'
                end: '4pm'


Use Case: Posting Failed Login Events to Slack
==============================================

This can be done using the following reactor SLS:

.. code-block:: jinja

    report-wtmp:
      runner.salt.cmd:
        - args:
          - fun: slack.post_message
          - channel: mychannel      # Slack channel
          - from_name: someuser     # Slack user
          - message: "Failed login from `{{ data.get('user', '') or 'unknown user' }}` on `{{ data['id'] }}`"

Match the event like so in the master config file:

.. code-block:: yaml

    reactor:

      - 'salt/beacon/*/btmp/':
        - salt://reactor/btmp.sls

.. note::
    This approach uses the :py:mod:`slack execution module
    <salt.modules.slack_notify>` directly on the master, and therefore requires
    that the master has a slack API key in its configuration:

    .. code-block:: yaml

        slack:
          api_key: xoxb-XXXXXXXXXXXX-XXXXXXXXXXXX-XXXXXXXXXXXXXXXXXXXXXXXX

    See the :py:mod:`slack execution module <salt.modules.slack_notify>`
    documentation for more information. While you can use an individual user's
    API key to post to Slack, a bot user is likely better suited for this. The
    :py:mod:`slack engine <salt.engines.slack>` documentation has information
    on how to set up a bot user.
"""

import datetime
import logging
import os
import struct

import salt.utils.files
import salt.utils.stringutils

__virtualname__ = "btmp"
BTMP = "/var/log/btmp"
FMT = b"hi32s4s32s256shhiii4i20x"
FIELDS = [
    "type",
    "PID",
    "line",
    "inittab",
    "user",
    "hostname",
    "exit_status",
    "session",
    "time",
    "addr",
]
SIZE = struct.calcsize(FMT)
LOC_KEY = "btmp.loc"

log = logging.getLogger(__name__)

try:
    import dateutil.parser as dateutil_parser

    _TIME_SUPPORTED = True
except ImportError:
    _TIME_SUPPORTED = False


def __virtual__():
    if os.path.isfile(BTMP):
        return __virtualname__
    return False


def _validate_time_range(trange, status, msg):
    """
    Check time range
    """
    # If trange is empty, just return the current status & msg
    if not trange:
        return status, msg

    if not isinstance(trange, dict):
        status = False
        msg = "The time_range parameter for btmp beacon must be a dictionary."

    if not all(k in trange for k in ("start", "end")):
        status = False
        msg = (
            "The time_range parameter for btmp beacon must contain start & end options."
        )

    return status, msg


def _gather_group_members(group, groups, users):
    """
    Gather group members
    """
    _group = __salt__["group.info"](group)

    if not _group:
        log.warning("Group %s does not exist, ignoring.", group)
        return

    for member in _group["members"]:
        if member not in users:
            users[member] = groups[group]


def _check_time_range(time_range, now):
    """
    Check time range
    """
    if _TIME_SUPPORTED:
        _start = dateutil_parser.parse(time_range["start"])
        _end = dateutil_parser.parse(time_range["end"])

        return bool(_start <= now <= _end)
    else:
        log.error("Dateutil is required.")
        return False


def _get_loc():
    """
    return the active file location
    """
    if LOC_KEY in __context__:
        return __context__[LOC_KEY]


def validate(config):
    """
    Validate the beacon configuration
    """
    vstatus = True
    vmsg = "Valid beacon configuration"

    # Configuration for load beacon should be a list of dicts
    if not isinstance(config, list):
        vstatus = False
        vmsg = "Configuration for btmp beacon must be a list."
    else:
        config = salt.utils.beacons.list_to_dict(config)

        if "users" in config:
            if not isinstance(config["users"], dict):
                vstatus = False
                vmsg = "User configuration for btmp beacon must be a dictionary."
            else:
                for user in config["users"]:
                    _time_range = config["users"][user].get("time_range", {})
                    vstatus, vmsg = _validate_time_range(_time_range, vstatus, vmsg)

            if not vstatus:
                return vstatus, vmsg

        if "groups" in config:
            if not isinstance(config["groups"], dict):
                vstatus = False
                vmsg = "Group configuration for btmp beacon must be a dictionary."
            else:
                for group in config["groups"]:
                    _time_range = config["groups"][group].get("time_range", {})
                    vstatus, vmsg = _validate_time_range(_time_range, vstatus, vmsg)
            if not vstatus:
                return vstatus, vmsg

        if "defaults" in config:
            if not isinstance(config["defaults"], dict):
                vstatus = False
                vmsg = "Defaults configuration for btmp beacon must be a dictionary."
            else:
                _time_range = config["defaults"].get("time_range", {})
                vstatus, vmsg = _validate_time_range(_time_range, vstatus, vmsg)
            if not vstatus:
                return vstatus, vmsg

    return vstatus, vmsg


def beacon(config):
    """
    Read the last btmp file and return information on the failed logins
    """
    ret = []

    users = {}
    groups = {}
    defaults = None

    for config_item in config:
        if "users" in config_item:
            users = config_item["users"]

        if "groups" in config_item:
            groups = config_item["groups"]

        if "defaults" in config_item:
            defaults = config_item["defaults"]

    with salt.utils.files.fopen(BTMP, "rb") as fp_:
        loc = __context__.get(LOC_KEY, 0)
        if loc == 0:
            fp_.seek(0, 2)
            __context__[LOC_KEY] = fp_.tell()
            return ret
        else:
            fp_.seek(loc)
        while True:
            now = datetime.datetime.now()
            raw = fp_.read(SIZE)
            if len(raw) != SIZE:
                return ret
            __context__[LOC_KEY] = fp_.tell()
            pack = struct.unpack(FMT, raw)
            event = {}
            for ind, field in enumerate(FIELDS):
                event[field] = pack[ind]
                if isinstance(event[field], (str, bytes)):
                    if isinstance(event[field], bytes):
                        event[field] = salt.utils.stringutils.to_unicode(event[field])
                    event[field] = event[field].strip("\x00")

            for group in groups:
                _gather_group_members(group, groups, users)

            if users:
                if event["user"] in users:
                    _user = users[event["user"]]
                    if isinstance(_user, dict) and "time_range" in _user:
                        if _check_time_range(_user["time_range"], now):
                            ret.append(event)
                    else:
                        if defaults and "time_range" in defaults:
                            if _check_time_range(defaults["time_range"], now):
                                ret.append(event)
                        else:
                            ret.append(event)
            else:
                if defaults and "time_range" in defaults:
                    if _check_time_range(defaults["time_range"], now):
                        ret.append(event)
                else:
                    ret.append(event)
    return ret
