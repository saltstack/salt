"""
Interface to Red Hat tuned-adm module

:maintainer:    Syed Ali <alicsyed@gmail.com>
:maturity:      new
:depends:       cmd.run
:platform:      Linux
"""

import salt.exceptions
from salt.modules.tuned import TUNED_OFF_RETURN_NAME


def profile(name):
    """
    This state module allows you to modify system tuned parameters

    Example tuned.sls file to set profile to virtual-guest

    tuned:
      tuned.profile
        - name: virtual-guest

    name
        tuned profile name to set the system to

    To see a valid list of states call execution module:
        :py:func:`tuned.list <salt.modules.tuned.list_>`
    """

    # create data-structure to return with default value
    ret = {"name": "", "changes": {}, "result": False, "comment": ""}

    ret[name] = name
    profile = name

    # get the current state of tuned-adm
    current_state_dict = __salt__["tuned.active"]()

    # Off is returned as retcode 1, stdout == TUNED_OFF_RETURN_NAME
    # any other type of error will be returned here
    if (
        current_state_dict["retcode"] != 0
        and current_state_dict["stdout"] != TUNED_OFF_RETURN_NAME
    ):
        ret["comment"] = current_state_dict["stderr"]
        return ret

    # if current state is same as requested state, return without doing much
    if current_state_dict["retcode"] == 0 and profile == current_state_dict["stdout"]:
        ret["result"] = True
        ret["comment"] = "System already in the correct state"
        return ret

    # test mode
    if __opts__["test"] is True:
        # Only perform the valid profile test if it is a test,
        #   tuned-adm command will fail and return message
        valid_profiles = __salt__["tuned.list"]()
        if profile not in valid_profiles:
            raise salt.exceptions.SaltInvocationError("Invalid Profile Name")
        ret["comment"] = 'The state of "{}" will be changed.'.format(
            current_state_dict["stdout"]
        )
        ret["changes"] = {
            "old": current_state_dict["stdout"],
            "new": f"Profile will be set to {profile}",
        }
        # return None when testing
        ret["result"] = None
        return ret

    # we come to this stage if current state was determined and is different that requested state
    # we there have to set the new state request
    new_state_dict = __salt__["tuned.profile"](profile)

    if new_state_dict["retcode"] != 0:
        ret["comment"] = new_state_dict["stderr"]
    else:
        # create the comment data structure
        ret["comment"] = f'Tunings changed to "{profile}"'
        # add the changes specifics
        ret["changes"] = {
            "old": current_state_dict["stdout"],
            "new": new_state_dict["stdout"],
        }
        ret["result"] = True

    # return with the dictionary data structure
    return ret


def off(name=None):
    """

    Turns 'tuned' off.
    Example tuned.sls file for turning tuned off:

    tuned:
      tuned.off: []


    To see a valid list of states call execution module:
        :py:func:`tuned.list <salt.modules.tuned.list_>`
    """

    # create data-structure to return with default value
    ret = {"name": "off", "changes": {}, "result": False, "comment": "off"}

    # check the current state of tuned
    current_state_dict = __salt__["tuned.active"]()

    # Off is returned as retcode 1, stdout == TUNED_OFF_RETURN_NAME
    if current_state_dict["retcode"] != 0:
        if current_state_dict["stdout"] == TUNED_OFF_RETURN_NAME:
            ret["result"] = True
            ret["comment"] = "System already in the correct state"
            return ret
        ret["comment"] = current_state_dict["stderr"]
        return ret

    # test mode
    if __opts__["test"] is True:
        ret["comment"] = 'The state of "{}" will be turned off.'.format(
            current_state_dict["stdout"]
        )
        ret["changes"] = {
            "old": current_state_dict["stdout"],
            "new": "Profile will be set to off",
        }
        # return None when testing
        ret["result"] = None
        return ret

    # execute the tuned.off module
    off_result_dict = __salt__["tuned.off"]()

    if off_result_dict["retcode"] != 0:
        ret["comment"] = off_result_dict["stderr"]
    else:
        ret["comment"] = "Tunings have been turned off"
        ret["changes"] = {
            "old": current_state_dict["stdout"],
            "new": "off",
        }
        ret["result"] = True

    # return with the dictionary data structure
    return ret
