"""
Module for chroot
:maintainer:    Alberto Planas <aplanas@suse.com>
:maturity:      new
:depends:       None
:platform:      Linux
"""

import copy
import logging
import os
import sys
import tempfile

import salt
import salt.client.ssh.state
import salt.client.ssh.wrapper.state
import salt.defaults.exitcodes
import salt.exceptions
import salt.utils.args
import salt.utils.files

__func_alias__ = {"apply_": "apply"}

log = logging.getLogger(__name__)


def __virtual__():
    """
    Chroot command is required.
    """
    if __utils__["path.which"]("chroot") is not None:
        return True
    else:
        return (False, "Module chroot requires the command chroot")


def exist(root):
    """
    Return True if the chroot environment is present.

    root
        Path to the chroot environment

    CLI Example:

    .. code-block:: bash

        salt myminion chroot.exist /chroot

    """
    dev = os.path.join(root, "dev")
    proc = os.path.join(root, "proc")
    sys = os.path.join(root, "sys")
    return all(os.path.isdir(i) for i in (root, dev, proc, sys))


def create(root):
    """
    Create a basic chroot environment.

    Note that this environment is not functional. The caller needs to
    install the minimal required binaries, including Python if
    chroot.call is called.

    root
        Path to the chroot environment

    CLI Example:

    .. code-block:: bash

        salt myminion chroot.create /chroot

    """
    if not exist(root):
        dev = os.path.join(root, "dev")
        proc = os.path.join(root, "proc")
        sys = os.path.join(root, "sys")
        try:
            os.makedirs(dev, mode=0o755)
            os.makedirs(proc, mode=0o555)
            os.makedirs(sys, mode=0o555)
        except OSError as e:
            log.error("Error when trying to create chroot directories: %s", e)
            return False
    return True


def in_chroot():
    """
    Return True if the process is inside a chroot jail

    .. versionadded:: 3004

    CLI Example:

    .. code-block:: bash

        salt myminion chroot.in_chroot

    """
    result = False

    try:
        # We cannot assume that we are "root", so we cannot read
        # '/proc/1/root', that is required for the usual way of
        # detecting that we are in a chroot jail.  We use the debian
        # ischroot method.
        with salt.utils.files.fopen(
            "/proc/1/mountinfo"
        ) as root_fd, salt.utils.files.fopen("/proc/self/mountinfo") as self_fd:
            root_mountinfo = root_fd.read()
            self_mountinfo = self_fd.read()
        result = root_mountinfo != self_mountinfo
    except OSError:
        pass

    return result


def call(root, function, *args, **kwargs):
    """
    Executes a Salt function inside a chroot environment.

    The chroot does not need to have Salt installed, but Python is
    required.

    root
        Path to the chroot environment

    function
        Salt execution module function

    CLI Example:

    .. code-block:: bash

        salt myminion chroot.call /chroot test.ping
        salt myminion chroot.call /chroot ssh.set_auth_key user key=mykey

    """

    if not function:
        raise salt.exceptions.CommandExecutionError("Missing function parameter")

    if not exist(root):
        raise salt.exceptions.CommandExecutionError("Chroot environment not found")

    # Create a temporary directory inside the chroot where we can
    # untar salt-thin
    thin_dest_path = tempfile.mkdtemp(dir=root)
    thin_path = __utils__["thin.gen_thin"](
        __opts__["cachedir"],
        extra_mods=__salt__["config.option"]("thin_extra_mods", ""),
        so_mods=__salt__["config.option"]("thin_so_mods", ""),
    )
    # Some bug in Salt is preventing us to use `archive.tar` here. A
    # AsyncZeroMQReqChannel is not closed at the end of the salt-call,
    # and makes the client never exit.
    #
    # stdout = __salt__['archive.tar']('xzf', thin_path, dest=thin_dest_path)
    #
    stdout = __salt__["cmd.run"](["tar", "xzf", thin_path, "-C", thin_dest_path])
    if stdout:
        __utils__["files.rm_rf"](thin_dest_path)
        return {"result": False, "comment": stdout}

    chroot_path = os.path.join(os.path.sep, os.path.relpath(thin_dest_path, root))
    try:
        safe_kwargs = salt.utils.args.clean_kwargs(**kwargs)
        salt_argv = (
            [
                f"python{sys.version_info[0]}",
                os.path.join(chroot_path, "salt-call"),
                "--metadata",
                "--local",
                "--log-file",
                os.path.join(chroot_path, "log"),
                "--cachedir",
                os.path.join(chroot_path, "cache"),
                "--out",
                "json",
                "-l",
                "quiet",
                "--",
                function,
            ]
            + list(args)
            + [f"{k}={v}" for (k, v) in safe_kwargs.items()]
        )
        ret = __salt__["cmd.run_chroot"](root, [str(x) for x in salt_argv])

        # Process "real" result in stdout
        try:
            data = __utils__["json.find_json"](ret["stdout"])
            local = data.get("local", data)
            if isinstance(local, dict) and "retcode" in local:
                __context__["retcode"] = local["retcode"]
            return local.get("return", data)
        except ValueError:
            return {
                "result": False,
                "retcode": ret["retcode"],
                "comment": {"stdout": ret["stdout"], "stderr": ret["stderr"]},
            }
    finally:
        __utils__["files.rm_rf"](thin_dest_path)


