"""Transactional update
====================

.. versionadded:: 3004

A transactional system, like `MicroOS`_, can present some challenges
when the user decided to manage it via Salt.

MicroOS provide a read-only rootfs and a tool,
``transactional-update``, that takes care of the management of the
system (updating, upgrading, installation or reboot, among others) in
an atomic way.

Atomicity is the main feature of MicroOS, and to guarantee this
property, this model leverages ``snapper``, ``zypper``, ``btrfs`` and
``overlayfs`` to create snapshots that will be updated independently
of the currently running system, and that are activated after the
reboot.  This implies, for example, that some changes made on the
system are not visible until the next reboot, as those changes are
living in a different snapshot of the file system.

This model presents a lot of problems with the traditional Salt model,
where the inspections (like 'is this package installed?') are executed
in order to determine if a subsequent action is required (like
'install this package').

Lets consider this use case, to see how it works on a traditional
system, and in a transactional system:

1) Check if ``apache`` is installed

2) If it is not installed, install it

3) Check that a ``vhost`` is configured for ``apache``

4) Make sure that ``apache2.service`` is enabled

5) If the configuration changes, restart ``apache2.service``

In the traditional system everything will work as expected.  The
system can see if the package is present or not, install it if it
isn't, and a re-check will shows that is already present.  The same
will happen to the configuration file in ``/etc/apache2``, that will
be available as soon the package gets installed.  Salt can inspect the
current form of this file, and add the missing bits if required.  Salt
can annotate that a change is present, and restart the service.

In a transactional system we will have multiple issues.  The first one
is that Salt can only see the content of the snapshot where the system
booted from.  Later snapshots may contain different content, including
the presence of ``apache``.  If Salt decides to install ``apache``
calling ``zypper``, it will fail, as this will try to write into the
read-only rootfs.  Even if Salt would call ``transactional-update pkg
install``, the package would only be present in the new transaction
(snapshot), and will not be found in the currently running system when
later Salt tries to validate the presence of the package in the
current one.

Any change in ``/etc`` alone will have also problems, as the changes
will be alive in a different overlay, only visible after the reboot.
And, finally, the service can only be enabled and restarted if the
service file is already present in the current ``/etc``.


General strategy
----------------

``transactional-update`` is the reference tool used for the
administration of transactional systems.  Newer versions of this tool
support the execution of random commands in the new transaction, the
continuation of a transaction, the automatic detection of changes in
new transactions and the merge of ``/etc`` overlays.

Continue a transaction
......................

One prerequisite already present is the support for branching from a
different snapshot than the current one in snapper.

With this feature we can represent in ``transactional-update`` the
action of creating a transaction snapshot based on one that is planned
to be the active one after the reboot.  This feature removes a lot of
user complains (like, for example, losing changes that are stored in a
transaction not yet activated), but also provide a more simple model
to work with.

So, for example, if the user have this scenario::

      +-----+  *=====*  +--V--+
    --| T.1 |--| T.2 |--| T.3 |
      +-----+  *=====*  +--A--+

where T.2 is the current active one, and T.3 is an snapshot generated
from T.2 with a new package (``apache2``), and is marked to be the
active after the reboot.

Previously, if the user (that is still on T.2) created a new
transaction, maybe for adding a new package (``tomcat``, for example),
the new T.4 will be based on the content of T.2 again, and not T.3, so
the new T.4 will have lost the changes of T.3 (i.e. `apache2` will not
be present in T.4).

With the ``--continue`` parameter, ``transactional-update`` will
create T.4 based on T.3, and nothing will be lost.

Command execution inside a new transaction
..........................................

With ``transactional-update run`` we will create a new transaction
based on the current one (T.2), where we can send interactive commands
that can modify the new transaction, and as commented, with
``transactional-update --continue run``, we will create a new
transaction based on the last created (T.3)

The ``run`` command can execute any application inside the new
transaction namespace.  This module uses this feature to execute the
different Salt execution modules, via ``call()``. Or even the full
``salt-thin`` or ``salt-call`` via ``sls()``, ``apply()``,
``single()`` or ``highstate``.

``transactional-update`` will drop empty snapshots
..................................................

The option ``--drop-if-no-change`` is used to detect whether there is
any change in the file system on the read-only subvolume of the new
transaction will be added.  If a change is present, the new
transaction will remain, if not it will be discarded.

For example::

  transactional-update --continue --drop-if-no-change run zypper in apache2"

If we are in the scenario described before, ``apache2`` is already
present in T.3.  In this case a new transaction, T.4, will be created
based on T.3, ``zypper`` will detect that the package is already
present and no change will be produced on T.4.  At the end of the
execution, ``transactional-update`` will validate that T.3 and T.4 are
equivalent and T.4 will be discarded.

If the command is::

  transactional-update --continue --drop-if-no-change run zypper in tomcat

the new T.4 will be indeed different from T.3, and will remain after
the transaction is closed.

With this feature, every time that we call any function of this
execution module, we will minimize the amount of transaction, while
maintaining the idempotence so some operations.

Report for pending transaction
..............................

A change in the system will create a new transaction, that needs to be
activated via a reboot.  With ``pending_transaction()`` we can check
if a reboot is needed.  We can execute the reboot using the
``reboot()`` function, that will follow the plan established by the
functions of the ``rebootmgr`` execution module.

``/etc`` overlay merge when no new transaction is created
.........................................................

In a transactional model, ``/etc`` is an overlay file system.  Changes
done during the update are only present in the new transaction, and so
will only be available after the reboot.  Or worse, if the transaction
gets dropped, because there is no change in the ``rootfs``, the
changes in ``/etc`` will be dropped too!.  This is designed like that
in order to make the configuration files for the new package available
only when new package is also available to the user.  So, after the
reboot.

This makes sense for the case when, for example, ``apache2`` is not
present in the current transaction, but we installed it.  The new
snapshot contains the ``apache2`` service, and the configuration files
in ``/etc`` will be accessible only after the reboot.

But this model presents an issue.  If we use ``transactional-update
--continue --drop-if-no-change run <command>``, where ``<command>``
does not make any change in the read-only subvolume, but only in
``/etc`` (which is also read-write in the running system), the new
overlay with the changes in ``/etc`` will be dropped together with the
transaction.

To fix this, ``transactional-update`` will detect that when no change
has been made on the read-only subvolume, but done in the overlay, the
transaction will be dropped and the changes in the overlay will be
merged back into ``/etc`` overlay of the current transaction.


Using the execution module
--------------------------

With this module we can create states that leverage Salt into this
kind of systems::

  # Install apache (low-level API)
  salt-call transactional_update.pkg_install apache2

  # We can call any execution module
  salt-call transactional_update.call pkg.install apache2

  # Or via a state
  salt-call transactional_update.single pkg.installed name=apache2

  # We can also execute a zypper directly
  salt-call transactional_update run "zypper in apache2" snapshot="continue"

  # We can reuse SLS states
  salt-call transactional_update.apply install_and_configure_apache

  # Or apply the full highstate
  salt-call transactional_update.highstate

  # Is there any change done in the system?
  salt-call transactional_update pending_transaction

  # If so, reboot via rebootmgr
  salt-call transactional_update reboot

  # We can enable the service
  salt-call service.enable apache2

  # If apache2 is available, this will work too
  salt-call service.restart apache2


Fixing some expectations
------------------------

This module alone is an improvement over the current state, but is
easy to see some limitations and problems:

Is not a fully transparent approach
...................................

The user needs to know if the system is transactional or not, as not
everything can be expressed inside a transaction (for example,
restarting a service inside transaction is not allowed).

Two step for service restart
............................

In the ``apache2` example from the beginning we can observe the
biggest drawback.  If the package ``apache2`` is missing, the new
module will create a new transaction, will execute ``pkg.install``
inside the transaction (creating the salt-thin, moving it inside and
delegating the execution to `transactional-update` CLI as part of the
full state).  Inside the transaction we can do too the required
changes in ``/etc`` for adding the new ``vhost``, and we can enable the
service via systemctl inside the same transaction.

At this point we will not merge the ``/etc`` overlay into the current
one, and we expect from the user call the ``reboot`` function inside
this module, in order to activate the new transaction and start the
``apache2`` service.

In the case that the package is already there, but the configuration
for the ``vhost`` is required, the new transaction will be dropped and
the ``/etc`` overlay will be visible in the live system.  Then from
outside the transaction, via a different call to Salt, we can command
a restart of the ``apache2`` service.

We can see that in both cases we break the user expectation, where a
change on the configuration will trigger automatically the restart of
the associated service.  In a transactional scenario we need two
different steps: or a reboot, or a restart from outside of the
transaction.

.. _MicroOS: https://microos.opensuse.org/

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

# required by _check_queue invocation later
import time  # pylint: disable=unused-import

import salt.client.ssh.state
import salt.client.ssh.wrapper.state
import salt.exceptions
import salt.utils.args
from salt.modules.state import _check_queue, _prior_running_states, _wait, running

__func_alias__ = {"apply_": "apply"}

log = logging.getLogger(__name__)


def __virtual__():
    """
    transactional-update command is required.
    """
    global _check_queue, _wait, _prior_running_states, running
    if __utils__["path.which"]("transactional-update"):
        _check_queue = salt.utils.functools.namespaced_function(_check_queue, globals())
        _wait = salt.utils.functools.namespaced_function(_wait, globals())
        _prior_running_states = salt.utils.functools.namespaced_function(
            _prior_running_states, globals()
        )
        running = salt.utils.functools.namespaced_function(running, globals())
        return True
    else:
        return (False, "Module transactional_update requires a transactional system")


class TransactionalUpdateHighstate(salt.client.ssh.state.SSHHighState):
    def _master_tops(self):
        return self.client.master_tops()


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
    """Run both cleanup-snapshots and cleanup-overlays.

    Identical to calling both cleanup-snapshots and cleanup-overlays.

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


