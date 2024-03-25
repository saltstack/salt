"""
Module for managing the LXD daemon and its containers.

.. versionadded:: 2019.2.0

`LXD(1)`_ is a container "hypervisor". This execution module provides
several functions to help manage it and its containers.

.. note::

    - `pylxd(2)`_ version >=2.2.5 is required to let this work,
      currently only available via pip.

        To install on Ubuntu:

        $ apt-get install libssl-dev python-pip
        $ pip install -U pylxd

    - you need lxd installed on the minion
      for the init() and version() methods.

    - for the config_get() and config_get() methods
      you need to have lxd-client installed.

.. _LXD(1): https://linuxcontainers.org/lxd/
.. _pylxd(2): https://github.com/lxc/pylxd/blob/master/doc/source/installation.rst

:maintainer: René Jochum <rene@jochums.at>
:maturity: new
:depends: python-pylxd
:platform: Linux
"""

import logging
import os
from datetime import datetime

import salt.utils.decorators.path
import salt.utils.files
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.utils.versions import Version

try:
    import pylxd

    HAS_PYLXD = True

    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    HAS_PYLXD = False


log = logging.getLogger(__name__)

__docformat__ = "restructuredtext en"

_pylxd_minimal_version = "2.2.5"

# Keep in sync with: https://github.com/lxc/lxd/blob/master/shared/osarch/architectures.go
_architectures = {
    "unknown": "0",
    "i686": "1",
    "x86_64": "2",
    "armv7l": "3",
    "aarch64": "4",
    "ppc": "5",
    "ppc64": "6",
    "ppc64le": "7",
    "s390x": "8",
}

# Keep in sync with: https://github.com/lxc/lxd/blob/master/shared/api/status_code.go
CONTAINER_STATUS_RUNNING = 103

__virtualname__ = "lxd"

_connection_pool = {}


def __virtual__():
    if HAS_PYLXD:
        if Version(pylxd_version()) < Version(_pylxd_minimal_version):
            return (
                False,
                'The lxd execution module cannot be loaded: pylxd "{}" is '
                'not supported, you need at least pylxd "{}"'.format(
                    pylxd_version(), _pylxd_minimal_version
                ),
            )

        return __virtualname__

    return (
        False,
        "The lxd execution module cannot be loaded: "
        "the pylxd python module is not available.",
    )


################
# LXD Management
################
@salt.utils.decorators.path.which("lxd")
def version():
    """
    Returns the actual lxd version.

    CLI Example:

    .. code-block:: bash

        salt '*' lxd.version

    """
    return __salt__["cmd.run"]("lxd --version")


def pylxd_version():
    """
    Returns the actual pylxd version.

    CLI Example:

    .. code-block:: bash

        salt '*' lxd.pylxd_version

    """
    return pylxd.__version__


@salt.utils.decorators.path.which("lxd")
def init(
    storage_backend="dir",
    trust_password=None,
    network_address=None,
    network_port=None,
    storage_create_device=None,
    storage_create_loop=None,
    storage_pool=None,
):
    """
    Calls lxd init --auto -- opts

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

    CLI Examples:

    To listen on all IPv4/IPv6 Addresses:

    .. code-block:: bash

        salt '*' lxd.init dir PaSsW0rD [::]

    To not listen on Network:

    .. code-block:: bash

        salt '*' lxd.init
    """

    cmd = f'lxd init --auto --storage-backend="{storage_backend}"'

    if trust_password is not None:
        cmd = cmd + f' --trust-password="{trust_password}"'

    if network_address is not None:
        cmd = cmd + f' --network-address="{network_address}"'

    if network_port is not None:
        cmd = cmd + f' --network-port="{network_port}"'

    if storage_create_device is not None:
        cmd = cmd + f' --storage-create-device="{storage_create_device}"'

    if storage_create_loop is not None:
        cmd = cmd + f' --storage-create-loop="{storage_create_loop}"'

    if storage_pool is not None:
        cmd = cmd + f' --storage-pool="{storage_pool}"'

    try:
        output = __salt__["cmd.run"](cmd)
    except ValueError as e:
        raise CommandExecutionError(
            f"Failed to call: '{cmd}', error was: {str(e)}",
        )

    if "error:" in output:
        raise CommandExecutionError(
            output[output.index("error:") + 7 :],
        )

    return output


@salt.utils.decorators.path.which("lxd")
@salt.utils.decorators.path.which("lxc")
def config_set(key, value):
    """
    Set an LXD daemon config option

    CLI Examples:

    To listen on IPv4 and IPv6 port 8443,
    you can omit the :8443 its the default:

    .. code-block:: bash

        salt '*' lxd.config_set core.https_address [::]:8443

    To set the server trust password:

    .. code-block:: bash

        salt '*' lxd.config_set core.trust_password blah

    """
    cmd = 'lxc config set "{}" "{}"'.format(
        key,
        value,
    )

    output = __salt__["cmd.run"](cmd)
    if "error:" in output:
        raise CommandExecutionError(
            output[output.index("error:") + 7 :],
        )

    return (f'Config value "{key}" successfully set.',)


@salt.utils.decorators.path.which("lxd")
@salt.utils.decorators.path.which("lxc")
def config_get(key):
    """
    Get an LXD daemon config option

    key :
        The key of the config value to retrieve

    CLI Examples:

    .. code-block:: bash

        salt '*' lxd.config_get core.https_address
    """

    cmd = f'lxc config get "{key}"'

    output = __salt__["cmd.run"](cmd)
    if "error:" in output:
        raise CommandExecutionError(
            output[output.index("error:") + 7 :],
        )

    return output


#######################
# Connection Management
#######################
def pylxd_client_get(remote_addr=None, cert=None, key=None, verify_cert=True):
    """
    Get an pyxld client, this is not meant to be run over the CLI.

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if you
        provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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

    See the `requests-docs`_ for the SSL stuff.

    .. _requests-docs: http://docs.python-requests.org/en/master/user/advanced/#ssl-cert-verification

    """

    pool_key = "|".join(
        (
            str(remote_addr),
            str(cert),
            str(key),
            str(verify_cert),
        )
    )

    if pool_key in _connection_pool:
        log.debug('Returning the client "%s" from our connection pool', remote_addr)
        return _connection_pool[pool_key]

    try:
        if remote_addr is None or remote_addr == "/var/lib/lxd/unix.socket":
            log.debug("Trying to connect to the local unix socket")
            client = pylxd.Client()
        else:
            if remote_addr.startswith("/"):
                client = pylxd.Client(remote_addr)
            else:
                if cert is None or key is None:
                    raise SaltInvocationError(
                        "You have to give a Cert and Key file for remote endpoints."
                    )

                cert = os.path.expanduser(cert)
                key = os.path.expanduser(key)

                if not os.path.isfile(cert):
                    raise SaltInvocationError(
                        'You have given an invalid cert path: "{}", the '
                        "file does not exist or is not a file.".format(cert)
                    )

                if not os.path.isfile(key):
                    raise SaltInvocationError(
                        'You have given an invalid key path: "{}", the '
                        "file does not exists or is not a file.".format(key)
                    )

                log.debug(
                    'Trying to connect to "%s" with cert "%s", key "%s" and '
                    'verify_cert "%s"',
                    remote_addr,
                    cert,
                    key,
                    verify_cert,
                )
                client = pylxd.Client(
                    endpoint=remote_addr,
                    cert=(
                        cert,
                        key,
                    ),
                    verify=verify_cert,
                )
    except pylxd.exceptions.ClientConnectionFailed:
        raise CommandExecutionError(f"Failed to connect to '{remote_addr}'")

    except TypeError as e:
        # Happens when the verification failed.
        raise CommandExecutionError(
            'Failed to connect to "{}", looks like the SSL verification '
            "failed, error was: {}".format(remote_addr, str(e))
        )

    _connection_pool[pool_key] = client

    return client


