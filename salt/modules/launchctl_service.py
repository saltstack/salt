"""
Module for the management of MacOS systems that use launchd/launchctl

.. important::
    If you feel that Salt should be using this module to manage services on a
    minion, and it is using a different module (or gives an error similar to
    *'service.start' is not available*), see :ref:`here
    <module-provider-override>`.

:depends:   - plistlib Python module
"""

import fnmatch
import logging
import os
import plistlib
import re

import salt.utils.data
import salt.utils.decorators as decorators
import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils
from salt.utils.versions import Version

# Set up logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "service"

BEFORE_YOSEMITE = True


def __virtual__():
    """
    Only work on MacOS
    """
    if not salt.utils.platform.is_darwin():
        return (
            False,
            "Failed to load the mac_service module:\nOnly available on macOS systems.",
        )

    if not os.path.exists("/bin/launchctl"):
        return (
            False,
            "Failed to load the mac_service module:\n"
            'Required binary not found: "/bin/launchctl"',
        )

    if Version(__grains__["osrelease"]) >= Version("10.11"):
        return (
            False,
            "Failed to load the mac_service module:\n"
            "Not available on El Capitan, uses mac_service.py",
        )

    if Version(__grains__["osrelease"]) >= Version("10.10"):
        global BEFORE_YOSEMITE
        BEFORE_YOSEMITE = False

    return __virtualname__


def _launchd_paths():
    """
    Paths where launchd services can be found
    """
    return [
        "/Library/LaunchAgents",
        "/Library/LaunchDaemons",
        "/System/Library/LaunchAgents",
        "/System/Library/LaunchDaemons",
    ]


@decorators.memoize
def _available_services():
    """
    Return a dictionary of all available services on the system
    """
    available_services = dict()
    for launch_dir in _launchd_paths():
        for root, dirs, files in salt.utils.path.os_walk(launch_dir):
            for filename in files:
                file_path = os.path.join(root, filename)
                # Follow symbolic links of files in _launchd_paths
                true_path = os.path.realpath(file_path)
                # ignore broken symlinks
                if not os.path.exists(true_path):
                    continue

                try:
                    # This assumes most of the plist files
                    # will be already in XML format
                    with salt.utils.files.fopen(file_path):
                        plist = plistlib.readPlist(salt.utils.data.decode(true_path))

                except Exception:  # pylint: disable=broad-except
                    # If plistlib is unable to read the file we'll need to use
                    # the system provided plutil program to do the conversion
                    cmd = f'/usr/bin/plutil -convert xml1 -o - -- "{true_path}"'
                    plist_xml = __salt__["cmd.run_all"](cmd, python_shell=False)[
                        "stdout"
                    ]
                    plist = plistlib.readPlistFromBytes(
                        salt.utils.stringutils.to_bytes(plist_xml)
                    )

                try:
                    available_services[plist.Label.lower()] = {
                        "filename": filename,
                        "file_path": true_path,
                        "plist": plist,
                    }
                except AttributeError:
                    # As of MacOS 10.12 there might be plist files without Label key
                    # in the searched directories. As these files do not represent
                    # services, thay are not added to the list.
                    pass

    return available_services


def _service_by_name(name):
    """
    Return the service info for a service by label, filename or path
    """
    services = _available_services()
    name = name.lower()

    if name in services:
        # Match on label
        return services[name]

    for service in services.values():
        if service["file_path"].lower() == name:
            # Match on full path
            return service
        basename, ext = os.path.splitext(service["filename"])
        if basename.lower() == name:
            # Match on basename
            return service

    return False


def get_all():
    """
    Return all installed services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_all
    """
    cmd = "launchctl list"

    service_lines = [
        line
        for line in __salt__["cmd.run"](cmd).splitlines()
        if not line.startswith("PID")
    ]

    service_labels_from_list = [line.split("\t")[2] for line in service_lines]
    service_labels_from_services = list(_available_services().keys())

    return sorted(set(service_labels_from_list + service_labels_from_services))


