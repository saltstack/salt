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

import os.path

from salt.exceptions import CommandExecutionError, SaltInvocationError

__docformat__ = "restructuredtext en"

__virtualname__ = "lxd"

_password_config_key = "core.trust_password"


def __virtual__():
    """
    Only load if the lxd module is available in __salt__
    """
    if "lxd.version" in __salt__:
        return __virtualname__
    return (False, "lxd module could not be loaded")


def init(
    name,
    storage_backend="dir",
    trust_password=None,
    network_address=None,
    network_port=None,
    storage_create_device=None,
    storage_create_loop=None,
    storage_pool=None,
    done_file="%SALT_CONFIG_DIR%/lxd_initialized",
):
    """
    Initializes the LXD Daemon, as LXD doesn't tell if its initialized
    we touch the done_file and check if it exist.

    This can only be called once per host unless you remove the done_file.

    name :
        Ignore this. This is just here for salt.

    storage_backend :
        Storage backend to use (zfs or dir, default: dir)

    trust_password :
        Password required to add new clients

    network_address : None
        Address to bind LXD to (default: none)

    network_port : None
        Port to bind LXD to (Default: 8443)

    storage_create_device : None
        Setup device based storage using this DEVICE

    storage_create_loop : None
        Setup loop based storage with this SIZE in GB

    storage_pool : None
        Storage pool to use or create

    done_file :
        Path where we check that this method has been called,
        as it can run only once and there's currently no way
        to ask LXD if init has been called.
    """

    ret = {
        "name": name,
        "storage_backend": storage_backend,
        "trust_password": True if trust_password is not None else False,
        "network_address": network_address,
        "network_port": network_port,
        "storage_create_device": storage_create_device,
        "storage_create_loop": storage_create_loop,
        "storage_pool": storage_pool,
        "done_file": done_file,
    }

    # TODO: Get a better path and don't hardcode '/etc/salt'
    done_file = done_file.replace("%SALT_CONFIG_DIR%", "/etc/salt")
    if os.path.exists(done_file):
        # Success we already did that.
        return _success(ret, "LXD is already initialized")

    if __opts__["test"]:
        return _success(ret, "Would initialize LXD")

    # We always touch the done_file, so when LXD is already initialized
    # we don't run this over and over.
    __salt__["file.touch"](done_file)

    try:
        __salt__["lxd.init"](
            storage_backend if storage_backend else None,
            trust_password if trust_password else None,
            network_address if network_address else None,
            network_port if network_port else None,
            storage_create_device if storage_create_device else None,
            storage_create_loop if storage_create_loop else None,
            storage_pool if storage_pool else None,
        )
    except CommandExecutionError as e:
        return _error(ret, str(e))

    return _success(ret, "Initialized the LXD Daemon")


def config_managed(name, value, force_password=False):
    """
    Manage a LXD Server config setting.

    name :
        The name of the config key.

    value :
        Its value.

    force_password : False
        Set this to True if you want to set the password on every run.

        As we can't retrieve the password from LXD we can't check
        if the current one is the same as the given one.

    """
    ret = {
        "name": name,
        "value": value if name != "core.trust_password" else True,
        "force_password": force_password,
    }

    try:
        current_value = __salt__["lxd.config_get"](name)
    except CommandExecutionError as e:
        return _error(ret, str(e))

    if name == _password_config_key and (not force_password or not current_value):
        return _success(
            ret,
            '"{}" is already set (we don\'t known if the password is correct)'.format(
                name
            ),
        )

    elif str(value) == current_value:
        return _success(ret, f'"{name}" is already set to "{value}"')

    if __opts__["test"]:
        if name == _password_config_key:
            msg = "Would set the LXD password"
            ret["changes"] = {"password": msg}
            return _unchanged(ret, msg)
        else:
            msg = f'Would set the "{name}" to "{value}"'
            ret["changes"] = {name: msg}
            return _unchanged(ret, msg)

    result_msg = ""
    try:
        result_msg = __salt__["lxd.config_set"](name, value)[0]
        if name == _password_config_key:
            ret["changes"] = {name: "Changed the password"}
        else:
            ret["changes"] = {name: f'Changed from "{current_value}" to {value}"'}
    except CommandExecutionError as e:
        return _error(ret, str(e))

    return _success(ret, result_msg)


def authenticate(name, remote_addr, password, cert, key, verify_cert=True):
    """
    Authenticate with a remote peer.

    .. notes:

        This function makes every time you run this a connection
        to remote_addr, you better call this only once.

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if you
        provide remote_addr!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    password :
        The PaSsW0rD

    cert :
        PEM Formatted SSL Zertifikate.

        Examples:
            /root/.config/lxc/client.crt

    key :
        PEM Formatted SSL Key.

        Examples:
            /root/.config/lxc/client.key

    verify_cert : True
        Wherever to verify the cert, this is by default True
        but in the most cases you want to set it off as LXD
        normally uses self-signed certificates.

    name:
        Ignore this. This is just here for salt.
    """
    ret = {
        "name": name,
        "remote_addr": remote_addr,
        "cert": cert,
        "key": key,
        "verify_cert": verify_cert,
    }

    try:
        client = __salt__["lxd.pylxd_client_get"](remote_addr, cert, key, verify_cert)
    except SaltInvocationError as e:
        return _error(ret, str(e))
    except CommandExecutionError as e:
        return _error(ret, str(e))

    if client.trusted:
        return _success(ret, "Already authenticated.")

    try:
        result = __salt__["lxd.authenticate"](
            remote_addr, password, cert, key, verify_cert
        )
    except CommandExecutionError as e:
        return _error(ret, str(e))

    if result is not True:
        return _error(ret, f"Failed to authenticate with peer: {remote_addr}")

    msg = f"Successfully authenticated with peer: {remote_addr}"
    ret["changes"] = msg
    return _success(ret, msg)


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