def pylxd_save_object(obj):
    """Saves an object (profile/image/container) and
        translate its execpetion on failure

    obj :
        The object to save

    This is an internal method, no CLI Example.
    """
    try:
        obj.save(wait=True)
    except pylxd.exceptions.LXDAPIException as e:
        raise CommandExecutionError(str(e))

    return True


def authenticate(remote_addr, password, cert, key, verify_cert=True):
    """
    Authenticate with a remote LXDaemon.

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if you
        provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443

    password :
        The password of the remote.

    cert :
        PEM Formatted SSL Certificate.

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

    CLI Example:

    .. code-block:: bash

        salt '*' lxd.authenticate https://srv01:8443 <yourpass> ~/.config/lxc/client.crt ~/.config/lxc/client.key false

    See the `requests-docs`_ for the SSL stuff.

    .. _requests-docs: http://docs.python-requests.org/en/master/user/advanced/#ssl-cert-verification

    """
    client = pylxd_client_get(remote_addr, cert, key, verify_cert)

    if client.trusted:
        return True

    try:
        client.authenticate(password)
    except pylxd.exceptions.LXDAPIException as e:
        # Wrong password
        raise CommandExecutionError(str(e))

    return client.trusted


######################
# Container Management
######################
def container_list(
    list_names=False, remote_addr=None, cert=None, key=None, verify_cert=True
):
    """
    Lists containers

    list_names : False
        Only return a list of names when True

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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

    CLI Examples:

    Full dict with all available information:

    .. code-block:: bash

        salt '*' lxd.container_list

    For a list of names:

    .. code-block:: bash

        salt '*' lxd.container_list true

    See also `container-attributes`_.

    .. _container-attributes: https://github.com/lxc/pylxd/blob/master/doc/source/containers.rst#container-attributes

    """

    client = pylxd_client_get(remote_addr, cert, key, verify_cert)
    containers = client.containers.all()
    if list_names:
        return [c.name for c in containers]

    return map(_pylxd_model_to_dict, containers)


def container_create(
    name,
    source,
    profiles=None,
    config=None,
    devices=None,
    architecture="x86_64",
    ephemeral=False,
    wait=True,
    remote_addr=None,
    cert=None,
    key=None,
    verify_cert=True,
    _raw=False,
):
    """
    Create a container

    name :
        The name of the container

    source :
        Can be either a string containing an image alias:
             "xenial/amd64"

        or an dict with type "image" with alias:
            {"type": "image",
             "alias": "xenial/amd64"}

        or image with "fingerprint":
            {"type": "image",
             "fingerprint": "SHA-256"}

        or image with "properties":
            {"type": "image",
             "properties": {
                "os": "ubuntu",
                "release": "14.04",
                "architecture": "x86_64"}}

        or none:
            {"type": "none"}

        or copy:
            {"type": "copy",
             "source": "my-old-container"}

    profiles : ['default']
        List of profiles to apply on this container

    config :
        A config dict or None (None = unset).

        Can also be a list:
            [{'key': 'boot.autostart', 'value': 1},
             {'key': 'security.privileged', 'value': '1'}]

    devices :
        A device dict or None (None = unset).

    architecture : 'x86_64'
        Can be one of the following:
            * unknown
            * i686
            * x86_64
            * armv7l
            * aarch64
            * ppc
            * ppc64
            * ppc64le
            * s390x

    ephemeral : False
        Destroy this container after stop?

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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

    _raw : False
        Return the raw pyxld object or a dict?

    CLI Examples:

    .. code-block:: bash

        salt '*' lxd.container_create test xenial/amd64

    See also the `rest-api-docs`_.

    .. _rest-api-docs: https://github.com/lxc/lxd/blob/master/doc/rest-api.md#post-1

    """
    if profiles is None:
        profiles = ["default"]

    if config is None:
        config = {}

    if devices is None:
        devices = {}

    client = pylxd_client_get(remote_addr, cert, key, verify_cert)

    if not isinstance(profiles, (list, tuple, set)):
        raise SaltInvocationError("'profiles' must be formatted as list/tuple/set.")

    if architecture not in _architectures:
        raise SaltInvocationError(
            "Unknown architecture '{}' given for the container '{}'".format(
                architecture, name
            )
        )

    if isinstance(source, str):
        source = {"type": "image", "alias": source}

    config, devices = normalize_input_values(config, devices)

    try:
        container = client.containers.create(
            {
                "name": name,
                "architecture": _architectures[architecture],
                "profiles": profiles,
                "source": source,
                "config": config,
                "ephemeral": ephemeral,
            },
            wait=wait,
        )
    except pylxd.exceptions.LXDAPIException as e:
        raise CommandExecutionError(str(e))

    if not wait:
        return container.json()["operation"]

    # Add devices if not wait and devices have been given.
    if devices:
        for dn, dargs in devices.items():
            container_device_add(name, dn, **dargs)

    if _raw:
        return container

    return _pylxd_model_to_dict(container)


def container_get(
    name=None, remote_addr=None, cert=None, key=None, verify_cert=True, _raw=False
):
    """Gets a container from the LXD

    name :
        The name of the container to get.

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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

    _raw :
        Return the pylxd object, this is internal and by states in use.
    """
    client = pylxd_client_get(remote_addr, cert, key, verify_cert)

    if name is None:
        containers = client.containers.all()
        if _raw:
            return containers
    else:
        containers = []
        try:
            containers = [client.containers.get(name)]
        except pylxd.exceptions.LXDAPIException:
            raise SaltInvocationError(f"Container '{name}' not found")
        if _raw:
            return containers[0]

    infos = []
    for container in containers:
        infos.append(dict([(container.name, _pylxd_model_to_dict(container))]))
    return infos


def container_delete(name, remote_addr=None, cert=None, key=None, verify_cert=True):
    """
    Delete a container

    name :
        Name of the container to delete

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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
    """
    container = container_get(name, remote_addr, cert, key, verify_cert, _raw=True)
    container.delete(wait=True)
    return True


def container_rename(
    name, newname, remote_addr=None, cert=None, key=None, verify_cert=True
):
    """
    Rename a container

    name :
        Name of the container to Rename

    newname :
        The new name of the container

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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
    """
    container = container_get(name, remote_addr, cert, key, verify_cert, _raw=True)

    if container.status_code == CONTAINER_STATUS_RUNNING:
        raise SaltInvocationError(f"Can't rename the running container '{name}'.")

    container.rename(newname, wait=True)
    return _pylxd_model_to_dict(container)


def container_state(name=None, remote_addr=None, cert=None, key=None, verify_cert=True):
    """
    Get container state

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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
    """
    client = pylxd_client_get(remote_addr, cert, key, verify_cert)

    if name is None:
        containers = client.containers.all()
    else:
        try:
            containers = [client.containers.get(name)]
        except pylxd.exceptions.LXDAPIException:
            raise SaltInvocationError(f"Container '{name}' not found")

    states = []
    for container in containers:
        state = {}
        state = container.state()

        states.append(
            dict(
                [
                    (
                        container.name,
                        {
                            k: getattr(state, k)
                            for k in dir(state)
                            if not k.startswith("_")
                        },
                    )
                ]
            )
        )
    return states


