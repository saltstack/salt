"""
Manage licensing for products using Windows Software Licensing Service via PowerShell CIM.

Supports management of Windows OS, Microsoft Office, and other Microsoft products
that use the Software Licensing Service (KMS and MAK activation).

Requires Windows 7 / Windows Server 2008 R2 or later.
Replaces the previous slmgr.vbs-based implementation.

.. versionchanged:: 3008.2
    Reimplemented using PowerShell CIM instead of slmgr.vbs (VBScript).
    Now supports managing any product using the Software Licensing Service,
    not just Windows OS.

.. code-block:: bash

    salt '*' license.install XXXXX-XXXXX-XXXXX-XXXXX-XXXXX
"""

import logging

import salt.exceptions
import salt.utils.platform
import salt.utils.win_pwsh

log = logging.getLogger(__name__)
__virtualname__ = "license"


def __virtual__():
    """
    Only works on Windows with PowerShell 3.0+
    """
    if not salt.utils.platform.is_windows():
        return (False, "Module win_license: module only works on Windows systems.")
    return __virtualname__


def _get_license_product(product_key=None):
    """
    Query CIM for a license product.

    If product_key is provided, returns that specific product.
    If product_key is None, returns the Windows OS product if available,
    otherwise returns the first installed product.

    Args:
        product_key (str): Optional product key to look up (searches last 5 digits).
                          If None, prioritizes Windows OS product.

    Returns:
        dict: Product information or None if not found.
    """
    if product_key:
        partial_key = product_key[-5:]
        cmd = f"Get-CimInstance -Query 'SELECT Name, Description, PartialProductKey, LicenseStatus FROM SoftwareLicensingProduct WHERE PartialProductKey = \"{partial_key}\"'"
    else:
        # Try to find Windows OS product first, then fall back to any product
        cmd = "Get-CimInstance -Query \"SELECT Name, Description, PartialProductKey, LicenseStatus FROM SoftwareLicensingProduct WHERE PartialProductKey is not NULL\" | Where-Object {$_.Name -like '*Windows*'} | Select-Object -First 1"

    try:
        result = salt.utils.win_pwsh.run_dict(cmd)
        if isinstance(result, dict) and result:
            return result
    except salt.exceptions.CommandExecutionError:
        pass

    # If no Windows product found and no specific key requested, get any product
    if not product_key:
        cmd = "Get-CimInstance -Query 'SELECT Name, Description, PartialProductKey, LicenseStatus FROM SoftwareLicensingProduct WHERE PartialProductKey is not NULL' | Select-Object -First 1"
        try:
            result = salt.utils.win_pwsh.run_dict(cmd)
            if isinstance(result, dict) and result:
                return result
        except salt.exceptions.CommandExecutionError:
            pass

    return None


def installed(product_key):
    """
    Check to see if the product key is already installed.

    Note: This is not 100% accurate as we can only see the last
     5 digits of the license.

    Args:

        product_key (str): The product key to check.

    Returns:
        bool: ``True`` if the last 5 digits match the current product key,
            otherwise ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' license.installed XXXXX-XXXXX-XXXXX-XXXXX-XXXXX
    """
    product = _get_license_product(product_key)
    return product is not None


def install(product_key):
    """
    Install the given product key

    Args:

        product_key (str): The product key to install.

    Returns:
        str: Success message

    Raises:
        CommandExecutionError: on failure

    CLI Example:

    .. code-block:: bash

        salt '*' license.install XXXXX-XXXXX-XXXXX-XXXXX-XXXXX
    """
    safe_key = product_key.replace("'", "''")
    cmd = f"$sls = Get-CimInstance SoftwareLicensingService; $sls | Invoke-CimMethod -MethodName InstallProductKey -Arguments @{{ProductKey='{safe_key}'}}"

    try:
        result = salt.utils.win_pwsh.run_dict(cmd)
        return "Product key installed successfully."
    except salt.exceptions.CommandExecutionError as exc:
        raise salt.exceptions.CommandExecutionError(str(exc))


