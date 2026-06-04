"""
Module for invoking individual PowerShell DSC Resources directly using
``Invoke-DscResource``.

This module allows Salt to apply, test, and retrieve the state of any
installed PowerShell DSC resource without compiling a MOF file or involving
the Local Configuration Manager (LCM).

Use the ``psget`` module to install DSC resource modules from the PowerShell
Gallery before using them here.

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


def _dict_to_ps_hashtable(data):
    """
    Convert a Python dict to a PowerShell ``@{Key = Value}`` hashtable string.

    Type mappings:

    - ``bool``         → ``$true`` / ``$false``
    - ``int`` / ``float`` → bare number
    - ``None``         → ``$null``
    - ``list``         → ``@('a', 'b')``
    - ``str``          → ``'value'`` with internal single-quotes doubled

    Args:
        data (dict): The dictionary to convert.

    Returns:
        str: A PowerShell hashtable string, e.g. ``@{Name = 'foo'; Count = 1}``.
    """
    parts = []
    for key, value in data.items():
        if isinstance(value, bool):
            ps_value = "$true" if value else "$false"
        elif isinstance(value, (int, float)):
            ps_value = str(value)
        elif value is None:
            ps_value = "$null"
        elif isinstance(value, list):
            items = ", ".join(
                f"'{str(item).replace(chr(39), chr(39) * 2)}'" for item in value
            )
            ps_value = f"@({items})"
        else:
            escaped = str(value).replace("'", "''")
            ps_value = f"'{escaped}'"
        parts.append(f"{key} = {ps_value}")
    return "@{" + "; ".join(parts) + "}"


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
        f" -Name '{name}'"
        f" -ModuleName '{module_name}'"
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
        f" -Name '{name}'"
        f" -ModuleName '{module_name}'"
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
        f" -Name '{name}'"
        f" -ModuleName '{module_name}'"
        f" -Method Set"
        f" -Property {ps_prop}"
    )
    log.debug("DSC Resource set: %s", cmd)
    with PowerShellSession() as session:
        session.run_strict(cmd)
    return True