def container_start(name, remote_addr=None, cert=None, key=None, verify_cert=True):
    """
    Start a container

    name :
        Name of the container to start

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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
    """
    container = container_get(name, remote_addr, cert, key, verify_cert, _raw=True)
    container.start(wait=True)
    return _pylxd_model_to_dict(container)


def container_stop(
    name,
    timeout=30,
    force=True,
    remote_addr=None,
    cert=None,
    key=None,
    verify_cert=True,
):
    """
    Stop a container

    name :
        Name of the container to stop

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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
    """
    container = container_get(name, remote_addr, cert, key, verify_cert, _raw=True)
    container.stop(timeout, force, wait=True)
    return _pylxd_model_to_dict(container)


def container_restart(name, remote_addr=None, cert=None, key=None, verify_cert=True):
    """
    Restart a container

    name :
        Name of the container to restart

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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
    """
    container = container_get(name, remote_addr, cert, key, verify_cert, _raw=True)
    container.restart(wait=True)
    return _pylxd_model_to_dict(container)


def container_freeze(name, remote_addr=None, cert=None, key=None, verify_cert=True):
    """
    Freeze a container

    name :
        Name of the container to freeze

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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
    """
    container = container_get(name, remote_addr, cert, key, verify_cert, _raw=True)
    container.freeze(wait=True)
    return _pylxd_model_to_dict(container)


def container_unfreeze(name, remote_addr=None, cert=None, key=None, verify_cert=True):
    """
    Unfreeze a container

    name :
        Name of the container to unfreeze

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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
    """
    container = container_get(name, remote_addr, cert, key, verify_cert, _raw=True)
    container.unfreeze(wait=True)
    return _pylxd_model_to_dict(container)


def container_migrate(
    name,
    stop_and_start=False,
    remote_addr=None,
    cert=None,
    key=None,
    verify_cert=True,
    src_remote_addr=None,
    src_cert=None,
    src_key=None,
    src_verify_cert=None,
):
    """Migrate a container.

    If the container is running, it either must be shut down
    first (use stop_and_start=True) or criu must be installed
    on the source and destination machines.

    For this operation both certs need to be authenticated,
    use :mod:`lxd.authenticate <salt.modules.lxd.authenticate`
    to authenticate your cert(s).

    name :
        Name of the container to migrate

    stop_and_start :
        Stop the container on the source and start it on dest

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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

    CLI Example:

    .. code-block:: bash

        # Authorize
        salt '*' lxd.authenticate https://srv01:8443 <yourpass> ~/.config/lxc/client.crt ~/.config/lxc/client.key false
        salt '*' lxd.authenticate https://srv02:8443 <yourpass> ~/.config/lxc/client.crt ~/.config/lxc/client.key false

        # Migrate phpmyadmin from srv01 to srv02
        salt '*' lxd.container_migrate phpmyadmin stop_and_start=true remote_addr=https://srv02:8443 cert=~/.config/lxc/client.crt key=~/.config/lxc/client.key verify_cert=False src_remote_addr=https://srv01:8443
    """
    if src_cert is None:
        src_cert = cert

    if src_key is None:
        src_key = key

    if src_verify_cert is None:
        src_verify_cert = verify_cert

    container = container_get(
        name, src_remote_addr, src_cert, src_key, src_verify_cert, _raw=True
    )

    dest_client = pylxd_client_get(remote_addr, cert, key, verify_cert)

    for pname in container.profiles:
        try:
            dest_client.profiles.get(pname)
        except pylxd.exceptions.LXDAPIException:
            raise SaltInvocationError(
                "not all the profiles from the source exist on the target"
            )

    was_running = container.status_code == CONTAINER_STATUS_RUNNING
    if stop_and_start and was_running:
        container.stop(wait=True)

    try:
        dest_container = container.migrate(dest_client, wait=True)
        dest_container.profiles = container.profiles
        dest_container.save()
    except pylxd.exceptions.LXDAPIException as e:
        raise CommandExecutionError(str(e))

    # Remove the source container
    container.delete(wait=True)

    if stop_and_start and was_running:
        dest_container.start(wait=True)

    return _pylxd_model_to_dict(dest_container)


def container_config_get(
    name, config_key, remote_addr=None, cert=None, key=None, verify_cert=True
):
    """
    Get a container config value

    name :
        Name of the container

    config_key :
        The config key to retrieve

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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
    """
    container = container_get(name, remote_addr, cert, key, verify_cert, _raw=True)
    return _get_property_dict_item(container, "config", config_key)


def container_config_set(
    name,
    config_key,
    config_value,
    remote_addr=None,
    cert=None,
    key=None,
    verify_cert=True,
):
    """
    Set a container config value

    name :
        Name of the container

    config_key :
        The config key to set

    config_value :
        The config value to set

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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
    """
    container = container_get(name, remote_addr, cert, key, verify_cert, _raw=True)

    return _set_property_dict_item(container, "config", config_key, config_value)


def container_config_delete(
    name, config_key, remote_addr=None, cert=None, key=None, verify_cert=True
):
    """
    Delete a container config value

    name :
        Name of the container

    config_key :
        The config key to delete

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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
    """
    container = container_get(name, remote_addr, cert, key, verify_cert, _raw=True)

    return _delete_property_dict_item(container, "config", config_key)


def container_device_get(
    name, device_name, remote_addr=None, cert=None, key=None, verify_cert=True
):
    """
    Get a container device

    name :
        Name of the container

    device_name :
        The device name to retrieve

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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
    """
    container = container_get(name, remote_addr, cert, key, verify_cert, _raw=True)

    return _get_property_dict_item(container, "devices", device_name)


def container_device_add(
    name,
    device_name,
    device_type="disk",
    remote_addr=None,
    cert=None,
    key=None,
    verify_cert=True,
    **kwargs,
):
    """
    Add a container device

    name :
        Name of the container

    device_name :
        The device name to add

    device_type :
        Type of the device

    ** kwargs :
        Additional device args

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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
    """
    container = container_get(name, remote_addr, cert, key, verify_cert, _raw=True)

    kwargs["type"] = device_type
    return _set_property_dict_item(container, "devices", device_name, kwargs)


def container_device_delete(
    name, device_name, remote_addr=None, cert=None, key=None, verify_cert=True
):
    """
    Delete a container device

    name :
        Name of the container

    device_name :
        The device name to delete

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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
    """
    container = container_get(name, remote_addr, cert, key, verify_cert, _raw=True)

    return _delete_property_dict_item(container, "devices", device_name)


