"""
Install and manage software licenses using Windows Software Licensing Service
==============================================================================

Manage product licenses (Windows OS, Office, etc.) using the Software Licensing Service.

.. code-block:: yaml

    activate_windows:
      license.activate:
        - product_key: XXXXX-XXXXX-XXXXX-XXXXX-XXXXX

    ensure_office_licensed:
      license.present:
        - product_key: XXXXX-XXXXX-XXXXX-XXXXX-XXXXX
        - activate_key: True

    remove_office_key:
      license.absent:
        - product_key: XXXXX-XXXXX-XXXXX-XXXXX-XXXXX
"""

import logging

import salt.exceptions
import salt.utils.data
import salt.utils.platform

log = logging.getLogger(__name__)
__virtualname__ = "license"


def __virtual__():
    """
    Only work on Windows
    """
    if salt.utils.platform.is_windows():
        return __virtualname__
    return (False, "Only Windows OS supported")


def activate(name, product_key=""):
    """
    Install and activate a product key.

    Args:
        name (str): Descriptive state ID.
        product_key (str): The product key to install and activate. If not specified,
            defaults to ``name`` for backwards compatibility.

    Returns:
        dict: A standard Salt state return dict with ``name``, ``result``,
            ``changes``, and ``comment`` keys.

    CLI Example:

    .. code-block:: yaml

        activate_windows:
          license.activate:
            - product_key: XXXXX-XXXXX-XXXXX-XXXXX-XXXXX

        XXXXX-XXXXX-XXXXX-XXXXX-XXXXX:
          license.activate
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}
    product_key = product_key or name

    # Get current state
    current_info = __salt__["license.info"](product_key)
    current_partial_key = current_info.get("partial_key") if current_info else None
    current_licensed = current_info.get("licensed", False) if current_info else False

    # Build state dicts for comparison
    old_state = {
        "product_key": current_partial_key,
        "licensed": current_licensed,
    }
    desired_state = {
        "product_key": product_key[-5:],
        "licensed": True,
    }

    # Check if changes are needed
    changes = salt.utils.data.recursive_diff(old_state, desired_state)

    # Test mode: report what would change
    if __opts__["test"]:
        ret["result"] = None
        ret["changes"] = changes
        if changes:
            ret["comment"] = "Product key would be configured as specified."
        else:
            ret["comment"] = "Product key is already in desired state."
        return ret

    # If no changes needed, return early
    if not changes:
        ret["result"] = True
        ret["comment"] = "Product key is already in desired state."
        return ret

    # Apply changes
    try:
        if current_partial_key != product_key[-5:]:
            __salt__["license.install"](product_key)

        if not current_licensed:
            __salt__["license.activate"](product_key)
    except salt.exceptions.CommandExecutionError as exc:
        ret["result"] = False
        ret["comment"] = f"Failed to configure product key: {exc}"
        return ret

    # Get new state and verify
    try:
        new_info = __salt__["license.info"](product_key)
        new_state = {
            "product_key": new_info.get("partial_key") if new_info else None,
            "licensed": new_info.get("licensed", False) if new_info else False,
        }
        ret["changes"] = salt.utils.data.recursive_diff(old_state, new_state)
    except salt.exceptions.CommandExecutionError as exc:
        ret["result"] = False
        ret["comment"] = f"Failed to verify product key: {exc}"
        return ret

    ret["result"] = True
    ret["comment"] = "Product key configured successfully."
    return ret


def present(name, product_key="", kms_host="", kms_port=0, activate_key=False):
    """
    Ensure that a product key is installed with optional KMS and activation.

    Args:
        name (str): Descriptive state ID.
        product_key (str): The product key to install. If not specified, defaults to
            ``name`` for backwards compatibility.
        kms_host (str): Optional KMS host name or IP address.
        kms_port (int): Optional KMS port number.
        activate_key (bool): Whether to activate the product key (default: False).

    Returns:
        dict: A standard Salt state return dict with ``name``, ``result``,
            ``changes``, and ``comment`` keys.

    CLI Example:

    .. code-block:: yaml

        install_office_key:
          license.present:
            - product_key: XXXXX-XXXXX-XXXXX-XXXXX-XXXXX
            - kms_host: kms.example.com
            - kms_port: 1688
            - activate_key: True
    """
    product_key = product_key or name
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    # Get current state
    key_installed = __salt__["license.installed"](product_key)
    current_info = __salt__["license.info"](product_key) if key_installed else None
    current_partial_key = current_info.get("partial_key") if current_info else None
    current_licensed = current_info.get("licensed", False) if current_info else False
    current_kms_host = __salt__["license.get_kms_host"](product_key)
    current_kms_port = __salt__["license.get_kms_port"](product_key)

    # Build state dicts for comparison
    old_state = {
        "product_key": current_partial_key,
        "licensed": current_licensed,
        "kms_host": current_kms_host,
        "kms_port": current_kms_port,
    }

    desired_state = {
        "product_key": product_key[-5:],
        "licensed": activate_key if activate_key else current_licensed,
        "kms_host": kms_host if kms_host else (current_kms_host or None),
        "kms_port": kms_port if kms_port else (current_kms_port or None),
    }

    # Check if changes are needed
    changes = salt.utils.data.recursive_diff(old_state, desired_state)

    # Test mode: report what would change
    if __opts__["test"]:
        ret["result"] = None
        ret["changes"] = changes
        if changes:
            ret["comment"] = "Product key would be configured as specified."
        else:
            ret["comment"] = "Product key is already in desired state."
        return ret

    # If no changes needed, return early
    if not changes:
        ret["result"] = True
        ret["comment"] = "Product key is already in desired state."
        return ret

    # Apply changes
    try:
        if current_partial_key != product_key[-5:]:
            __salt__["license.install"](product_key)

        if kms_host and current_kms_host != kms_host:
            __salt__["license.set_kms_host"](kms_host, product_key)

        if kms_port and current_kms_port != kms_port:
            __salt__["license.set_kms_port"](kms_port, product_key)

        if activate_key and not current_licensed:
            __salt__["license.activate"](product_key)
    except salt.exceptions.CommandExecutionError as exc:
        ret["result"] = False
        ret["comment"] = f"Failed to configure product key: {exc}"
        return ret

    # Get new state and verify
    try:
        new_info = __salt__["license.info"](product_key)
        new_state = {
            "product_key": new_info.get("partial_key") if new_info else None,
            "licensed": new_info.get("licensed", False) if new_info else False,
            "kms_host": __salt__["license.get_kms_host"](product_key),
            "kms_port": __salt__["license.get_kms_port"](product_key),
        }
        ret["changes"] = salt.utils.data.recursive_diff(old_state, new_state)
    except salt.exceptions.CommandExecutionError as exc:
        ret["result"] = False
        ret["comment"] = f"Failed to verify product key: {exc}"
        return ret

    ret["result"] = True
    ret["comment"] = "Product key configured successfully."
    return ret


def absent(name, product_key="", all_keys=False):
    """
    Ensure that a product key is uninstalled.

    Args:
        name (str): Descriptive state ID.
        product_key (str): The product key to remove. If not specified, defaults to
            ``name`` for backwards compatibility. Ignored if ``all_keys=True``.
        all_keys (bool): If True, remove all product keys (default: False).

    Returns:
        dict: A standard Salt state return dict with ``name``, ``result``,
            ``changes``, and ``comment`` keys.

    CLI Example:

    .. code-block:: yaml

        remove_office_key:
          license.absent:
            - product_key: XXXXX-XXXXX-XXXXX-XXXXX-XXXXX

        remove_all_licenses:
          license.absent:
            - all_keys: True
    """
    product_key = product_key or name
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    # Get current state
    if all_keys:
        current_info = __salt__["license.info"]()
    else:
        current_info = __salt__["license.info"](product_key)

    current_partial_key = current_info.get("partial_key") if current_info else None

    # Build state dicts for comparison
    old_state = {"product_key": current_partial_key}
    desired_state = {"product_key": None}

    # Check if changes are needed
    changes = salt.utils.data.recursive_diff(old_state, desired_state)

    # Test mode: report what would change
    if __opts__["test"]:
        ret["result"] = None
        ret["changes"] = changes
        if changes:
            ret["comment"] = "Product key would be removed."
        else:
            ret["comment"] = "Product key is not installed."
        return ret

    # If no changes needed, return early
    if not changes:
        ret["result"] = True
        ret["comment"] = "Product key is not installed."
        return ret

    # Remove the key
    try:
        if all_keys:
            __salt__["license.uninstall"]()
        else:
            __salt__["license.uninstall"](product_key)
    except salt.exceptions.CommandExecutionError as exc:
        ret["result"] = False
        ret["comment"] = f"Failed to remove product key: {exc}"
        return ret

    # Get new state and verify
    try:
        new_info = (
            __salt__["license.info"]()
            if all_keys
            else __salt__["license.info"](product_key)
        )
        new_state = {"product_key": new_info.get("partial_key") if new_info else None}
        ret["changes"] = salt.utils.data.recursive_diff(old_state, new_state)
    except salt.exceptions.CommandExecutionError as exc:
        ret["result"] = False
        ret["comment"] = f"Failed to verify product key removal: {exc}"
        return ret

    ret["result"] = True
    ret["comment"] = "Product key removed successfully."
    return ret


def present_kms(name, kms_host, kms_port=0, product_key=""):
    """
    Ensure KMS host and port are configured.

    Args:
        name (str): Descriptive state ID.
        kms_host (str): The KMS host name or IP address.
        kms_port (int): Optional KMS port number. If not specified, leaves the port unchanged.
        product_key (str): Optional product key to configure KMS for. If not specified,
            configures global KMS settings.

    Returns:
        dict: A standard Salt state return dict with ``name``, ``result``,
            ``changes``, and ``comment`` keys.

    CLI Example:

    .. code-block:: yaml

        configure_kms_globally:
          license.present_kms:
            - kms_host: kms.example.com
            - kms_port: 1688

        configure_kms_for_office:
          license.present_kms:
            - kms_host: kms.example.com
            - kms_port: 1688
            - product_key: XXXXX-XXXXX-XXXXX-XXXXX-XXXXX
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    # Get current state
    current_kms_host = __salt__["license.get_kms_host"](product_key)
    current_kms_port = __salt__["license.get_kms_port"](product_key)

    # Build state dicts for comparison
    old_state = {
        "kms_host": current_kms_host,
        "kms_port": current_kms_port,
    }

    desired_state = {
        "kms_host": kms_host,
        "kms_port": kms_port if kms_port else (current_kms_port or None),
    }

    # Check if changes are needed
    changes = salt.utils.data.recursive_diff(old_state, desired_state)

    # Test mode: report what would change
    if __opts__["test"]:
        ret["result"] = None
        ret["changes"] = changes
        if changes:
            ret["comment"] = "KMS would be configured as specified."
        else:
            ret["comment"] = "KMS settings are already in desired state."
        return ret

    # If no changes needed, return early
    if not changes:
        ret["result"] = True
        ret["comment"] = "KMS settings are already in desired state."
        return ret

    # Apply changes
    try:
        if current_kms_host != kms_host:
            __salt__["license.set_kms_host"](kms_host, product_key)

        if kms_port and current_kms_port != kms_port:
            __salt__["license.set_kms_port"](kms_port, product_key)
    except salt.exceptions.CommandExecutionError as exc:
        ret["result"] = False
        ret["comment"] = f"Failed to configure KMS: {exc}"
        return ret

    # Get new state and verify
    try:
        new_state = {
            "kms_host": __salt__["license.get_kms_host"](product_key),
            "kms_port": __salt__["license.get_kms_port"](product_key),
        }
        ret["changes"] = salt.utils.data.recursive_diff(old_state, new_state)
    except salt.exceptions.CommandExecutionError as exc:
        ret["result"] = False
        ret["comment"] = f"Failed to verify KMS settings: {exc}"
        return ret

    ret["result"] = True
    ret["comment"] = "KMS configured successfully."
    return ret


