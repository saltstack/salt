"""
Utility functions for state functions

.. versionadded:: 2018.3.0
"""

import copy
import logging
import os

import salt.payload
import salt.state
import salt.utils.files
import salt.utils.process
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

_empty = object()


def acquire_queue_lock(opts):
    """
    Acquire the state queue lock
    """
    lock_path = os.path.join(opts["cachedir"], "minion_queue.lock")
    # Use a large timeout to mimic infinite blocking of FileLock, as wait_lock defaults to 5s
    return salt.utils.files.wait_lock(lock_path, lock_fn=lock_path, timeout=86400)


def acquire_async_queue_lock(opts):
    """
    Acquire the job queue lock asynchronously
    """
    lock_path = os.path.join(opts["cachedir"], "minion_queue.lock")
    # Use timeout that allows queue processing to work but doesn't hang tests
    return salt.utils.files.await_lock(
        lock_path, lock_fn=lock_path, timeout=5.0, sleep=0.1
    )


import errno


def get_active_states(opts):
    """
    Return a list of active state jobs from the proc directory.
    Unlike saltutil.is_running, this does NOT filter out the current process.
    """
    ret = []
    proc_dir = os.path.join(opts["cachedir"], "proc")
    if not os.path.isdir(proc_dir):
        return ret

    try:
        proc_files = os.listdir(proc_dir)
    except OSError as exc:
        if exc.errno in (errno.EMFILE, errno.ENFILE, errno.ENOMEM):
            # System is resource constrained, we cannot reliably determine active states.
            # Re-raising ensures we don't assume "no jobs" and cause a storm.
            raise
        log.error("Unable to list proc directory %s: %s", proc_dir, exc)
        return ret

    for fn_ in proc_files:
        path = os.path.join(proc_dir, fn_)
        try:
            with salt.utils.files.fopen(path, "rb") as fp_:
                buf = fp_.read()

            if not buf:
                continue

            try:
                data = salt.payload.loads(buf)
            except NameError:
                # msgpack error
                continue

            if not isinstance(data, dict):
                continue

            pid = data.get("pid")
            if not pid:
                continue

            if salt.utils.process.os_is_running(pid):
                if data.get("fun", "").startswith("state."):
                    ret.append(data)

        except (OSError, ValueError) as exc:
            # If we run out of FDs while reading a specific file, stop and raise.
            if isinstance(exc, OSError) and exc.errno in (errno.EMFILE, errno.ENFILE):
                raise
            continue

    return ret


def check_prior_running_states(opts, jid, active_jobs):
    """
    Check for prior running states that would block the execution of the current job.
    Returns a list of blocking jobs.
    """
    ret = []
    # Work on a copy to avoid side effects
    active_jobs = list(active_jobs)

    # Check for queued jobs in BOTH state_queue and job_queue
    # Also check for 'running_' files to close the "Invisible Gap"
    for queue_name in ("state_queue", "job_queue"):
        queue_dir = os.path.join(opts["cachedir"], queue_name)
        if not os.path.exists(queue_dir):
            continue

        try:
            for fn in os.listdir(queue_dir):
                # We check for both 'queued_' and 'running_'
                # 'running_' files are those that have been popped from the queue
                # but haven't yet written their PID to the proc directory.
                if (
                    fn.startswith("queued_") or fn.startswith("running_")
                ) and fn.endswith(".p"):
                    # fn is <prefix>_<timestamp>_<jid>.p
                    parts = fn[:-2].split("_")
                    if len(parts) >= 3:
                        # The JID is the third part
                        job_jid = parts[2]
                        # If the JID itself contains underscores (uncommon but possible),
                        # it might be split further. Re-join just in case.
                        if len(parts) > 3:
                            job_jid = "_".join(parts[2:])

                        # We use PID 0 to indicate it's not a real process yet
                        active_jobs.append(
                            {"jid": job_jid, "fun": "state.apply", "pid": 0}
                        )
        except OSError as exc:
            log.error("Unable to list queue directory %s: %s", queue_dir, exc)

    if active_jobs:
        # log.debug("check_prior_running_states: checking JID %s against active jobs: %s", jid, active_jobs)
        pass

    for data in active_jobs:
        data_jid = data.get("jid")
        if data_jid is None:
            continue

        if jid is None:
            # If no JID is provided (e.g. local call without JID), assume current job is newer
            # than any running job, so any running job is a "prior" job.
            ret.append(data)
            continue

        try:
            # Explicitly ignore the current JID to prevent self-queueing loops
            if str(data_jid) == str(jid):
                continue

            # Only block if the other job is OLDER than the current one.
            # This ensures FIFO ordering and prevents deadlocks where two
            # jobs block each other.
            # Salt JIDs are usually timestamp-based strings (e.g. 20230524100000)
            # which sort correctly as strings OR ints.
            if str(data_jid) < str(jid):
                ret.append(data)
        except (ValueError, TypeError):
            continue
    return ret


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
    for fstate, fchunks in highstate.items():
        if fstate == st["__id__"]:
            continue
        else:
            for mod_, fchunk in fchunks.items():
                if not isinstance(mod_, str) or mod_.startswith("__"):
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
                            for knob, fvalue in fdata.items():
                                if knob != "onfail":
                                    continue
                                for freqs in fvalue:
                                    for fmod, fid in freqs.items():
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

        True: if onfail handlers succeeded
        False: if one on those handler failed
        None: if the state does not have onfail requisites

    """
    nret = None
    if state_id and state_result and highstate and isinstance(highstate, dict):
        onfails = search_onfail_requisites(state_id, highstate)
        if onfails:
            for handler in onfails:
                fstate, mod_, fchunk = handler
                for rstateid, rstate in running.items():
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
    for state_id, state_result in running.items():
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
            if not isinstance(saltenv, str):
                saltenv = str(saltenv)
            if opts["lock_saltenv"] and saltenv != opts["saltenv"]:
                raise CommandExecutionError(
                    "lock_saltenv is enabled, saltenv cannot be changed"
                )
            opts["saltenv"] = kwargs["saltenv"]

    if "pillarenv" in kwargs or opts.get("pillarenv_from_saltenv", False):
        pillarenv = kwargs.get("pillarenv") or kwargs.get("saltenv")
        if pillarenv is not None and not isinstance(pillarenv, str):
            opts["pillarenv"] = str(pillarenv)
        else:
            opts["pillarenv"] = pillarenv

    return opts
