# -*- coding: utf-8 -*-
"""
Create ssh executor system
"""
from __future__ import absolute_import, print_function

import logging

# Import python libs
import os
import time

import salt.client.ssh.shell
import salt.client.ssh.state
import salt.loader
import salt.log
import salt.minion
import salt.roster
import salt.state
import salt.utils.args
import salt.utils.data
import salt.utils.files
import salt.utils.hashutils
import salt.utils.jid
import salt.utils.json
import salt.utils.platform
import salt.utils.state
import salt.utils.thin

# Import salt libs
from salt.exceptions import SaltInvocationError

# Import 3rd-party libs
from salt.ext import six

__func_alias__ = {"apply_": "apply"}
log = logging.getLogger(__name__)


def _ssh_state(chunks, st_kwargs, kwargs, test=False):
    """
    Function to run a state with the given chunk via salt-ssh
    """
    file_refs = salt.client.ssh.state.lowstate_file_refs(
        chunks,
        _merge_extra_filerefs(
            kwargs.get("extra_filerefs", ""), __opts__.get("extra_filerefs", "")
        ),
    )
    # Create the tar containing the state pkg and relevant files.
    trans_tar = salt.client.ssh.state.prep_trans_tar(
        __context__["fileclient"], chunks, file_refs, __pillar__, st_kwargs["id_"]
    )
    trans_tar_sum = salt.utils.hashutils.get_hash(trans_tar, __opts__["hash_type"])
    cmd = "state.pkg {0}/salt_state.tgz test={1} pkg_sum={2} hash_type={3}".format(
        __opts__["thin_dir"], test, trans_tar_sum, __opts__["hash_type"]
    )
    single = salt.client.ssh.Single(
        __opts__,
        cmd,
        fsclient=__context__["fileclient"],
        minion_opts=__salt__.minion_opts,
        **st_kwargs
    )
    single.shell.send(trans_tar, "{0}/salt_state.tgz".format(__opts__["thin_dir"]))
    stdout, stderr, _ = single.cmd_block()

    # Clean up our tar
    try:
        os.remove(trans_tar)
    except (OSError, IOError):
        pass

    # Read in the JSON data and return the data structure
    try:
        return salt.utils.data.decode(
            salt.utils.json.loads(stdout, object_hook=salt.utils.data.encode_dict)
        )
    except Exception as e:  # pylint: disable=broad-except
        log.error("JSON Render failed for: %s\n%s", stdout, stderr)
        log.error(str(e))

    # If for some reason the json load fails, return the stdout
    return salt.utils.data.decode(stdout)


def _set_retcode(ret, highstate=None):
    """
    Set the return code based on the data back from the state system
    """

    # Set default retcode to 0
    __context__["retcode"] = 0

    if isinstance(ret, list):
        __context__["retcode"] = 1
        return
    if not salt.utils.state.check_result(ret, highstate=highstate):

        __context__["retcode"] = 2


def _check_pillar(kwargs, pillar=None):
    """
    Check the pillar for errors, refuse to run the state if there are errors
    in the pillar and return the pillar errors
    """
    if kwargs.get("force"):
        return True
    pillar_dict = pillar if pillar is not None else __pillar__
    if "_errors" in pillar_dict:
        return False
    return True


def _wait(jid):
    """
    Wait for all previously started state jobs to finish running
    """
    if jid is None:
        jid = salt.utils.jid.gen_jid(__opts__)
    states = _prior_running_states(jid)
    while states:
        time.sleep(1)
        states = _prior_running_states(jid)


def _merge_extra_filerefs(*args):
    """
    Takes a list of filerefs and returns a merged list
    """
    ret = []
    for arg in args:
        if isinstance(arg, six.string_types):
            if arg:
                ret.extend(arg.split(","))
        elif isinstance(arg, list):
            if arg:
                ret.extend(arg)
    return ",".join(ret)


def _cleanup_slsmod_low_data(low_data):
    """
    Set "slsmod" keys to None to make
    low_data JSON serializable
    """
    for i in low_data:
        if "slsmod" in i:
            i["slsmod"] = None