def container_file_put(
    name,
    src,
    dst,
    recursive=False,
    overwrite=False,
    mode=None,
    uid=None,
    gid=None,
    saltenv="base",
    remote_addr=None,
    cert=None,
    key=None,
    verify_cert=True,
):
    """
    Put a file into a container

    name :
        Name of the container

    src :
        The source file or directory

    dst :
        The destination file or directory

    recursive :
        Decent into src directory

    overwrite :
        Replace destination if it exists

    mode :
        Set file mode to octal number

    uid :
        Set file uid (owner)

    gid :
        Set file gid (group)

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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

    CLI Example:

    .. code-block:: bash

        salt '*' lxd.container_file_put <container name> /var/tmp/foo /var/tmp/

    """
    # Possibilities:
    #  (src, dst, dir, dir1, and dir2 are directories)
    #  cp /src/file1 /dst/file1
    #  cp /src/file1 /dst/file2
    #  cp /src/file1 /dst
    #  cp /src/file1 /dst/
    #  cp -r /src/dir /dst/
    #  cp -r /src/dir/ /dst/
    #  cp -r /src/dir1 /dst/dir2 (which is not /src/dir1 /dst/dir2/)
    #  cp -r /src/dir1 /dst/dir2/

    # Fix mode. Salt commandline doesn't use octals, so 0600 will be
    # the decimal integer 600 (and not the octal 0600). So, it it's
    # and integer, handle it as if it where a octal representation.
    mode = str(mode)
    if not mode.startswith("0"):
        mode = f"0{mode}"

    container = container_get(name, remote_addr, cert, key, verify_cert, _raw=True)

    src = os.path.expanduser(src)

    if not os.path.isabs(src):
        if src.find("://") >= 0:
            cached_file = __salt__["cp.cache_file"](src, saltenv=saltenv)
            if not cached_file:
                raise SaltInvocationError(f"File '{src}' not found")
            if not os.path.isabs(cached_file):
                raise SaltInvocationError("File path must be absolute.")
            src = cached_file

    # Make sure that src doesn't end with '/', unless it's '/'
    src = src.rstrip(os.path.sep)
    if not src:
        src = os.path.sep

    if not os.path.exists(src):
        raise CommandExecutionError(f"No such file or directory '{src}'")

    if os.path.isdir(src) and not recursive:
        raise SaltInvocationError(
            "Cannot copy overwriting a directory without recursive flag set to true!"
        )

    try:
        dst_is_directory = False
        container.files.get(os.path.join(dst, "."))
    except pylxd.exceptions.NotFound:
        pass
    except pylxd.exceptions.LXDAPIException as why:
        if str(why).find("Is a directory") >= 0:
            dst_is_directory = True

    if os.path.isfile(src):
        # Source is a file
        if dst_is_directory:
            dst = os.path.join(dst, os.path.basename(src))
            if not overwrite:
                found = True
                try:
                    container.files.get(os.path.join(dst))
                except pylxd.exceptions.NotFound:
                    found = False
                except pylxd.exceptions.LXDAPIException as why:
                    if str(why).find("not found") >= 0:
                        # Old version of pylxd
                        found = False
                    else:
                        raise
                if found:
                    raise SaltInvocationError(
                        "Destination exists and overwrite is false"
                    )
        if mode is not None or uid is not None or gid is not None:
            # Need to get file stats
            stat = os.stat(src)
            if mode is None:
                mode = oct(stat.st_mode)
            if uid is None:
                uid = stat.st_uid
            if gid is None:
                gid = stat.st_gid

        with salt.utils.files.fopen(src, "rb") as src_fp:
            container.files.put(dst, src_fp.read(), mode=mode, uid=uid, gid=gid)
        return True
    elif not os.path.isdir(src):
        raise SaltInvocationError("Source is neither file nor directory")

    # Source is a directory
    # idx for dstdir = dst + src[idx:]
    if dst.endswith(os.sep):
        idx = len(os.path.dirname(src))
    elif dst_is_directory:
        idx = len(src)
    else:
        # Destination is not a directory and doesn't end with '/'
        # Check that the parent directory of dst exists
        # and is a directory
        try:
            container.files.get(os.path.join(os.path.dirname(dst), "."))
        except pylxd.exceptions.NotFound:
            pass
        except pylxd.exceptions.LXDAPIException as why:
            if str(why).find("Is a directory") >= 0:
                dst_is_directory = True
                # destination is non-existent
                # cp -r /src/dir1 /scr/dir1
                # cp -r /src/dir1 /scr/dir2
                idx = len(src)
                overwrite = True

    # Copy src directory recursive
    if not overwrite:
        raise SaltInvocationError("Destination exists and overwrite is false")

    # Collect all directories first, to create them in one call
    # (for performance reasons)
    dstdirs = []
    for path, _, files in os.walk(src):
        dstdir = os.path.join(dst, path[idx:].lstrip(os.path.sep))
        dstdirs.append(dstdir)
    container.execute(["mkdir", "-p"] + dstdirs)

    set_mode = mode
    set_uid = uid
    set_gid = gid
    # Now transfer the files
    for path, _, files in os.walk(src):
        dstdir = os.path.join(dst, path[idx:].lstrip(os.path.sep))
        for name in files:
            src_name = os.path.join(path, name)
            dst_name = os.path.join(dstdir, name)

            if mode is not None or uid is not None or gid is not None:
                # Need to get file stats
                stat = os.stat(src_name)
                if mode is None:
                    set_mode = oct(stat.st_mode)
                if uid is None:
                    set_uid = stat.st_uid
                if gid is None:
                    set_gid = stat.st_gid

            with salt.utils.files.fopen(src_name, "rb") as src_fp:
                container.files.put(
                    dst_name, src_fp.read(), mode=set_mode, uid=set_uid, gid=set_gid
                )

    return True


def container_file_get(
    name,
    src,
    dst,
    overwrite=False,
    mode=None,
    uid=None,
    gid=None,
    remote_addr=None,
    cert=None,
    key=None,
    verify_cert=True,
):
    """
    Get a file from a container

    name :
        Name of the container

    src :
        The source file or directory

    dst :
        The destination file or directory

    mode :
        Set file mode to octal number

    uid :
        Set file uid (owner)

    gid :
        Set file gid (group)

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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

    """
    # Fix mode. Salt commandline doesn't use octals, so 0600 will be
    # the decimal integer 600 (and not the octal 0600). So, it it's
    # and integer, handle it as if it where a octal representation.

    # Do only if mode is not None, otherwise we get 0None
    if mode is not None:
        mode = str(mode)
        if not mode.startswith("0"):
            mode = f"0{mode}"

    container = container_get(name, remote_addr, cert, key, verify_cert, _raw=True)

    dst = os.path.expanduser(dst)
    if not os.path.isabs(dst):
        raise SaltInvocationError("File path must be absolute.")

    if os.path.isdir(dst):
        dst = os.path.join(dst, os.path.basename(src))
    elif not os.path.isdir(os.path.dirname(dst)):
        raise SaltInvocationError("Parent directory for destination doesn't exist.")

    if os.path.exists(dst):
        if not overwrite:
            raise SaltInvocationError("Destination exists and overwrite is false.")
        if not os.path.isfile(dst):
            raise SaltInvocationError("Destination exists but is not a file.")
    else:
        dst_path = os.path.dirname(dst)
        if not os.path.isdir(dst_path):
            raise CommandExecutionError(f"No such file or directory '{dst_path}'")
        # Seems to be duplicate of line 1794, produces /path/file_name/file_name
        # dst = os.path.join(dst, os.path.basename(src))

    with salt.utils.files.fopen(dst, "wb") as df:
        df.write(container.files.get(src))

    if mode:
        os.chmod(dst, mode)
    if uid or uid == "0":
        uid = int(uid)
    else:
        uid = -1
    if gid or gid == "0":
        gid = int(gid)
    else:
        gid = -1
    if uid != -1 or gid != -1:
        os.chown(dst, uid, gid)
    return True


