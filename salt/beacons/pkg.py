"""
Watch for pkgs that have upgrades, then fire an event.

.. versionadded:: 2016.3.0
"""
import logging

__virtualname__ = "pkg"

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if strace is installed
    """
    if "pkg.upgrade_available" in __salt__:
        return __virtualname__
    else:
        err_msg = "pkg.upgrade_available is missing."
        log.error("Unable to load %s beacon: %s", __virtualname__, err_msg)
        return False, err_msg


def validate(config):
    """
    Validate the beacon configuration
    """
    # Configuration for pkg beacon should be a list
    if not isinstance(config, list):
        return False, "Configuration for pkg beacon must be a list."

    # Configuration for pkg beacon should contain pkgs
    pkgs_found = False
    pkgs_not_list = False
    for config_item in config:
        if "pkgs" in config_item:
            pkgs_found = True
            if isinstance(config_item["pkgs"], list):
                pkgs_not_list = True

    if not pkgs_found or not pkgs_not_list:
        return False, "Configuration for pkg beacon requires list of pkgs."
    return True, "Valid beacon configuration"


def beacon(config):
    """
    Check if installed packages are the latest versions
    and fire an event for those that have upgrades.

    .. code-block:: yaml

        beacons:
          pkg:
            - pkgs:
                - zsh
                - apache2
            - refresh: True
    """
    if "beacon.pkg" not in __context__:
        __context__["beacon.pkg"] = {}

    ret = []

    _refresh = False
    pkgs = []
    for config_item in config:
        if "pkgs" in config_item:
            pkgs += config_item["pkgs"]
        if "refresh" in config and config["refresh"]:
            _refresh = True

    for pkg in pkgs:
        if pkg not in __context__["beacon.pkg"]:
            __context__["beacon.pkg"][pkg] = None
        status = __context__["beacon.pkg"][pkg]

        # Status is None, so skip the first pass
        _installed = __salt__["pkg.version"](pkg, use_context=False)
        if _installed:
            version = _installed
            __context__["beacon.pkg"][pkg] = "installed"

            _latest = __salt__["pkg.latest_version"](pkg, refresh=_refresh)
            if _latest:
                version = _latest
                __context__["beacon.pkg"][pkg] = "upgrade"
        else:
            __context__["beacon.pkg"][pkg] = "not-installed"
            version = None

        if status:
            if __context__["beacon.pkg"][pkg] != status:
                _pkg = {
                    "pkg": pkg,
                    "version": version,
                    "status": __context__["beacon.pkg"][pkg],
                }
                ret.append(_pkg)
    return ret