def uninstall(product_key=None):
    """
    Uninstall a product key.

    Args:
        product_key (str): Optional product key to uninstall. If not provided, uninstalls
                          the Windows OS product key (if installed). Specify a product key
                          to uninstall other products (e.g., Microsoft Office).

    Returns:
        str: Success message

    Raises:
        CommandExecutionError: on failure

    CLI Example:

    .. code-block:: bash

        salt '*' license.uninstall
        salt '*' license.uninstall XXXXX-XXXXX-XXXXX-XXXXX-ABCDE
    """
    product = _get_license_product(product_key)
    if not product:
        raise salt.exceptions.CommandExecutionError(
            "No product key found to uninstall."
        )

    cmd = f"$prod = Get-CimInstance -Query 'SELECT ID FROM SoftwareLicensingProduct WHERE PartialProductKey = \"{product['PartialProductKey']}\"' | Select-Object -First 1; $prod | Invoke-CimMethod -MethodName UninstallProductKey"

    try:
        result = salt.utils.win_pwsh.run_dict(cmd)
        return "Product key uninstalled successfully."
    except salt.exceptions.CommandExecutionError as exc:
        raise salt.exceptions.CommandExecutionError(str(exc))


def activate(product_key=None):
    """
    Activate a product using the Software Licensing Service.

    Args:
        product_key (str): Optional product key to activate. If not provided, activates
                          the Windows OS product key (if installed).

    Returns:
        str: Success message

    Raises:
        CommandExecutionError: on failure

    CLI Example:

    .. code-block:: bash

        salt '*' license.activate
        salt '*' license.activate XXXXX-XXXXX-XXXXX-XXXXX-ABCDE
    """
    product = _get_license_product(product_key)
    if not product:
        raise salt.exceptions.CommandExecutionError("No product key found to activate.")

    cmd = f"$prod = Get-CimInstance -Query 'SELECT ID FROM SoftwareLicensingProduct WHERE PartialProductKey = \"{product['PartialProductKey']}\"' | Select-Object -First 1; $prod | Invoke-CimMethod -MethodName Activate"

    try:
        result = salt.utils.win_pwsh.run_dict(cmd)
        return "Product key activated successfully."
    except salt.exceptions.CommandExecutionError as exc:
        raise salt.exceptions.CommandExecutionError(str(exc))


def license_status(product_key=None):
    """
    Get the license status code for a product key.

    Args:
        product_key (str): Optional product key to check. If not provided, checks
                          the Windows OS product key (if installed).

    Returns:
        int: License status code:
            - 0: Unlicensed
            - 1: Licensed (valid and activated)
            - 2: OOBGrace (out of box grace period)
            - 3: OOTGrace (out of tolerance grace period)
            - 4: NonGenuineGrace (non-genuine grace period)
            - 5: Notification (notification period)
            - 6: ExtendedGrace (extended grace period)

    CLI Example:

    .. code-block:: bash

        salt '*' license.license_status
        salt '*' license.license_status XXXXX-XXXXX-XXXXX-XXXXX-ABCDE
    """
    product = _get_license_product(product_key)
    if not product:
        return 0  # Unlicensed

    return int(product.get("LicenseStatus", 0))


def licensed(product_key=None):
    """
    Check if a product is properly licensed and activated.

    Args:
        product_key (str): Optional product key to check. If not provided, checks
                          the Windows OS product key (if installed).

    Returns:
        bool: True if the product has a license status of 1 (Licensed and activated),
              False otherwise (including grace periods and unlicensed states)

    CLI Example:

    .. code-block:: bash

        salt '*' license.licensed
        salt '*' license.licensed XXXXX-XXXXX-XXXXX-XXXXX-ABCDE
    """
    return license_status(product_key) == 1


def info(product_key=None):
    """
    Return information about a product license.

    Args:
        product_key (str): Optional product key to get info for. If not provided, returns
                          information about the Windows OS product key (if installed).

    Returns:
        dict: License information containing:
            - name: Product name
            - description: Product description
            - partial_key: Last 5 digits of the product key
            - licensed: Boolean, True if status is Licensed (status == 1)
            - status: License status code (0-6)
            - status_name: Human-readable status name

            Status codes and names:
            - 0: Unlicensed
            - 1: Licensed
            - 2: OOBGrace
            - 3: OOTGrace
            - 4: NonGenuineGrace
            - 5: Notification
            - 6: ExtendedGrace

    Returns None if product not found.

    CLI Example:

    .. code-block:: bash

        salt '*' license.info
        salt '*' license.info XXXXX-XXXXX-XXXXX-XXXXX-ABCDE
    """
    product = _get_license_product(product_key)
    if not product:
        return None

    status_code = product.get("LicenseStatus", 0)
    status_names = {
        0: "Unlicensed",
        1: "Licensed",
        2: "OOBGrace",
        3: "OOTGrace",
        4: "NonGenuineGrace",
        5: "Notification",
        6: "ExtendedGrace",
    }

    return {
        "name": product.get("Name"),
        "description": product.get("Description"),
        "partial_key": product.get("PartialProductKey"),
        "licensed": status_code == 1,
        "status": status_code,
        "status_name": status_names.get(status_code, "Unknown"),
    }


