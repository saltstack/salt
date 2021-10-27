"""
Beacon to monitor disk usage.

.. versionadded:: 2015.5.0

:depends: python-psutil
"""
import logging
import re

import salt.utils.beacons
import salt.utils.platform

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

log = logging.getLogger(__name__)

__virtualname__ = "diskusage"


def __virtual__():
    if HAS_PSUTIL is False:
        return False
    else:
        return __virtualname__


def validate(config):
    """
    Validate the beacon configuration
    """
    # Configuration for diskusage beacon should be a list of dicts
    if not isinstance(config, list):
        return False, "Configuration for diskusage beacon must be a list."
    return True, "Valid beacon configuration"


def beacon(config):
    r"""
    Monitor the disk usage of the minion

    Specify thresholds for each disk and only emit a beacon if any of them are
    exceeded.

    .. code-block:: yaml

        beacons:
          diskusage:
            - /: 63%
            - /mnt/nfs: 50%

    Windows drives must be quoted to avoid yaml syntax errors

    .. code-block:: yaml

        beacons:
          diskusage:
            -  interval: 120
            - 'c:\\': 90%
            - 'd:\\': 50%

    Regular expressions can be used as mount points.

    .. code-block:: yaml

        beacons:
          diskusage:
            - '^\/(?!home).*$': 90%
            - '^[a-zA-Z]:\\$': 50%

    The first one will match all mounted disks beginning with "/", except /home
    The second one will match disks from A:\ to Z:\ on a Windows system

    Note that if a regular expression are evaluated after static mount points,
    which means that if a regular expression matches another defined mount point,
    it will override the previously defined threshold.

    """
    whitelist = []
    config = salt.utils.beacons.remove_hidden_options(config, whitelist)
    parts = psutil.disk_partitions(all=True)
    ret = []
    for mounts in config:
        mount = next(iter(mounts))

        # Because we're using regular expressions
        # if our mount doesn't end with a $, insert one.
        mount_re = mount
        if not mount.endswith("$"):
            mount_re = "{}$".format(mount)

        if salt.utils.platform.is_windows():
            # mount_re comes in formatted with a $ at the end
            # can be `C:\\$` or `C:\\\\$`
            # re string must be like `C:\\\\` regardless of \\ or \\\\
            # also, psutil returns uppercase
            mount_re = re.sub(r":\\\$", r":\\\\", mount_re)
            mount_re = re.sub(r":\\\\\$", r":\\\\", mount_re)
            mount_re = mount_re.upper()

        for part in parts:
            if re.match(mount_re, part.mountpoint):
                _mount = part.mountpoint

                try:
                    _current_usage = psutil.disk_usage(_mount)
                except OSError:
                    log.warning("%s is not a valid mount point.", _mount)
                    continue

                current_usage = _current_usage.percent
                monitor_usage = mounts[mount]
                if isinstance(monitor_usage, str) and "%" in monitor_usage:
                    monitor_usage = re.sub("%", "", monitor_usage)
                monitor_usage = float(monitor_usage)
                if current_usage >= monitor_usage:
                    ret.append({"diskusage": current_usage, "mount": _mount})
    return ret
