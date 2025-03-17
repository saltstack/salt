import logging
import os

import salt.modules.cmdmod
import salt.utils.json
import salt.utils.path
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError

__virtualname__ = "ansible"

log = logging.getLogger(__name__)


def __virtual__():
    if salt.utils.path.which("ansible-inventory"):
        return __virtualname__
    return (False, "Install `ansible` to use inventory")


def targets(inventory=None, inventories=None, yaml=False, export=False):
    """
    Return the targets from the ansible inventory_file
    Default: /etc/salt/roster
    """

    if inventory is None and inventories is None:
        inventory = "/etc/ansible/hosts"
    multi_inventory = True
    if not isinstance(inventories, list):
        multi_inventory = False
        inventories = []
    if inventory is not None and inventory not in inventories:
        inventories.append(inventory)

    extra_cmd = []
    if export:
        extra_cmd.append("--export")
    if yaml:
        extra_cmd.append("--yaml")

    ret = {}

    for inventory in inventories:
        if not os.path.isfile(inventory):
            raise CommandExecutionError(f"Inventory file not found: {inventory}")
        if not os.path.isabs(inventory):
            raise CommandExecutionError(
                f"Path to inventory file must be an absolute path: {inventory}"
            )

        inv = salt.modules.cmdmod.run(
            "ansible-inventory -i {} --list {}".format(inventory, " ".join(extra_cmd)),
            env={"ANSIBLE_DEPRECATION_WARNINGS": "0"},
            reset_system_locale=False,
        )

        if yaml:
            inv = salt.utils.stringutils.to_str(inv)
        else:
            try:
                inv = salt.utils.json.loads(salt.utils.stringutils.to_str(inv))
            except ValueError:
                raise CommandExecutionError(
                    f"Error processing the inventory {inventory}: {inv}"
                )

        if not multi_inventory:
            ret = inv
            break

        ret[inventory] = inv

    return ret