def apply_(root, mods=None, **kwargs):
    """
    Apply an state inside a chroot.

    This function will call `chroot.highstate` or `chroot.sls` based
    on the arguments passed to this function. It exists as a more
    intuitive way of applying states.

    root
        Path to the chroot environment

    For a formal description of the possible parameters accepted in
    this function, check `state.apply_` documentation.

    CLI Example:

    .. code-block:: bash

        salt myminion chroot.apply /chroot
        salt myminion chroot.apply /chroot stuff
        salt myminion chroot.apply /chroot stuff pillar='{"foo": "bar"}'

    """
    if mods:
        return sls(root, mods, **kwargs)
    return highstate(root, **kwargs)


def _create_and_execute_salt_state(root, chunks, file_refs, test, hash_type):
    """
    Create the salt_state tarball, and execute in the chroot
    """
    # Create the tar containing the state pkg and relevant files.
    salt.client.ssh.wrapper.state._cleanup_slsmod_low_data(chunks)
    with salt.fileclient.get_file_client(__opts__) as client:
        trans_tar = salt.client.ssh.state.prep_trans_tar(
            client,
            chunks,
            file_refs,
            __pillar__.value(),
            root,
        )
    trans_tar_sum = salt.utils.hashutils.get_hash(trans_tar, hash_type)

    ret = None

    # Create a temporary directory inside the chroot where we can move
    # the salt_state.tgz
    salt_state_path = tempfile.mkdtemp(dir=root)
    salt_state_path = os.path.join(salt_state_path, "salt_state.tgz")
    salt_state_path_in_chroot = salt_state_path.replace(root, "", 1)
    try:
        salt.utils.files.copyfile(trans_tar, salt_state_path)
        ret = call(
            root,
            "state.pkg",
            salt_state_path_in_chroot,
            test=test,
            pkg_sum=trans_tar_sum,
            hash_type=hash_type,
        )
    finally:
        __utils__["files.rm_rf"](salt_state_path)

    return ret


def sls(root, mods, saltenv="base", test=None, exclude=None, **kwargs):
    """
    Execute the states in one or more SLS files inside the chroot.

    root
        Path to the chroot environment

    saltenv
        Specify a salt fileserver environment to be used when applying
        states

    mods
        List of states to execute

    test
        Run states in test-only (dry-run) mode

    exclude
        Exclude specific states from execution. Accepts a list of sls
        names, a comma-separated string of sls names, or a list of
        dictionaries containing ``sls`` or ``id`` keys. Glob-patterns
        may be used to match multiple states.

    For a formal description of the possible parameters accepted in
    this function, check `state.sls` documentation.

    CLI Example:

    .. code-block:: bash

        salt '*' chroot.sls /chroot stuff pillar='{"foo": "bar"}'
    """
    # Get a copy of the pillar data, to avoid overwriting the current
    # pillar, instead the one delegated
    pillar = copy.deepcopy(__pillar__.value())
    pillar.update(kwargs.get("pillar", {}))

    # Clone the options data and apply some default values. May not be
    # needed, as this module just delegate
    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)

    st_ = salt.client.ssh.state.SSHHighState(
        opts, pillar, __salt__, salt.fileclient.get_file_client(__opts__)
    )

    if isinstance(mods, str):
        mods = mods.split(",")

    with st_:
        high_data, errors = st_.render_highstate({saltenv: mods})
        if exclude:
            if isinstance(exclude, str):
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
        if errors:
            return errors

        high_data = st_.state.apply_exclude(high_data)

        # Compile and verify the raw chunks
        chunks = st_.state.compile_high_data(high_data)
    file_refs = salt.client.ssh.state.lowstate_file_refs(
        chunks,
        salt.client.ssh.wrapper.state._merge_extra_filerefs(
            kwargs.get("extra_filerefs", ""), opts.get("extra_filerefs", "")
        ),
    )

    hash_type = opts["hash_type"]
    return _create_and_execute_salt_state(root, chunks, file_refs, test, hash_type)


def highstate(root, **kwargs):
    """
    Retrieve the state data from the salt master for this minion and
    execute it inside the chroot.

    root
        Path to the chroot environment

    For a formal description of the possible parameters accepted in
    this function, check `state.highstate` documentation.

    CLI Example:

    .. code-block:: bash

        salt myminion chroot.highstate /chroot
        salt myminion chroot.highstate /chroot pillar='{"foo": "bar"}'

    """
    # Get a copy of the pillar data, to avoid overwriting the current
    # pillar, instead the one delegated
    pillar = copy.deepcopy(__pillar__.value())
    pillar.update(kwargs.get("pillar", {}))

    # Clone the options data and apply some default values. May not be
    # needed, as this module just delegate
    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)
    with salt.client.ssh.state.SSHHighState(
        opts, pillar, __salt__, salt.fileclient.get_file_client(__opts__)
    ) as st_:

        # Compile and verify the raw chunks
        chunks = st_.compile_low_chunks()
        file_refs = salt.client.ssh.state.lowstate_file_refs(
            chunks,
            salt.client.ssh.wrapper.state._merge_extra_filerefs(
                kwargs.get("extra_filerefs", ""), opts.get("extra_filerefs", "")
            ),
        )
        # Check for errors
        for chunk in chunks:
            if not isinstance(chunk, dict):
                __context__["retcode"] = 1
                return chunks

        test = kwargs.pop("test", False)
        hash_type = opts["hash_type"]
        return _create_and_execute_salt_state(root, chunks, file_refs, test, hash_type)