def set_kms_host(host, product_key=None):
    """
    Set the KMS host for a product key.

    If product_key is not provided, sets the global KMS host.

    Args:
        host (str): The KMS host name or IP address.
        product_key (str): Optional product key. If not provided, sets global KMS host.

    Returns:
        str: Success message

    Raises:
        CommandExecutionError: on failure

    CLI Example:

    .. code-block:: bash

        salt '*' license.set_kms_host kms.example.com
        salt '*' license.set_kms_host kms.example.com XXXXX-XXXXX-XXXXX-XXXXX-ABCDE
    """
    safe_host = host.replace("'", "''")
    if product_key:
        partial_key = product_key[-5:]
        cmd = f"$prod = Get-CimInstance -Query 'SELECT ID FROM SoftwareLicensingProduct WHERE PartialProductKey = \"{partial_key}\"' | Select-Object -First 1; $prod | Invoke-CimMethod -MethodName SetKeyManagementServiceMachine -Arguments @{{MachineName='{safe_host}'}}"
    else:
        cmd = f"$sls = Get-CimInstance SoftwareLicensingService; $sls | Invoke-CimMethod -MethodName SetKeyManagementServiceMachine -Arguments @{{MachineName='{safe_host}'}}"

    try:
        result = salt.utils.win_pwsh.run_dict(cmd)
        return "KMS host set successfully."
    except salt.exceptions.CommandExecutionError as exc:
        raise salt.exceptions.CommandExecutionError(str(exc))


def set_kms_port(port, product_key=None):
    """
    Set the KMS port for a product key.

    If product_key is not provided, sets the global KMS port.

    Args:
        port (int): The KMS port number.
        product_key (str): Optional product key. If not provided, sets global KMS port.

    Returns:
        str: Success message

    Raises:
        CommandExecutionError: on failure

    CLI Example:

    .. code-block:: bash

        salt '*' license.set_kms_port 1688
        salt '*' license.set_kms_port 1688 XXXXX-XXXXX-XXXXX-XXXXX-ABCDE
    """
    port = int(port)
    if product_key:
        partial_key = product_key[-5:]
        cmd = f"$prod = Get-CimInstance -Query 'SELECT ID FROM SoftwareLicensingProduct WHERE PartialProductKey = \"{partial_key}\"' | Select-Object -First 1; $prod | Invoke-CimMethod -MethodName SetKeyManagementServicePort -Arguments @{{PortNumber=[uint32]{port}}}"
    else:
        cmd = f"$sls = Get-CimInstance SoftwareLicensingService; $sls | Invoke-CimMethod -MethodName SetKeyManagementServicePort -Arguments @{{PortNumber=[uint32]{port}}}"

    try:
        result = salt.utils.win_pwsh.run_dict(cmd)
        return "KMS port set successfully."
    except salt.exceptions.CommandExecutionError as exc:
        raise salt.exceptions.CommandExecutionError(str(exc))


def clear_kms_host(product_key=None):
    """
    Clear the KMS host for a product key.

    If product_key is not provided, clears the global KMS host.

    Args:
        product_key (str): Optional product key. If not provided, clears global KMS host.

    Returns:
        str: Success message

    Raises:
        CommandExecutionError: on failure

    CLI Example:

    .. code-block:: bash

        salt '*' license.clear_kms_host
        salt '*' license.clear_kms_host XXXXX-XXXXX-XXXXX-XXXXX-ABCDE
    """
    if product_key:
        partial_key = product_key[-5:]
        cmd = f"$prod = Get-CimInstance -Query 'SELECT ID FROM SoftwareLicensingProduct WHERE PartialProductKey = \"{partial_key}\"' | Select-Object -First 1; $prod | Invoke-CimMethod -MethodName ClearKeyManagementServiceMachine"
    else:
        cmd = "$sls = Get-CimInstance SoftwareLicensingService; $sls | Invoke-CimMethod -MethodName ClearKeyManagementServiceMachine"

    try:
        result = salt.utils.win_pwsh.run_dict(cmd)
        rv = result.get("ReturnValue") if isinstance(result, dict) else None
        if rv is not None and rv != 0:
            raise salt.exceptions.CommandExecutionError(
                f"ClearKeyManagementServiceMachine failed with ReturnValue {rv}"
            )
        return "KMS host cleared successfully."
    except salt.exceptions.CommandExecutionError as exc:
        raise salt.exceptions.CommandExecutionError(str(exc))


