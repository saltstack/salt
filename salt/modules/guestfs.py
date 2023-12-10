"""
Interact with virtual machine images via libguestfs

:depends:   - libguestfs
"""

import hashlib
import logging
import os
import tempfile
import time

import salt.utils.path
from salt.config import DEFAULT_HASH_TYPE

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if libguestfs python bindings are installed
    """
    if salt.utils.path.which("guestmount"):
        return "guestfs"
    return (
        False,
        "The guestfs execution module cannot be loaded: guestmount binary not in path.",
    )


def mount(location, access="rw", root=None):
    """
    Mount an image

    CLI Example:

    .. code-block:: bash

        salt '*' guest.mount /srv/images/fedora.qcow
    """
    if root is None:
        root = os.path.join(
            tempfile.gettempdir(), "guest", location.lstrip(os.sep).replace("/", ".")
        )
        log.debug("Using root %s", root)
    if not os.path.isdir(root):
        try:
            os.makedirs(root)
        except OSError:
            # Somehow the path already exists
            pass
    while True:
        if os.listdir(root):
            # Stuff is in there, don't use it
            hash_type = getattr(hashlib, __opts__.get("hash_type", DEFAULT_HASH_TYPE))
            rand = hash_type(os.urandom(32)).hexdigest()
            root = os.path.join(
                tempfile.gettempdir(),
                "guest",
                location.lstrip(os.sep).replace("/", ".") + rand,
            )
            log.debug("Establishing new root as %s", root)
            if not os.path.isdir(root):
                try:
                    os.makedirs(root)
                except OSError:
                    log.info("Path already existing: %s", root)
        else:
            break
    cmd = f"guestmount -i -a {location} --{access} {root}"
    __salt__["cmd.run"](cmd, python_shell=False)
    return root


def umount(name, disk=None):
    """
    Unmount an image

    CLI Example:

    .. code-block:: bash

        salt '*' guestfs.umount /mountpoint disk=/srv/images/fedora.qcow
    """
    cmd = f"guestunmount -q {name}"
    __salt__["cmd.run"](cmd)

    # Wait at most 5s that the disk is no longuer used
    loops = 0
    while (
        disk is not None
        and loops < 5
        and len(__salt__["cmd.run"](f"lsof {disk}").splitlines()) != 0
    ):
        loops = loops + 1
        time.sleep(1)
