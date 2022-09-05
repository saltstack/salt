"""
virt.query outputter
====================

Used to display the output from the :mod:`virt.query <salt.runners.virt.query>`
runner.
"""


def output(data, **kwargs):  # pylint: disable=unused-argument
    """
    Display output for the salt-run virt.query function
    """
    out = ""
    for id_ in data["data"]:
        out += "{}\n".format(id_)
        for vm_ in data["data"][id_]["vm_info"]:
            out += "  {}\n".format(vm_)
            vm_data = data[id_]["vm_info"][vm_]
            if "cpu" in vm_data:
                out += "    CPU: {}\n".format(vm_data["cpu"])
            if "mem" in vm_data:
                out += "    Memory: {}\n".format(vm_data["mem"])
            if "state" in vm_data:
                out += "    State: {}\n".format(vm_data["state"])
            if "graphics" in vm_data:
                if vm_data["graphics"].get("type", "") == "vnc":
                    out += "    Graphics: vnc - {}:{}\n".format(
                        id_, vm_data["graphics"]["port"]
                    )
            if "disks" in vm_data:
                for disk, d_data in vm_data["disks"].items():
                    out += "    Disk - {}:\n".format(disk)
                    out += "      Size: {}\n".format(d_data["disk size"])
                    out += "      File: {}\n".format(d_data["file"])
                    out += "      File Format: {}\n".format(d_data["file format"])
            if "nics" in vm_data:
                for mac in vm_data["nics"]:
                    out += "    Nic - {}:\n".format(mac)
                    out += "      Source: {}\n".format(
                        vm_data["nics"][mac]["source"][
                            next(iter(vm_data["nics"][mac]["source"].keys()))
                        ]
                    )
                    out += "      Type: {}\n".format(vm_data["nics"][mac]["type"])
    return out
