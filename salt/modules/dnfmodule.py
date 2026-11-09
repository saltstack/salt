"""
Support for managing DNF modules (modularity / AppStreams)

DNF modularity (also known as AppStreams) was introduced in RHEL 8 and is
available on RHEL/CentOS/Rocky/Alma/Oracle Linux 8 and 9, where it allows
multiple versions of the same software to be shipped within a single
repository. This module wraps the ``dnf module`` sub-command to enable,
disable, install, remove and reset module streams in a Pythonic, idempotent
way instead of resorting to :py:func:`cmd.run <salt.modules.cmdmod.run>`.

.. note::
    Modularity is a feature of DNF (``dnf``/``dnf4``) only. It is not provided
    by ``yum``, ``tdnf`` or ``dnf5`` (modularity was dropped in ``dnf5``), so
    this module is confined to systems where the ``dnf`` binary is present.

.. versionadded:: 3008.0
"""

import logging
import re

import salt.utils.environment
import salt.utils.path
import salt.utils.systemd
from salt.exceptions import CommandExecutionError, SaltInvocationError

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "dnfmodule"

__func_alias__ = {"list_": "list"}


def __virtual__():
    """
    Confine this module to DNF based systems that provide modularity.
    """
    try:
        os_family = __grains__["os_family"].lower()
    except (KeyError, AttributeError):
        return (False, "Module dnfmodule: no RedHat based system detected")

    if os_family != "redhat":
        return (False, "Module dnfmodule: only available on RedHat based systems")

    if _dnf() is None:
        return (
            False,
            "Module dnfmodule: the 'dnf' binary is required for module management",
        )

    return __virtualname__


def _dnf():
    """
    Return the path to the ``dnf`` binary, or ``None`` if it is not available.

    Modularity is implemented by ``dnf`` (a.k.a. ``dnf4``) only, so ``dnf5``,
    ``yum`` and ``tdnf`` are intentionally not considered here.
    """
    return salt.utils.path.which("dnf")


def _call_dnf(args, **kwargs):
    """
    Run a ``dnf`` command and return the ``cmd.run_all`` result dictionary.
    """
    params = {
        "output_loglevel": "trace",
        "python_shell": False,
        "env": salt.utils.environment.get_module_environment(globals()),
    }
    params.update(kwargs)

    cmd = []
    if salt.utils.systemd.has_scope(__context__) and __salt__["config.get"](
        "systemd.scope", True
    ):
        cmd.extend(["systemd-run", "--scope"])
    cmd.append(_dnf())
    cmd.extend(args)

    return __salt__["cmd.run_all"](cmd, **params)


def _parse_module_list(output):
    """
    Parse the table produced by ``dnf module list`` into a list of dicts.

    ``dnf module list`` groups its output under per-repository headers, each
    followed by a ``Name  Stream  Profiles  Summary`` column header. Only the
    rows that follow a column header (and precede the next blank line) are
    actual module rows; everything else (metadata notices, repository headers
    and the trailing hint) is ignored.
    """
    modules = []
    in_table = False
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            # A blank line terminates the current per-repository table.
            in_table = False
            continue
        low = stripped.lower()
        if low.startswith("name") and "stream" in low and "profiles" in low:
            in_table = True
            continue
        if low.startswith("hint:"):
            in_table = False
            continue
        if not in_table:
            # Repository header or metadata noise.
            continue

        parts = stripped.split()
        if len(parts) < 2:
            continue
        name = parts[0]
        stream = parts[1]

        # Collect the ``[d][e][x]`` markers that immediately follow the stream.
        rest = parts[2:]
        stream_markers = ""
        while rest and re.fullmatch(r"(\[[a-z]\])+", rest[0]):
            stream_markers += rest.pop(0)
        line_markers = re.findall(r"\[([a-z])\]", stripped)

        modules.append(
            {
                "name": name,
                "stream": stream,
                "profiles": " ".join(rest[:-1]) if len(rest) > 1 else "",
                "summary": rest[-1] if rest else "",
                "default": "d" in stream_markers,
                "enabled": "e" in stream_markers,
                "disabled": "x" in stream_markers,
                "installed": "i" in line_markers,
            }
        )
    return modules


def list_(name=None, enabled=False, disabled=False, installed=False):
    """
    Return the modules known to DNF as a list of dictionaries.

    Each dictionary contains the ``name``, ``stream``, ``profiles`` and
    ``summary`` of the module as well as the ``default``, ``enabled``,
    ``disabled`` and ``installed`` boolean flags.

    name
        Limit the listing to the named module (a module name, optionally with a
        ``:stream`` suffix).

    enabled
        Only list modules that have an enabled stream
        (``dnf module list --enabled``).

    disabled
        Only list modules that have a disabled stream
        (``dnf module list --disabled``).

    installed
        Only list modules that have an installed profile
        (``dnf module list --installed``).

    CLI Examples:

    .. code-block:: bash

        salt '*' dnfmodule.list
        salt '*' dnfmodule.list nodejs
        salt '*' dnfmodule.list enabled=True
    """
    cmd = ["--quiet", "module", "list"]
    if enabled:
        cmd.append("--enabled")
    if disabled:
        cmd.append("--disabled")
    if installed:
        cmd.append("--installed")
    if name:
        # Drop any stream so the listing matches the whole module.
        cmd.append(name.split(":", 1)[0])

    out = _call_dnf(cmd, ignore_retcode=True)
    return _parse_module_list(out["stdout"])


