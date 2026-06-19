"""
State module for managing Windows PowerShell DSC Resources via
``Invoke-DscResource``.

This module manages individual DSC resources without compiling a MOF file or
involving the Local Configuration Manager (LCM). Salt controls the idempotency:
it calls the resource's ``Test`` method first, and only calls ``Set`` if a
change is needed.

Use the ``psget`` module to install DSC resource modules from the PowerShell
Gallery before referencing them in states.

Example:

.. code-block:: yaml

    ensure_web_server:
      dsc_resource.managed:
        - name: WindowsFeature
        - module_name: PSDesiredStateConfiguration
        - properties:
            Name: Web-Server
            Ensure: Present

    remove_telnet:
      dsc_resource.managed:
        - name: WindowsFeature
        - module_name: PSDesiredStateConfiguration
        - properties:
            Name: Telnet-Client
            Ensure: Absent

    create_config_file:
      dsc_resource.managed:
        - name: File
        - module_name: PSDesiredStateConfiguration
        - properties:
            DestinationPath: C:\\App\\config.txt
            Ensure: Present
            Contents: managed by Salt

.. versionadded:: 3008.1
"""

import logging

import salt.utils.data
import salt.utils.platform
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

__virtualname__ = "dsc_resource"


def __virtual__():
    """
    Only load on Windows.
    """
    if salt.utils.platform.is_windows():
        return __virtualname__
    return False, "DSC Resource: Only available on Windows systems"


def _normalize_str_values(data):
    """
    Recursively lowercase all string keys and values in a dict.

    DSC property names and values are case-insensitive (e.g. ``"Ensure"`` and
    ``"ensure"`` refer to the same property, ``"Present"`` and ``"present"``
    are the same value), but Python string comparison is not. Normalizing both
    keys and values before calling ``recursive_diff`` prevents case-only
    differences — such as pillar-supplied lowercase keys vs. DSC's capitalized
    output — from appearing as spurious changes in the state diff.
    """
    if isinstance(data, dict):
        return {
            (k.lower() if isinstance(k, str) else k): _normalize_str_values(v)
            for k, v in data.items()
        }
    if isinstance(data, str):
        return data.lower()
    return data


def managed(name, module_name, properties):
    r"""
    Ensure a DSC resource is in the desired state.

    Calls ``dsc_resource.test`` to check whether changes are needed. If the
    resource is already in the desired state, returns immediately with no
    changes. Otherwise calls ``dsc_resource.set`` to apply the configuration,
    then verifies the result with another ``dsc_resource.test`` call.

    The ``changes`` dictionary uses the actual before and after values returned
    by ``dsc_resource.get``, giving a real diff of the resource properties.

    Args:

        name (str):
            The name of the DSC resource to manage, for example
            ``WindowsFeature`` or ``File``. This also serves as the state ID.
            Required.

        module_name (str):
            The name of the PowerShell module that contains the resource. For
            built-in resources use ``PSDesiredStateConfiguration``. Required.

        properties (dict):
            A dictionary of the desired resource properties. The required and
            optional keys vary by DSC resource. Required.

    Returns:
        dict: A standard Salt state return with ``name``, ``result``,
        ``changes``, and ``comment`` keys.

        ``result`` values:

        - ``True``  — no changes were needed, or changes were applied
          successfully.
        - ``None``  — running in test mode and changes would be made.
        - ``False`` — an error occurred or changes could not be verified.

    CLI Example:

    .. code-block:: yaml

        install_iis:
          dsc_resource.managed:
            - name: WindowsFeature
            - module_name: PSDesiredStateConfiguration
            - properties:
                Name: Web-Server
                Ensure: Present

    .. code-block:: yaml

        write_hosts_entry:
          dsc_resource.managed:
            - name: File
            - module_name: PSDesiredStateConfiguration
            - properties:
                DestinationPath: C:\\Temp\\hello.txt
                Ensure: Present
                Contents: Hello from Salt

    .. versionadded:: 3008.1
    """
    ret = {"name": name, "result": False, "changes": {}, "comment": ""}

    # Capture current state for before/after reporting
    try:
        old_state = __salt__["dsc_resource.get"](name, module_name, properties)
    except CommandExecutionError as exc:
        ret["comment"] = f"Failed to get state of DSC resource {name!r}: {exc}"
        return ret

    # Check whether changes are needed
    try:
        in_desired_state = __salt__["dsc_resource.test"](name, module_name, properties)
    except CommandExecutionError as exc:
        ret["comment"] = f"Failed to test DSC resource {name!r}: {exc}"
        return ret

    if in_desired_state:
        ret["result"] = True
        ret["comment"] = f"DSC resource {name!r} is already in the desired state."
        return ret

    # Test mode: report what would change without applying
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"DSC resource {name!r} would be applied."
        ret["changes"] = salt.utils.data.recursive_diff(
            _normalize_str_values(old_state), _normalize_str_values(properties)
        )
        return ret

    # Apply the resource
    try:
        __salt__["dsc_resource.set"](name, module_name, properties)
    except CommandExecutionError as exc:
        ret["comment"] = f"Failed to apply DSC resource {name!r}: {exc}"
        return ret

    # Verify the change took effect and collect the new state
    try:
        in_desired_state = __salt__["dsc_resource.test"](name, module_name, properties)
        new_state = __salt__["dsc_resource.get"](name, module_name, properties)
    except CommandExecutionError as exc:
        ret["comment"] = f"Failed to verify DSC resource {name!r}: {exc}"
        return ret

    if in_desired_state:
        ret["result"] = True
        ret["changes"] = salt.utils.data.recursive_diff(
            _normalize_str_values(old_state), _normalize_str_values(new_state)
        )
        ret["comment"] = f"DSC resource {name!r} applied successfully."
    else:
        ret["result"] = False
        ret["comment"] = f"Failed to apply DSC resource {name!r}."

    return ret
