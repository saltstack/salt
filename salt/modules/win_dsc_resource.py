"""
Module for invoking individual PowerShell DSC Resources directly using
``Invoke-DscResource``.

This module allows Salt to apply, test, and retrieve the state of any
installed PowerShell DSC resource without compiling a MOF file or involving
the Local Configuration Manager (LCM).

Use the ``psget`` module to install DSC resource modules from the PowerShell
Gallery before using them here.

.. versionadded:: 3008.1

:depends:
    - pythonnet
    - PowerShell 5.0
"""

import logging

import salt.utils.platform
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)

__virtualname__ = "dsc_resource"

__func_alias__ = {
    "set_": "set",
}

try:
    from salt.utils.win_pwsh import HAS_CLR, HAS_PWSH_SDK, PowerShellSession
except ImportError:
    HAS_CLR = False
    HAS_PWSH_SDK = False


def __virtual__():
    """
    Only load on Windows with pythonnet and the PowerShell SDK available.
    """
    if not salt.utils.platform.is_windows():
        return False, "DSC Resource: Only available on Windows systems"
    if not HAS_CLR:
        return False, "DSC Resource: Requires pythonnet (pip install pythonnet)"
    if not HAS_PWSH_SDK:
        return (
            False,
            "DSC Resource: Requires the PowerShell SDK"
            " (System.Management.Automation)",
        )
    return __virtualname__


def _ps_value(value):
    """
    Convert a single Python value to its PowerShell literal representation.

    Type mappings:

    - ``bool``            -> ``$true`` / ``$false``
    - ``int`` / ``float`` -> bare number
    - ``None``            -> ``$null``
    - ``dict``            -> ``@{Key = Value}`` (recursive)
    - ``list``            -> ``@(item, ...)`` with each element typed (recursive)
    - ``str``             -> ``'value'`` with internal single-quotes doubled

    Args:
        value: The value to convert.

    Returns:
        str: The PowerShell literal for *value*.
    """
    if isinstance(value, bool):
        return "$true" if value else "$false"
    if isinstance(value, (int, float)):
        return str(value)
    if value is None:
        return "$null"
    if isinstance(value, dict):
        return _dict_to_ps_hashtable(value)
    if isinstance(value, list):
        items = ", ".join(_ps_value(item) for item in value)
        return f"@({items})"
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def _dict_to_ps_hashtable(data):
    """
    Convert a Python dict to a PowerShell ``@{Key = Value}`` hashtable string.

    Delegates per-value conversion to :func:`_ps_value`, which handles bools,
    numbers, ``None``, nested dicts, lists (with full type support per element),
    and strings. Supported property types:

    - Scalar: ``str``, ``int``, ``float``, ``bool``, ``None``
    - Array: ``list`` of any of the above, or of nested ``dict``
    - Nested hashtable: ``dict``

    Args:
        data (dict): The dictionary to convert.

    Returns:
        str: A PowerShell hashtable string, e.g. ``@{Name = 'foo'; Count = 1}``.
    """
    parts = [f"'{_ps_quote(key)}' = {_ps_value(value)}" for key, value in data.items()]
    return "@{" + "; ".join(parts) + "}"


def _ps_quote(s):
    """
    Escape a string for safe interpolation inside a PowerShell single-quoted
    string by doubling any embedded single-quote characters.

    Args:
        s (str): The string to escape.

    Returns:
        str: The escaped string (without surrounding quotes).
    """
    return str(s).replace("'", "''")


def get(name, module_name, properties):
    r"""
    Return the current state of a DSC resource by calling
    ``Invoke-DscResource -Method Get``.

    Args:

        name (str):
            The name of the DSC resource to query. For example,
            ``WindowsFeature`` or ``File``. Required.

        module_name (str):
            The name of the PowerShell module that contains the resource. For
            built-in resources use ``PSDesiredStateConfiguration``. Required.

        properties (dict):
            A dictionary of resource properties sufficient to identify the
            resource instance. The required keys vary by resource. Required.

    Returns:
        dict: A dictionary of the resource's current property values as
        reported by the DSC resource's ``Get`` method.

    Raises:
        CommandExecutionError: If the PowerShell call fails.
        SaltInvocationError: If required arguments are missing or invalid.

    CLI Example:

    .. code-block:: bash

        salt '*' dsc_resource.get File PSDesiredStateConfiguration \
            properties="{'DestinationPath': 'C:\\Temp\\test.txt', 'Ensure': 'Present'}"

    .. code-block:: bash

        salt '*' dsc_resource.get WindowsFeature PSDesiredStateConfiguration \
            properties="{'Name': 'Web-Server', 'Ensure': 'Present'}"

    .. versionadded:: 3008.1
    """
    if not name:
        raise SaltInvocationError("name is required")
    if not module_name:
        raise SaltInvocationError("module_name is required")
    if not isinstance(properties, dict):
        raise SaltInvocationError("properties must be a dict")

    ps_prop = _dict_to_ps_hashtable(properties)
    cmd = (
        f"Invoke-DscResource"
        f" -Name '{_ps_quote(name)}'"
        f" -ModuleName '{_ps_quote(module_name)}'"
        f" -Method Get"
        f" -Property {ps_prop}"
        f" | Select-Object * -ExcludeProperty Cim*, PSComputerName"
    )
    log.debug("DSC Resource get: %s", cmd)
    with PowerShellSession() as session:
        return session.run_json(cmd)


