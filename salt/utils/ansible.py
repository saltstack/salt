# -*- coding: utf-8 -*-
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import os

# Import Salt libs
import salt.utils.json
import salt.utils.path
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError

__virtualname__ = "ansible"

log = logging.getLogger(__name__)

# Load the __salt__ dunder if not already loaded (when called from utils-module)
__salt__ = None


def __virtual__():  # pylint: disable=expected-2-blank-lines-found-0
    try:
        global __salt__  # pylint: disable=global-statement
        if not __salt__:
            __salt__ = salt.loader.minion_mods(__opts__)
            return (
                salt.utils.path.which("ansible-inventory") and __virtualname__,
                "Install `ansible` to use inventory",
            )
    except Exception as e:  # pylint: disable=broad-except
        log.error("Could not load __salt__: %s", e)
        return False


def targets(inventory="/etc/ansible/hosts", **kwargs):
    """
    Return the targets from the ansible inventory_file
    Default: /etc/salt/roster
    """
    if not os.path.isfile(inventory):
        raise CommandExecutionError("Inventory file not found: {}".format(inventory))

    extra_cmd = ""
    if kwargs.get("export", False):
        extra_cmd += "--export "
    if kwargs.get("yaml", False):
        extra_cmd += "--yaml "
    inv = __salt__["cmd.run"](
        "ansible-inventory -i {} --list {}".format(inventory, extra_cmd)
    )
    if kwargs.get("yaml", False):
        return salt.utils.stringutils.to_str(inv)
    else:
        return salt.utils.json.loads(salt.utils.stringutils.to_str(inv))
