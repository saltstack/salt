"""
The acl module handles publisher_acl and client_acl operations

Additional information on publisher_acl can be
found by reading the salt documentation:

    https://docs.saltproject.io/en/latest/ref/publisheracl.html
"""

# Import python libraries
import fnmatch

import salt.utils.stringutils


class ClientACL:
    """
    Represents the client ACL and provides methods to query the ACL
    for operations performed by remote CLI clients.

    Remote CLI clients (salt-run, salt-key, etc.) using client authentication
    can have their access controlled via client_acl configuration.
    """

    def __init__(self, client_acl):
        """
        Initialize the ClientACL

        :param dict client_acl: The client_acl configuration from master config.
                                Expected format:
                                {
                                    'client-id-1': {
                                        'runner': ['*'],
                                        'wheel': ['key.*']
                                    },
                                    'client-id-2': {
                                        'runner': ['jobs.*', 'cache.*'],
                                        'wheel': []
                                    }
                                }
        """
        self.client_acl = client_acl or {}

    def _get_client_permissions(self, client_id):
        """
        Get merged permissions for a client ID, supporting glob pattern matching.

        Multiple patterns can match a single client_id. When this happens,
        permissions from all matching patterns are merged together.

        :param str client_id: The client ID to check
        :rtype: dict or None
        :return: Merged permissions dict or None if no match found
        """
        if not self.client_acl:
            return None

        # Check for exact match first (optimization)
        if client_id in self.client_acl:
            return self.client_acl[client_id]

        # Check for pattern matches
        matched_perms = {}
        found_match = False

        for pattern, perms in self.client_acl.items():
            if fnmatch.fnmatch(client_id, pattern):
                found_match = True
                # Merge permissions from all matching patterns
                for perm_type, perm_list in perms.items():
                    if perm_type not in matched_perms:
                        matched_perms[perm_type] = []
                    # Merge lists, avoiding duplicates
                    if isinstance(perm_list, list):
                        for item in perm_list:
                            if item not in matched_perms[perm_type]:
                                matched_perms[perm_type].append(item)
                    else:
                        matched_perms[perm_type] = perm_list

        return matched_perms if found_match else None

    _CMD_TYPE_ALIASES = {
        "runner": ("runner", "runners"),
        "wheel": ("wheel", "wheels"),
    }

    def client_is_allowed(self, client_id, cmd, cmd_type):
        """
        Check if a client ID is allowed to run a specific command.

        :param str client_id: The client ID making the request
        :param str cmd: The command/function to execute (e.g., 'jobs.list_jobs', 'key.list_all')
        :param str cmd_type: The type of command ('runner' or 'wheel')

        :rtype: bool
        :return: True if the client is allowed, False otherwise
        """
        # If no client_acl configured, allow all access (backward compatibility)
        if not self.client_acl:
            return True

        # Get permissions for this client (supports pattern matching)
        client_perms = self._get_client_permissions(client_id)

        # If client_id doesn't match any patterns, deny access
        if client_perms is None:
            return False

        # Accept both singular and plural forms (``runner``/``runners``,
        # ``wheel``/``wheels``), matching the ``minion``/``minions`` alias
        # already supported in ``client_can_target_minion``.
        aliases = self._CMD_TYPE_ALIASES.get(cmd_type, (cmd_type,))
        key = next((k for k in aliases if k in client_perms), None)
        if key is None:
            return False

        allowed_cmds = client_perms[key]

        # Empty list means deny all (explicit empty permissions)
        if not allowed_cmds:
            return False

        # Check if command is allowed
        if isinstance(cmd, str):
            cmd = [cmd]

        for fun in cmd:
            if not salt.utils.stringutils.check_whitelist_blacklist(
                fun, whitelist=allowed_cmds
            ):
                return False

        return True

    def client_is_blacklisted(self, client_id, cmd, cmd_type, blacklist):
        """
        Check if a client is blacklisted from running a specific command.

        :param str client_id: The client ID making the request
        :param str cmd: The command/function to execute
        :param str cmd_type: The type of command ('runner' or 'wheel')
        :param dict blacklist: Blacklist configuration

        :rtype: bool
        :return: True if the client is blacklisted, False otherwise
        """
        if not blacklist:
            return False

        # Check if client_id itself is blacklisted
        blacklisted_clients = blacklist.get("clients", [])
        if not salt.utils.stringutils.check_whitelist_blacklist(
            client_id, blacklist=blacklisted_clients
        ):
            return True

        # Check if the command is blacklisted for this cmd_type
        blacklisted_cmds = blacklist.get(cmd_type, [])
        if isinstance(cmd, str):
            cmd = [cmd]

        for fun in cmd:
            if not salt.utils.stringutils.check_whitelist_blacklist(
                fun, blacklist=blacklisted_cmds
            ):
                return True

        return False

    # Convenience methods for testing and clearer semantics
    def client_can_run_runner(self, client_id, runner_name):
        """
        Check if a client can run a specific runner.

        :param str client_id: The client ID making the request
        :param str runner_name: The runner function name (e.g., 'test.ping')
        :rtype: bool
        :return: True if the client can run the runner, False otherwise
        """
        return self.client_is_allowed(client_id, runner_name, "runner")

    def client_can_run_wheel(self, client_id, wheel_name):
        """
        Check if a client can run a specific wheel function.

        :param str client_id: The client ID making the request
        :param str wheel_name: The wheel function name (e.g., 'key.list_all')
        :rtype: bool
        :return: True if the client can run the wheel function, False otherwise
        """
        return self.client_is_allowed(client_id, wheel_name, "wheel")

    def client_can_target_minion(self, client_id, minion_id):
        """
        Check if a client can target a specific minion.

        :param str client_id: The client ID making the request
        :param str minion_id: The minion ID to target
        :rtype: bool
        :return: True if the client can target the minion, False otherwise
        """
        # Check if minions targeting is configured for this client
        if not self.client_acl:
            return True

        # Get permissions for this client (supports pattern matching)
        client_perms = self._get_client_permissions(client_id)

        # If client_id doesn't match any patterns, deny access
        if client_perms is None:
            return False

        # Support both "minion" and "minions" for backward compatibility
        if "minions" not in client_perms and "minion" not in client_perms:
            # If minion targeting not configured, deny by default
            return False

        allowed_minions = client_perms.get("minions", client_perms.get("minion", []))

        # Empty list means deny all (explicit empty permissions)
        if not allowed_minions:
            return False

        return salt.utils.stringutils.check_whitelist_blacklist(
            minion_id, whitelist=allowed_minions
        )

    def client_can_run_minion_function(self, client_id, function_name):
        """
        Check if a client can run a specific function on minions.

        :param str client_id: The client ID making the request
        :param str function_name: The minion function name (e.g., 'test.ping')
        :rtype: bool
        :return: True if the client can run the function, False otherwise
        """
        # Check if minion_functions is configured for this client
        if not self.client_acl:
            return True

        # Get permissions for this client (supports pattern matching)
        client_perms = self._get_client_permissions(client_id)

        # If client_id doesn't match any patterns, deny access
        if client_perms is None:
            return False

        # Support "modules", "minion_function", and "minion_functions" for compatibility
        if (
            "modules" not in client_perms
            and "minion_function" not in client_perms
            and "minion_functions" not in client_perms
        ):
            # If minion function execution not configured, deny by default
            return False

        allowed_functions = client_perms.get(
            "modules",
            client_perms.get(
                "minion_functions", client_perms.get("minion_function", [])
            ),
        )

        # Empty list means deny all (explicit empty permissions)
        if not allowed_functions:
            return False

        return salt.utils.stringutils.check_whitelist_blacklist(
            function_name, whitelist=allowed_functions
        )

    def client_can_target_minions(self, client_id, minion_list):
        """
        Check if a client can target all minions in a list.

        :param str client_id: The client ID making the request
        :param list minion_list: List of minion IDs to check
        :rtype: tuple
        :return: (bool, list) - (True if all allowed, list of denied minions)
        """
        if not self.client_acl:
            return True, []

        # Get permissions for this client (supports pattern matching)
        client_perms = self._get_client_permissions(client_id)

        # If client_id doesn't match any patterns, deny all
        if client_perms is None:
            return False, minion_list

        denied_minions = []
        for minion_id in minion_list:
            if not self.client_can_target_minion(client_id, minion_id):
                denied_minions.append(minion_id)

        return len(denied_minions) == 0, denied_minions

    def client_can_publish(self, client_id, minion_list, function_name):
        """
        Check if a client can publish a function to a list of minions.
        This is the main authorization check for publish operations.

        :param str client_id: The client ID making the request
        :param list minion_list: List of minion IDs to target
        :param str function_name: The function to execute
        :rtype: dict
        :return: Dict with 'allowed' (bool) and 'error' (dict) keys
        """
        # No ACL configured - allow all (backward compatible)
        if not self.client_acl:
            return {"allowed": True, "error": None}

        # Get permissions for this client (supports pattern matching)
        client_perms = self._get_client_permissions(client_id)

        # Client not in ACL - deny all
        if client_perms is None:
            return {
                "allowed": False,
                "error": {
                    "name": "ClientAuthorizationError",
                    "message": (
                        f'Client "{client_id}" is not authorized to execute commands. '
                        "No client_acl configuration found for this client."
                    ),
                },
            }

        # Check minion targeting
        can_target, denied_minions = self.client_can_target_minions(
            client_id, minion_list
        )
        if not can_target:
            return {
                "allowed": False,
                "error": {
                    "name": "ClientAuthorizationError",
                    "message": (
                        f'Client "{client_id}" is not authorized to target '
                        f"the following minion(s): {', '.join(denied_minions)}"
                    ),
                },
            }

        # Check function execution
        if not self.client_can_run_minion_function(client_id, function_name):
            return {
                "allowed": False,
                "error": {
                    "name": "ClientAuthorizationError",
                    "message": (
                        f'Client "{client_id}" is not authorized to execute '
                        f'function "{function_name}".'
                    ),
                },
            }

        # All checks passed
        return {"allowed": True, "error": None}

    def client_has_permission(self, client_id, permission_type, target):
        """
        Generic permission check for any permission type.

        :param str client_id: The client ID making the request
        :param str permission_type: The type of permission ('runner', 'wheel', 'minion', 'minion_function')
        :param str target: The target to check (function name, minion ID, etc.)
        :rtype: bool
        :return: True if the client has permission, False otherwise
        """
        # Map permission types to the correct keys in config
        type_map = {
            "runners": "runner",
            "runner": "runner",
            "wheels": "wheel",
            "wheel": "wheel",
            "minions": "minions",
            "minion": "minions",
            "modules": "modules",
            "minion_functions": "modules",
            "minion_function": "modules",
        }

        config_key = type_map.get(permission_type, permission_type)

        # Check if no ACL configured (backward compatibility)
        if not self.client_acl:
            return True

        # Check if this client_id is in the ACL
        if client_id not in self.client_acl:
            return False

        client_perms = self.client_acl[client_id]

        # Check if this permission type is configured for this client
        if config_key not in client_perms:
            return False

        allowed_targets = client_perms[config_key]

        # Check if target is allowed
        return salt.utils.stringutils.check_whitelist_blacklist(
            target, whitelist=allowed_targets
        )

    def get_denial_message(self, client_id, permission_type, target):
        """
        Get a user-friendly denial message for logging/display.

        :param str client_id: The client ID that was denied
        :param str permission_type: The type of permission that was denied
        :param str target: The target that was denied
        :rtype: str
        :return: A formatted denial message
        """
        type_names = {
            "runner": "runner function",
            "wheel": "wheel function",
            "minion": "minion",
            "minion_function": "minion function",
        }

        type_name = type_names.get(permission_type, permission_type)

        return (
            f"Client '{client_id}' is not authorized to execute "
            f"{type_name} '{target}'"
        )

    def authorize_runner(self, client_id, fun):
        """
        Return a ``{"allowed": bool, "error": dict|None}`` decision for a
        client calling a specific runner function.  Shape matches
        :meth:`client_can_publish` so :func:`stacked_authorize` can compose
        it with an eauth decision uniformly across publish/runner/wheel.
        """
        if self.client_is_allowed(client_id, fun, "runner"):
            return {"allowed": True, "error": None}
        return {
            "allowed": False,
            "error": {
                "name": "ClientAuthorizationError",
                "message": (
                    f'Client "{client_id}" is not authorized to execute '
                    f'runner function "{fun}".'
                ),
            },
        }

    def authorize_wheel(self, client_id, fun):
        """
        Return a ``{"allowed": bool, "error": dict|None}`` decision for a
        client calling a specific wheel function.  Shape matches
        :meth:`authorize_runner` and :meth:`client_can_publish`.
        """
        if self.client_is_allowed(client_id, fun, "wheel"):
            return {"allowed": True, "error": None}
        return {
            "allowed": False,
            "error": {
                "name": "ClientAuthorizationError",
                "message": (
                    f'Client "{client_id}" is not authorized to execute '
                    f'wheel function "{fun}".'
                ),
            },
        }