def cleanup_snapshots(self_update=False):
    """Mark unused snapshots for snapper removal.

    If the current root filesystem is identical to the active root
    filesystem (means after a reboot, before transactional-update
    creates a new snapshot with updates), all old snapshots without a
    cleanup algorithm get a cleanup algorithm set. This is to make
    sure, that old snapshots will be deleted by snapper. See the
    section about cleanup algorithms in snapper(8).

    self_update
        Check for newer transactional-update versions.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update cleanup_snapshots

    """
    cmd = ["transactional-update"]
    cmd.extend(_global_params(self_update=self_update))
    cmd.append("cleanup-snapshots")
    return _cmd(cmd)


def cleanup_overlays(self_update=False):
    """Remove unused overlay layers.

    Removes all unreferenced (and thus unused) /etc overlay
    directories in /var/lib/overlay.

    self_update
        Check for newer transactional-update versions.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update cleanup_overlays

    """
    cmd = ["transactional-update"]
    cmd.extend(_global_params(self_update=self_update))
    cmd.append("cleanup-overlays")
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

    activate_transaction
        If at the end of the transaction there is a pending activation
        (i.e there is a new snaphot in the system), a new reboot will
        be scheduled (default False)

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update.call test.ping
        salt microos transactional_update.call ssh.set_auth_key user key=mykey
        salt microos transactional_update.call pkg.install emacs activate_transaction=True

    """

    if not function:
        raise salt.exceptions.CommandExecutionError("Missing function parameter")

    activate_transaction = kwargs.pop("activate_transaction", False)

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
        except ValueError:
            return {"result": False, "retcode": 1, "comment": ret_stdout}
    finally:
        __utils__["files.rm_rf"](thin_dest_path)

        # Check if reboot is needed
        if activate_transaction and pending_transaction():
            reboot()


def apply_(mods=None, **kwargs):
    """Apply an state inside a transaction.

    This function will call `transactional_update.highstate` or
    `transactional_update.sls` based on the arguments passed to this
    function. It exists as a more intuitive way of applying states.

    For a formal description of the possible parameters accepted in
    this function, check `state.apply_` documentation.

    activate_transaction
        If at the end of the transaction there is a pending activation
        (i.e there is a new snaphot in the system), a new reboot will
        be scheduled (default False)

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update.apply
        salt microos transactional_update.apply stuff
        salt microos transactional_update.apply stuff pillar='{"foo": "bar"}'
        salt microos transactional_update.apply stuff activate_transaction=True

    """
    if mods:
        return sls(mods, **kwargs)
    return highstate(**kwargs)


def _create_and_execute_salt_state(
    chunks, file_refs, test, hash_type, activate_transaction
):
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
            activate_transaction=activate_transaction,
        )
    finally:
        __utils__["files.rm_rf"](salt_state_path)

    return ret


def sls(
    mods,
    saltenv="base",
    test=None,
    exclude=None,
    activate_transaction=False,
    queue=False,
    **kwargs
):
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

    activate_transaction
        If at the end of the transaction there is a pending activation
        (i.e there is a new snaphot in the system), a new reboot will
        be scheduled (default False)

    queue
        Instead of failing immediately when another state run is in progress,
        queue the new state run to begin running once the other has finished.

        This option starts a new thread for each queued state run, so use this
        option sparingly. (Default: False)

    For a formal description of the possible parameters accepted in
    this function, check `state.sls` documentation.

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update.sls stuff pillar='{"foo": "bar"}'
        salt microos transactional_update.sls stuff activate_transaction=True

    """
    conflict = _check_queue(queue, kwargs)
    if conflict is not None:
        return conflict

    # Get a copy of the pillar data, to avoid overwriting the current
    # pillar, instead the one delegated
    pillar = copy.deepcopy(__pillar__)
    pillar.update(kwargs.get("pillar", {}))

    # Clone the options data and apply some default values. May not be
    # needed, as this module just delegate
    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)
    st_ = TransactionalUpdateHighstate(
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
    return _create_and_execute_salt_state(
        chunks, file_refs, test, hash_type, activate_transaction
    )


def highstate(activate_transaction=False, queue=False, **kwargs):
    """Retrieve the state data from the salt master for this minion and
    execute it inside a transaction.

    For a formal description of the possible parameters accepted in
    this function, check `state.highstate` documentation.

    activate_transaction
        If at the end of the transaction there is a pending activation
        (i.e there is a new snaphot in the system), a new reboot will
        be scheduled (default False)

    queue
        Instead of failing immediately when another state run is in progress,
        queue the new state run to begin running once the other has finished.

        This option starts a new thread for each queued state run, so use this
        option sparingly. (Default: False)

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update.highstate
        salt microos transactional_update.highstate pillar='{"foo": "bar"}'
        salt microos transactional_update.highstate activate_transaction=True

    """
    conflict = _check_queue(queue, kwargs)
    if conflict is not None:
        return conflict

    # Get a copy of the pillar data, to avoid overwriting the current
    # pillar, instead the one delegated
    pillar = copy.deepcopy(__pillar__)
    pillar.update(kwargs.get("pillar", {}))

    # Clone the options data and apply some default values. May not be
    # needed, as this module just delegate
    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)
    st_ = TransactionalUpdateHighstate(
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
    return _create_and_execute_salt_state(
        chunks, file_refs, test, hash_type, activate_transaction
    )


def single(fun, name, test=None, activate_transaction=False, queue=False, **kwargs):
    """Execute a single state function with the named kwargs, returns
    False if insufficient data is sent to the command

    By default, the values of the kwargs will be parsed as YAML. So,
    you can specify lists values, or lists of single entry key-value
    maps, as you would in a YAML salt file. Alternatively, JSON format
    of keyword values is also supported.

    activate_transaction
        If at the end of the transaction there is a pending activation
        (i.e there is a new snaphot in the system), a new reboot will
        be scheduled (default False)

    queue
        Instead of failing immediately when another state run is in progress,
        queue the new state run to begin running once the other has finished.

        This option starts a new thread for each queued state run, so use this
        option sparingly. (Default: False)

    CLI Example:

    .. code-block:: bash

        salt microos transactional_update.single pkg.installed name=emacs
        salt microos transactional_update.single pkg.installed name=emacs activate_transaction=True

    """
    conflict = _check_queue(queue, kwargs)
    if conflict is not None:
        return conflict

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
    return _create_and_execute_salt_state(
        chunks, file_refs, test, hash_type, activate_transaction
    )