def _cleanup_slsmod_high_data(high_data):
    """
    Set "slsmod" keys to None to make
    high_data JSON serializable
    """
    for i in six.itervalues(high_data):
        if "stateconf" in i:
            stateconf_data = i["stateconf"][1]
            if "slsmod" in stateconf_data:
                stateconf_data["slsmod"] = None


def _parse_mods(mods):
    """
    Parse modules.
    """
    if isinstance(mods, six.string_types):
        mods = [item.strip() for item in mods.split(",") if item.strip()]

    return mods


def sls(mods, saltenv="base", test=None, exclude=None, **kwargs):
    """
    Create the seed file for a state.sls run
    """
    st_kwargs = __salt__.kwargs
    __opts__["grains"] = __grains__
    __pillar__.update(kwargs.get("pillar", {}))
    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)
    st_ = salt.client.ssh.state.SSHHighState(
        opts, __pillar__, __salt__, __context__["fileclient"]
    )
    st_.push_active()
    mods = _parse_mods(mods)
    high_data, errors = st_.render_highstate({saltenv: mods})
    if exclude:
        if isinstance(exclude, six.string_types):
            exclude = exclude.split(",")
        if "__exclude__" in high_data:
            high_data["__exclude__"].extend(exclude)
        else:
            high_data["__exclude__"] = exclude
    high_data, ext_errors = st_.state.reconcile_extend(high_data)
    errors += ext_errors
    errors += st_.state.verify_high(high_data)
    if errors:
        return errors
    high_data, req_in_errors = st_.state.requisite_in(high_data)
    errors += req_in_errors
    high_data = st_.state.apply_exclude(high_data)
    # Verify that the high data is structurally sound
    if errors:
        return errors
    # Compile and verify the raw chunks
    chunks = st_.state.compile_high_data(high_data)
    file_refs = salt.client.ssh.state.lowstate_file_refs(
        chunks,
        _merge_extra_filerefs(
            kwargs.get("extra_filerefs", ""), opts.get("extra_filerefs", "")
        ),
    )

    roster = salt.roster.Roster(opts, opts.get("roster", "flat"))
    roster_grains = roster.opts["grains"]

    # Create the tar containing the state pkg and relevant files.
    _cleanup_slsmod_low_data(chunks)
    trans_tar = salt.client.ssh.state.prep_trans_tar(
        __context__["fileclient"],
        chunks,
        file_refs,
        __pillar__,
        st_kwargs["id_"],
        roster_grains,
    )
    trans_tar_sum = salt.utils.hashutils.get_hash(trans_tar, opts["hash_type"])
    cmd = "state.pkg {0}/salt_state.tgz test={1} pkg_sum={2} hash_type={3}".format(
        opts["thin_dir"], test, trans_tar_sum, opts["hash_type"]
    )
    single = salt.client.ssh.Single(
        opts,
        cmd,
        fsclient=__context__["fileclient"],
        minion_opts=__salt__.minion_opts,
        **st_kwargs
    )
    single.shell.send(trans_tar, "{0}/salt_state.tgz".format(opts["thin_dir"]))
    stdout, stderr, _ = single.cmd_block()

    # Clean up our tar
    try:
        os.remove(trans_tar)
    except (OSError, IOError):
        pass

    # Read in the JSON data and return the data structure
    try:
        return salt.utils.json.loads(stdout)
    except Exception as e:  # pylint: disable=broad-except
        log.error("JSON Render failed for: %s\n%s", stdout, stderr)
        log.error(six.text_type(e))

    # If for some reason the json load fails, return the stdout
    return stdout


def running(concurrent=False):
    """
    Return a list of strings that contain state return data if a state function
    is already running. This function is used to prevent multiple state calls
    from being run at the same time.

    CLI Example:

    .. code-block:: bash

        salt '*' state.running
    """
    ret = []
    if concurrent:
        return ret
    active = __salt__["saltutil.is_running"]("state.*")
    for data in active:
        err = (
            'The function "{0}" is running as PID {1} and was started at '
            "{2} with jid {3}"
        ).format(
            data["fun"],
            data["pid"],
            salt.utils.jid.jid_to_time(data["jid"]),
            data["jid"],
        )
        ret.append(err)
    return ret