def stacked_authorize(client_decision, eauth_decision):
    """
    Compose two authorization decisions with AND semantics.

    Both ``client_decision`` and ``eauth_decision`` are dicts in the shape
    returned by :meth:`ClientACL.client_can_publish` /
    :meth:`ClientACL.authorize_runner` /
    :meth:`ClientACL.authorize_wheel`:
    ``{"allowed": bool, "error": dict|None}``.

    Returns ``(ok, error_dict)``: ``ok`` is True iff both inputs allow;
    on denial, ``error_dict`` is the first non-``None`` error (client
    first, then eauth) so callers can attribute which policy denied.
    """
    client_ok = bool(client_decision.get("allowed"))
    eauth_ok = bool(eauth_decision.get("allowed"))
    if client_ok and eauth_ok:
        return True, None
    err = client_decision.get("error") or eauth_decision.get("error")
    return False, err


class PublisherACL:
    """
    Represents the publisher ACL and provides methods
    to query the ACL for given operations
    """

    def __init__(self, blacklist):
        self.blacklist = blacklist

    def user_is_blacklisted(self, user):
        """
        Takes a username as a string and returns a boolean. True indicates that
        the provided user has been blacklisted
        """
        return not salt.utils.stringutils.check_whitelist_blacklist(
            user, blacklist=self.blacklist.get("users", [])
        )

    def cmd_is_blacklisted(self, cmd):
        # If this is a regular command, it is a single function
        if isinstance(cmd, str):
            cmd = [cmd]
        for fun in cmd:
            if not salt.utils.stringutils.check_whitelist_blacklist(
                fun, blacklist=self.blacklist.get("modules", [])
            ):
                return True
        return False

    def user_is_whitelisted(self, user):
        return salt.utils.stringutils.check_whitelist_blacklist(
            user, whitelist=self.blacklist.get("users", [])
        )

    def cmd_is_whitelisted(self, cmd):
        # If this is a regular command, it is a single function
        if isinstance(cmd, str):
            cmd = [cmd]
        for fun in cmd:
            if salt.utils.stringutils.check_whitelist_blacklist(
                fun, whitelist=self.blacklist.get("modules", [])
            ):
                return True
        return False
