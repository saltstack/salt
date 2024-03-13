"""
Parses roster entries out of Host directives from SSH known_hosts

.. versionadded:: 3006.0

Sample configuration:

.. note::

    The ``known_hosts`` file only contains hostname/IP. To pass other parameters,
    use ``roster_defaults``.

.. code-block:: yaml

    ssh_known_hosts_file: /Users/user1/.ssh/known_hosts
    roster_defaults:
      user: user1
      sudo: True

Now you can use the module

.. code-block:: bash

    salt-ssh --roster sshknownhosts '*' -r "echo hi"

Or with a Saltfile

.. code-block:: yaml

    salt-ssh:
      ssh_known_hosts_file: /Users/user1/.ssh/known_hosts

.. code-block:: bash

    salt-ssh --roster sshknownhosts '*' -r "echo hi"

"""

import logging
import os

import salt.utils.files
import salt.utils.stringutils

log = logging.getLogger(__name__)


def _parse_ssh_known_hosts_line(line):
    """
    Parse one line from a known_hosts line

    :param line: Individual lines from the ssh known_hosts file
    :return: Dict that contain the three fields from a known_hosts line
    """
    line_unicode = salt.utils.stringutils.to_unicode(line)
    fields = line_unicode.split(" ")

    if len(fields) < 3:
        log.warn("Not enough fields found in known_hosts in line : %s", line)
        return None

    fields = fields[:3]

    names, keytype, key = fields
    names = names.split(",")

    return {"names": names, "keytype": keytype, "key": key}


def _parse_ssh_known_hosts(lines):
    """
    Parses lines from the SSH known_hosts to create roster targets.

    :param lines: lines from the ssh known_hosts file
    :return: Dictionary of targets in similar style to the flat roster
    """

    targets_ = {}
    for line in lines:
        host_key = _parse_ssh_known_hosts_line(line)

        for host in host_key["names"]:
            targets_.update({host: {"host": host}})

    return targets_


def targets(tgt, tgt_type="glob"):
    """
    Return the targets from a known_hosts file
    """

    ssh_known_hosts_file = __opts__.get("ssh_known_hosts_file")

    if not os.path.isfile(ssh_known_hosts_file):
        log.error("Cannot find SSH known_hosts file")
        raise OSError("Cannot find SSH known_hosts file")
    if not os.access(ssh_known_hosts_file, os.R_OK):
        log.error("Cannot access SSH known_hosts file: %s", ssh_known_hosts_file)
        raise OSError(f"Cannot access SSH known_hosts file: {ssh_known_hosts_file}")

    with salt.utils.files.fopen(ssh_known_hosts_file, "r") as hostfile:
        raw = _parse_ssh_known_hosts([line.rstrip() for line in hostfile])

    return __utils__["roster_matcher.targets"](raw, tgt, tgt_type, "ipv4")
