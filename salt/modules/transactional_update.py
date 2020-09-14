"""
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

import salt.client.ssh.state
import salt.client.ssh.wrapper.state
import salt.exceptions
import salt.utils.args

__func_alias__ = {"apply_": "apply"}

log = logging.getLogger(__name__)

# Define not exported variables from Salt, so this can be imported as
# a normal module
try:
    __context__
    __grains__
    __opts__
    __pillar__
    __salt__
    __utils__
except NameError:
    __context__ = {}
    __grains__ = {}
    __opts__ = {}
    __pillar__ = {}
    __salt__ = {}
    __utils__ = {}


def __virtual__():
    """
    transactional-update command is required.
    """
    if __utils__["path.which"]("transactional-update"):
        return True
    else:
        return (False, "Module transactional_update requires a transactional system")


def _global_params(self_update, snapshot=None, quiet=False):
    """Utility function to prepare common global parameters."""
    params = ["--non-interactive", "--drop-if-no-change"]
    if self_update is False:
        params.append("--no-selfupdate")
    if snapshot and snapshot != "continue":
        params.extend(["--continue", snapshot])
    elif snapshot:
        params.append("--continue")
    if quiet:
        params.append("--quiet")
    return params


def _pkg_params(pkg, pkgs, args):
    """Utility function to prepare common package parameters."""
    params = []

    if not pkg and not pkgs:
        raise salt.exceptions.CommandExecutionError("Provide pkg or pkgs parameters")

    if args and isinstance(args, str):
        params.extend(args.split())
    elif args and isinstance(args, list):
        params.extend(args)

    if pkg:
        params.append(pkg)

    if pkgs and isinstance(pkgs, str):
        params.extend(pkgs.split())
    elif pkgs and isinstance(pkgs, list):
        params.extend(pkgs)

    return params


def _cmd(cmd, retcode=False):
    """Utility function to run commands."""
    result = __salt__["cmd.run_all"](cmd)
    if retcode:
        return result["retcode"]

    if result["retcode"]:
        raise salt.exceptions.CommandExecutionError(result["stderr"])

    return result["stdout"]


def transactional():
    """Check if the system is a transactional system

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update transactional

    """
    return bool(__utils__["path.which"]("transactional-update"))


def in_transaction():
    """Check if Salt is executing while in a transaction

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update in_transaction

    """
    return transactional() and __salt__["chroot.in_chroot"]()


def cleanup(self_update=False):
    """Mark unused snapshots for snapper removal.

    If the current root filesystem is identical to the active root
    filesystem (means after a reboot, before transactional-update
    creates a new snapshot with updates), all old snapshots without a
    cleanup algorithm get a cleanup algorithm set. This is to make
    sure, that old snapshots will be deleted by snapper. See the
    section about cleanup algorithms in snapper(8).

    Also removes all unreferenced (and thus unused) /etc overlay
    directories in /var/lib/overlay.

    self_update
        Check for newer transactional-update versions.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update cleanup

    """
    cmd = ["transactional-update"]
    cmd.extend(_global_params(self_update=self_update))
    cmd.append("cleanup")
    return _cmd(cmd)


def grub_cfg(self_update=False, snapshot=None):
    """Regenerate grub.cfg

    grub2-mkconfig(8) is called to create a new /boot/grub2/grub.cfg
    configuration file for the bootloader.

    self_update
        Check for newer transactional-update versions.

    snapshot
        Use the given snapshot or, if no number is given, the current
        default snapshot as a base for the next snapshot. Use
        "continue" to indicate the last snapshot done.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update grub_cfg snapshot="continue"

    """
    cmd = ["transactional-update"]
    cmd.extend(_global_params(self_update=self_update, snapshot=snapshot))
    cmd.append("grub.cfg")
    return _cmd(cmd)


def bootloader(self_update=False, snapshot=None):
    """Reinstall the bootloader

    Same as grub.cfg, but will also rewrite the bootloader itself.

    self_update
        Check for newer transactional-update versions.

    snapshot
        Use the given snapshot or, if no number is given, the current
        default snapshot as a base for the next snapshot. Use
        "continue" to indicate the last snapshot done.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update bootloader snapshot="continue"

    """
    cmd = ["transactional-update"]
    cmd.extend(_global_params(self_update=self_update, snapshot=snapshot))
    cmd.append("bootloader")
    return _cmd(cmd)


def initrd(self_update=False, snapshot=None):
    """Regenerate initrd

    A new initrd is created in a snapshot.

    self_update
        Check for newer transactional-update versions.

    snapshot
        Use the given snapshot or, if no number is given, the current
        default snapshot as a base for the next snapshot. Use
        "continue" to indicate the last snapshot done.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update initrd snapshot="continue"

    """
    cmd = ["transactional-update"]
    cmd.extend(_global_params(self_update=self_update, snapshot=snapshot))
    cmd.append("initrd")
    return _cmd(cmd)


def kdump(self_update=False, snapshot=None):
    """Regenerate kdump initrd

    A new initrd for kdump is created in a snapshot.

    self_update
        Check for newer transactional-update versions.

    snapshot
        Use the given snapshot or, if no number is given, the current
        default snapshot as a base for the next snapshot. Use
        "continue" to indicate the last snapshot done.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update kdump snapshot="continue"

    """
    cmd = ["transactional-update"]
    cmd.extend(_global_params(self_update=self_update, snapshot=snapshot))
    cmd.append("kdump")
    return _cmd(cmd)


def run(command, self_update=False, snapshot=None):
    """Run a command in a new snapshot

    Execute the command inside a new snapshot. By default this snaphot
    will remain, but if --drop-if-no-chage is set, the new snapshot
    will be dropped if there is no change in the file system.

    command
        Command with parameters that will be executed (as string or
        array)

    self_update
        Check for newer transactional-update versions.

    snapshot
        Use the given snapshot or, if no number is given, the current
        default snapshot as a base for the next snapshot. Use
        "continue" to indicate the last snapshot done.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update run "mkdir /tmp/dir" snapshot="continue"

    """
    cmd = ["transactional-update"]
    cmd.extend(_global_params(self_update=self_update, snapshot=snapshot, quiet=True))
    cmd.append("run")
    if isinstance(command, str):
        cmd.extend(command.split())
    elif isinstance(command, list):
        cmd.extend(command)
    else:
        raise salt.exceptions.CommandExecutionError("Command parameter not recognized")
    return _cmd(cmd)


def reboot(self_update=False):
    """Reboot after update

    Trigger a reboot after updating the system.

    Several different reboot methods are supported, configurable via
    the REBOOT_METHOD configuration option in
    transactional-update.conf(5). By default rebootmgrd(8) will be
    used to reboot the system according to the configured policies if
    the service is running, otherwise systemctl reboot will be called.

    self_update
        Check for newer transactional-update versions.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update reboot

    """
    cmd = ["transactional-update"]
    cmd.extend(_global_params(self_update=self_update))
    cmd.append("reboot")
    return _cmd(cmd)


def dup(self_update=False, snapshot=None):
    """Call 'zypper dup'

    If new updates are available, a new snapshot is created and zypper
    dup --no-allow-vendor-change is used to update the
    snapshot. Afterwards, the snapshot is activated and will be used
    as the new root filesystem during next boot.

    self_update
        Check for newer transactional-update versions.

    snapshot
        Use the given snapshot or, if no number is given, the current
        default snapshot as a base for the next snapshot. Use
        "continue" to indicate the last snapshot done.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update dup snapshot="continue"
    """
    cmd = ["transactional-update"]
    cmd.extend(_global_params(self_update=self_update, snapshot=snapshot))
    cmd.append("dup")
    return _cmd(cmd)


def up(self_update=False, snapshot=None):
    """Call 'zypper up'

    If new updates are available, a new snapshot is created and zypper
    up is used to update the snapshot. Afterwards, the snapshot is
    activated and will be used as the new root filesystem during next
    boot.

    self_update
        Check for newer transactional-update versions.

    snapshot
        Use the given snapshot or, if no number is given, the current
        default snapshot as a base for the next snapshot. Use
        "continue" to indicate the last snapshot done.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update up snapshot="continue"

    """
    cmd = ["transactional-update"]
    cmd.extend(_global_params(self_update=self_update, snapshot=snapshot))
    cmd.append("up")
    return _cmd(cmd)


def patch(self_update=False, snapshot=None):
    """Call 'zypper patch'

    If new updates are available, a new snapshot is created and zypper
    patch is used to update the snapshot. Afterwards, the snapshot is
    activated and will be used as the new root filesystem during next
    boot.

    self_update
        Check for newer transactional-update versions.

    snapshot
        Use the given snapshot or, if no number is given, the current
        default snapshot as a base for the next snapshot. Use
        "continue" to indicate the last snapshot done.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update patch snapshot="continue"

    """
    cmd = ["transactional-update"]
    cmd.extend(_global_params(self_update=self_update, snapshot=snapshot))
    cmd.append("patch")
    return _cmd(cmd)


def migration(self_update=False, snapshot=None):
    """Updates systems registered via SCC / SMT

    On systems which are registered against the SUSE Customer Center
    (SCC) or SMT, a migration to a new version of the installed
    products can be made with this option.

    self_update
        Check for newer transactional-update versions.

    snapshot
        Use the given snapshot or, if no number is given, the current
        default snapshot as a base for the next snapshot. Use
        "continue" to indicate the last snapshot done.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update migration snapshot="continue"

    """
    cmd = ["transactional-update"]
    cmd.extend(_global_params(self_update=self_update, snapshot=snapshot))
    cmd.append("migration")
    return _cmd(cmd)


def pkg_install(pkg=None, pkgs=None, args=None, self_update=False, snapshot=None):
    """Install individual packages

    Installs additional software. See the install description in the
    "Package Management Commands" section of zypper's man page for all
    available arguments.

    pkg
        Package name to install

    pkgs
        List of packages names to install

    args
        String or list of extra parameters for zypper

    self_update
        Check for newer transactional-update versions.

    snapshot
        Use the given snapshot or, if no number is given, the current
        default snapshot as a base for the next snapshot. Use
        "continue" to indicate the last snapshot done.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update pkg_install pkg=emacs snapshot="continue"

    """
    cmd = ["transactional-update"]
    cmd.extend(_global_params(self_update=self_update, snapshot=snapshot))
    cmd.extend(["pkg", "install"])
    cmd.extend(_pkg_params(pkg, pkgs, args))
    return _cmd(cmd)


def pkg_remove(pkg=None, pkgs=None, args=None, self_update=False, snapshot=None):
    """Remove individual packages

    Removes installed software. See the remove description in the
    "Package Management Commands" section of zypper's man page for all
    available arguments.

    pkg
        Package name to install

    pkgs
        List of packages names to install

    args
        String or list of extra parameters for zypper

    self_update
        Check for newer transactional-update versions.

    snapshot
        Use the given snapshot or, if no number is given, the current
        default snapshot as a base for the next snapshot. Use
        "continue" to indicate the last snapshot done.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update pkg_remove pkg=vim snapshot="continue"
    """
    cmd = ["transactional-update"]
    cmd.extend(_global_params(self_update=self_update, snapshot=snapshot))
    cmd.extend(["pkg", "remove"])
    cmd.extend(_pkg_params(pkg, pkgs, args))
    return _cmd(cmd)


def pkg_update(pkg=None, pkgs=None, args=None, self_update=False, snapshot=None):
    """Updates individual packages

    Update selected software. See the update description in the
    "Update Management Commands" section of zypper's man page for all
    available arguments.

    pkg
        Package name to install

    pkgs
        List of packages names to install

    args
        String or list of extra parameters for zypper

    self_update
        Check for newer transactional-update versions.

    snapshot
        Use the given snapshot or, if no number is given, the current
        default snapshot as a base for the next snapshot. Use
        "continue" to indicate the last snapshot done.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update pkg_update pkg=emacs snapshot="continue"

    """
    cmd = ["transactional-update"]
    cmd.extend(_global_params(self_update=self_update, snapshot=snapshot))
    cmd.extend(["pkg", "update"])
    cmd.extend(_pkg_params(pkg, pkgs, args))
    return _cmd(cmd)


def rollback(snapshot=None):
    """Set the current, given or last working snapshot as default snapshot

    Sets the default root file system. On a read-only system the root
    file system is set directly using btrfs. On read-write systems
    snapper(8) rollback is called.

    If no snapshot number is given, the current root file system is
    set as the new default root file system. Otherwise number can
    either be a snapshot number (as displayed by snapper list) or the
    word last. last will try to reset to the latest working snapshot.

    snapshot
        Use the given snapshot or, if no number is given, the current
        default snapshot as a base for the next snapshot. Use
        "last" to indicate the last working snapshot done.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update rollback

    """
    if (
        snapshot
        and isinstance(snapshot, str)
        and snapshot != "last"
        and not snapshot.isnumeric()
    ):
        raise salt.exceptions.CommandExecutionError(
            "snapshot should be a number or 'last'"
        )
    cmd = ["transactional-update"]
    cmd.append("rollback")
    if snapshot:
        cmd.append(snapshot)
    return _cmd(cmd)


def pending_transaction():
    """Check if there is a pending transaction

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update pending_transaction

    """
    # If we are running inside a transaction, we do not have a good
    # way yet to detect a pending transaction
    if in_transaction():
        raise salt.exceptions.CommandExecutionError(
            "pending_transaction cannot be executed inside a transaction"
        )

    cmd = ["snapper", "--no-dbus", "list", "--columns", "number"]
    snapshots = _cmd(cmd)

    return any(snapshot.endswith("+") for snapshot in snapshots)


def call(function, *args, **kwargs):
    """Executes a Salt function inside a transaction.

    The chroot does not need to have Salt installed, but Python is
    required.

    function
        Salt execution module function

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update.call test.ping
        salt microos transactional_update.call ssh.set_auth_key user key=mykey

    """

    if not function:
        raise salt.exceptions.CommandExecutionError("Missing function parameter")

    # Generate the salt-thin and create a temporary directory in a
    # place that the new transaction will have access to, and where we
    # can untar salt-thin
    thin_path = __utils__["thin.gen_thin"](
        __opts__["cachedir"],
        extra_mods=__salt__["config.option"]("thin_extra_mods", ""),
        so_mods=__salt__["config.option"]("thin_so_mods", ""),
    )
    thin_dest_path = tempfile.mkdtemp(dir=__opts__["cachedir"])
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

    try:
        safe_kwargs = salt.utils.args.clean_kwargs(**kwargs)
        salt_argv = (
            [
                "python{}".format(sys.version_info[0]),
                os.path.join(thin_dest_path, "salt-call"),
                "--metadata",
                "--local",
                "--log-file",
                os.path.join(thin_dest_path, "log"),
                "--cachedir",
                os.path.join(thin_dest_path, "cache"),
                "--out",
                "json",
                "-l",
                "quiet",
                "--",
                function,
            ]
            + list(args)
            + ["{}={}".format(k, v) for (k, v) in safe_kwargs.items()]
        )
        try:
            ret_stdout = run([str(x) for x in salt_argv], snapshot="continue")
        except salt.exceptions.CommandExecutionError as e:
            ret_stdout = e.message

        # Process "real" result in stdout
        try:
            data = __utils__["json.find_json"](ret_stdout)
            local = data.get("local", data)
            if isinstance(local, dict) and "retcode" in local:
                __context__["retcode"] = local["retcode"]
            return local.get("return", data)
        except (KeyError, ValueError):
            return {"result": False, "comment": ret_stdout}
    finally:
        __utils__["files.rm_rf"](thin_dest_path)


def apply_(mods=None, **kwargs):
    """Apply an state inside a transaction.

    This function will call `transactional_update.highstate` or
    `transactional_update.sls` based on the arguments passed to this
    function. It exists as a more intuitive way of applying states.

    For a formal description of the possible parameters accepted in
    this function, check `state.apply_` documentation.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update.apply
        salt microos transactional_update.apply stuff
        salt microos transactional_update.apply stuff pillar='{"foo": "bar"}'

    """
    if mods:
        return sls(mods, **kwargs)
    return highstate(**kwargs)


def _create_and_execute_salt_state(chunks, file_refs, test, hash_type):
    """Create the salt_state tarball, and execute it in a transaction"""

    # Create the tar containing the state pkg and relevant files.
    salt.client.ssh.wrapper.state._cleanup_slsmod_low_data(chunks)
    trans_tar = salt.client.ssh.state.prep_trans_tar(
        salt.fileclient.get_file_client(__opts__), chunks, file_refs, __pillar__
    )
    trans_tar_sum = salt.utils.hashutils.get_hash(trans_tar, hash_type)

    ret = None

    # Create a temporary directory accesible later by the transaction
    # where we can move the salt_state.tgz
    salt_state_path = tempfile.mkdtemp(dir=__opts__["cachedir"])
    salt_state_path = os.path.join(salt_state_path, "salt_state.tgz")
    try:
        salt.utils.files.copyfile(trans_tar, salt_state_path)
        ret = call(
            "state.pkg",
            salt_state_path,
            test=test,
            pkg_sum=trans_tar_sum,
            hash_type=hash_type,
        )
    finally:
        __utils__["files.rm_rf"](salt_state_path)

    return ret


def sls(mods, saltenv="base", test=None, exclude=None, **kwargs):
    """Execute the states in one or more SLS files inside a transaction.

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

        salt microos transactional_update.sls stuff pillar='{"foo": "bar"}'

    """
    # Get a copy of the pillar data, to avoid overwriting the current
    # pillar, instead the one delegated
    pillar = copy.deepcopy(__pillar__)
    pillar.update(kwargs.get("pillar", {}))

    # Clone the options data and apply some default values. May not be
    # needed, as this module just delegate
    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)
    st_ = salt.client.ssh.state.SSHHighState(
        opts, pillar, __salt__, salt.fileclient.get_file_client(__opts__)
    )

    if isinstance(mods, str):
        mods = mods.split(",")

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
    return _create_and_execute_salt_state(chunks, file_refs, test, hash_type)


def highstate(**kwargs):
    """Retrieve the state data from the salt master for this minion and
    execute it inside a transaction.

    For a formal description of the possible parameters accepted in
    this function, check `state.highstate` documentation.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update.highstate
        salt microos transactional_update.highstate pillar='{"foo": "bar"}'

    """
    # Get a copy of the pillar data, to avoid overwriting the current
    # pillar, instead the one delegated
    pillar = copy.deepcopy(__pillar__)
    pillar.update(kwargs.get("pillar", {}))

    # Clone the options data and apply some default values. May not be
    # needed, as this module just delegate
    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)
    st_ = salt.client.ssh.state.SSHHighState(
        opts, pillar, __salt__, salt.fileclient.get_file_client(__opts__)
    )

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
    return _create_and_execute_salt_state(chunks, file_refs, test, hash_type)


def single(fun, name, test=None, **kwargs):
    """Execute a single state function with the named kwargs, returns
    False if insufficient data is sent to the command

    By default, the values of the kwargs will be parsed as YAML. So,
    you can specify lists values, or lists of single entry key-value
    maps, as you would in a YAML salt file. Alternatively, JSON format
    of keyword values is also supported.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update.single pkg.installed name=emacs

    """
    # Get a copy of the pillar data, to avoid overwriting the current
    # pillar, instead the one delegated
    pillar = copy.deepcopy(__pillar__)
    pillar.update(kwargs.get("pillar", {}))

    # Clone the options data and apply some default values. May not be
    # needed, as this module just delegate
    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)
    st_ = salt.client.ssh.state.SSHState(opts, pillar)

    # state.fun -> [state, fun]
    comps = fun.split(".")
    if len(comps) < 2:
        __context__["retcode"] = 1
        return "Invalid function passed"

    # Create the low chunk, using kwargs as a base
    kwargs.update({"state": comps[0], "fun": comps[1], "__id__": name, "name": name})

    # Verify the low chunk
    err = st_.verify_data(kwargs)
    if err:
        __context__["retcode"] = 1
        return err

    # Must be a list of low-chunks
    chunks = [kwargs]

    # Retrieve file refs for the state run, so we can copy relevant
    # files down to the minion before executing the state
    file_refs = salt.client.ssh.state.lowstate_file_refs(
        chunks,
        salt.client.ssh.wrapper.state._merge_extra_filerefs(
            kwargs.get("extra_filerefs", ""), opts.get("extra_filerefs", "")
        ),
    )

    hash_type = opts["hash_type"]
    return _create_and_execute_salt_state(chunks, file_refs, test, hash_type)