def _prior_running_states(jid):
    """
    Return a list of dicts of prior calls to state functions.  This function is
    used to queue state calls so only one is run at a time.
    """

    ret = []
    active = __salt__["saltutil.is_running"]("state.*")
    for data in active:
        try:
            data_jid = int(data["jid"])
        except ValueError:
            continue
        if data_jid < int(jid):
            ret.append(data)
    return ret


def _check_queue(queue, kwargs):
    """
    Utility function to queue the state run if requested
    and to check for conflicts in currently running states
    """
    if queue:
        _wait(kwargs.get("__pub_jid"))
    else:
        conflict = running(concurrent=kwargs.get("concurrent", False))
        if conflict:
            __context__["retcode"] = 1
            return conflict


def _get_initial_pillar(opts):
    return (
        __pillar__
        if __opts__["__cli"] == "salt-call"
        and opts["pillarenv"] == __opts__["pillarenv"]
        else None
    )


def low(data, **kwargs):
    """
    Execute a single low data call
    This function is mostly intended for testing the state system

    CLI Example:

    .. code-block:: bash

        salt '*' state.low '{"state": "pkg", "fun": "installed", "name": "vi"}'
    """
    st_kwargs = __salt__.kwargs
    __opts__["grains"] = __grains__
    chunks = [data]
    st_ = salt.client.ssh.state.SSHHighState(
        __opts__, __pillar__, __salt__, __context__["fileclient"]
    )
    for chunk in chunks:
        chunk["__id__"] = chunk["name"] if not chunk.get("__id__") else chunk["__id__"]
    err = st_.state.verify_data(data)
    if err:
        return err
    file_refs = salt.client.ssh.state.lowstate_file_refs(
        chunks,
        _merge_extra_filerefs(
            kwargs.get("extra_filerefs", ""), __opts__.get("extra_filerefs", "")
        ),
    )
    roster = salt.roster.Roster(__opts__, __opts__.get("roster", "flat"))
    roster_grains = roster.opts["grains"]

    # Create the tar containing the state pkg and relevant files.
    trans_tar = salt.client.ssh.state.prep_trans_tar(
        __context__["fileclient"],
        chunks,
        file_refs,
        __pillar__,
        st_kwargs["id_"],
        roster_grains,
    )
    trans_tar_sum = salt.utils.hashutils.get_hash(trans_tar, __opts__["hash_type"])
    cmd = "state.pkg {0}/salt_state.tgz pkg_sum={1} hash_type={2}".format(
        __opts__["thin_dir"], trans_tar_sum, __opts__["hash_type"]
    )
    single = salt.client.ssh.Single(
        __opts__,
        cmd,
        fsclient=__context__["fileclient"],
        minion_opts=__salt__.minion_opts,
        **st_kwargs
    )
    single.shell.send(trans_tar, "{0}/salt_state.tgz".format(__opts__["thin_dir"]))
    stdout, stderr, _ = single.cmd_block()

    # Clean up our tar
    try:
        os.remove(trans_tar)
    except (OSError, IOError):
        pass

    # Read in the JSON data and return the data structure
    try:
        return salt.utils.json.loads(stdout)
    except Exception as e:  # pylint: disable=broad-except
        log.error("JSON Render failed for: %s\n%s", stdout, stderr)
        log.error(six.text_type(e))

    # If for some reason the json load fails, return the stdout
    return stdout


def _get_test_value(test=None, **kwargs):
    """
    Determine the correct value for the test flag.
    """
    ret = True
    if test is None:
        if salt.utils.args.test_mode(test=test, **kwargs):
            ret = True
        else:
            ret = __opts__.get("test", None)
    else:
        ret = test
    return ret


