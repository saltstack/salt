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
from typing import Any

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

log = logging.getLogger(__name__)

__virtualname__ = "ps"
__accepted_statuses__ = ["sleeping", "idle", "running", "stopped"]


def __virtual__() -> str | tuple[bool, str]:
    if not HAS_PSUTIL:
        err_msg = "psutil library is missing."
        log.error("Unable to load %s beacon: %s", __virtualname__, err_msg)
        return False, err_msg
    return __virtualname__


def validate(config: dict[str, Any]) -> tuple[bool, str]:
    """
    Validate the beacon configuration

    :param config: Beacon configuration dictionary. Must contain a ``processes``
        key whose value is a list of single-key dicts. Each entry maps a process
        name to a dict with a required ``status`` key (one of
        ``sleeping``, ``idle``, ``running``, ``stopped``) and an optional
        ``username`` key.
    :type config: dict
    :returns: ``(True, "Valid beacon configuration")`` or ``(False, <reason>)``.
    :rtype: tuple(bool, str)
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


def beacon(config: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Search for given process(es) by name and optionally username, and return
    their status along with per-instance details.

    .. versionchanged:: 3009.0
        The ``processes`` config key now accepts a list of single-key dicts
        (each mapping a process name to a sub-dict with ``status`` and an
        optional ``username``) instead of a flat ``process_name: running``
        mapping.  Each matched entry in the return value now includes
        ``username`` and ``create_time`` in the instance tuples.

    :param config: Beacon configuration dictionary. Must contain a
        ``processes`` key (see :func:`validate` for the expected structure).
    :type config: dict

    Example Config

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

    The ``username`` key is optional. When present only instances running
    under that user are returned; when absent all instances are returned.

    The beacon fires only when the observed state matches the configured
    ``status``.  For example, a ``status: running`` entry is included in
    the return value only when at least one matching process is found;
    a ``status: stopped`` entry is included only when no matching process
    is found.

    :returns: A sorted list of dicts, one per matched process entry.  Each
        dict maps the process name to a sub-dict with:

        ``status``
            ``"running"`` or ``"stopped"``.

        ``instances``
            A list of ``(pid, username, create_time)`` tuples, sorted by
            PID.  Empty when ``status`` is ``"stopped"``.

    :rtype: list[dict]
    """
    ret: list[dict[str, Any]] = []
    procs: list[Any] = []

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

        current_result: dict[str, Any] = {process_name: {}}
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


def _safe_name(proc: Any) -> str:
    """Return process name, or empty string if unavailable."""
    try:
        return proc.name()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return ""


def _safe_username(proc: Any) -> str:
    """Return process username, or empty string if unavailable."""
    try:
        return proc.username()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return ""


def _context_pull_props(proc: Any) -> tuple[int, str, float]:
    """
    Retrieve process properties.

    Uses ``oneshot()`` to cache multiple attributes in a single call.
    See https://psutil.readthedocs.io/en/latest/#psutil.Process.oneshot

    :param proc: A :class:`psutil.Process` instance.
    :returns: A ``(pid, username, create_time)`` tuple.
    :rtype: tuple(int, str, float)
    """
    with proc.oneshot():
        return (proc.pid, proc.username(), proc.create_time())
