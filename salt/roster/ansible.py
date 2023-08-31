"""
Read in an Ansible inventory file or script.

Flat inventory files should be in the regular ansible inventory format.

.. code-block:: ini

    # /tmp/example_roster
    [servers]
    salt.gtmanfred.com ansible_ssh_user=gtmanfred ansible_ssh_host=127.0.0.1 ansible_ssh_port=22 ansible_ssh_pass='password' ansible_sudo_pass='password'

    [desktop]
    home ansible_ssh_user=gtmanfred ansible_ssh_host=12.34.56.78 ansible_ssh_port=23 ansible_ssh_pass='password' ansible_sudo_pass='password'

    [computers:children]
    desktop
    servers

    [computers:vars]
    http_port=80

then salt-ssh can be used to hit any of them

.. code-block:: bash

    [~]# salt-ssh --roster=ansible --roster-file=/tmp/example_roster -N all test.ping
    salt.gtmanfred.com:
        True
    home:
        True
    [~]# salt-ssh --roster=ansible --roster-file=/tmp/example_roster -N desktop test.ping
    home:
        True
    [~]# salt-ssh --roster=ansible --roster-file=/tmp/example_roster -N computers test.ping
    salt.gtmanfred.com:
        True
    home:
        True
    [~]# salt-ssh --roster=ansible --roster-file=/tmp/example_roster salt.gtmanfred.com test.ping
    salt.gtmanfred.com:
        True

There is also the option of specifying a dynamic inventory, and generating it on the fly

.. code-block:: bash

    #!/bin/bash
    # filename: /etc/salt/hosts
    echo '{
        "servers": [
            "salt.gtmanfred.com"
        ],
        "desktop": [
            "home"
        ],
        "computers": {
            "hosts": [],
            "children": [
                "desktop",
                "servers"
            ],
            "vars": {
                "http_port": 80
            }
        },
        "_meta": {
            "hostvars": {
                "salt.gtmanfred.com": {
                    "ansible_ssh_user": "gtmanfred",
                    "ansible_ssh_host": "127.0.0.1",
                    "ansible_sudo_pass": "password",
                    "ansible_ssh_pass": "password",
                    "ansible_ssh_port": 22
                },
                "home": {
                    "ansible_ssh_user": "gtmanfred",
                    "ansible_ssh_host": "12.34.56.78",
                    "ansible_sudo_pass": "password",
                    "ansible_ssh_pass": "password",
                    "ansible_ssh_port": 23
                }
            }
        }
    }'

This is the format that an inventory script needs to output to work with ansible, and thus here.

.. code-block:: bash

    [~]# salt-ssh --roster=ansible --roster-file /etc/salt/hosts salt.gtmanfred.com test.ping
    salt.gtmanfred.com:
            True

.. note::

    A dynamic inventory script must have the executable bit set. In the above
    example, ``chmod +x /etc/salt/hosts``.

Any of the [groups] or direct hostnames will return.  The 'all' is special, and returns everything.
"""

import copy
import fnmatch

import salt.utils.ansible
import salt.utils.path
from salt.roster import get_roster_file

CONVERSION = {
    "ansible_ssh_host": "host",
    "ansible_ssh_port": "port",
    "ansible_ssh_user": "user",
    "ansible_ssh_pass": "passwd",
    "ansible_sudo_pass": "sudo",
    "ansible_ssh_private_key_file": "priv",
}

__virtualname__ = "ansible"


def __virtual__():
    if salt.utils.path.which("ansible-inventory"):
        return __virtualname__
    else:
        return False, "Install `ansible` to use inventory"


def targets(tgt, tgt_type="glob", **kwargs):
    """
    Return the targets from the ansible inventory_file
    Default: /etc/salt/roster
    """
    __context__["inventory"] = salt.utils.ansible.targets(
        inventory=get_roster_file(__opts__)
    )

    if tgt_type == "glob":
        hosts = [
            host for host in _get_hosts_from_group("all") if fnmatch.fnmatch(host, tgt)
        ]
    elif tgt_type == "list":
        hosts = [host for host in _get_hosts_from_group("all") if host in tgt]
    elif tgt_type == "nodegroup":
        hosts = _get_hosts_from_group(tgt)
    else:
        hosts = []

    return {host: _get_hostvars(host) for host in hosts}


def _get_hosts_from_group(group):
    inventory = __context__["inventory"]
    if group not in inventory:
        return []
    hosts = [host for host in inventory[group].get("hosts", [])]
    for child in inventory[group].get("children", []):
        child_info = _get_hosts_from_group(child)
        if child_info not in hosts:
            hosts.extend(_get_hosts_from_group(child))
    return hosts


def _get_hostvars(host):
    hostvars = __context__["inventory"]["_meta"].get("hostvars", {}).get(host, {})
    ret = copy.deepcopy(__opts__.get("roster_defaults", {}))
    for value in CONVERSION:
        if value in hostvars:
            ret[CONVERSION[value]] = hostvars.pop(value)
    ret["minion_opts"] = hostvars
    if "host" not in ret:
        ret["host"] = host
    return ret