def _split_name(name):
    """
    Split ``module[:stream]`` into a ``(module, stream)`` tuple. ``stream`` is
    ``None`` when no stream was supplied.
    """
    if not name:
        raise SaltInvocationError("A module name is required")
    module, _, stream = name.partition(":")
    # ``name`` may also carry a ``/profile`` suffix (module:stream/profile).
    stream = stream.split("/", 1)[0]
    return module, (stream or None)


def is_enabled(name):
    """
    Return ``True`` if the given module (and stream, if specified) currently has
    an enabled stream.

    name
        The module name, optionally with a ``:stream`` suffix
        (e.g. ``nodejs`` or ``nodejs:18``).

    CLI Example:

    .. code-block:: bash

        salt '*' dnfmodule.is_enabled nodejs:18
    """
    module, stream = _split_name(name)
    for entry in list_(name=module):
        if (
            entry["name"] == module
            and entry["enabled"]
            and (stream is None or entry["stream"] == stream)
        ):
            return True
    return False


def is_disabled(name):
    """
    Return ``True`` if the given module currently has a disabled stream.

    name
        The module name, optionally with a ``:stream`` suffix.

    CLI Example:

    .. code-block:: bash

        salt '*' dnfmodule.is_disabled nodejs
    """
    module, stream = _split_name(name)
    for entry in list_(name=module):
        if (
            entry["name"] == module
            and entry["disabled"]
            and (stream is None or entry["stream"] == stream)
        ):
            return True
    return False


def is_installed(name):
    """
    Return ``True`` if the given module currently has an installed profile.

    name
        The module name, optionally with a ``:stream`` suffix.

    CLI Example:

    .. code-block:: bash

        salt '*' dnfmodule.is_installed nodejs:18
    """
    module, stream = _split_name(name)
    for entry in list_(name=module):
        if (
            entry["name"] == module
            and entry["installed"]
            and (stream is None or entry["stream"] == stream)
        ):
            return True
    return False


def enabled_stream(name):
    """
    Return the stream that is currently enabled for the given module, or
    ``None`` if the module has no enabled stream. Only one stream of a module
    can be enabled at a time.

    name
        The module name (any ``:stream`` suffix is ignored).

    CLI Example:

    .. code-block:: bash

        salt '*' dnfmodule.enabled_stream nodejs
    """
    module, _ = _split_name(name)
    for entry in list_(name=module):
        if entry["name"] == module and entry["enabled"]:
            return entry["stream"]
    return None


def _run_action(action, name):
    """
    Run ``dnf -y module <action> <name>`` and return ``True`` on success.
    """
    if not name:
        raise SaltInvocationError("A module name is required")
    out = _call_dnf(["-y", "module", action, name])
    if out["retcode"] != 0:
        raise CommandExecutionError(
            f"Failed to {action} module '{name}'",
            info={"result": out},
        )
    return True


def enable(name, switch=False):
    """
    Enable a module stream. Enabling a stream makes the packages from that
    stream available for installation but does not install them.

    name
        The module name with the stream to enable (e.g. ``nodejs:18``). If no
        stream is given, the default stream is enabled.

    switch
        DNF refuses to enable a stream while a *different* stream of the same
        module is already enabled. When ``False`` (the default) a clear error
        is raised describing the conflict rather than DNF's raw multi-line
        message. When ``True`` the module is reset first and the requested
        stream is then enabled, switching the enabled stream.

    CLI Examples:

    .. code-block:: bash

        salt '*' dnfmodule.enable nodejs:18
        salt '*' dnfmodule.enable nodejs:18 switch=True
    """
    module, requested = _split_name(name)
    current = enabled_stream(module)
    if current is not None and requested is not None and current != requested:
        if not switch:
            raise CommandExecutionError(
                f"Module '{module}' already has stream '{current}' enabled; "
                f"refusing to switch to stream '{requested}'. Reset the module "
                f"first ('dnfmodule.reset {module}') or pass switch=True."
            )
        reset(module)
    return _run_action("enable", name)


def disable(name):
    """
    Disable a module. All of the module's streams become unavailable and any
    enabled stream is reset.

    name
        The module name to disable (e.g. ``nodejs``).

    CLI Example:

    .. code-block:: bash

        salt '*' dnfmodule.disable nodejs
    """
    return _run_action("disable", name)


def install(name):
    """
    Install a module profile. This enables the corresponding stream (if it is
    not already enabled) and installs the profile's packages.

    name
        The module to install, optionally with a stream and/or profile
        (e.g. ``nodejs:18`` or ``nodejs:18/common``).

    CLI Example:

    .. code-block:: bash

        salt '*' dnfmodule.install nodejs:18/common
    """
    return _run_action("install", name)


def remove(name):
    """
    Remove the installed packages of a module profile. The stream remains
    enabled; use :py:func:`reset` or :py:func:`disable` to change the stream.

    name
        The module to remove, optionally with a stream and/or profile.

    CLI Example:

    .. code-block:: bash

        salt '*' dnfmodule.remove nodejs:18/common
    """
    return _run_action("remove", name)


def reset(name):
    """
    Reset a module to its initial state, neither enabled nor disabled. The
    default stream (if any) becomes effective again.

    name
        The module name to reset (e.g. ``nodejs``).

    CLI Example:

    .. code-block:: bash

        salt '*' dnfmodule.reset nodejs
    """
    return _run_action("reset", name)
