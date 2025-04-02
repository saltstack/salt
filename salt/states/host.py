"""
Management of addresses and names in hosts file
===============================================

The ``/etc/hosts`` file can be managed to contain definitions for specific hosts:

.. code-block:: yaml

    salt-master:
      host.present:
        - ip: 192.168.0.42

Or using the ``names`` directive, you can put several names for the same IP.
(Do not try one name with space-separated values).

.. code-block:: yaml

    server1:
      host.present:
        - ip: 192.168.0.42
        - names:
          - server1
          - florida

.. note::

    Changing the ``names`` in ``host.present`` does not cause an
    update to remove the old entry.

.. code-block:: yaml

    server1:
      host.present:
        - ip:
          - 192.168.0.42
          - 192.168.0.43
          - 192.168.0.44
        - names:
          - server1

You can replace all existing names for a particular IP address:

.. code-block:: yaml

    127.0.1.1:
      host.only:
        - hostnames:
          - foo.example.com
          - foo

Or delete all existing names for an address:

.. code-block:: yaml

    203.0.113.25:
        host.only:
          - hostnames: []

You can also include comments:

.. code-block:: yaml

    server1:
      host.present:
        - ip: 192.168.0.42
        - names:
          - server1
          - florida
        - comment: A very important comment

"""

import logging

import salt.utils.validate.net

log = logging.getLogger(__name__)


def present(name, ip, comment="", clean=False):  # pylint: disable=C0103
    """
    Ensures that the named host is present with the given ip

    name
        The host to assign an ip to

    ip
        The ip addr(s) to apply to the host. Can be a single IP or a list of IP
        addresses.

    comment
        A comment to include for the host entry

        .. versionadded:: 3001

    clean
        Remove any entries which don't match those configured in the ``ip``
        option. Default is ``False``.

        .. versionadded:: 2018.3.4
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    if not isinstance(ip, list):
        ip = [ip]

    all_hosts = __salt__["hosts.list_hosts"]()
    comments = []
    to_add = set()
    to_remove = set()
    update_comment = set()

    # First check for IPs not currently in the hosts file
    to_add.update([(addr, name) for addr in ip if addr not in all_hosts])

    if comment:
        update_comment.update([(addr, comment) for addr in ip if addr not in all_hosts])

    # Now sweep through the hosts file and look for entries matching either the
    # IP address(es) or hostname.
    for addr, host_info in all_hosts.items():
        if addr not in ip:
            if "aliases" in host_info and name in host_info["aliases"]:
                # Found match for hostname, but the corresponding IP is not in
                # our list, so we need to remove it.
                if clean:
                    to_remove.add((addr, name))
                else:
                    ret.setdefault("warnings", []).append(
                        "Host {0} present for IP address {1}. To get rid of "
                        "this warning, either run this state with 'clean' "
                        "set to True to remove {0} from {1}, or add {1} to "
                        "the 'ip' argument.".format(name, addr)
                    )
        else:
            if "aliases" in host_info and name in host_info["aliases"]:
                if (
                    comment
                    and "comment" in host_info
                    and host_info["comment"] != comment
                ):
                    update_comment.add((addr, comment))
                elif comment and "comment" not in host_info:
                    update_comment.add((addr, comment))
                else:
                    # No changes needed for this IP address and hostname
                    comments.append(f"Host {name} ({addr}) already present")
            else:
                # IP address listed in hosts file, but hostname is not present.
                # We will need to add it.
                if salt.utils.validate.net.ip_addr(addr):
                    to_add.add((addr, name))
                    if comment:
                        update_comment.add((addr, comment))
                else:
                    ret["result"] = False
                    comments.append(f"Invalid IP Address for {name} ({addr})")

    for addr, name in to_add:
        if __opts__["test"]:
            ret["result"] = None
            comments.append(f"Host {name} ({addr}) would be added")
        else:
            if __salt__["hosts.add_host"](addr, name):
                comments.append(f"Added host {name} ({addr})")
            else:
                ret["result"] = False
                comments.append(f"Failed to add host {name} ({addr})")
                continue
        ret["changes"].setdefault("added", {}).setdefault(addr, []).append(name)

    for addr, comment in update_comment:
        if __opts__["test"]:
            comments.append(f"Comment for {addr} ({comment}) would be added")
        else:
            if __salt__["hosts.set_comment"](addr, comment):
                comments.append(f"Set comment for host {addr} ({comment})")
            else:
                ret["result"] = False
                comments.append(f"Failed to add comment for host {addr} ({comment})")
                continue
        ret["changes"].setdefault("comment_added", {}).setdefault(addr, []).append(
            comment
        )

    for addr, name in to_remove:
        if __opts__["test"]:
            ret["result"] = None
            comments.append(f"Host {name} ({addr}) would be removed")
        else:
            if __salt__["hosts.rm_host"](addr, name):
                comments.append(f"Removed host {name} ({addr})")
            else:
                ret["result"] = False
                comments.append(f"Failed to remove host {name} ({addr})")
                continue
        ret["changes"].setdefault("removed", {}).setdefault(addr, []).append(name)

    ret["comment"] = "\n".join(comments)
    return ret


def absent(name, ip):  # pylint: disable=C0103
    """
    Ensure that the named host is absent

    name
        The host to remove

    ip
        The ip addr(s) of the host to remove
    """
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    if not isinstance(ip, list):
        ip = [ip]

    comments = []
    for _ip in ip:
        if not __salt__["hosts.has_pair"](_ip, name):
            ret["result"] = True
            comments.append(f"Host {name} ({_ip}) already absent")
        else:
            if __opts__["test"]:
                comments.append(f"Host {name} ({_ip}) needs to be removed")
            else:
                if __salt__["hosts.rm_host"](_ip, name):
                    ret["changes"] = {"host": name}
                    ret["result"] = True
                    comments.append(f"Removed host {name} ({_ip})")
                else:
                    ret["result"] = False
                    comments.append("Failed to remove host")
    ret["comment"] = "\n".join(comments)
    return ret


def only(name, hostnames):
    """
    Ensure that only the given hostnames are associated with the
    given IP address.

    .. versionadded:: 2016.3.0

    name
        The IP address to associate with the given hostnames.

    hostnames
        Either a single hostname or a list of hostnames to associate
        with the given IP address in the given order.  Any other
        hostname associated with the IP address is removed.  If no
        hostnames are specified, all hostnames associated with the
        given IP address are removed.
    """
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    if isinstance(hostnames, str):
        hostnames = [hostnames]

    old = " ".join(__salt__["hosts.get_alias"](name))
    new = " ".join(x.strip() for x in hostnames)

    if old == new:
        ret["comment"] = f'IP address {name} already set to "{new}"'
        ret["result"] = True
        return ret

    if __opts__["test"]:
        ret["comment"] = f'Would change {name} from "{old}" to "{new}"'
        return ret

    ret["result"] = __salt__["hosts.set_host"](name, new)
    if not ret["result"]:
        ret["comment"] = 'hosts.set_host failed to change {} from "{}" to "{}"'.format(
            name, old, new
        )
        return ret

    ret["comment"] = f'successfully changed {name} from "{old}" to "{new}"'
    ret["changes"] = {name: {"old": old, "new": new}}
    return ret