def test(name, module_name, properties):
    r"""
    Test whether a DSC resource is in the desired state by calling
    ``Invoke-DscResource -Method Test``.

    Args:

        name (str):
            The name of the DSC resource to test. Required.

        module_name (str):
            The name of the PowerShell module that contains the resource.
            Required.

        properties (dict):
            A dictionary of the desired resource properties. Required.

    Returns:
        bool: ``True`` if the resource is already in the desired state,
        ``False`` if changes are needed.

    Raises:
        CommandExecutionError: If the PowerShell call fails.
        SaltInvocationError: If required arguments are missing or invalid.

    CLI Example:

    .. code-block:: bash

        salt '*' dsc_resource.test File PSDesiredStateConfiguration \
            properties="{'DestinationPath': 'C:\\Temp\\test.txt', 'Ensure': 'Present'}"

    .. code-block:: bash

        salt '*' dsc_resource.test WindowsFeature PSDesiredStateConfiguration \
            properties="{'Name': 'Web-Server', 'Ensure': 'Present'}"

    .. versionadded:: 3008.1
    """
    if not name:
        raise SaltInvocationError("name is required")
    if not module_name:
        raise SaltInvocationError("module_name is required")
    if not isinstance(properties, dict):
        raise SaltInvocationError("properties must be a dict")

    ps_prop = _dict_to_ps_hashtable(properties)
    cmd = (
        f"(Invoke-DscResource"
        f" -Name '{_ps_quote(name)}'"
        f" -ModuleName '{_ps_quote(module_name)}'"
        f" -Method Test"
        f" -Property {ps_prop}).InDesiredState"
    )
    log.debug("DSC Resource test: %s", cmd)
    with PowerShellSession() as session:
        result = session.run(cmd)
    if isinstance(result, bool):
        return result
    return str(result).lower() == "true"


def set_(name, module_name, properties):
    r"""
    Apply a DSC resource to the desired state by calling
    ``Invoke-DscResource -Method Set``.

    Args:

        name (str):
            The name of the DSC resource to apply. Required.

        module_name (str):
            The name of the PowerShell module that contains the resource.
            Required.

        properties (dict):
            A dictionary of the desired resource properties. Required.

    Returns:
        bool: ``True`` if the resource was applied successfully.

    Raises:
        CommandExecutionError: If the resource failed to apply.
        SaltInvocationError: If required arguments are missing or invalid.

    CLI Example:

    .. code-block:: bash

        salt '*' dsc_resource.set File PSDesiredStateConfiguration \
            properties="{'DestinationPath': 'C:\\Temp\\test.txt', 'Ensure': 'Present', 'Contents': 'hello'}"

    .. code-block:: bash

        salt '*' dsc_resource.set WindowsFeature PSDesiredStateConfiguration \
            properties="{'Name': 'Web-Server', 'Ensure': 'Present'}"

    .. versionadded:: 3008.1
    """
    if not name:
        raise SaltInvocationError("name is required")
    if not module_name:
        raise SaltInvocationError("module_name is required")
    if not isinstance(properties, dict):
        raise SaltInvocationError("properties must be a dict")

    ps_prop = _dict_to_ps_hashtable(properties)
    cmd = (
        f"Invoke-DscResource"
        f" -Name '{_ps_quote(name)}'"
        f" -ModuleName '{_ps_quote(module_name)}'"
        f" -Method Set"
        f" -Property {ps_prop}"
    )
    log.debug("DSC Resource set: %s", cmd)
    with PowerShellSession() as session:
        session.run_strict(cmd)
    return True