def container_execute(
    name, cmd, remote_addr=None, cert=None, key=None, verify_cert=True
):
    """
    Execute a command list on a container.

    name :
        Name of the container

    cmd :
        Command to be executed (as a list)

        Example :
            '["ls", "-l"]'

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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

    CLI Example:

    .. code-block:: bash

        salt '*' lxd.container_execute <container name> '["ls", "-l"]'

    """
    container = container_get(name, remote_addr, cert, key, verify_cert, _raw=True)
    try:
        result = container.execute(cmd)
        saltresult = {}
        if not hasattr(result, "exit_code"):
            saltresult = dict(
                exit_code=0,
                stdout=result[0],
                stderr=result[1],
            )
        else:
            saltresult = dict(
                exit_code=result.exit_code,
                stdout=result.stdout,
                stderr=result.stderr,
            )
    except pylxd.exceptions.NotFound as e:
        # TODO: Using exit_code 0 here is not always right,
        # in the most cases the command worked ok though.
        # See: https://github.com/lxc/pylxd/issues/280
        saltresult = dict(exit_code=0, stdout="", stderr=str(e))

    if int(saltresult["exit_code"]) > 0:
        saltresult["result"] = False
    else:
        saltresult["result"] = True

    return saltresult


####################
# Profile Management
####################
def profile_list(
    list_names=False, remote_addr=None, cert=None, key=None, verify_cert=True
):
    """Lists all profiles from the LXD.

    list_names :

        Return a list of names instead of full blown dicts.

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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

    CLI Examples:

    .. code-block:: bash

        salt '*' lxd.profile_list true --out=json
        salt '*' lxd.profile_list --out=json
    """

    client = pylxd_client_get(remote_addr, cert, key, verify_cert)

    profiles = client.profiles.all()
    if list_names:
        return [p.name for p in profiles]

    return map(_pylxd_model_to_dict, profiles)


def profile_create(
    name,
    config=None,
    devices=None,
    description=None,
    remote_addr=None,
    cert=None,
    key=None,
    verify_cert=True,
):
    """Creates a profile.

    name :
        The name of the profile to get.

    config :
        A config dict or None (None = unset).

        Can also be a list:
            [{'key': 'boot.autostart', 'value': 1},
             {'key': 'security.privileged', 'value': '1'}]

    devices :
        A device dict or None (None = unset).

    description :
        A description string or None (None = unset).

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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

    CLI Examples:

    .. code-block:: bash

        salt '*' lxd.profile_create autostart config="{boot.autostart: 1, boot.autostart.delay: 2, boot.autostart.priority: 1}"
        salt '*' lxd.profile_create shared_mounts devices="{shared_mount: {type: 'disk', source: '/home/shared', path: '/home/shared'}}"

    See the `lxd-docs`_ for the details about the config and devices dicts.

    .. _lxd-docs: https://github.com/lxc/lxd/blob/master/doc/rest-api.md#post-10
    """
    client = pylxd_client_get(remote_addr, cert, key, verify_cert)

    config, devices = normalize_input_values(config, devices)

    try:
        profile = client.profiles.create(name, config, devices)
    except pylxd.exceptions.LXDAPIException as e:
        raise CommandExecutionError(str(e))

    if description is not None:
        profile.description = description
        pylxd_save_object(profile)

    return _pylxd_model_to_dict(profile)


def profile_get(
    name, remote_addr=None, cert=None, key=None, verify_cert=True, _raw=False
):
    """Gets a profile from the LXD

    name :
        The name of the profile to get.

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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

    _raw :
        Return the pylxd object, this is internal and by states in use.

    CLI Examples:

    .. code-block:: bash

        salt '*' lxd.profile_get autostart
    """
    client = pylxd_client_get(remote_addr, cert, key, verify_cert)

    profile = None
    try:
        profile = client.profiles.get(name)
    except pylxd.exceptions.LXDAPIException:
        raise SaltInvocationError(f"Profile '{name}' not found")

    if _raw:
        return profile

    return _pylxd_model_to_dict(profile)


def profile_delete(name, remote_addr=None, cert=None, key=None, verify_cert=True):
    """Deletes a profile.

    name :
        The name of the profile to delete.

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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

    CLI Example:

    .. code-block:: bash

        salt '*' lxd.profile_delete shared_mounts
    """
    profile = profile_get(name, remote_addr, cert, key, verify_cert, _raw=True)

    profile.delete()
    return True


def profile_config_get(
    name, config_key, remote_addr=None, cert=None, key=None, verify_cert=True
):
    """Get a profile config item.

    name :
        The name of the profile to get the config item from.

    config_key :
        The key for the item to retrieve.

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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

    CLI Example:

    .. code-block:: bash

        salt '*' lxd.profile_config_get autostart boot.autostart
    """
    profile = profile_get(name, remote_addr, cert, key, verify_cert, _raw=True)

    return _get_property_dict_item(profile, "config", config_key)


def profile_config_set(
    name,
    config_key,
    config_value,
    remote_addr=None,
    cert=None,
    key=None,
    verify_cert=True,
):
    """Set a profile config item.

    name :
        The name of the profile to set the config item to.

    config_key :
        The items key.

    config_value :
        Its items value.

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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

    CLI Example:

    .. code-block:: bash

        salt '*' lxd.profile_config_set autostart boot.autostart 0
    """
    profile = profile_get(name, remote_addr, cert, key, verify_cert, _raw=True)

    return _set_property_dict_item(profile, "config", config_key, config_value)


def profile_config_delete(
    name, config_key, remote_addr=None, cert=None, key=None, verify_cert=True
):
    """Delete a profile config item.

    name :
        The name of the profile to delete the config item.

    config_key :
        The config key for the value to retrieve.

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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

    CLI Example:

    .. code-block:: bash

        salt '*' lxd.profile_config_delete autostart boot.autostart.delay
    """
    profile = profile_get(name, remote_addr, cert, key, verify_cert, _raw=True)

    return _delete_property_dict_item(profile, "config", config_key)


def profile_device_get(
    name, device_name, remote_addr=None, cert=None, key=None, verify_cert=True
):
    """Get a profile device.

    name :
        The name of the profile to get the device from.

    device_name :
        The name of the device to retrieve.

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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

    CLI Example:

    .. code-block:: bash

        salt '*' lxd.profile_device_get default eth0
    """
    profile = profile_get(name, remote_addr, cert, key, verify_cert, _raw=True)

    return _get_property_dict_item(profile, "devices", device_name)


def profile_device_set(
    name,
    device_name,
    device_type="disk",
    remote_addr=None,
    cert=None,
    key=None,
    verify_cert=True,
    **kwargs,
):
    """Set a profile device.

    name :
        The name of the profile to set the device to.

    device_name :
        The name of the device to set.

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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

    CLI Example:

    .. code-block:: bash

        salt '*' lxd.profile_device_set autostart eth1 nic nictype=bridged parent=lxdbr0
    """
    profile = profile_get(name, remote_addr, cert, key, verify_cert, _raw=True)

    kwargs["type"] = device_type

    for k, v in kwargs.items():
        kwargs[k] = str(v)

    return _set_property_dict_item(profile, "devices", device_name, kwargs)


def profile_device_delete(
    name, device_name, remote_addr=None, cert=None, key=None, verify_cert=True
):
    """Delete a profile device.

    name :
        The name of the profile to delete the device.

    device_name :
        The name of the device to delete.

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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

    CLI Example:

    .. code-block:: bash

        salt '*' lxd.profile_device_delete autostart eth1

    """
    profile = profile_get(name, remote_addr, cert, key, verify_cert, _raw=True)

    return _delete_property_dict_item(profile, "devices", device_name)