def high(data, **kwargs):
    """
    Execute the compound calls stored in a single set of high data
    This function is mostly intended for testing the state system

    CLI Example:

    .. code-block:: bash

        salt '*' state.high '{"vim": {"pkg": ["installed"]}}'
    """
    __pillar__.update(kwargs.get("pillar", {}))
    st_kwargs = __salt__.kwargs
    __opts__["grains"] = __grains__
    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)
    st_ = salt.client.ssh.state.SSHHighState(
        opts, __pillar__, __salt__, __context__["fileclient"]
    )
    st_.push_active()
    chunks = st_.state.compile_high_data(data)
    file_refs = salt.client.ssh.state.lowstate_file_refs(
        chunks,
        _merge_extra_filerefs(
            kwargs.get("extra_filerefs", ""), opts.get("extra_filerefs", "")
        ),
    )

    roster = salt.roster.Roster(opts, opts.get("roster", "flat"))
    roster_grains = roster.opts["grains"]

    # Create the tar containing the state pkg and relevant files.
    _cleanup_slsmod_low_data(chunks)
    trans_tar = salt.client.ssh.state.prep_trans_tar(
        __context__["fileclient"],
        chunks,
        file_refs,
        __pillar__,
        st_kwargs["id_"],
        roster_grains,
    )
    trans_tar_sum = salt.utils.hashutils.get_hash(trans_tar, opts["hash_type"])
    cmd = "state.pkg {0}/salt_state.tgz pkg_sum={1} hash_type={2}".format(
        opts["thin_dir"], trans_tar_sum, opts["hash_type"]
    )
    single = salt.client.ssh.Single(
        opts,
        cmd,
        fsclient=__context__["fileclient"],
        minion_opts=__salt__.minion_opts,
        **st_kwargs
    )
    single.shell.send(trans_tar, "{0}/salt_state.tgz".format(opts["thin_dir"]))
    stdout, stderr, _ = single.cmd_block()

    # Clean up our tar
    try:
        os.remove(trans_tar)
    except (OSError, IOError):
        pass

    # Read in the JSON data and return the data structure
    try:
        return salt.utils.json.loads(stdout)
    except Exception as e:  # pylint: disable=broad-except
        log.error("JSON Render failed for: %s\n%s", stdout, stderr)
        log.error(six.text_type(e))

    # If for some reason the json load fails, return the stdout
    return stdout


def apply_(mods=None, **kwargs):
    """
    .. versionadded:: 2015.5.3

    Apply states! This function will call highstate or state.sls based on the
    arguments passed in, state.apply is intended to be the main gateway for
    all state executions.

    CLI Example:

    .. code-block:: bash

        salt '*' state.apply
        salt '*' state.apply test
        salt '*' state.apply test,pkgs
    """
    if mods:
        return sls(mods, **kwargs)
    return highstate(**kwargs)


def request(mods=None, **kwargs):
    """
    .. versionadded:: 2017.7.3

    Request that the local admin execute a state run via
    `salt-call state.run_request`
    All arguments match state.apply

    CLI Example:

    .. code-block:: bash

        salt '*' state.request
        salt '*' state.request test
        salt '*' state.request test,pkgs
    """
    kwargs["test"] = True
    ret = apply_(mods, **kwargs)
    notify_path = os.path.join(__opts__["cachedir"], "req_state.p")
    serial = salt.payload.Serial(__opts__)
    req = check_request()
    req.update(
        {
            kwargs.get("name", "default"): {
                "test_run": ret,
                "mods": mods,
                "kwargs": kwargs,
            }
        }
    )
    with salt.utils.files.set_umask(0o077):
        try:
            if salt.utils.platform.is_windows():
                # Make sure cache file isn't read-only
                __salt__["cmd.run"]('attrib -R "{0}"'.format(notify_path))
            with salt.utils.files.fopen(notify_path, "w+b") as fp_:
                serial.dump(req, fp_)
        except (IOError, OSError):
            log.error(
                "Unable to write state request file %s. Check permission.", notify_path
            )
    return ret


def check_request(name=None):
    """
    .. versionadded:: 2017.7.3

    Return the state request information, if any

    CLI Example:

    .. code-block:: bash

        salt '*' state.check_request
    """
    notify_path = os.path.join(__opts__["cachedir"], "req_state.p")
    serial = salt.payload.Serial(__opts__)
    if os.path.isfile(notify_path):
        with salt.utils.files.fopen(notify_path, "rb") as fp_:
            # Not sure if this needs to be decoded since it is being returned,
            # and msgpack serialization will encode it to bytes anyway.
            req = serial.load(fp_)
        if name:
            return req[name]
        return req
    return {}


