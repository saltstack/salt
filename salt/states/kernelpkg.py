"""
Manage kernel packages and active kernel version
=========================================================================

Example state to install the latest kernel from package repositories:

.. code-block:: yaml

    install-latest-kernel:
      kernelpkg.latest_installed: []

Example state to boot the system if a new kernel has been installed:

.. code-block:: yaml

    boot-latest-kernel:
      kernelpkg.latest_active:
        - at_time: 1

Example state chaining the install and reboot operations:

.. code-block:: yaml

    install-latest-kernel:
      kernelpkg.latest_installed: []

    boot-latest-kernel:
      kernelpkg.latest_active:
        - at_time: 1
        - onchanges:
          - kernelpkg: install-latest-kernel

Chaining can also be achieved using wait/listen requisites:

.. code-block:: yaml

    install-latest-kernel:
      kernelpkg.latest_installed: []

    boot-latest-kernel:
      kernelpkg.latest_wait:
        - at_time: 1
        - listen:
          - kernelpkg: install-latest-kernel
"""

import logging

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only make these states available if a kernelpkg provider has been detected or
    assigned for this minion
    """
    if "kernelpkg.upgrade" in __salt__:
        return True
    return (False, "kernelpkg module could not be loaded")


def latest_installed(name, **kwargs):  # pylint: disable=unused-argument
    """
    Ensure that the latest version of the kernel available in the
    repositories is installed.

    .. note::

        This state only installs the kernel, but does not activate it.
        The new kernel should become active at the next reboot.
        See :py:func:`kernelpkg.needs_reboot <salt.modules.kernelpkg_linux_yum.needs_reboot>` for details on
        how to detect this condition, and :py:func:`~salt.states.kernelpkg.latest_active`
        to initiale a reboot when needed.

    name
        Arbitrary name for the state. Does not affect behavior.
    """
    installed = __salt__["kernelpkg.list_installed"]()
    upgrade = __salt__["kernelpkg.latest_available"]()
    ret = {"name": name}

    if upgrade in installed:
        ret["result"] = True
        ret["comment"] = "The latest kernel package is already installed: {}".format(
            upgrade
        )
        ret["changes"] = {}

    else:

        if __opts__["test"]:
            ret["result"] = None
            ret["changes"] = {}
            ret["comment"] = "The latest kernel package will be installed: {}".format(
                upgrade
            )

        else:
            result = __salt__["kernelpkg.upgrade"]()
            ret["result"] = True
            ret["changes"] = result["upgrades"]
            ret["comment"] = (
                "The latest kernel package has been installed, but not activated."
            )

    return ret


def latest_active(name, at_time=None, **kwargs):  # pylint: disable=unused-argument
    """
    Initiate a reboot if the running kernel is not the latest one installed.

    .. note::

        This state does not install any patches. It only compares the running
        kernel version number to other kernel versions also installed in the
        system. If the running version is not the latest one installed, this
        state will reboot the system.

        See :py:func:`kernelpkg.upgrade <salt.modules.kernelpkg_linux_yum.upgrade>` and
        :py:func:`~salt.states.kernelpkg.latest_installed`
        for ways to install new kernel packages.

        This module does not attempt to understand or manage boot loader configurations
        it is possible to have a new kernel installed, but a boot loader configuration
        that will never activate it. For this reason, it would not be advisable to
        schedule this state to run automatically.

        Because this state function may cause the system to reboot, it may be preferable
        to move it to the very end of the state run.
        See :py:func:`~salt.states.kernelpkg.latest_wait`
        for a waitable state that can be called with the `listen` requesite.

    name
        Arbitrary name for the state. Does not affect behavior.

    at_time
        The wait time in minutes before the system will be rebooted.
    """
    active = __salt__["kernelpkg.active"]()
    latest = __salt__["kernelpkg.latest_installed"]()
    ret = {"name": name}

    if __salt__["kernelpkg.needs_reboot"]():

        ret["comment"] = "The system will be booted to activate kernel: {}".format(
            latest
        )

        if __opts__["test"]:
            ret["result"] = None
            ret["changes"] = {"kernel": {"old": active, "new": latest}}

        else:
            __salt__["system.reboot"](at_time=at_time)
            ret["result"] = True
            ret["changes"] = {"kernel": {"old": active, "new": latest}}

    else:
        ret["result"] = True
        ret["comment"] = "The latest installed kernel package is active: {}".format(
            active
        )
        ret["changes"] = {}

    return ret


def latest_wait(name, at_time=None, **kwargs):  # pylint: disable=unused-argument
    """
    Initiate a reboot if the running kernel is not the latest one installed. This is the
    waitable version of :py:func:`~salt.states.kernelpkg.latest_active` and
    will not take any action unless triggered by a watch or listen requesite.

    .. note::

        Because this state function may cause the system to reboot, it may be preferable
        to move it to the very end of the state run using `listen` or `listen_in` requisites.

        .. code-block:: yaml

            system-up-to-date:
              pkg.uptodate:
                - refresh: true

            boot-latest-kernel:
              kernelpkg.latest_wait:
                - at_time: 1
                - listen:
                  - pkg: system-up-to-date

    name
        Arbitrary name for the state. Does not affect behavior.

    at_time
        The wait time in minutes before the system will be rebooted.
    """
    return {"name": name, "changes": {}, "result": True, "comment": ""}


def mod_watch(name, sfun, **kwargs):
    """
    Execute a kernelpkg state based on a watch or listen call
    """
    if sfun in ("latest_active", "latest_wait"):
        return latest_active(name, **kwargs)
    else:
        return {
            "name": name,
            "changes": {},
            "comment": "kernelpkg.{} does not work with the watch requisite.".format(
                sfun
            ),
            "result": False,
        }