##################
# Image Management
##################
def image_list(
    list_aliases=False, remote_addr=None, cert=None, key=None, verify_cert=True
):
    """Lists all images from the LXD.

    list_aliases :

        Return a dict with the fingerprint as key and
        a list of aliases as value instead.

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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

    CLI Examples:

    .. code-block:: bash

        salt '*' lxd.image_list true --out=json
        salt '*' lxd.image_list --out=json
    """
    client = pylxd_client_get(remote_addr, cert, key, verify_cert)

    images = client.images.all()
    if list_aliases:
        return {i.fingerprint: [a["name"] for a in i.aliases] for i in images}

    return map(_pylxd_model_to_dict, images)


def image_get(
    fingerprint, remote_addr=None, cert=None, key=None, verify_cert=True, _raw=False
):
    """Get an image by its fingerprint

    fingerprint :
        The fingerprint of the image to retrieve

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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

    _raw : False
        Return the raw pylxd object or a dict of it?

    CLI Examples:

    .. code-block:: bash

        salt '*' lxd.image_get <fingerprint>
    """
    client = pylxd_client_get(remote_addr, cert, key, verify_cert)

    image = None
    try:
        image = client.images.get(fingerprint)
    except pylxd.exceptions.LXDAPIException:
        raise SaltInvocationError(f"Image with fingerprint '{fingerprint}' not found")

    if _raw:
        return image

    return _pylxd_model_to_dict(image)


def image_get_by_alias(
    alias, remote_addr=None, cert=None, key=None, verify_cert=True, _raw=False
):
    """Get an image by an alias

    alias :
        The alias of the image to retrieve

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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

    _raw : False
        Return the raw pylxd object or a dict of it?

    CLI Examples:

    .. code-block:: bash

        salt '*' lxd.image_get_by_alias xenial/amd64
    """
    client = pylxd_client_get(remote_addr, cert, key, verify_cert)

    image = None
    try:
        image = client.images.get_by_alias(alias)
    except pylxd.exceptions.LXDAPIException:
        raise SaltInvocationError(f"Image with alias '{alias}' not found")

    if _raw:
        return image

    return _pylxd_model_to_dict(image)


def image_delete(image, remote_addr=None, cert=None, key=None, verify_cert=True):
    """Delete an image by an alias or fingerprint

    name :
        The alias or fingerprint of the image to delete,
        can be a obj for the states.

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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

    CLI Examples:

    .. code-block:: bash

        salt '*' lxd.image_delete xenial/amd64
    """

    image = _verify_image(image, remote_addr, cert, key, verify_cert)

    image.delete()
    return True


def image_from_simplestreams(
    server,
    alias,
    remote_addr=None,
    cert=None,
    key=None,
    verify_cert=True,
    aliases=None,
    public=False,
    auto_update=False,
    _raw=False,
):
    """Create an image from simplestreams

    server :
        Simplestreams server URI

    alias :
        The alias of the image to retrieve

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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

    aliases : []
        List of aliases to append to the copied image

    public : False
        Make this image public available

    auto_update : False
        Should LXD auto update that image?

    _raw : False
        Return the raw pylxd object or a dict of the image?

    CLI Examples:

    .. code-block:: bash

        salt '*' lxd.image_from_simplestreams "https://cloud-images.ubuntu.com/releases" "trusty/amd64" aliases='["t", "trusty/amd64"]' auto_update=True
    """
    if aliases is None:
        aliases = []

    client = pylxd_client_get(remote_addr, cert, key, verify_cert)

    try:
        image = client.images.create_from_simplestreams(
            server, alias, public=public, auto_update=auto_update
        )
    except pylxd.exceptions.LXDAPIException as e:
        raise CommandExecutionError(str(e))

    # Aliases support
    for alias in aliases:
        image_alias_add(image, alias)

    if _raw:
        return image

    return _pylxd_model_to_dict(image)


def image_from_url(
    url,
    remote_addr=None,
    cert=None,
    key=None,
    verify_cert=True,
    aliases=None,
    public=False,
    auto_update=False,
    _raw=False,
):
    """Create an image from an url

    url :
        The URL from where to download the image

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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

    aliases : []
        List of aliases to append to the copied image

    public : False
        Make this image public available

    auto_update : False
        Should LXD auto update that image?

    _raw : False
        Return the raw pylxd object or a dict of the image?

    CLI Examples:

    .. code-block:: bash

        salt '*' lxd.image_from_url https://dl.stgraber.org/lxd aliases='["busybox-amd64"]'
    """
    if aliases is None:
        aliases = []

    client = pylxd_client_get(remote_addr, cert, key, verify_cert)

    try:
        image = client.images.create_from_url(
            url, public=public, auto_update=auto_update
        )
    except pylxd.exceptions.LXDAPIException as e:
        raise CommandExecutionError(str(e))

    # Aliases support
    for alias in aliases:
        image_alias_add(image, alias)

    if _raw:
        return image

    return _pylxd_model_to_dict(image)


def image_from_file(
    filename,
    remote_addr=None,
    cert=None,
    key=None,
    verify_cert=True,
    aliases=None,
    public=False,
    saltenv="base",
    _raw=False,
):
    """Create an image from a file

    filename :
        The filename of the rootfs

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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

    aliases : []
        List of aliases to append to the copied image

    public : False
        Make this image public available

    saltenv : base
        The saltenv to use for salt:// copies

    _raw : False
        Return the raw pylxd object or a dict of the image?

    CLI Examples:

    .. code-block:: bash

        salt '*' lxd.image_from_file salt://lxd/files/busybox.tar.xz aliases=["busybox-amd64"]
    """
    if aliases is None:
        aliases = []

    cached_file = __salt__["cp.cache_file"](filename, saltenv=saltenv)
    data = b""
    with salt.utils.files.fopen(cached_file, "r+b") as fp:
        data = fp.read()

    client = pylxd_client_get(remote_addr, cert, key, verify_cert)

    try:
        image = client.images.create(data, public=public, wait=True)
    except pylxd.exceptions.LXDAPIException as e:
        raise CommandExecutionError(str(e))

    # Aliases support
    for alias in aliases:
        image_alias_add(image, alias)

    if _raw:
        return image

    return _pylxd_model_to_dict(image)