def clear_request(name=None):
    """
    .. versionadded:: 2017.7.3

    Clear out the state execution request without executing it

    CLI Example:

    .. code-block:: bash

        salt '*' state.clear_request
    """
    notify_path = os.path.join(__opts__["cachedir"], "req_state.p")
    serial = salt.payload.Serial(__opts__)
    if not os.path.isfile(notify_path):
        return True
    if not name:
        try:
            os.remove(notify_path)
        except (IOError, OSError):
            pass
    else:
        req = check_request()
        if name in req:
            req.pop(name)
        else:
            return False
        with salt.utils.files.set_umask(0o077):
            try:
                if salt.utils.platform.is_windows():
                    # Make sure cache file isn't read-only
                    __salt__["cmd.run"]('attrib -R "{0}"'.format(notify_path))
                with salt.utils.files.fopen(notify_path, "w+b") as fp_:
                    serial.dump(req, fp_)
            except (IOError, OSError):
                log.error(
                    "Unable to write state request file %s. Check permission.",
                    notify_path,
                )
    return True


def run_request(name="default", **kwargs):
    """
    .. versionadded:: 2017.7.3

    Execute the pending state request

    CLI Example:

    .. code-block:: bash

        salt '*' state.run_request
    """
    req = check_request()
    if name not in req:
        return {}
    n_req = req[name]
    if "mods" not in n_req or "kwargs" not in n_req:
        return {}
    req[name]["kwargs"].update(kwargs)
    if "test" in n_req["kwargs"]:
        n_req["kwargs"].pop("test")
    if req:
        ret = apply_(n_req["mods"], **n_req["kwargs"])
        try:
            os.remove(os.path.join(__opts__["cachedir"], "req_state.p"))
        except (IOError, OSError):
            pass
        return ret
    return {}


def highstate(test=None, **kwargs):
    """
    Retrieve the state data from the salt master for this minion and execute it

    CLI Example:

    .. code-block:: bash

        salt '*' state.highstate

        salt '*' state.highstate exclude=sls_to_exclude
        salt '*' state.highstate exclude="[{'id': 'id_to_exclude'}, {'sls': 'sls_to_exclude'}]"
    """
    __pillar__.update(kwargs.get("pillar", {}))
    st_kwargs = __salt__.kwargs
    __opts__["grains"] = __grains__
    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)
    st_ = salt.client.ssh.state.SSHHighState(
        opts, __pillar__, __salt__, __context__["fileclient"]
    )
    st_.push_active()
    chunks = st_.compile_low_chunks()
    file_refs = salt.client.ssh.state.lowstate_file_refs(
        chunks,
        _merge_extra_filerefs(
            kwargs.get("extra_filerefs", ""), opts.get("extra_filerefs", "")
        ),
    )
    # Check for errors
    for chunk in chunks:
        if not isinstance(chunk, dict):
            __context__["retcode"] = 1
            return chunks

    roster = salt.roster.Roster(opts, opts.get("roster", "flat"))
    roster_grains = roster.opts["grains"]

    # Create the tar containing the state pkg and relevant files.
    _cleanup_slsmod_low_data(chunks)
    trans_tar = salt.client.ssh.state.prep_trans_tar(
        __context__["fileclient"],
        chunks,
        file_refs,
        __pillar__,
        st_kwargs["id_"],
        roster_grains,
    )
    trans_tar_sum = salt.utils.hashutils.get_hash(trans_tar, opts["hash_type"])
    cmd = "state.pkg {0}/salt_state.tgz test={1} pkg_sum={2} hash_type={3}".format(
        opts["thin_dir"], test, trans_tar_sum, opts["hash_type"]
    )
    single = salt.client.ssh.Single(
        opts,
        cmd,
        fsclient=__context__["fileclient"],
        minion_opts=__salt__.minion_opts,
        **st_kwargs
    )
    single.shell.send(trans_tar, "{0}/salt_state.tgz".format(opts["thin_dir"]))
    stdout, stderr, _ = single.cmd_block()

    # Clean up our tar
    try:
        os.remove(trans_tar)
    except (OSError, IOError):
        pass

    # Read in the JSON data and return the data structure
    try:
        return salt.utils.json.loads(stdout)
    except Exception as e:  # pylint: disable=broad-except
        log.error("JSON Render failed for: %s\n%s", stdout, stderr)
        log.error(six.text_type(e))

    # If for some reason the json load fails, return the stdout
    return stdout


