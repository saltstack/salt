"""
Support for GRUB Legacy
"""

import os

import salt.utils.decorators as decorators
import salt.utils.files
from salt.exceptions import CommandExecutionError

# Define the module's virtual name
__virtualname__ = "grub"


def __virtual__():
    """
    Only load the module if grub is installed
    """
    if os.path.exists(_detect_conf()):
        return __virtualname__
    return (
        False,
        "The grub_legacy execution module cannot be loaded: "
        "the grub config file does not exist in /boot/grub/",
    )


@decorators.memoize
def _detect_conf():
    """
    GRUB conf location differs depending on distro
    """
    if __grains__["os_family"] == "RedHat":
        return "/boot/grub/grub.conf"
    # Defaults for Ubuntu, Debian, Arch, and others
    return "/boot/grub/menu.lst"


def version():
    """
    Return server version from grub --version

    CLI Example:

    .. code-block:: bash

        salt '*' grub.version
    """
    cmd = "/sbin/grub --version"
    out = __salt__["cmd.run"](cmd)
    return out


def conf():
    """
    Parse GRUB conf file

    CLI Example:

    .. code-block:: bash

        salt '*' grub.conf
    """
    stanza = ""
    stanzas = []
    in_stanza = False
    ret = {}
    pos = 0
    try:
        with salt.utils.files.fopen(_detect_conf(), "r") as _fp:
            for line in _fp:
                line = salt.utils.stringutils.to_unicode(line)
                if line.startswith("#"):
                    continue
                if line.startswith("\n"):
                    in_stanza = False
                    if "title" in stanza:
                        stanza += f"order {pos}"
                        pos += 1
                        stanzas.append(stanza)
                    stanza = ""
                    continue
                if line.strip().startswith("title"):
                    if in_stanza:
                        stanza += f"order {pos}"
                        pos += 1
                        stanzas.append(stanza)
                        stanza = ""
                    else:
                        in_stanza = True
                if in_stanza:
                    stanza += line
                if not in_stanza:
                    key, value = _parse_line(line)
                    ret[key] = value
            if in_stanza:
                if not line.endswith("\n"):
                    line += "\n"
                stanza += line
                stanza += f"order {pos}"
                pos += 1
                stanzas.append(stanza)
    except OSError as exc:
        msg = "Could not read grub config: {0}"
        raise CommandExecutionError(msg.format(exc))

    ret["stanzas"] = []
    for stanza in stanzas:
        mydict = {}
        for line in stanza.strip().splitlines():
            key, value = _parse_line(line)
            mydict[key] = value
        ret["stanzas"].append(mydict)
    return ret


def _parse_line(line=""):
    """
    Used by conf() to break config lines into
    name/value pairs
    """
    parts = line.split()
    key = parts.pop(0)
    value = " ".join(parts)
    return key, value