def image_copy_lxd(
    source,
    src_remote_addr,
    src_cert,
    src_key,
    src_verify_cert,
    remote_addr,
    cert,
    key,
    verify_cert=True,
    aliases=None,
    public=None,
    auto_update=None,
    _raw=False,
):
    """Copy an image from another LXD instance

    source :
        An alias or a fingerprint of the source.

    src_remote_addr :
        An URL to the source remote daemon

        Examples:
            https://mysourceserver.lan:8443

    src_cert :
        PEM Formatted SSL Certificate for the source

        Examples:
            ~/.config/lxc/client.crt

    src_key :
        PEM Formatted SSL Key for the source

        Examples:
            ~/.config/lxc/client.key

    src_verify_cert : True
        Wherever to verify the cert, this is by default True
        but in the most cases you want to set it off as LXD
        normally uses self-signed certificates.

    remote_addr :
        Address of the destination daemon

        Examples:
            https://mydestserver.lan:8443

    cert :
        PEM Formatted SSL Certificate for the destination

        Examples:
            ~/.config/lxc/client.crt

    key :
        PEM Formatted SSL Key for the destination

        Examples:
            ~/.config/lxc/client.key

    verify_cert : True
        Wherever to verify the cert, this is by default True
        but in the most cases you want to set it off as LXD
        normally uses self-signed certificates.

    aliases : []
        List of aliases to append to the copied image

    public : None
        Make this image public available, None = copy source

    auto_update : None
        Wherever to auto-update from the original source, None = copy source

    _raw : False
        Return the raw pylxd object or a dict of the destination image?

    CLI Examples:

    .. code-block:: bash

        salt '*' lxd.image_copy_lxd xenial/amd64 https://srv01:8443 ~/.config/lxc/client.crt ~/.config/lxc/client.key false https://srv02:8443 ~/.config/lxc/client.crt ~/.config/lxc/client.key false aliases="['xenial/amd64']"
    """
    if aliases is None:
        aliases = []

    log.debug(
        'Trying to copy the image "%s" from "%s" to "%s"',
        source,
        src_remote_addr,
        remote_addr,
    )

    # This will fail with a SaltInvocationError if
    # the image doesn't exists on the source and with a CommandExecutionError
    # on connection problems.
    src_image = None
    try:
        src_image = image_get_by_alias(
            source, src_remote_addr, src_cert, src_key, src_verify_cert, _raw=True
        )
    except SaltInvocationError:
        src_image = image_get(
            source, src_remote_addr, src_cert, src_key, src_verify_cert, _raw=True
        )

    # Will fail with a CommandExecutionError on connection problems.
    dest_client = pylxd_client_get(remote_addr, cert, key, verify_cert)

    dest_image = src_image.copy(
        dest_client, public=public, auto_update=auto_update, wait=True
    )

    # Aliases support
    for alias in aliases:
        image_alias_add(dest_image, alias)

    if _raw:
        return dest_image

    return _pylxd_model_to_dict(dest_image)


def image_alias_add(
    image,
    alias,
    description="",
    remote_addr=None,
    cert=None,
    key=None,
    verify_cert=True,
):
    """Create an alias on the given image

    image :
        An image alias, a fingerprint or a image object

    alias :
        The alias to add

    description :
        Description of the alias

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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

    CLI Examples:

    .. code-block:: bash

        salt '*' lxd.image_alias_add xenial/amd64 x "Short version of xenial/amd64"
    """
    image = _verify_image(image, remote_addr, cert, key, verify_cert)

    for alias_info in image.aliases:
        if alias_info["name"] == alias:
            return True
    image.add_alias(alias, description)

    return True


def image_alias_delete(
    image, alias, remote_addr=None, cert=None, key=None, verify_cert=True
):
    """Delete an alias (this is currently not restricted to the image)

    image :
        An image alias, a fingerprint or a image object

    alias :
        The alias to delete

    remote_addr :
        An URL to a remote Server, you also have to give cert and key if
        you provide remote_addr and its a TCP Address!

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

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

    CLI Examples:

    .. code-block:: bash

        salt '*' lxd.image_alias_add xenial/amd64 x "Short version of xenial/amd64"
    """
    image = _verify_image(image, remote_addr, cert, key, verify_cert)

    try:
        image.delete_alias(alias)
    except pylxd.exceptions.LXDAPIException:
        return False

    return True


#####################
# Snapshot Management
#####################


def snapshots_all(container, remote_addr=None, cert=None, key=None, verify_cert=True):
    """
    Get all snapshots for a container

    container :
        The name of the container to get.

    remote_addr :
        An URL to a remote server. The 'cert' and 'key' fields must also be
        provided if 'remote_addr' is defined.

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

        Examples:
            ~/.config/lxc/client.crt

    key :
        PEM Formatted SSL Key.

        Examples:
            ~/.config/lxc/client.key

    verify_cert : True
        Verify the ssl certificate.  Default: True

    CLI Examples:

    .. code-block:: bash

        salt '*' lxd.snapshots_all test-container
    """
    containers = container_get(
        container, remote_addr, cert, key, verify_cert, _raw=True
    )
    if container:
        containers = [containers]
    ret = {}
    for cont in containers:
        ret.update({cont.name: [{"name": c.name} for c in cont.snapshots.all()]})

    return ret


def snapshots_create(
    container, name=None, remote_addr=None, cert=None, key=None, verify_cert=True
):
    """
    Create a snapshot for a container

    container :
        The name of the container to get.

    name :
        The name of the snapshot.

    remote_addr :
        An URL to a remote server. The 'cert' and 'key' fields must also be
        provided if 'remote_addr' is defined.

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

        Examples:
            ~/.config/lxc/client.crt

    key :
        PEM Formatted SSL Key.

        Examples:
            ~/.config/lxc/client.key

    verify_cert : True
        Verify the ssl certificate.  Default: True

    CLI Examples:

    .. code-block:: bash

        salt '*' lxd.snapshots_create test-container test-snapshot
    """
    cont = container_get(container, remote_addr, cert, key, verify_cert, _raw=True)
    if not name:
        name = datetime.now().strftime("%Y%m%d%H%M%S")

    cont.snapshots.create(name)

    for c in snapshots_all(container).get(container):
        if c.get("name") == name:
            return {"name": name}

    return {"name": False}


def snapshots_delete(
    container, name, remote_addr=None, cert=None, key=None, verify_cert=True
):
    """
    Delete a snapshot for a container

    container :
        The name of the container to get.

    name :
        The name of the snapshot.

    remote_addr :
        An URL to a remote server. The 'cert' and 'key' fields must also be
        provided if 'remote_addr' is defined.

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

        Examples:
            ~/.config/lxc/client.crt

    key :
        PEM Formatted SSL Key.

        Examples:
            ~/.config/lxc/client.key

    verify_cert : True
        Verify the ssl certificate.  Default: True

    CLI Examples:

    .. code-block:: bash

        salt '*' lxd.snapshots_delete test-container test-snapshot
    """
    cont = container_get(container, remote_addr, cert, key, verify_cert, _raw=True)

    try:
        for s in cont.snapshots.all():
            if s.name == name:
                s.delete()
                return True
    except pylxd.exceptions.LXDAPIException:
        pass

    return False


def snapshots_get(
    container, name, remote_addr=None, cert=None, key=None, verify_cert=True
):
    """
    Get information about snapshot for a container

    container :
        The name of the container to get.

    name :
        The name of the snapshot.

    remote_addr :
        An URL to a remote server. The 'cert' and 'key' fields must also be
        provided if 'remote_addr' is defined.

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    cert :
        PEM Formatted SSL Certificate.

        Examples:
            ~/.config/lxc/client.crt

    key :
        PEM Formatted SSL Key.

        Examples:
            ~/.config/lxc/client.key

    verify_cert : True
        Verify the ssl certificate.  Default: True

    CLI Examples:

    .. code-block:: bash

        salt '*' lxd.snapshots_get test-container test-snapshot
    """
    container = container_get(container, remote_addr, cert, key, verify_cert, _raw=True)
    return container.snapshots.get(name)


################
# Helper Methods
################