def top(topfn, test=None, **kwargs):
    """
    Execute a specific top file instead of the default

    CLI Example:

    .. code-block:: bash

        salt '*' state.top reverse_top.sls
        salt '*' state.top reverse_top.sls exclude=sls_to_exclude
        salt '*' state.top reverse_top.sls exclude="[{'id': 'id_to_exclude'}, {'sls': 'sls_to_exclude'}]"
    """
    __pillar__.update(kwargs.get("pillar", {}))
    st_kwargs = __salt__.kwargs
    __opts__["grains"] = __grains__
    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)
    if salt.utils.args.test_mode(test=test, **kwargs):
        opts["test"] = True
    else:
        opts["test"] = __opts__.get("test", None)
    st_ = salt.client.ssh.state.SSHHighState(
        opts, __pillar__, __salt__, __context__["fileclient"]
    )
    st_.opts["state_top"] = os.path.join("salt://", topfn)
    st_.push_active()
    chunks = st_.compile_low_chunks()
    file_refs = salt.client.ssh.state.lowstate_file_refs(
        chunks,
        _merge_extra_filerefs(
            kwargs.get("extra_filerefs", ""), opts.get("extra_filerefs", "")
        ),
    )

    roster = salt.roster.Roster(opts, opts.get("roster", "flat"))
    roster_grains = roster.opts["grains"]

    # Create the tar containing the state pkg and relevant files.
    _cleanup_slsmod_low_data(chunks)
    trans_tar = salt.client.ssh.state.prep_trans_tar(
        __context__["fileclient"],
        chunks,
        file_refs,
        __pillar__,
        st_kwargs["id_"],
        roster_grains,
    )
    trans_tar_sum = salt.utils.hashutils.get_hash(trans_tar, opts["hash_type"])
    cmd = "state.pkg {0}/salt_state.tgz test={1} pkg_sum={2} hash_type={3}".format(
        opts["thin_dir"], test, trans_tar_sum, opts["hash_type"]
    )
    single = salt.client.ssh.Single(
        opts,
        cmd,
        fsclient=__context__["fileclient"],
        minion_opts=__salt__.minion_opts,
        **st_kwargs
    )
    single.shell.send(trans_tar, "{0}/salt_state.tgz".format(opts["thin_dir"]))
    stdout, stderr, _ = single.cmd_block()

    # Clean up our tar
    try:
        os.remove(trans_tar)
    except (OSError, IOError):
        pass

    # Read in the JSON data and return the data structure
    try:
        return salt.utils.json.loads(stdout)
    except Exception as e:  # pylint: disable=broad-except
        log.error("JSON Render failed for: %s\n%s", stdout, stderr)
        log.error(six.text_type(e))

    # If for some reason the json load fails, return the stdout
    return stdout


def show_highstate(**kwargs):
    """
    Retrieve the highstate data from the salt master and display it

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_highstate
    """
    __opts__["grains"] = __grains__
    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)
    st_ = salt.client.ssh.state.SSHHighState(
        opts, __pillar__, __salt__, __context__["fileclient"]
    )
    st_.push_active()
    chunks = st_.compile_highstate()
    _cleanup_slsmod_high_data(chunks)
    return chunks


def show_lowstate(**kwargs):
    """
    List out the low data that will be applied to this minion

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_lowstate
    """
    __opts__["grains"] = __grains__
    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)
    st_ = salt.client.ssh.state.SSHHighState(
        opts, __pillar__, __salt__, __context__["fileclient"]
    )
    st_.push_active()
    chunks = st_.compile_low_chunks()
    _cleanup_slsmod_low_data(chunks)
    return chunks