def absent_kms(name, host=False, port=False, product_key=""):
    """
    Ensure KMS host and/or port are removed.

    Args:
        name (str): Descriptive state ID.
        host (bool): Remove KMS host (default: False).
        port (bool): Remove KMS port (default: False).
        product_key (str): Optional product key to scope operations to. If not specified,
            modifies global KMS settings.

    Returns:
        dict: A standard Salt state return dict with ``name``, ``result``,
            ``changes``, and ``comment`` keys.

    CLI Example:

    .. code-block:: yaml

        clear_global_kms_host:
          license.absent_kms:
            - host: True

        clear_kms_port_for_office:
          license.absent_kms:
            - product_key: XXXXX-XXXXX-XXXXX-XXXXX-XXXXX
            - port: True
    """
    if not host and not port:
        ret = {
            "name": name,
            "result": False,
            "comment": "Must specify host=True or port=True",
            "changes": {},
        }
        log.error("Must specify host=True or port=True to remove KMS settings")
        return ret

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    # Get current state (only get what we're going to change)
    current_kms_host = __salt__["license.get_kms_host"](product_key) if host else None
    current_kms_port = __salt__["license.get_kms_port"](product_key) if port else None

    # Build state dicts for comparison
    old_state = {}
    desired_state = {}

    if host:
        old_state["kms_host"] = current_kms_host
        desired_state["kms_host"] = None

    if port:
        old_state["kms_port"] = current_kms_port
        desired_state["kms_port"] = None

    # Check if changes are needed
    changes = salt.utils.data.recursive_diff(old_state, desired_state)

    # Test mode: report what would change
    if __opts__["test"]:
        ret["result"] = None
        ret["changes"] = changes
        if changes:
            ret["comment"] = "KMS settings would be cleared."
        else:
            ret["comment"] = "KMS settings are already cleared."
        return ret

    # If no changes needed, return early
    if not changes:
        ret["result"] = True
        ret["comment"] = "KMS settings are already cleared."
        return ret

    # Clear KMS host if needed
    if host and current_kms_host:
        try:
            __salt__["license.clear_kms_host"](product_key)
        except salt.exceptions.CommandExecutionError as exc:
            ret["result"] = False
            ret["comment"] = f"Failed to clear KMS host: {exc}"
            return ret

    # Clear KMS port if needed
    if port and current_kms_port:
        try:
            __salt__["license.clear_kms_port"](product_key)
        except salt.exceptions.CommandExecutionError as exc:
            ret["result"] = False
            ret["comment"] = f"Failed to clear KMS port: {exc}"
            return ret

    # Get new state and verify
    try:
        new_state = {}
        if host:
            new_state["kms_host"] = __salt__["license.get_kms_host"](product_key)
        if port:
            new_state["kms_port"] = __salt__["license.get_kms_port"](product_key)

        ret["changes"] = salt.utils.data.recursive_diff(old_state, new_state)
    except salt.exceptions.CommandExecutionError as exc:
        ret["result"] = False
        ret["comment"] = f"Failed to verify KMS settings: {exc}"
        return ret

    ret["result"] = True
    ret["comment"] = "KMS settings cleared successfully."
    return ret
