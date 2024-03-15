"""
Beacon to fire events at login of users as registered in the wtmp file

.. versionadded:: 2015.5.0


Example Configuration
=====================

.. code-block:: yaml

    # Fire events on all logins
    beacons:
      wtmp: []

    # Matching on user name, using a default time range
    beacons:
      wtmp:
        - users:
            gareth:
        - defaults:
            time_range:
                start: '8am'
                end: '4pm'

    # Matching on user name, overriding the default time range
    beacons:
      wtmp:
        - users:
            gareth:
                time_range:
                    start: '7am'
                    end: '3pm'
        - defaults:
            time_range:
                start: '8am'
                end: '4pm'

    # Matching on group name, overriding the default time range
    beacons:
      wtmp:
        - groups:
            users:
                time_range:
                    start: '7am'
                    end: '3pm'
        - defaults:
            time_range:
                start: '8am'
                end: '4pm'


How to Tell What An Event Means
===============================

In the events that this beacon fires, a type of ``7`` denotes a login, while a
type of ``8`` denotes a logout. These values correspond to the ``ut_type``
value from a wtmp/utmp event (see the ``wtmp`` manpage for more information).
In the extremely unlikely case that your platform uses different values, they
can be overridden using a ``ut_type`` key in the beacon configuration:

.. code-block:: yaml

    beacons:
      wtmp:
        - ut_type:
            login: 9
            logout: 10

This beacon's events include an ``action`` key which will be either ``login``
or ``logout`` depending on the event type.

.. versionchanged:: 2019.2.0
    ``action`` key added to beacon event, and ``ut_type`` config parameter
    added.


Use Case: Posting Login/Logout Events to Slack
==============================================

This can be done using the following reactor SLS:

.. code-block:: jinja

    report-wtmp:
      runner.salt.cmd:
        - args:
          - fun: slack.post_message
          - channel: mychannel      # Slack channel
          - from_name: someuser     # Slack user
          - message: "{{ data.get('action', 'Unknown event') | capitalize }} from `{{ data.get('user', '') or 'unknown user' }}` on `{{ data['id'] }}`"

Match the event like so in the master config file:

.. code-block:: yaml

    reactor:

      - 'salt/beacon/*/wtmp/':
        - salt://reactor/wtmp.sls

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

import salt.utils.beacons
import salt.utils.files
import salt.utils.stringutils

__virtualname__ = "wtmp"
WTMP = "/var/log/wtmp"
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
LOC_KEY = "wtmp.loc"
TTY_KEY_PREFIX = "wtmp.tty."
LOGIN_TYPE = 7
LOGOUT_TYPE = 8

log = logging.getLogger(__name__)

try:
    import dateutil.parser as dateutil_parser

    _TIME_SUPPORTED = True
except ImportError:
    _TIME_SUPPORTED = False


def __virtual__():
    if os.path.isfile(WTMP):
        return __virtualname__
    err_msg = f"{WTMP} does not exist."
    log.error("Unable to load %s beacon: %s", __virtualname__, err_msg)
    return False, err_msg


def _validate_time_range(trange, status, msg):
    """
    Check time range
    """
    # If trange is empty, just return the current status & msg
    if not trange:
        return status, msg

    if not isinstance(trange, dict):
        status = False
        msg = "The time_range parameter for wtmp beacon must be a dictionary."

    if not all(k in trange for k in ("start", "end")):
        status = False
        msg = (
            "The time_range parameter for wtmp beacon must contain start & end options."
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

    # Configuration for wtmp beacon should be a list of dicts
    if not isinstance(config, list):
        vstatus = False
        vmsg = "Configuration for wtmp beacon must be a list."
    else:
        config = salt.utils.beacons.list_to_dict(config)

        if "users" in config:
            if not isinstance(config["users"], dict):
                vstatus = False
                vmsg = "User configuration for wtmp beacon must be a dictionary."
            else:
                for user in config["users"]:
                    _time_range = config["users"][user].get("time_range", {})
                    vstatus, vmsg = _validate_time_range(_time_range, vstatus, vmsg)

            if not vstatus:
                return vstatus, vmsg

        if "groups" in config:
            if not isinstance(config["groups"], dict):
                vstatus = False
                vmsg = "Group configuration for wtmp beacon must be a dictionary."
            else:
                for group in config["groups"]:
                    _time_range = config["groups"][group].get("time_range", {})
                    vstatus, vmsg = _validate_time_range(_time_range, vstatus, vmsg)
            if not vstatus:
                return vstatus, vmsg

        if "defaults" in config:
            if not isinstance(config["defaults"], dict):
                vstatus = False
                vmsg = "Defaults configuration for wtmp beacon must be a dictionary."
            else:
                _time_range = config["defaults"].get("time_range", {})
                vstatus, vmsg = _validate_time_range(_time_range, vstatus, vmsg)
            if not vstatus:
                return vstatus, vmsg

    return vstatus, vmsg


def beacon(config):
    """
    Read the last wtmp file and return information on the logins
    """
    ret = []

    users = {}
    groups = {}
    defaults = None

    login_type = LOGIN_TYPE
    logout_type = LOGOUT_TYPE

    for config_item in config:
        if "users" in config_item:
            users = config_item["users"]

        if "groups" in config_item:
            groups = config_item["groups"]

        if "defaults" in config_item:
            defaults = config_item["defaults"]

        if config_item == "ut_type":
            try:
                login_type = config_item["ut_type"]["login"]
            except KeyError:
                pass
            try:
                logout_type = config_item["ut_type"]["logout"]
            except KeyError:
                pass

    with salt.utils.files.fopen(WTMP, "rb") as fp_:
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

            if event["type"] == login_type:
                event["action"] = "login"
                # Store the tty to identify the logout event
                __context__["{}{}".format(TTY_KEY_PREFIX, event["line"])] = event[
                    "user"
                ]
            elif event["type"] == logout_type:
                event["action"] = "logout"
                try:
                    event["user"] = __context__.pop(
                        "{}{}".format(TTY_KEY_PREFIX, event["line"])
                    )
                except KeyError:
                    pass

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