def sls_id(id_, mods, test=None, queue=False, **kwargs):
    """
    Call a single ID from the named module(s) and handle all requisites

    The state ID comes *before* the module ID(s) on the command line.

    id
        ID to call

    mods
        Comma-delimited list of modules to search for given id and its requisites

    .. versionadded:: 2017.7.3

    saltenv : base
        Specify a salt fileserver environment to be used when applying states

    pillarenv
        Specify a Pillar environment to be used when applying states. This
        can also be set in the minion config file using the
        :conf_minion:`pillarenv` option. When neither the
        :conf_minion:`pillarenv` minion config option nor this CLI argument is
        used, all Pillar environments will be merged together.

    CLI Example:

    .. code-block:: bash

        salt '*' state.sls_id my_state my_module

        salt '*' state.sls_id my_state my_module,a_common_module
    """
    st_kwargs = __salt__.kwargs
    conflict = _check_queue(queue, kwargs)
    if conflict is not None:
        return conflict
    orig_test = __opts__.get("test", None)
    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)
    opts["test"] = _get_test_value(test, **kwargs)

    # Since this is running a specific ID within a specific SLS file, fall back
    # to the 'base' saltenv if none is configured and none was passed.
    if opts["saltenv"] is None:
        opts["saltenv"] = "base"

    st_ = salt.client.ssh.state.SSHHighState(
        __opts__, __pillar__, __salt__, __context__["fileclient"]
    )

    if not _check_pillar(kwargs, st_.opts["pillar"]):
        __context__["retcode"] = 5
        err = ["Pillar failed to render with the following messages:"]
        err += __pillar__["_errors"]
        return err

    split_mods = _parse_mods(mods)
    st_.push_active()
    high_, errors = st_.render_highstate({opts["saltenv"]: split_mods})
    errors += st_.state.verify_high(high_)
    # Apply requisites to high data
    high_, req_in_errors = st_.state.requisite_in(high_)
    if req_in_errors:
        # This if statement should not be necessary if there were no errors,
        # but it is required to get the unit tests to pass.
        errors.extend(req_in_errors)
    if errors:
        __context__["retcode"] = 1
        return errors
    chunks = st_.state.compile_high_data(high_)
    chunk = [x for x in chunks if x.get("__id__", "") == id_]

    if not chunk:
        raise SaltInvocationError(
            "No matches for ID '{0}' found in SLS '{1}' within saltenv "
            "'{2}'".format(id_, mods, opts["saltenv"])
        )

    ret = _ssh_state(chunk, st_kwargs, kwargs, test=test)
    _set_retcode(ret, highstate=highstate)
    # Work around Windows multiprocessing bug, set __opts__['test'] back to
    # value from before this function was run.
    __opts__["test"] = orig_test
    return ret


def show_sls(mods, saltenv="base", test=None, **kwargs):
    """
    Display the state data from a specific sls or list of sls files on the
    master

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_sls core,edit.vim dev
    """
    __pillar__.update(kwargs.get("pillar", {}))
    __opts__["grains"] = __grains__
    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)
    if salt.utils.args.test_mode(test=test, **kwargs):
        opts["test"] = True
    else:
        opts["test"] = __opts__.get("test", None)
    st_ = salt.client.ssh.state.SSHHighState(
        opts, __pillar__, __salt__, __context__["fileclient"]
    )
    st_.push_active()
    mods = _parse_mods(mods)
    high_data, errors = st_.render_highstate({saltenv: mods})
    high_data, ext_errors = st_.state.reconcile_extend(high_data)
    errors += ext_errors
    errors += st_.state.verify_high(high_data)
    if errors:
        return errors
    high_data, req_in_errors = st_.state.requisite_in(high_data)
    errors += req_in_errors
    high_data = st_.state.apply_exclude(high_data)
    # Verify that the high data is structurally sound
    if errors:
        return errors
    _cleanup_slsmod_high_data(high_data)
    return high_data


def show_low_sls(mods, saltenv="base", test=None, **kwargs):
    """
    Display the low state data from a specific sls or list of sls files on the
    master.

    .. versionadded:: 2016.3.2

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_sls core,edit.vim dev
    """
    __pillar__.update(kwargs.get("pillar", {}))
    __opts__["grains"] = __grains__

    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)
    if salt.utils.args.test_mode(test=test, **kwargs):
        opts["test"] = True
    else:
        opts["test"] = __opts__.get("test", None)
    st_ = salt.client.ssh.state.SSHHighState(
        opts, __pillar__, __salt__, __context__["fileclient"]
    )
    st_.push_active()
    mods = _parse_mods(mods)
    high_data, errors = st_.render_highstate({saltenv: mods})
    high_data, ext_errors = st_.state.reconcile_extend(high_data)
    errors += ext_errors
    errors += st_.state.verify_high(high_data)
    if errors:
        return errors
    high_data, req_in_errors = st_.state.requisite_in(high_data)
    errors += req_in_errors
    high_data = st_.state.apply_exclude(high_data)
    # Verify that the high data is structurally sound
    if errors:
        return errors
    ret = st_.state.compile_high_data(high_data)
    _cleanup_slsmod_low_data(ret)
    return ret


