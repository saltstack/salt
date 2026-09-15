"""
Manage UEFI boot entries
"""


def present(name, loader, disk="/dev/sda", part=1, index=None):
    """
    Ensure EFI entry is present

    Example:

    .. code-block:: yaml

        my_efi_entry:
          efi.present:
            - name: Debian
            - loader: '\\EFI\\debian\\grub.efi'
            - index: 0
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": []}

    entries = __salt__["efi.list_entries"]()
    # Find bootnum
    bootnum = None
    for bn, info in entries.items():
        if info["label"] == name:
            bootnum = bn
            break

    added = False
    if not bootnum:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"].append(f"EFI entry '{name}' would be added.")
        elif __salt__["efi.add_entry"](name, loader, disk, part):
            added = True
            ret["changes"]["new"] = name
            ret["comment"].append(f"EFI entry '{name}' added.")
            # Re-fetch bootnum
            new_entries = __salt__["efi.list_entries"]()
            for bn, info in new_entries.items():
                if info["label"] == name:
                    bootnum = bn
                    break

        else:
            ret["result"] = False
            ret["comment"].append(f"Failed to add EFI entry '{name}'.")
            return ret

    order_updated = False
    if bootnum and index is not None:
        order = __salt__["efi.get_bootorder"]()
        if bootnum in order:
            order.remove(bootnum)

        # Ensure index is within bounds
        idx = max(0, min(len(order), index))
        order.insert(idx, bootnum)

        # Check if order actually changed
        current_order = __salt__["efi.get_bootorder"]()
        if order != current_order:
            if __opts__["test"]:
                ret["result"] = None
                ret["comment"].append(f"Boot order would be updated to index {idx}.")
            elif __salt__["efi.set_bootorder"](order):
                order_updated = True
                ret["changes"]["bootorder"] = order
                ret["comment"].append(f"Boot order updated to index {idx}.")
            else:
                ret["result"] = False
                ret["comment"].append("Failed to update boot order.")
        elif not added:
            ret["comment"].append("Boot order is already correct.")

    if not added and not order_updated and not ret["comment"]:
        ret["comment"].append(f"EFI entry '{name}' is already present.")

    ret["comment"] = " ".join(ret["comment"])
    return ret


def absent(name):
    """
    Ensure EFI entry is absent

    Example:

    .. code-block:: yaml

        my_efi_entry:
          efi.absent:
            - name: Debian
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    entries = __salt__["efi.list_entries"]()
    # Find bootnum
    bootnum = None
    for bn, info in entries.items():
        if info["label"] == name:
            bootnum = bn
            break

    if not bootnum:
        ret["comment"] = f"EFI entry '{name}' is already absent."
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"EFI entry '{name}' would be removed."
        return ret

    if __salt__["efi.remove_entry"](bootnum):
        ret["changes"] = {"old": name}
        ret["comment"] = f"EFI entry '{name}' removed."
    else:
        ret["result"] = False
        ret["comment"] = f"Failed to remove EFI entry '{name}'."

    return ret


def order_set(name, bootorder):
    """
    Ensure boot order is set

    Example:

    .. code-block:: yaml

        my_boot_order:
          efi.order_set:
            - bootorder:
              - 0001
              - 0002
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    current_order = __salt__["efi.get_bootorder"]()
    if current_order == bootorder:
        ret["comment"] = "Boot order is already set."
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Boot order would be set to {bootorder}."
        return ret

    if __salt__["efi.set_bootorder"](bootorder):
        ret["changes"] = {"old": current_order, "new": bootorder}
        ret["comment"] = "Boot order set."
    else:
        ret["result"] = False
        ret["comment"] = "Failed to set boot order."

    return ret
