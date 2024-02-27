"""
Manage LXD containers.

.. versionadded:: 2019.2.0

.. note:

    - :ref:`pylxd` version 2 is required to let this work,
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

__virtualname__ = "lxd_container"

# Keep in sync with: https://github.com/lxc/lxd/blob/master/shared/status.go
CONTAINER_STATUS_RUNNING = 103
CONTAINER_STATUS_FROZEN = 110
CONTAINER_STATUS_STOPPED = 102


def __virtual__():
    """
    Only load if the lxd module is available in __salt__
    """
    if "lxd.version" in __salt__:
        return __virtualname__
    return (False, "lxd module could not be loaded")


def present(
    name,
    running=None,
    source=None,
    profiles=None,
    config=None,
    devices=None,
    architecture="x86_64",
    ephemeral=False,
    restart_on_change=False,
    remote_addr=None,
    cert=None,
    key=None,
    verify_cert=True,
):
    """
    Create the named container if it does not exist

    name
        The name of the container to be created

    running : None
        * If ``True``, ensure that the container is running
        * If ``False``, ensure that the container is stopped
        * If ``None``, do nothing with regards to the running state of the
          container

    source : None
        Can be either a string containing an image alias:

        .. code-block:: none

             "xenial/amd64"

        or an dict with type "image" with alias:

        .. code-block:: python

            {"type": "image",
             "alias": "xenial/amd64"}

        or image with "fingerprint":

        .. code-block:: python

            {"type": "image",
             "fingerprint": "SHA-256"}

        or image with "properties":

        .. code-block:: python

            {"type": "image",
             "properties": {
                "os": "ubuntu",
                "release": "14.04",
                "architecture": "x86_64"
             }}

        or none:

        .. code-block:: python

            {"type": "none"}

        or copy:

        .. code-block:: python

            {"type": "copy",
             "source": "my-old-container"}

    profiles : ['default']
        List of profiles to apply on this container

    config :
        A config dict or None (None = unset).

        Can also be a list:

        .. code-block:: python

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

    restart_on_change : False
        Restart the container when we detect changes on the config or
        its devices?

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
    """
    if profiles is None:
        profiles = ["default"]

    if source is None:
        source = {}

    ret = {
        "name": name,
        "running": running,
        "profiles": profiles,
        "source": source,
        "config": config,
        "devices": devices,
        "architecture": architecture,
        "ephemeral": ephemeral,
        "restart_on_change": restart_on_change,
        "remote_addr": remote_addr,
        "cert": cert,
        "key": key,
        "verify_cert": verify_cert,
        "changes": {},
    }

    container = None
    try:
        container = __salt__["lxd.container_get"](
            name, remote_addr, cert, key, verify_cert, _raw=True
        )
    except CommandExecutionError as e:
        return _error(ret, str(e))
    except SaltInvocationError as e:
        # Profile not found
        pass

    if container is None:
        if __opts__["test"]:
            # Test is on, just return that we would create the container
            msg = f'Would create the container "{name}"'
            ret["changes"] = {"created": msg}
            if running is True:
                msg = msg + " and start it."
                ret["changes"]["started"] = 'Would start the container "{}"'.format(
                    name
                )

            ret["changes"] = {"created": msg}
            return _unchanged(ret, msg)

        # create the container
        try:
            __salt__["lxd.container_create"](
                name,
                source,
                profiles,
                config,
                devices,
                architecture,
                ephemeral,
                True,  # Wait
                remote_addr,
                cert,
                key,
                verify_cert,
            )
        except CommandExecutionError as e:
            return _error(ret, str(e))

        msg = f'Created the container "{name}"'
        ret["changes"] = {"created": msg}

        if running is True:
            try:
                __salt__["lxd.container_start"](
                    name, remote_addr, cert, key, verify_cert
                )
            except CommandExecutionError as e:
                return _error(ret, str(e))

            msg = msg + " and started it."
            ret["changes"] = {"started": f'Started the container "{name}"'}

        return _success(ret, msg)

    # Container exists, lets check for differences
    new_profiles = set(map(str, profiles))
    old_profiles = set(map(str, container.profiles))

    container_changed = False

    profile_changes = []
    # Removed profiles
    for k in old_profiles.difference(new_profiles):
        if not __opts__["test"]:
            profile_changes.append(f'Removed profile "{k}"')
            old_profiles.discard(k)
        else:
            profile_changes.append(f'Would remove profile "{k}"')

    # Added profiles
    for k in new_profiles.difference(old_profiles):
        if not __opts__["test"]:
            profile_changes.append(f'Added profile "{k}"')
            old_profiles.add(k)
        else:
            profile_changes.append(f'Would add profile "{k}"')

    if profile_changes:
        container_changed = True
        ret["changes"]["profiles"] = profile_changes
        container.profiles = list(old_profiles)

    # Config and devices changes
    config, devices = __salt__["lxd.normalize_input_values"](config, devices)
    changes = __salt__["lxd.sync_config_devices"](
        container, config, devices, __opts__["test"]
    )
    if changes:
        container_changed = True
        ret["changes"].update(changes)

    is_running = container.status_code == CONTAINER_STATUS_RUNNING

    if not __opts__["test"]:
        try:
            __salt__["lxd.pylxd_save_object"](container)
        except CommandExecutionError as e:
            return _error(ret, str(e))

    if running != is_running:
        if running is True:
            if __opts__["test"]:
                changes["running"] = "Would start the container"
                return _unchanged(
                    ret,
                    f'Container "{name}" would get changed and started.',
                )
            else:
                container.start(wait=True)
                changes["running"] = "Started the container"

        elif running is False:
            if __opts__["test"]:
                changes["stopped"] = "Would stopped the container"
                return _unchanged(
                    ret,
                    f'Container "{name}" would get changed and stopped.',
                )
            else:
                container.stop(wait=True)
                changes["stopped"] = "Stopped the container"

    if (
        (running is True or running is None)
        and is_running
        and restart_on_change
        and container_changed
    ):

        if __opts__["test"]:
            changes["restarted"] = "Would restart the container"
            return _unchanged(ret, f'Would restart the container "{name}"')
        else:
            container.restart(wait=True)
            changes["restarted"] = f'Container "{name}" has been restarted'
            return _success(ret, f'Container "{name}" has been restarted')

    if not container_changed:
        return _success(ret, "No changes")

    if __opts__["test"]:
        return _unchanged(ret, f'Container "{name}" would get changed.')

    return _success(ret, "{} changes".format(len(ret["changes"].keys())))


def absent(name, stop=False, remote_addr=None, cert=None, key=None, verify_cert=True):
    """
    Ensure a LXD container is not present, destroying it if present

    name :
        The name of the container to destroy

    stop :
        stop before destroying
        default: false

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
    """
    ret = {
        "name": name,
        "stop": stop,
        "remote_addr": remote_addr,
        "cert": cert,
        "key": key,
        "verify_cert": verify_cert,
        "changes": {},
    }

    try:
        container = __salt__["lxd.container_get"](
            name, remote_addr, cert, key, verify_cert, _raw=True
        )
    except CommandExecutionError as e:
        return _error(ret, str(e))
    except SaltInvocationError as e:
        # Container not found
        return _success(ret, f'Container "{name}" not found.')

    if __opts__["test"]:
        ret["changes"] = {"removed": f'Container "{name}" would get deleted.'}
        return _unchanged(ret, ret["changes"]["removed"])

    if stop and container.status_code == CONTAINER_STATUS_RUNNING:
        container.stop(wait=True)

    container.delete(wait=True)

    ret["changes"]["deleted"] = f'Container "{name}" has been deleted.'
    return _success(ret, ret["changes"]["deleted"])


def running(
    name, restart=False, remote_addr=None, cert=None, key=None, verify_cert=True
):
    """
    Ensure a LXD container is running and restart it if restart is True

    name :
        The name of the container to start/restart.

    restart :
        restart the container if it is already started.

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
    """
    ret = {
        "name": name,
        "restart": restart,
        "remote_addr": remote_addr,
        "cert": cert,
        "key": key,
        "verify_cert": verify_cert,
        "changes": {},
    }

    try:
        container = __salt__["lxd.container_get"](
            name, remote_addr, cert, key, verify_cert, _raw=True
        )
    except CommandExecutionError as e:
        return _error(ret, str(e))
    except SaltInvocationError as e:
        # Container not found
        return _error(ret, f'Container "{name}" not found')

    is_running = container.status_code == CONTAINER_STATUS_RUNNING

    if is_running:
        if not restart:
            return _success(ret, f'The container "{name}" is already running')
        else:
            if __opts__["test"]:
                ret["changes"]["restarted"] = 'Would restart the container "{}"'.format(
                    name
                )
                return _unchanged(ret, ret["changes"]["restarted"])
            else:
                container.restart(wait=True)
                ret["changes"]["restarted"] = 'Restarted the container "{}"'.format(
                    name
                )
                return _success(ret, ret["changes"]["restarted"])

    if __opts__["test"]:
        ret["changes"]["started"] = f'Would start the container "{name}"'
        return _unchanged(ret, ret["changes"]["started"])

    container.start(wait=True)
    ret["changes"]["started"] = f'Started the container "{name}"'
    return _success(ret, ret["changes"]["started"])


def frozen(name, start=True, remote_addr=None, cert=None, key=None, verify_cert=True):
    """
    Ensure a LXD container is frozen, start and freeze it if start is true

    name :
        The name of the container to freeze

    start :
        start and freeze it

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
    """
    ret = {
        "name": name,
        "start": start,
        "remote_addr": remote_addr,
        "cert": cert,
        "key": key,
        "verify_cert": verify_cert,
        "changes": {},
    }

    try:
        container = __salt__["lxd.container_get"](
            name, remote_addr, cert, key, verify_cert, _raw=True
        )
    except CommandExecutionError as e:
        return _error(ret, str(e))
    except SaltInvocationError as e:
        # Container not found
        return _error(ret, f'Container "{name}" not found')

    if container.status_code == CONTAINER_STATUS_FROZEN:
        return _success(ret, f'Container "{name}" is alredy frozen')

    is_running = container.status_code == CONTAINER_STATUS_RUNNING

    if not is_running and not start:
        return _error(
            ret,
            'Container "{}" is not running and start is False, cannot freeze it'.format(
                name
            ),
        )

    elif not is_running and start:
        if __opts__["test"]:
            ret["changes"][
                "started"
            ] = f'Would start the container "{name}" and freeze it after'
            return _unchanged(ret, ret["changes"]["started"])
        else:
            container.start(wait=True)
            ret["changes"]["started"] = f'Start the container "{name}"'

    if __opts__["test"]:
        ret["changes"]["frozen"] = f'Would freeze the container "{name}"'
        return _unchanged(ret, ret["changes"]["frozen"])

    container.freeze(wait=True)
    ret["changes"]["frozen"] = f'Froze the container "{name}"'

    return _success(ret, ret["changes"]["frozen"])


def stopped(name, kill=False, remote_addr=None, cert=None, key=None, verify_cert=True):
    """
    Ensure a LXD container is stopped, kill it if kill is true else stop it

    name :
        The name of the container to stop

    kill :
        kill if true

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
    """
    ret = {
        "name": name,
        "kill": kill,
        "remote_addr": remote_addr,
        "cert": cert,
        "key": key,
        "verify_cert": verify_cert,
        "changes": {},
    }

    try:
        container = __salt__["lxd.container_get"](
            name, remote_addr, cert, key, verify_cert, _raw=True
        )
    except CommandExecutionError as e:
        return _error(ret, str(e))
    except SaltInvocationError as e:
        # Container not found
        return _error(ret, f'Container "{name}" not found')

    if container.status_code == CONTAINER_STATUS_STOPPED:
        return _success(ret, f'Container "{name}" is already stopped')

    if __opts__["test"]:
        ret["changes"]["stopped"] = f'Would stop the container "{name}"'
        return _unchanged(ret, ret["changes"]["stopped"])

    container.stop(force=kill, wait=True)
    ret["changes"]["stopped"] = f'Stopped the container "{name}"'
    return _success(ret, ret["changes"]["stopped"])


def migrated(
    name,
    remote_addr,
    cert,
    key,
    verify_cert,
    src_remote_addr,
    stop_and_start=False,
    src_cert=None,
    src_key=None,
    src_verify_cert=None,
):
    """Ensure a container is migrated to another host

    If the container is running, it either must be shut down
    first (use stop_and_start=True) or criu must be installed
    on the source and destination machines.

    For this operation both certs need to be authenticated,
    use :mod:`lxd.authenticate <salt.states.lxd.authenticate`
    to authenticate your cert(s).

    name :
        The container to migrate

    remote_addr :
        An URL to the destination remote Server

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

    src_remote_addr :
        An URL to the source remote Server

        Examples:
            https://myserver.lan:8443
            /var/lib/mysocket.sock

    stop_and_start:
        Stop before migrating and start after

    src_cert :
        PEM Formatted SSL Zertifikate, if None we copy "cert"

        Examples:
            ~/.config/lxc/client.crt

    src_key :
        PEM Formatted SSL Key, if None we copy "key"

        Examples:
            ~/.config/lxc/client.key

    src_verify_cert :
        Wherever to verify the cert, if None we copy "verify_cert"
    """
    ret = {
        "name": name,
        "remote_addr": remote_addr,
        "cert": cert,
        "key": key,
        "verify_cert": verify_cert,
        "src_remote_addr": src_remote_addr,
        "src_and_start": stop_and_start,
        "src_cert": src_cert,
        "src_key": src_key,
        "changes": {},
    }

    dest_container = None
    try:
        dest_container = __salt__["lxd.container_get"](
            name, remote_addr, cert, key, verify_cert, _raw=True
        )
    except CommandExecutionError as e:
        return _error(ret, str(e))
    except SaltInvocationError as e:
        # Destination container not found
        pass

    if dest_container is not None:
        return _success(ret, f'Container "{name}" exists on the destination')

    if src_verify_cert is None:
        src_verify_cert = verify_cert

    try:
        __salt__["lxd.container_get"](
            name, src_remote_addr, src_cert, src_key, src_verify_cert, _raw=True
        )
    except CommandExecutionError as e:
        return _error(ret, str(e))
    except SaltInvocationError as e:
        # Container not found
        return _error(ret, f'Source Container "{name}" not found')

    if __opts__["test"]:
        ret["changes"]["migrated"] = (
            'Would migrate the container "{}" from "{}" to "{}"'.format(
                name, src_remote_addr, remote_addr
            )
        )
        return _unchanged(ret, ret["changes"]["migrated"])

    try:
        __salt__["lxd.container_migrate"](
            name,
            stop_and_start,
            remote_addr,
            cert,
            key,
            verify_cert,
            src_remote_addr,
            src_cert,
            src_key,
            src_verify_cert,
        )
    except CommandExecutionError as e:
        return _error(ret, str(e))

    ret["changes"]["migrated"] = 'Migrated the container "{}" from "{}" to "{}"'.format(
        name, src_remote_addr, remote_addr
    )
    return _success(ret, ret["changes"]["migrated"])


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
