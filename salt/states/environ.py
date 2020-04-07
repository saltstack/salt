# -*- coding: utf-8 -*-
"""
Support for getting and setting the environment variables
of the current salt process.
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import os

# Import Salt libs
import salt.utils.platform

# Import 3rd-party libs
from salt.ext import six


def __virtual__():
    """
    No dependency checks, and not renaming, just return True
    """
    return True


def _norm_key(key):
    """
    Normalize windows environment keys
    """
    if salt.utils.platform.is_windows():
        return key.upper()
    return key


def setenv(
    name,
    value,
    false_unsets=False,
    clear_all=False,
    update_minion=False,
    permanent=False,
):
    """
    Set the salt process environment variables.

    name
        The environment key to set. Must be a string.

    value
        Either a string or dict. When string, it will be the value
        set for the environment key of 'name' above.
        When a dict, each key/value pair represents an environment
        variable to set.

    false_unsets
        If a key's value is False and false_unsets is True, then the
        key will be removed from the salt processes environment dict
        entirely. If a key's value is False and false_unsets is not
        True, then the key's value will be set to an empty string.
        Default: False

    clear_all
        USE WITH CAUTION! This option can unset environment variables
        needed for salt to function properly.
        If clear_all is True, then any environment variables not
        defined in the environ dict will be deleted.
        Default: False

    update_minion
        If True, apply these environ changes to the main salt-minion
        process. If False, the environ changes will only affect the
        current salt subprocess.
        Default: False

    permanent
        On Windows minions this will set the environment variable in the
        registry so that it is always added as a environment variable when
        applications open. If you want to set the variable to HKLM instead of
        HKCU just pass in "HKLM" for this parameter. On all other minion types
        this will be ignored. Note: This will only take affect on applications
        opened after this has been set.

    Example:

    .. code-block:: yaml

        a_string_env:
           environ.setenv:
             - name: foo
             - value: bar
             - update_minion: True

        a_dict_env:
           environ.setenv:
             - name: does_not_matter
             - value:
                 foo: bar
                 baz: quux
    """

    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    environ = {}
    if isinstance(value, six.string_types) or value is False:
        environ[name] = value
    elif isinstance(value, dict):
        environ = value
    else:
        ret["result"] = False
        ret["comment"] = "Environ value must be string, dict or False"
        return ret

    if clear_all is True:
        # Any keys not in 'environ' dict supplied by user will be unset
        to_unset = [key for key in os.environ if key not in environ]
        for key in to_unset:
            if false_unsets is not True:
                # This key value will change to ''
                ret["changes"].update({key: ""})
            else:
                # We're going to delete the key
                ret["changes"].update({key: None})

    current_environ = dict(os.environ)
    already_set = []
    for key, val in six.iteritems(environ):
        if val is False:
            # We unset this key from the environment if
            # false_unsets is True. Otherwise we want to set
            # the value to ''
            def key_exists():
                if salt.utils.platform.is_windows():
                    permanent_hive = "HKCU"
                    permanent_key = "Environment"
                    if permanent == "HKLM":
                        permanent_hive = "HKLM"
                        permanent_key = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"

                    out = __salt__["reg.read_value"](
                        permanent_hive, permanent_key, _norm_key(key)
                    )
                    return out["success"] is True
                else:
                    return False

            if current_environ.get(_norm_key(key), None) is None and not key_exists():
                # The key does not exist in environment
                if false_unsets is not True:
                    # This key will be added with value ''
                    ret["changes"].update({key: ""})
            else:
                # The key exists.
                if false_unsets is not True:
                    # Check to see if the value will change
                    if current_environ.get(_norm_key(key), None) != "":
                        # This key value will change to ''
                        ret["changes"].update({key: ""})
                else:
                    # We're going to delete the key
                    ret["changes"].update({key: None})
        elif current_environ.get(_norm_key(key), "") == val:
            already_set.append(key)
        else:
            ret["changes"].update({key: val})

    if __opts__["test"]:
        if ret["changes"]:
            ret["comment"] = "Environ values will be changed"
        else:
            ret["comment"] = "Environ values are already set with the correct values"
        return ret

    if ret["changes"]:
        environ_ret = __salt__["environ.setenv"](
            environ, false_unsets, clear_all, update_minion, permanent
        )
        if not environ_ret:
            ret["result"] = False
            ret["comment"] = "Failed to set environ variables"
            return ret
        ret["result"] = True
        ret["changes"] = environ_ret
        ret["comment"] = "Environ values were set"
    else:
        ret["comment"] = "Environ values were already set with the correct values"
    return ret
