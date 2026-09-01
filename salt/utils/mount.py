"""
Common functions for managing mounts
"""

import logging
import os

import salt.utils.files
import salt.utils.stringutils
import salt.utils.versions
import salt.utils.yaml

log = logging.getLogger(__name__)

# Specifications that fstab(5) accepts in place of a device path.
# The kernel only ever reports device paths
_SWAP_SPEC_TAGS = ("UUID=", "LABEL=", "PARTUUID=", "PARTLABEL=")


def _read_file(path):
    """
    Reads and returns the contents of a text file
    """
    try:
        with salt.utils.files.fopen(path, "rb") as contents:
            return salt.utils.yaml.safe_load(contents)
    except OSError:
        return {}


def get_cache(opts):
    """
    Return the mount cache file location.
    """
    return os.path.join(opts["cachedir"], "mounts")


def read_cache(opts):
    """
    Write the mount cache file.
    """
    cache_file = get_cache(opts)
    return _read_file(cache_file)


def write_cache(cache, opts):
    """
    Write the mount cache file.
    """
    cache_file = get_cache(opts)

    try:
        _cache = salt.utils.stringutils.to_bytes(salt.utils.yaml.safe_dump(cache))
        with salt.utils.files.fopen(cache_file, "wb+") as fp_:
            fp_.write(_cache)
        return True
    except OSError:
        log.error("Failed to cache mounts", exc_info_on_loglevel=logging.DEBUG)
        return False


def _resolve_canonical(name, salt_obj=None):
    """
    Return the canonical device path of a device specification.

    ``name`` can be the path of a device node or file, a symlink to
    either, or one of the ``TAG=value`` specifications accepted by fstab(5),
    e.g. ``UUID=066e0200-2867-4ebe-b9e6-f30026ca2314``.

    Specifications that cannot be resolved are returned unchanged, so that
    the caller can still report them the way the user spelled them.
    """
    if name.upper().startswith(_SWAP_SPEC_TAGS):
        device = _convert_to(name, "device", salt_obj)
        if not device:
            # No block device carries that tag.  Hand the specification back
            # unchanged rather than turning it into a bogus path.
            return name
        name = device

    return os.path.realpath(name)


def _convert_to(maybe_device, convert_to, salt_obj=None):
    """
    Convert a device name, UUID or LABEL to a device name, UUID or
    LABEL.

    Return the fs_spec required for fstab.

    """

    # Fast path. If we already have the information required, we can
    # save one blkid call
    if (
        not convert_to
        or (convert_to == "device" and maybe_device.startswith("/"))
        or maybe_device.startswith(f"{convert_to.upper()}=")
    ):
        return maybe_device

    # Get the device information
    if maybe_device.startswith("/"):
        blkid = salt_obj["disk.blkid"](maybe_device)
    else:
        blkid = salt_obj["disk.blkid"](token=maybe_device)

    result = None
    if len(blkid) == 1:
        if convert_to == "device":
            result = next(iter(blkid))
        else:
            key = convert_to.upper()
            result = f"{key}={next(iter(blkid.values()))[key]}"

    return result