def clear_kms_port(product_key=None):
    """
    Clear the KMS port for a product key.

    If product_key is not provided, clears the global KMS port.

    Args:
        product_key (str): Optional product key. If not provided, clears global KMS port.

    Returns:
        str: Success message

    Raises:
        CommandExecutionError: on failure

    CLI Example:

    .. code-block:: bash

        salt '*' license.clear_kms_port
        salt '*' license.clear_kms_port XXXXX-XXXXX-XXXXX-XXXXX-ABCDE
    """
    if product_key:
        partial_key = product_key[-5:]
        cmd = f"$prod = Get-CimInstance -Query 'SELECT ID FROM SoftwareLicensingProduct WHERE PartialProductKey = \"{partial_key}\"' | Select-Object -First 1; $prod | Invoke-CimMethod -MethodName ClearKeyManagementServicePort"
    else:
        cmd = "$sls = Get-CimInstance SoftwareLicensingService; $sls | Invoke-CimMethod -MethodName ClearKeyManagementServicePort"

    try:
        result = salt.utils.win_pwsh.run_dict(cmd)
        rv = result.get("ReturnValue") if isinstance(result, dict) else None
        if rv is not None and rv != 0:
            raise salt.exceptions.CommandExecutionError(
                f"ClearKeyManagementServicePort failed with ReturnValue {rv}"
            )
        return "KMS port cleared successfully."
    except salt.exceptions.CommandExecutionError as exc:
        raise salt.exceptions.CommandExecutionError(str(exc))


def get_kms_host(product_key=None):
    """
    Get the KMS host for a product key.

    If product_key is not provided, returns the global KMS host.

    Args:
        product_key (str): Optional product key. If not provided, returns global KMS host.

    Returns:
        str: The KMS host name or IP address, or None if not set

    CLI Example:

    .. code-block:: bash

        salt '*' license.get_kms_host
        salt '*' license.get_kms_host XXXXX-XXXXX-XXXXX-XXXXX-ABCDE
    """
    if product_key:
        partial_key = product_key[-5:]
        cmd = f"Get-CimInstance -Query 'SELECT KeyManagementServiceMachine FROM SoftwareLicensingProduct WHERE PartialProductKey = \"{partial_key}\"'"
    else:
        cmd = "Get-CimInstance -Query 'SELECT KeyManagementServiceMachine FROM SoftwareLicensingService'"

    try:
        result = salt.utils.win_pwsh.run_dict(cmd)
        if isinstance(result, dict):
            host = result.get("KeyManagementServiceMachine", "")
            return host if host else None
    except salt.exceptions.CommandExecutionError:
        pass

    return None


def get_kms_port(product_key=None):
    """
    Get the KMS port for a product key.

    If product_key is not provided, returns the global KMS port.

    Args:
        product_key (str): Optional product key. If not provided, returns global KMS port.

    Returns:
        int: The KMS port number, or None if not set

    CLI Example:

    .. code-block:: bash

        salt '*' license.get_kms_port
        salt '*' license.get_kms_port XXXXX-XXXXX-XXXXX-XXXXX-ABCDE
    """
    if product_key:
        partial_key = product_key[-5:]
        cmd = f"Get-CimInstance -Query 'SELECT KeyManagementServicePort FROM SoftwareLicensingProduct WHERE PartialProductKey = \"{partial_key}\"'"
    else:
        # CIM always reports the effective port (1688 default) even when not explicitly configured.
        # The registry reflects the explicitly configured value: absent/0 means not set.
        cmd = (
            "Get-ItemProperty -Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\SoftwareProtectionPlatform' "
            "-Name 'KeyManagementServicePort' -ErrorAction SilentlyContinue"
        )

    try:
        result = salt.utils.win_pwsh.run_dict(cmd)
        if isinstance(result, dict):
            port = result.get("KeyManagementServicePort", 0)
            return int(port) if port else None
    except salt.exceptions.CommandExecutionError:
        pass

    return None
