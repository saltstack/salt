"""
Network SNMP
============

Manage the SNMP configuration on network devices.

:codeauthor: Mircea Ulinic <ping@mirceaulinic.net>
:maturity:   new
:depends:    napalm
:platform:   unix

Dependencies
------------

- :mod:`napalm snmp management module (salt.modules.napalm_snmp) <salt.modules.napalm_snmp>`

.. versionadded:: 2016.11.0
"""

import logging

import salt.utils.json
import salt.utils.napalm

log = logging.getLogger(__name__)


# ----------------------------------------------------------------------------------------------------------------------
# state properties
# ----------------------------------------------------------------------------------------------------------------------

__virtualname__ = "netsnmp"

_COMMUNITY_MODE_MAP = {
    "read-only": "ro",
    "readonly": "ro",
    "read-write": "rw",
    "write": "rw",
}

# ----------------------------------------------------------------------------------------------------------------------
# global variables
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
# property functions
# ----------------------------------------------------------------------------------------------------------------------


def __virtual__():
    """
    NAPALM library must be installed for this module to work and run in a (proxy) minion.
    """
    return salt.utils.napalm.virtual(__opts__, __virtualname__, __file__)


# ----------------------------------------------------------------------------------------------------------------------
# helper functions -- will not be exported
# ----------------------------------------------------------------------------------------------------------------------


def _ordered_dict_to_dict(config):

    """
    Forced the datatype to dict, in case OrderedDict is used.
    """

    return salt.utils.json.loads(salt.utils.json.dumps(config))


def _expand_config(config, defaults):

    """
    Completed the values of the expected config for the edge cases with the default values.
    """

    defaults.update(config)
    return defaults


def _valid_dict(dic):

    """
    Valid dictionary?
    """

    return isinstance(dic, dict) and len(dic) > 0


def _valid_str(value):

    """
    Valid str?
    """

    return isinstance(value, str) and len(value) > 0


def _community_defaults():

    """
    Returns the default values of a community.
    """

    return {"mode": "ro"}


def _clear_community_details(community_details):

    """
    Clears community details.
    """

    for key in ["acl", "mode"]:
        _str_elem(community_details, key)

    _mode = community_details.get["mode"] = community_details.get("mode").lower()

    if _mode in _COMMUNITY_MODE_MAP.keys():
        community_details["mode"] = _COMMUNITY_MODE_MAP.get(_mode)

    if community_details["mode"] not in ["ro", "rw"]:
        community_details["mode"] = "ro"  # default is read-only

    return community_details


def _str_elem(config, key):

    """
    Re-adds the value of a specific key in the dict, only in case of valid str value.
    """

    _value = config.pop(key, "")
    if _valid_str(_value):
        config[key] = _value


def _check_config(config):

    """
    Checks the desired config and clears interesting details.
    """

    if not _valid_dict(config):
        return True, ""

    _community = config.get("community")
    _community_tmp = {}
    if not _community:
        return False, "Must specify at least a community."
    if _valid_str(_community):
        _community_tmp[_community] = _community_defaults()
    elif isinstance(_community, list):
        # if the user specifies the communities as list
        for _comm in _community:
            if _valid_str(_comm):
                # list of values
                _community_tmp[_comm] = _community_defaults()
                # default mode is read-only
            if _valid_dict(_comm):
                # list of dicts
                for _comm_name, _comm_details in _comm.items():
                    if _valid_str(_comm_name):
                        _community_tmp[_comm_name] = _clear_community_details(
                            _comm_details
                        )
    elif _valid_dict(_community):
        # directly as dict of communities
        # recommended way...
        for _comm_name, _comm_details in _community.items():
            if _valid_str(_comm_name):
                _community_tmp[_comm_name] = _clear_community_details(_comm_details)
    else:
        return False, "Please specify a community or a list of communities."

    if not _valid_dict(_community_tmp):
        return False, "Please specify at least a valid community!"

    config["community"] = _community_tmp

    for key in ["location", "contact", "chassis_id"]:
        # not mandatory, but should be here only if valid
        _str_elem(config, key)

    return True, ""


def _retrieve_device_config():

    """
    Retrieves the SNMP config from the device.
    """

    return __salt__["snmp.config"]()


def _create_diff_action(diff, diff_key, key, value):

    """
    DRY to build diff parts (added, removed, updated).
    """

    if diff_key not in diff.keys():
        diff[diff_key] = {}
    diff[diff_key][key] = value


def _create_diff(diff, fun, key, prev, curr):

    """
    Builds the diff dictionary.
    """

    if not fun(prev):
        _create_diff_action(diff, "added", key, curr)
    elif fun(prev) and not fun(curr):
        _create_diff_action(diff, "removed", key, prev)
    elif not fun(curr):
        _create_diff_action(diff, "updated", key, curr)


