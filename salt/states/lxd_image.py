"""
Manage LXD images.

.. versionadded:: 2019.2.0

.. link: https://github.com/lxc/pylxd/blob/master/doc/source/installation.rst

.. note:

    - :role:`pylxd <link>` version 2 is required to let this work,
      currently only available via pip.

        To install on Ubuntu:

        $ apt-get install libssl-dev python-pip
        $ pip install -U pylxd

    - you need lxd installed on the minion
      for the init() and version() methods.

    - for the config_get() and config_get() methods
      you need to have lxd-client installed.


:maintainer: René Jochum <rene@jochums.at>
:maturity: new
:depends: python-pylxd
:platform: Linux
"""


from salt.exceptions import CommandExecutionError, SaltInvocationError

__docformat__ = "restructuredtext en"

__virtualname__ = "lxd_image"


def __virtual__():
    """
    Only load if the lxd module is available in __salt__
    """
    if "lxd.version" in __salt__:
        return __virtualname__
    return (False, "lxd module could not be loaded")


def present(
    name,
    source,
    aliases=None,
    public=None,
    auto_update=None,
    remote_addr=None,
    cert=None,
    key=None,
    verify_cert=True,
):
    """
    Ensure an image exists, copy it else from source

    name :
        An alias of the image, this is used to check if the image exists and
        it will be added as alias to the image on copy/create.

    source :
        Source dict.

        For an LXD to LXD copy:

        .. code-block:: yaml

            source:
                type: lxd
                name: ubuntu/xenial/amd64  # This can also be a fingerprint.
                remote_addr: https://images.linuxcontainers.org:8443
                cert: ~/.config/lxd/client.crt
                key: ~/.config/lxd/client.key
                verify_cert: False

        .. attention:

            For this kind of remote you also need to provide:
            - a https:// remote_addr
            - a cert and key
            - verify_cert

        From file:

        .. code-block:: yaml

            source:
                type: file
                filename: salt://lxd/files/busybox.tar.xz
                saltenv: base

        From simplestreams:

        .. code-block:: yaml

            source:
                type: simplestreams
                server: https://cloud-images.ubuntu.com/releases
                name: xenial/amd64

        From an URL:

        .. code-block:: yaml

            source:
                type: url
                url: https://dl.stgraber.org/lxd

    aliases :
        List of aliases to append, can be empty.

    public :
        Make this image public available on this instance?
            None on source_type LXD means copy source
            None on source_type file means False

    auto_update :
        Try to auto-update from the original source?
            None on source_type LXD means copy source
            source_type file does not have auto-update.

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
    if aliases is None:
        aliases = []

    # Create a copy of aliases, since we're modifying it here
    aliases = aliases[:]
    ret = {
        "name": name,
        "source": source,
        "aliases": aliases,
        "public": public,
        "auto_update": auto_update,
        "remote_addr": remote_addr,
        "cert": cert,
        "key": key,
        "verify_cert": verify_cert,
        "changes": {},
    }

    image = None
    try:
        image = __salt__["lxd.image_get_by_alias"](
            name, remote_addr, cert, key, verify_cert, _raw=True
        )
    except CommandExecutionError as e:
        return _error(ret, str(e))
    except SaltInvocationError as e:
        # Image not found
        pass

    if image is None:
        if __opts__["test"]:
            # Test is on, just return that we would create the image
            msg = 'Would create the image "{}"'.format(name)
            ret["changes"] = {"created": msg}
            return _unchanged(ret, msg)

        try:
            if source["type"] == "lxd":
                image = __salt__["lxd.image_copy_lxd"](
                    source["name"],
                    src_remote_addr=source["remote_addr"],
                    src_cert=source["cert"],
                    src_key=source["key"],
                    src_verify_cert=source.get("verify_cert", True),
                    remote_addr=remote_addr,
                    cert=cert,
                    key=key,
                    verify_cert=verify_cert,
                    aliases=aliases,
                    public=public,
                    auto_update=auto_update,
                    _raw=True,
                )

            if source["type"] == "file":
                if "saltenv" not in source:
                    source["saltenv"] = __env__
                image = __salt__["lxd.image_from_file"](
                    source["filename"],
                    remote_addr=remote_addr,
                    cert=cert,
                    key=key,
                    verify_cert=verify_cert,
                    aliases=aliases,
                    public=False if public is None else public,
                    saltenv=source["saltenv"],
                    _raw=True,
                )

            if source["type"] == "simplestreams":
                image = __salt__["lxd.image_from_simplestreams"](
                    source["server"],
                    source["name"],
                    remote_addr=remote_addr,
                    cert=cert,
                    key=key,
                    verify_cert=verify_cert,
                    aliases=aliases,
                    public=False if public is None else public,
                    auto_update=False if auto_update is None else auto_update,
                    _raw=True,
                )

            if source["type"] == "url":
                image = __salt__["lxd.image_from_url"](
                    source["url"],
                    remote_addr=remote_addr,
                    cert=cert,
                    key=key,
                    verify_cert=verify_cert,
                    aliases=aliases,
                    public=False if public is None else public,
                    auto_update=False if auto_update is None else auto_update,
                    _raw=True,
                )
        except CommandExecutionError as e:
            return _error(ret, str(e))

    # Sync aliases
    if name not in aliases:
        aliases.append(name)

    old_aliases = {str(a["name"]) for a in image.aliases}
    new_aliases = set(map(str, aliases))

    alias_changes = []
    # Removed aliases
    for k in old_aliases.difference(new_aliases):
        if not __opts__["test"]:
            __salt__["lxd.image_alias_delete"](image, k)
            alias_changes.append('Removed alias "{}"'.format(k))
        else:
            alias_changes.append('Would remove alias "{}"'.format(k))

    # New aliases
    for k in new_aliases.difference(old_aliases):
        if not __opts__["test"]:
            __salt__["lxd.image_alias_add"](image, k, "")
            alias_changes.append('Added alias "{}"'.format(k))
        else:
            alias_changes.append('Would add alias "{}"'.format(k))

    if alias_changes:
        ret["changes"]["aliases"] = alias_changes

    # Set public
    if public is not None and image.public != public:
        if not __opts__["test"]:
            ret["changes"]["public"] = "Setting the image public to {!s}".format(public)
            image.public = public
            __salt__["lxd.pylxd_save_object"](image)
        else:
            ret["changes"]["public"] = "Would set public to {!s}".format(public)

    if __opts__["test"] and ret["changes"]:
        return _unchanged(ret, "Would do {} changes".format(len(ret["changes"].keys())))

    return _success(ret, "{} changes".format(len(ret["changes"].keys())))


def absent(name, remote_addr=None, cert=None, key=None, verify_cert=True):
    """
    name :
        An alias or fingerprint of the image to check and delete.

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
        "remote_addr": remote_addr,
        "cert": cert,
        "key": key,
        "verify_cert": verify_cert,
        "changes": {},
    }
    image = None
    try:
        image = __salt__["lxd.image_get_by_alias"](
            name, remote_addr, cert, key, verify_cert, _raw=True
        )
    except CommandExecutionError as e:
        return _error(ret, str(e))
    except SaltInvocationError as e:
        try:
            image = __salt__["lxd.image_get"](
                name, remote_addr, cert, key, verify_cert, _raw=True
            )
        except CommandExecutionError as e:
            return _error(ret, str(e))
        except SaltInvocationError as e:
            return _success(ret, 'Image "{}" not found.'.format(name))

    if __opts__["test"]:
        ret["changes"] = {"removed": 'Image "{}" would get deleted.'.format(name)}
        return _success(ret, ret["changes"]["removed"])

    __salt__["lxd.image_delete"](image)

    ret["changes"] = {"removed": 'Image "{}" has been deleted.'.format(name)}
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
