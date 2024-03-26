"""
Manage LXD profiles.

.. versionadded:: 2019.2.0

.. note:

    - `pylxd`_ version 2 is required to let this work,
      currently only available via pip.

        To install on Ubuntu:

        $ apt-get install libssl-dev python-pip
        $ pip install -U pylxd

    - you need lxd installed on the minion
      for the init() and version() methods.

    - for the config_get() and config_get() methods
      you need to have lxd-client installed.

.. _pylxd: https://github.com/lxc/pylxd/blob/master/doc/source/installation.rst

:maintainer: René Jochum <rene@jochums.at>
:maturity: new
:depends: python-pylxd
:platform: Linux
"""

from salt.exceptions import CommandExecutionError, SaltInvocationError

__docformat__ = "restructuredtext en"

__virtualname__ = "lxd_profile"


def __virtual__():
    """
    Only load if the lxd module is available in __salt__
    """
    if "lxd.version" in __salt__:
        return __virtualname__
    return (False, "lxd module could not be loaded")


def present(
    name,
    description=None,
    config=None,
    devices=None,
    remote_addr=None,
    cert=None,
    key=None,
    verify_cert=True,
):
    """
    Creates or updates LXD profiles

    name :
        The name of the profile to create/update

    description :
        A description string

    config :
        A config dict or None (None = unset).

        Can also be a list:
            [{'key': 'boot.autostart', 'value': 1},
             {'key': 'security.privileged', 'value': '1'}]

    devices :
        A device dict or None (None = unset).

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if you
        provide remote_addr!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Zertifikate.

        Examples:
            ~/.config/lxc/client.crt

    key :
        PEM Formatted SSL Key.

        Examples:
            ~/.config/lxc/client.key

    verify_cert : True
        Wherever to verify the cert, this is by default True
        but in the most cases you want to set it off as LXD
        normally uses self-signed certificates.

    See the `lxd-docs`_ for the details about the config and devices dicts.
    See the `requests-docs` for the SSL stuff.

    .. _lxd-docs: https://github.com/lxc/lxd/blob/master/doc/rest-api.md#post-10
    .. _requests-docs: http://docs.python-requests.org/en/master/user/advanced/#ssl-cert-verification  # noqa
    """
    ret = {
        "name": name,
        "description": description,
        "config": config,
        "devices": devices,
        "remote_addr": remote_addr,
        "cert": cert,
        "key": key,
        "verify_cert": verify_cert,
        "changes": {},
    }

    profile = None
    try:
        profile = __salt__["lxd.profile_get"](
            name, remote_addr, cert, key, verify_cert, _raw=True
        )
    except CommandExecutionError as e:
        return _error(ret, str(e))
    except SaltInvocationError as e:
        # Profile not found
        pass

    if description is None:
        description = ""

    if profile is None:
        if __opts__["test"]:
            # Test is on, just return that we would create the profile
            msg = f'Would create the profile "{name}"'
            ret["changes"] = {"created": msg}
            return _unchanged(ret, msg)

        # Create the profile
        try:
            __salt__["lxd.profile_create"](
                name, config, devices, description, remote_addr, cert, key, verify_cert
            )

        except CommandExecutionError as e:
            return _error(ret, str(e))

        msg = f'Profile "{name}" has been created'
        ret["changes"] = {"created": msg}
        return _success(ret, msg)

    config, devices = __salt__["lxd.normalize_input_values"](config, devices)

    #
    # Description change
    #
    if str(profile.description) != str(description):
        ret["changes"]["description"] = (
            'Description changed, from "{}" to "{}".'.format(
                profile.description, description
            )
        )

        profile.description = description

    changes = __salt__["lxd.sync_config_devices"](
        profile, config, devices, __opts__["test"]
    )
    ret["changes"].update(changes)

    if not ret["changes"]:
        return _success(ret, "No changes")

    if __opts__["test"]:
        return _unchanged(ret, f'Profile "{name}" would get changed.')

    try:
        __salt__["lxd.pylxd_save_object"](profile)
    except CommandExecutionError as e:
        return _error(ret, str(e))

    return _success(ret, "{} changes".format(len(ret["changes"].keys())))


def absent(name, remote_addr=None, cert=None, key=None, verify_cert=True):
    """
    Ensure a LXD profile is not present, removing it if present.

    name :
        The name of the profile to remove.

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if you
        provide remote_addr!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Zertifikate.

        Examples:
            ~/.config/lxc/client.crt

    key :
        PEM Formatted SSL Key.

        Examples:
            ~/.config/lxc/client.key

    verify_cert : True
        Wherever to verify the cert, this is by default True
        but in the most cases you want to set it off as LXD
        normally uses self-signed certificates.

    See the `requests-docs` for the SSL stuff.

    .. _requests-docs: http://docs.python-requests.org/en/master/user/advanced/#ssl-cert-verification  # noqa
    """
    ret = {
        "name": name,
        "remote_addr": remote_addr,
        "cert": cert,
        "key": key,
        "verify_cert": verify_cert,
        "changes": {},
    }
    if __opts__["test"]:
        try:
            __salt__["lxd.profile_get"](name, remote_addr, cert, key, verify_cert)
        except CommandExecutionError as e:
            return _error(ret, str(e))
        except SaltInvocationError as e:
            # Profile not found
            return _success(ret, f'Profile "{name}" not found.')

        ret["changes"] = {"removed": f'Profile "{name}" would get deleted.'}
        return _success(ret, ret["changes"]["removed"])

    try:
        __salt__["lxd.profile_delete"](name, remote_addr, cert, key, verify_cert)
    except CommandExecutionError as e:
        return _error(ret, str(e))
    except SaltInvocationError as e:
        # Profile not found
        return _success(ret, f'Profile "{name}" not found.')

    ret["changes"] = {"removed": f'Profile "{name}" has been deleted.'}
    return _success(ret, ret["changes"]["removed"])


def _success(ret, success_msg):
    ret["result"] = True
    ret["comment"] = success_msg
    if "changes" not in ret:
        ret["changes"] = {}
    return ret


def _unchanged(ret, msg):
    ret["result"] = None
    ret["comment"] = msg
    if "changes" not in ret:
        ret["changes"] = {}
    return ret


def _error(ret, err_msg):
    ret["result"] = False
    ret["comment"] = err_msg
    if "changes" not in ret:
        ret["changes"] = {}
    return ret