def normalize_input_values(config, devices):
    """
    normalize config input so returns can be put into mongodb, which doesn't like `.`

    This is not meant to be used on the commandline.

    CLI Examples:

    .. code-block:: bash

        salt '*' lxd.normalize_input_values config={} devices={}
    """
    if isinstance(config, list):
        if config and "key" in config[0] and "value" in config[0]:
            config = {d["key"]: d["value"] for d in config}
        else:
            config = {}

    if isinstance(config, str):
        raise SaltInvocationError("config can't be a string, validate your YAML input.")

    if isinstance(devices, str):
        raise SaltInvocationError(
            "devices can't be a string, validate your YAML input."
        )

    # Golangs wants strings
    if config is not None:
        for k, v in config.items():
            config[k] = str(v)
    if devices is not None:
        for dn in devices:
            for k, v in devices[dn].items():
                devices[dn][k] = v

    return (
        config,
        devices,
    )


def sync_config_devices(obj, newconfig, newdevices, test=False):
    """Syncs the given config and devices with the object
    (a profile or a container)
    returns a changes dict with all changes made.

    obj :
        The object to sync with / or just test with.

    newconfig:
        The new config to check with the obj.

    newdevices:
        The new devices to check with the obj.

    test:
        Wherever to not change anything and give "Would change" message.
    """
    changes = {}

    #
    # config changes
    #
    if newconfig is None:
        newconfig = {}

    newconfig = dict(
        list(zip(map(str, newconfig.keys()), map(str, newconfig.values())))
    )
    cck = set(newconfig.keys())

    obj.config = dict(
        list(zip(map(str, obj.config.keys()), map(str, obj.config.values())))
    )
    ock = set(obj.config.keys())

    config_changes = {}
    # Removed keys
    for k in ock.difference(cck):
        # Ignore LXD internals.
        if k.startswith("volatile.") or k.startswith("image."):
            continue

        if not test:
            config_changes[k] = 'Removed config key "{}", its value was "{}"'.format(
                k, obj.config[k]
            )
            del obj.config[k]
        else:
            config_changes[k] = 'Would remove config key "{} with value "{}"'.format(
                k, obj.config[k]
            )

    # same keys
    for k in cck.intersection(ock):
        # Ignore LXD internals.
        if k.startswith("volatile.") or k.startswith("image."):
            continue

        if newconfig[k] != obj.config[k]:
            if not test:
                config_changes[k] = (
                    'Changed config key "{}" to "{}", its value was "{}"'.format(
                        k, newconfig[k], obj.config[k]
                    )
                )
                obj.config[k] = newconfig[k]
            else:
                config_changes[k] = (
                    'Would change config key "{}" to "{}", its current value is "{}"'.format(
                        k, newconfig[k], obj.config[k]
                    )
                )

    # New keys
    for k in cck.difference(ock):
        # Ignore LXD internals.
        if k.startswith("volatile.") or k.startswith("image."):
            continue

        if not test:
            config_changes[k] = f'Added config key "{k}" = "{newconfig[k]}"'
            obj.config[k] = newconfig[k]
        else:
            config_changes[k] = 'Would add config key "{}" = "{}"'.format(
                k, newconfig[k]
            )

    if config_changes:
        changes["config"] = config_changes

    #
    # devices changes
    #
    if newdevices is None:
        newdevices = {}

    dk = set(obj.devices.keys())
    ndk = set(newdevices.keys())

    devices_changes = {}
    # Removed devices
    for k in dk.difference(ndk):
        # Ignore LXD internals.
        if k == "root":
            continue

        if not test:
            devices_changes[k] = f'Removed device "{k}"'
            del obj.devices[k]
        else:
            devices_changes[k] = f'Would remove device "{k}"'

    # Changed devices
    for k, v in obj.devices.items():
        # Ignore LXD internals also for new devices.
        if k == "root":
            continue

        if k not in newdevices:
            # In test mode we don't delete devices above.
            continue

        if newdevices[k] != v:
            if not test:
                devices_changes[k] = f'Changed device "{k}"'
                obj.devices[k] = newdevices[k]
            else:
                devices_changes[k] = f'Would change device "{k}"'

    # New devices
    for k in ndk.difference(dk):
        # Ignore LXD internals.
        if k == "root":
            continue

        if not test:
            devices_changes[k] = f'Added device "{k}"'
            obj.devices[k] = newdevices[k]
        else:
            devices_changes[k] = f'Would add device "{k}"'

    if devices_changes:
        changes["devices"] = devices_changes

    return changes


def _set_property_dict_item(obj, prop, key, value):
    """Sets the dict item key of the attr from obj.

    Basicaly it does getattr(obj, prop)[key] = value.


    For the disk device we added some checks to make
    device changes on the CLI saver.
    """
    attr = getattr(obj, prop)
    if prop == "devices":
        device_type = value["type"]

        if device_type == "disk":

            if "path" not in value:
                raise SaltInvocationError("path must be given as parameter")

            if value["path"] != "/" and "source" not in value:
                raise SaltInvocationError("source must be given as parameter")

        for k in value.keys():
            if k.startswith("__"):
                del value[k]

        attr[key] = value

    else:  # config
        attr[key] = str(value)

    pylxd_save_object(obj)

    return _pylxd_model_to_dict(obj)


def _get_property_dict_item(obj, prop, key):
    attr = getattr(obj, prop)
    if key not in attr:
        raise SaltInvocationError(f"'{key}' doesn't exists")

    return attr[key]


def _delete_property_dict_item(obj, prop, key):
    attr = getattr(obj, prop)
    if key not in attr:
        raise SaltInvocationError(f"'{key}' doesn't exists")

    del attr[key]
    pylxd_save_object(obj)

    return True


def _verify_image(image, remote_addr=None, cert=None, key=None, verify_cert=True):
    # Get image by alias/fingerprint or check for fingerprint attribute
    if isinstance(image, str):
        name = image

        # This will fail with a SaltInvocationError if
        # the image doesn't exists on the source and with a
        # CommandExecutionError on connection problems.
        image = None
        try:
            image = image_get_by_alias(
                name, remote_addr, cert, key, verify_cert, _raw=True
            )
        except SaltInvocationError:
            image = image_get(name, remote_addr, cert, key, verify_cert, _raw=True)
    elif not hasattr(image, "fingerprint"):
        raise SaltInvocationError(f"Invalid image '{image}'")
    return image


def _pylxd_model_to_dict(obj):
    """Translates a plyxd model object to a dict"""
    marshalled = {}
    for key in obj.__attributes__.keys():
        if hasattr(obj, key):
            marshalled[key] = getattr(obj, key)
    return marshalled


#
# Monkey patching for missing functionality in pylxd
#

if HAS_PYLXD:
    import pylxd.exceptions  # NOQA

    if not hasattr(pylxd.exceptions, "NotFound"):
        # Old version of pylxd

        class NotFound(pylxd.exceptions.LXDAPIException):
            """An exception raised when an object is not found."""

        pylxd.exceptions.NotFound = NotFound

    try:
        from pylxd.container import Container
    except ImportError:
        from pylxd.models.container import Container

    def put(self, filepath, data, mode=None, uid=None, gid=None):
        headers = {}
        if mode is not None:
            if isinstance(mode, int):
                mode = oct(mode)
            elif not mode.startswith("0"):
                mode = f"0{mode}"
            headers["X-LXD-mode"] = mode
        if uid is not None:
            headers["X-LXD-uid"] = str(uid)
        if gid is not None:
            headers["X-LXD-gid"] = str(gid)
        response = self._client.api.containers[self._container.name].files.post(
            params={"path": filepath}, data=data, headers=headers
        )
        return response.status_code == 200

    Container.FilesManager.put = put