def _get_launchctl_data(job_label, runas=None):
    if BEFORE_YOSEMITE:
        cmd = f"launchctl list -x {job_label}"
    else:
        cmd = f"launchctl list {job_label}"

    launchctl_data = __salt__["cmd.run_all"](cmd, python_shell=False, runas=runas)

    if launchctl_data["stderr"]:
        # The service is not loaded, further, it might not even exist
        # in either case we didn't get XML to parse, so return an empty
        # dict
        return None

    return launchctl_data["stdout"]


def available(job_label):
    """
    Check that the given service is available.

    CLI Example:

    .. code-block:: bash

        salt '*' service.available com.openssh.sshd
    """
    return True if _service_by_name(job_label) else False


def missing(job_label):
    """
    The inverse of service.available
    Check that the given service is not available.

    CLI Example:

    .. code-block:: bash

        salt '*' service.missing com.openssh.sshd
    """
    return False if _service_by_name(job_label) else True


def status(name, runas=None):
    """
    Return the status for a service via systemd.
    If the name contains globbing, a dict mapping service name to True/False
    values is returned.

    .. versionchanged:: 2018.3.0
        The service name can now be a glob (e.g. ``salt*``)

    Args:
        name (str): The name of the service to check
        runas (str): User to run launchctl commands

    Returns:
        bool: True if running, False otherwise
        dict: Maps service name to True if running, False otherwise

    CLI Example:

    .. code-block:: bash

        salt '*' service.status <service name>
    """

    contains_globbing = bool(re.search(r"\*|\?|\[.+\]", name))
    if contains_globbing:
        services = fnmatch.filter(get_all(), name)
    else:
        services = [name]
    results = {}
    for service in services:
        service_info = _service_by_name(service)

        lookup_name = service_info["plist"]["Label"] if service_info else service
        launchctl_data = _get_launchctl_data(lookup_name, runas=runas)

        if launchctl_data:
            if BEFORE_YOSEMITE:
                results[service] = "PID" in plistlib.loads(launchctl_data)
            else:
                pattern = '"PID" = [0-9]+;'
                results[service] = True if re.search(pattern, launchctl_data) else False
        else:
            results[service] = False
    if contains_globbing:
        return results
    return results[name]


def stop(job_label, runas=None):
    """
    Stop the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service label>
        salt '*' service.stop org.ntp.ntpd
        salt '*' service.stop /System/Library/LaunchDaemons/org.ntp.ntpd.plist
    """
    service = _service_by_name(job_label)
    if service:
        cmd = "launchctl unload -w {}".format(service["file_path"], runas=runas)
        return not __salt__["cmd.retcode"](cmd, runas=runas, python_shell=False)

    return False


def start(job_label, runas=None):
    """
    Start the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.start <service label>
        salt '*' service.start org.ntp.ntpd
        salt '*' service.start /System/Library/LaunchDaemons/org.ntp.ntpd.plist
    """
    service = _service_by_name(job_label)
    if service:
        cmd = "launchctl load -w {}".format(service["file_path"], runas=runas)
        return not __salt__["cmd.retcode"](cmd, runas=runas, python_shell=False)

    return False


def restart(job_label, runas=None):
    """
    Restart the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service label>
    """
    stop(job_label, runas=runas)
    return start(job_label, runas=runas)


def enabled(job_label, runas=None):
    """
    Return True if the named service is enabled, false otherwise

    CLI Example:

    .. code-block:: bash

        salt '*' service.enabled <service label>
    """
    overrides_data = dict(
        plistlib.readPlist("/var/db/launchd.db/com.apple.launchd/overrides.plist")
    )
    if overrides_data.get(job_label, False):
        if overrides_data[job_label]["Disabled"]:
            return False
        else:
            return True
    else:
        return False


def disabled(job_label, runas=None):
    """
    Return True if the named service is disabled, false otherwise

    CLI Example:

    .. code-block:: bash

        salt '*' service.disabled <service label>
    """
    overrides_data = dict(
        plistlib.readPlist("/var/db/launchd.db/com.apple.launchd/overrides.plist")
    )
    if overrides_data.get(job_label, False):
        if overrides_data[job_label]["Disabled"]:
            return True
        else:
            return False
    else:
        return True
