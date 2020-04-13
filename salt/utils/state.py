# -*- coding: utf-8 -*-
"""
Utility functions for state functions

.. versionadded:: 2018.3.0
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import copy

import salt.state
from salt.exceptions import CommandExecutionError

# Import Salt libs
from salt.ext import six

_empty = object()


def gen_tag(low):
    """
    Generate the running dict tag string from the low data structure
    """
    return "{0[state]}_|-{0[__id__]}_|-{0[name]}_|-{0[fun]}".format(low)


def search_onfail_requisites(sid, highstate):
    """
    For a particular low chunk, search relevant onfail related states
    """
    onfails = []
    if "_|-" in sid:
        st = salt.state.split_low_tag(sid)
    else:
        st = {"__id__": sid}
    for fstate, fchunks in six.iteritems(highstate):
        if fstate == st["__id__"]:
            continue
        else:
            for mod_, fchunk in six.iteritems(fchunks):
                if not isinstance(mod_, six.string_types) or mod_.startswith("__"):
                    continue
                else:
                    if not isinstance(fchunk, list):
                        continue
                    else:
                        # bydefault onfail will fail, but you can
                        # set onfail_stop: False to prevent the highstate
                        # to stop if you handle it
                        onfail_handled = False
                        for fdata in fchunk:
                            if not isinstance(fdata, dict):
                                continue
                            onfail_handled = fdata.get("onfail_stop", True) is False
                            if onfail_handled:
                                break
                        if not onfail_handled:
                            continue
                        for fdata in fchunk:
                            if not isinstance(fdata, dict):
                                continue
                            for knob, fvalue in six.iteritems(fdata):
                                if knob != "onfail":
                                    continue
                                for freqs in fvalue:
                                    for fmod, fid in six.iteritems(freqs):
                                        if not (
                                            fid == st["__id__"]
                                            and fmod == st.get("state", fmod)
                                        ):
                                            continue
                                        onfails.append((fstate, mod_, fchunk))
    return onfails


def check_onfail_requisites(state_id, state_result, running, highstate):
    """
    When a state fail and is part of a highstate, check
    if there is onfail requisites.
    When we find onfail requisites, we will consider the state failed
    only if at least one of those onfail requisites also failed

    Returns:

        True: if onfail handlers suceeded
        False: if one on those handler failed
        None: if the state does not have onfail requisites

    """
    nret = None
    if state_id and state_result and highstate and isinstance(highstate, dict):
        onfails = search_onfail_requisites(state_id, highstate)
        if onfails:
            for handler in onfails:
                fstate, mod_, fchunk = handler
                for rstateid, rstate in six.iteritems(running):
                    if "_|-" in rstateid:
                        st = salt.state.split_low_tag(rstateid)
                    # in case of simple state, try to guess
                    else:
                        id_ = rstate.get("__id__", rstateid)
                        if not id_:
                            raise ValueError("no state id")
                        st = {"__id__": id_, "state": mod_}
                    if mod_ == st["state"] and fstate == st["__id__"]:
                        ofresult = rstate.get("result", _empty)
                        if ofresult in [False, True]:
                            nret = ofresult
                        if ofresult is False:
                            # as soon as we find an errored onfail, we stop
                            break
                # consider that if we parsed onfailes without changing
                # the ret, that we have failed
                if nret is None:
                    nret = False
    return nret


def check_result(running, recurse=False, highstate=None):
    """
    Check the total return value of the run and determine if the running
    dict has any issues
    """
    if not isinstance(running, dict):
        return False

    if not running:
        return False

    ret = True
    for state_id, state_result in six.iteritems(running):
        expected_type = dict
        # The __extend__ state is a list
        if "__extend__" == state_id:
            expected_type = list
        if not recurse and not isinstance(state_result, expected_type):
            ret = False
        if ret and isinstance(state_result, dict):
            result = state_result.get("result", _empty)
            if result is False:
                ret = False
            # only override return value if we are not already failed
            elif result is _empty and isinstance(state_result, dict) and ret:
                ret = check_result(state_result, recurse=True, highstate=highstate)
        # if we detect a fail, check for onfail requisites
        if not ret:
            # ret can be None in case of no onfail reqs, recast it to bool
            ret = bool(
                check_onfail_requisites(state_id, state_result, running, highstate)
            )
        # return as soon as we got a failure
        if not ret:
            break
    return ret


def merge_subreturn(original_return, sub_return, subkey=None):
    """
    Update an existing state return (`original_return`) in place
    with another state return (`sub_return`), i.e. for a subresource.

    Returns:
        dict: The updated state return.

    The existing state return does not need to have all the required fields,
    as this is meant to be called from the internals of a state function,
    but any existing data will be kept and respected.

    It is important after using this function to check the return value
    to see if it is False, in which case the main state should return.
    Prefer to check `_ret['result']` instead of `ret['result']`,
    as the latter field may not yet be populated.

    Code Example:

    .. code-block:: python
        def state_func(name, config, alarm=None):
            ret = {'name': name, 'comment': '', 'changes': {}}
            if alarm:
                _ret = __states__['subresource.managed'](alarm)
                __utils__['state.merge_subreturn'](ret, _ret)
                if _ret['result'] is False:
                    return ret
    """
    if not subkey:
        subkey = sub_return["name"]

    if sub_return["result"] is False:
        # True or None stay the same
        original_return["result"] = sub_return["result"]

    sub_comment = sub_return["comment"]
    if not isinstance(sub_comment, list):
        sub_comment = [sub_comment]
    original_return.setdefault("comment", [])
    if isinstance(original_return["comment"], list):
        original_return["comment"].extend(sub_comment)
    else:
        if original_return["comment"]:
            # Skip for empty original comments
            original_return["comment"] += "\n"
        original_return["comment"] += "\n".join(sub_comment)

    if sub_return["changes"]:  # changes always exists
        original_return.setdefault("changes", {})
        original_return["changes"][subkey] = sub_return["changes"]

    return original_return


def get_sls_opts(opts, **kwargs):
    """
    Return a copy of the opts for use, optionally load a local config on top
    """
    opts = copy.deepcopy(opts)

    if "localconfig" in kwargs:
        return salt.config.minion_config(kwargs["localconfig"], defaults=opts)

    if "saltenv" in kwargs:
        saltenv = kwargs["saltenv"]
        if saltenv is not None:
            if not isinstance(saltenv, six.string_types):
                saltenv = six.text_type(saltenv)
            if opts["lock_saltenv"] and saltenv != opts["saltenv"]:
                raise CommandExecutionError(
                    "lock_saltenv is enabled, saltenv cannot be changed"
                )
            opts["saltenv"] = kwargs["saltenv"]

    if "pillarenv" in kwargs or opts.get("pillarenv_from_saltenv", False):
        pillarenv = kwargs.get("pillarenv") or kwargs.get("saltenv")
        if pillarenv is not None and not isinstance(pillarenv, six.string_types):
            opts["pillarenv"] = six.text_type(pillarenv)
        else:
            opts["pillarenv"] = pillarenv

    return opts
