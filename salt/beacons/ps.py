r"""
Send events based on process status.

The config below sets up beacons to check that
processes are running or stopped. If there are multiple
instances of a process running, you may specify which
user's process to watch (good example would be
IIS App Pools).

.. code-block:: yaml

    beacons:
      ps:
        - processes:
            - powershell.exe:
                status: running
            - w3svc.exe:
                status: running
                username: 'DOMAIN\username1'
            - mysql:
                status: stopped

"""

import logging
from typing import Any

import salt.utils.beacons

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


def _normalize_processes(processes: Any) -> list[dict[str, dict[str, Any]]] | None:
    """
    Normalize the ``processes`` value to the new list-of-single-key-dicts form.

    Accepts either:

    * the new form, a list of single-key dicts, e.g.
      ``[{"mysql": {"status": "running"}}]``
    * the legacy flat-dict form, e.g. ``{"mysql": "running"}``, which is
      upgraded in-place and a :py:class:`DeprecationWarning`-style log
      message is emitted.

    Returns the normalized list, or ``None`` if the shape can't be
    interpreted.
    """
    if isinstance(processes, list):
        return processes

    if isinstance(processes, dict):
        log.warning(
            "ps beacon: the flat 'processes: {name: status}' config form is "
            "deprecated and will be removed in a future release. Use the new "
            "list form documented in the ps beacon module."
        )
        normalized: list[dict[str, dict[str, Any]]] = []
        for name, value in processes.items():
            if isinstance(value, dict):
                normalized.append({name: value})
            else:
                normalized.append({name: {"status": value}})
        return normalized

    return None


def validate(config: list) -> tuple[bool, str]:
    """
    Validate the beacon configuration

    :param config: Beacon configuration as a list of single-key dicts.
        Must include a ``processes`` key whose value is a list of
        single-key dicts (each mapping a process name to a dict with a
        required ``status`` key, one of ``sleeping``, ``idle``,
        ``running``, ``stopped``, and an optional ``username`` key).
        The legacy ``processes: {name: status}`` flat-dict form is
        still accepted with a deprecation warning.
    :type config: list
    :returns: ``(True, "Valid beacon configuration")`` or ``(False, <reason>)``.
    :rtype: tuple(bool, str)
    """
    # Configuration for ps beacon should be a list of single-key dicts
    # merged by the beacon framework into {"processes": [...]}.
    if not isinstance(config, list):
        return False, "Configuration for ps beacon must be a list."

    merged = salt.utils.beacons.list_to_dict(config)

    if "processes" not in merged:
        return False, "Configuration for ps beacon requires processes."

    normalized = _normalize_processes(merged["processes"])
    if normalized is None:
        return False, "Processes for ps beacon must be a list."

    for entry in normalized:
        if not isinstance(entry, dict) or len(entry) != 1:
            return False, "Each process entry for ps beacon must be a single-key dict."
        proc_config = next(iter(entry.values()))
        if not isinstance(proc_config, dict):
            return False, "Each process entry value must be a dict with a 'status' key."
        status = proc_config.get("status", "")
        if status not in __accepted_statuses__:
            return (
                False,
                f"Status not supported, currently supported are {', '.join(__accepted_statuses__)}.",
            )

    return True, "Valid beacon configuration"


def beacon(config: list) -> list[dict[str, Any]]:
    r"""
    Search for given process(es) by name and optionally username, and return
    their status along with per-instance details.

    .. versionchanged:: 3009.0
        The ``processes`` config key now accepts a list of single-key dicts
        (each mapping a process name to a sub-dict with ``status`` and an
        optional ``username``) instead of a flat ``process_name: running``
        mapping.  The legacy flat-dict form is still accepted with a
        deprecation warning. Each matched entry in the return value now
        includes ``username`` and ``create_time`` in the instance tuples.

    :param config: Beacon configuration as a list of single-key dicts.
        See :func:`validate` for the expected structure.
    :type config: list

    Example Config

    .. code-block:: yaml

        beacons:
          ps:
            - processes:
                - powershell.exe:
                    status: running
                - w3svc.exe:
                    status: running
                    username: 'DOMAIN\username1'
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

    merged = salt.utils.beacons.list_to_dict(config) if isinstance(config, list) else {}
    processes = _normalize_processes(merged.get("processes", [])) or []

    for proc in psutil.process_iter():
        try:
            procs.append(proc)
        except psutil.NoSuchProcess:
            continue

    for process in processes:
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

    .. versionadded:: 3009.0

    Uses ``oneshot()`` to cache multiple attributes in a single call.
    See https://psutil.readthedocs.io/en/latest/#psutil.Process.oneshot

    :param proc: A :class:`psutil.Process` instance.
    :returns: A ``(pid, username, create_time)`` tuple.
    :rtype: tuple(int, str, float)
    """
    with proc.oneshot():
        return (proc.pid, proc.username(), proc.create_time())
