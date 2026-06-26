"""
Send events based on process status.

The config below sets up beacons to check that
processes are running or stopped. If there are multiple
instances of a process running, you may specify which
user's process to watch (good example would be
IIS App Pools).

.. code-block:: yaml

    beacons:
      ps:
        processes:
          - powershell.exe:
             status: running
          - w3svc.exe:
             status: running
             username: "DOMAIN\\username1"
          - mysql:
             status: stopped

"""

import logging

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

log = logging.getLogger(__name__)

__virtualname__ = "ps"
__accepted_statuses__ = ["sleeping", "idle", "running", "stopped"]


def __virtual__():
    if not HAS_PSUTIL:
        err_msg = "psutil library is missing."
        log.error("Unable to load %s beacon: %s", __virtualname__, err_msg)
        return False, err_msg
    return __virtualname__


def validate(config):
    """
    Validate the beacon configuration
    """
    # Configuration for ps beacon should be a dictionary with a 'processes' key
    if not isinstance(config, dict):
        return (
            False,
            "Configuration for ps beacon must be a dictionary with key 'processes' that contains a list.",
        )

    if "processes" not in config:
        return False, "Configuration for ps beacon requires processes."

    if not isinstance(config["processes"], list):
        return False, "Processes for ps beacon must be a list."

    for entry in config["processes"]:
        proc_config = next(iter(entry.values()))
        status = proc_config.get("status", "")
        if status not in __accepted_statuses__:
            return (
                False,
                f"Status not supported, currently supported are {', '.join(__accepted_statuses__)}.",
            )

    return True, "Valid beacon configuration"


def beacon(config):
    """
    Search for given process(es) by name and optionally username.
    """
    ret = []
    procs = []

    for proc in psutil.process_iter():
        try:
            procs.append(proc)
        except psutil.NoSuchProcess:
            continue

    for process in config.get("processes", []):
        process_name = next(iter(process.keys()))
        proc_config = process[process_name]
        expected_status = proc_config.get("status", "running")

        found = [p for p in procs if _safe_name(p) == process_name]

        # Skip if the expected status condition is not met
        if (found and expected_status == "stopped") or (
            not found and expected_status == "running"
        ):
            continue

        current_result = {process_name: {}}
        username = proc_config.get("username", "")

        if username:
            found = [
                p
                for p in procs
                if _safe_name(p) == process_name and _safe_username(p) == username
            ]

        current_result[process_name]["status"] = "running" if found else "stopped"

        current_result[process_name]["instances"] = (
            sorted(map(_context_pull_props, found), key=lambda x: x[0]) if found else []
        )

        ret.append(current_result)

    return sorted(ret, key=lambda x: list(x.keys()))


def _safe_name(proc):
    """Return process name, or empty string if unavailable."""
    try:
        return proc.name()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return ""


def _safe_username(proc):
    """Return process username, or empty string if unavailable."""
    try:
        return proc.username()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return ""


def _context_pull_props(proc):
    """
    Retrieve process properties.

    Uses ``oneshot()`` to cache multiple attributes in a single call.
    See https://psutil.readthedocs.io/en/latest/#psutil.Process.oneshot
    """
    with proc.oneshot():
        return (proc.pid, proc.username(), proc.create_time())