def _compute_diff(existing, expected):

    """
    Computes the differences between the existing and the expected SNMP config.
    """

    diff = {}

    for key in ["location", "contact", "chassis_id"]:
        if existing.get(key) != expected.get(key):
            _create_diff(diff, _valid_str, key, existing.get(key), expected.get(key))

    for key in ["community"]:  # for the moment only onen
        if existing.get(key) != expected.get(key):
            _create_diff(diff, _valid_dict, key, existing.get(key), expected.get(key))

    return diff


def _configure(changes):

    """
    Calls the configuration template to apply the configuration changes on the device.
    """

    cfgred = True
    reasons = []
    fun = "update_config"

    for key in ["added", "updated", "removed"]:
        _updated_changes = changes.get(key, {})
        if not _updated_changes:
            continue
        _location = _updated_changes.get("location", "")
        _contact = _updated_changes.get("contact", "")
        _community = _updated_changes.get("community", {})
        _chassis_id = _updated_changes.get("chassis_id", "")
        if key == "removed":
            fun = "remove_config"
        _ret = __salt__["snmp.{fun}".format(fun=fun)](
            location=_location,
            contact=_contact,
            community=_community,
            chassis_id=_chassis_id,
            commit=False,
        )
        cfgred = cfgred and _ret.get("result")
        if not _ret.get("result") and _ret.get("comment"):
            reasons.append(_ret.get("comment"))

    return {"result": cfgred, "comment": "\n".join(reasons) if reasons else ""}


# ----------------------------------------------------------------------------------------------------------------------
# callable functions
# ----------------------------------------------------------------------------------------------------------------------


def managed(name, config=None, defaults=None):

    """
    Configures the SNMP on the device as specified in the SLS file.

    SLS Example:

    .. code-block:: yaml

        snmp_example:
            netsnmp.managed:
                 - config:
                    location: Honolulu, HI, US
                 - defaults:
                    contact: noc@cloudflare.com

    Output example (for the SLS above, e.g. called snmp.sls under /router/):

    .. code-block:: bash

        $ sudo salt edge01.hnl01 state.sls router.snmp test=True
        edge01.hnl01:
        ----------
                  ID: snmp_example
            Function: snmp.managed
              Result: None
             Comment: Testing mode: configuration was not changed!
             Started: 13:29:06.872363
            Duration: 920.466 ms
             Changes:
                      ----------
                      added:
                          ----------
                          chassis_id:
                              None
                          contact:
                              noc@cloudflare.com
                          location:
                              Honolulu, HI, US

        Summary for edge01.hnl01
        ------------
        Succeeded: 1 (unchanged=1, changed=1)
        Failed:    0
        ------------
        Total states run:     1
        Total run time: 920.466 ms
    """

    result = False
    comment = ""
    changes = {}

    ret = {"name": name, "changes": changes, "result": result, "comment": comment}

    # make sure we're working only with dict
    config = _ordered_dict_to_dict(config)
    defaults = _ordered_dict_to_dict(defaults)

    expected_config = _expand_config(config, defaults)
    if not isinstance(expected_config, dict):
        ret["comment"] = "User provided an empty SNMP config!"
        return ret
    valid, message = _check_config(expected_config)

    if not valid:  # check and clean
        ret["comment"] = "Please provide a valid configuration: {error}".format(
            error=message
        )
        return ret

    # ----- Retrieve existing users configuration and determine differences ------------------------------------------->

    _device_config = _retrieve_device_config()
    if not _device_config.get("result"):
        ret["comment"] = "Cannot retrieve SNMP config from the device: {reason}".format(
            reason=_device_config.get("comment")
        )
        return ret

    device_config = _device_config.get("out", {})

    if device_config == expected_config:
        ret.update({"comment": "SNMP already configured as needed.", "result": True})
        return ret

    diff = _compute_diff(device_config, expected_config)

    changes.update(diff)

    ret.update({"changes": changes})

    if __opts__["test"] is True:
        ret.update(
            {"result": None, "comment": "Testing mode: configuration was not changed!"}
        )
        return ret

    # <---- Retrieve existing NTP peers and determine peers to be added/removed --------------------------------------->

    # ----- Call _set_users and _delete_users as needed ------------------------------------------------------->

    expected_config_change = False
    result = True

    if diff:
        _configured = _configure(diff)
        if _configured.get("result"):
            expected_config_change = True
        else:  # something went wrong...
            result = False
            comment = (
                "Cannot push new SNMP config: \n{reason}".format(
                    reason=_configured.get("comment")
                )
                + comment
            )

    if expected_config_change:
        result, comment = __salt__["net.config_control"]()

    # <---- Call _set_users and _delete_users as needed --------------------------------------------------------

    ret.update({"result": result, "comment": comment})

    return ret