def show_top(**kwargs):
    """
    Return the top data that the minion will use for a highstate

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_top
    """
    __opts__["grains"] = __grains__
    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)
    st_ = salt.client.ssh.state.SSHHighState(
        opts, __pillar__, __salt__, __context__["fileclient"]
    )
    top_data = st_.get_top()
    errors = []
    errors += st_.verify_tops(top_data)
    if errors:
        return errors
    matches = st_.top_matches(top_data)
    return matches


def single(fun, name, test=None, **kwargs):
    """
    .. versionadded:: 2015.5.0

    Execute a single state function with the named kwargs, returns False if
    insufficient data is sent to the command

    By default, the values of the kwargs will be parsed as YAML. So, you can
    specify lists values, or lists of single entry key-value maps, as you
    would in a YAML salt file. Alternatively, JSON format of keyword values
    is also supported.

    CLI Example:

    .. code-block:: bash

        salt '*' state.single pkg.installed name=vim

    """
    st_kwargs = __salt__.kwargs
    __opts__["grains"] = __grains__

    # state.fun -> [state, fun]
    comps = fun.split(".")
    if len(comps) < 2:
        __context__["retcode"] = 1
        return "Invalid function passed"

    # Create the low chunk, using kwargs as a base
    kwargs.update({"state": comps[0], "fun": comps[1], "__id__": name, "name": name})

    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)

    # Set test mode
    if salt.utils.args.test_mode(test=test, **kwargs):
        opts["test"] = True
    else:
        opts["test"] = __opts__.get("test", None)

    # Get the override pillar data
    __pillar__.update(kwargs.get("pillar", {}))

    # Create the State environment
    st_ = salt.client.ssh.state.SSHState(opts, __pillar__)

    # Verify the low chunk
    err = st_.verify_data(kwargs)
    if err:
        __context__["retcode"] = 1
        return err

    # Must be a list of low-chunks
    chunks = [kwargs]

    # Retrieve file refs for the state run, so we can copy relevant files down
    # to the minion before executing the state
    file_refs = salt.client.ssh.state.lowstate_file_refs(
        chunks,
        _merge_extra_filerefs(
            kwargs.get("extra_filerefs", ""), opts.get("extra_filerefs", "")
        ),
    )

    roster = salt.roster.Roster(opts, opts.get("roster", "flat"))
    roster_grains = roster.opts["grains"]

    # Create the tar containing the state pkg and relevant files.
    trans_tar = salt.client.ssh.state.prep_trans_tar(
        __context__["fileclient"],
        chunks,
        file_refs,
        __pillar__,
        st_kwargs["id_"],
        roster_grains,
    )

    # Create a hash so we can verify the tar on the target system
    trans_tar_sum = salt.utils.hashutils.get_hash(trans_tar, opts["hash_type"])

    # We use state.pkg to execute the "state package"
    cmd = "state.pkg {0}/salt_state.tgz test={1} pkg_sum={2} hash_type={3}".format(
        opts["thin_dir"], test, trans_tar_sum, opts["hash_type"]
    )

    # Create a salt-ssh Single object to actually do the ssh work
    single = salt.client.ssh.Single(
        opts,
        cmd,
        fsclient=__context__["fileclient"],
        minion_opts=__salt__.minion_opts,
        **st_kwargs
    )

    # Copy the tar down
    single.shell.send(trans_tar, "{0}/salt_state.tgz".format(opts["thin_dir"]))

    # Run the state.pkg command on the target
    stdout, stderr, _ = single.cmd_block()

    # Clean up our tar
    try:
        os.remove(trans_tar)
    except (OSError, IOError):
        pass

    # Read in the JSON data and return the data structure
    try:
        return salt.utils.json.loads(stdout)
    except Exception as e:  # pylint: disable=broad-except
        log.error("JSON Render failed for: %s\n%s", stdout, stderr)
        log.error(six.text_type(e))

    # If for some reason the json load fails, return the stdout
    return stdout
