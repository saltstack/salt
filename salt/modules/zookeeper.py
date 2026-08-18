"""
Zookeeper Module
~~~~~~~~~~~~~~~~
:maintainer:    SaltStack
:maturity:      new
:platform:      all
:depends:       kazoo

.. versionadded:: 2018.3.0

Configuration
=============

:configuration: This module is not usable until the following are specified
    either in a pillar or in the minion's config file:

    .. code-block:: yaml

        zookeeper:
          hosts: zoo1,zoo2,zoo3
          default_acl:
            - username: daniel
              password: test
              read: true
              write: true
              create: true
              delete: true
              admin: true
          username: daniel
          password: test

    If configuration for multiple zookeeper environments is required, they can
    be set up as different configuration profiles. For example:

    .. code-block:: yaml

        zookeeper:
          prod:
            hosts: zoo1,zoo2,zoo3
            default_acl:
              - username: daniel
                password: test
                read: true
                write: true
                create: true
                delete: true
                admin: true
            username: daniel
            password: test
          dev:
            hosts:
              - dev1
              - dev2
              - dev3
            default_acl:
              - username: daniel
                password: test
                read: true
                write: true
                create: true
                delete: true
                admin: true
            username: daniel
            password: test
"""

# Import Salt libraries
import salt.utils.stringutils

# Import python libraries
try:
    import kazoo.client
    import kazoo.security

    HAS_KAZOO = True
except ImportError:
    HAS_KAZOO = False


__virtualname__ = "zookeeper"


def __virtual__():
    if HAS_KAZOO:
        return __virtualname__
    return (False, "Missing dependency: kazoo")


def _get_zk_conn(profile=None, **connection_args):
    if profile:
        prefix = "zookeeper:" + profile
    else:
        prefix = "zookeeper"

    def get(key, default=None):
        """
        look in connection_args first, then default to config file
        """
        return connection_args.get(key) or __salt__["config.get"](
            ":".join([prefix, key]), default
        )

    hosts = get("hosts", "127.0.0.1:2181")
    scheme = get("scheme", None)
    username = get("username", None)
    password = get("password", None)
    default_acl = get("default_acl", None)

    if isinstance(hosts, list):
        hosts = ",".join(hosts)

    if username is not None and password is not None and scheme is None:
        scheme = "digest"

    auth_data = None
    if scheme and username and password:
        auth_data = [(scheme, ":".join([username, password]))]

    if default_acl is not None:
        if isinstance(default_acl, list):
            default_acl = [make_digest_acl(**acl) for acl in default_acl]
        else:
            default_acl = [make_digest_acl(**default_acl)]

    __context__.setdefault("zkconnection", {}).setdefault(
        profile or hosts,
        kazoo.client.KazooClient(
            hosts=hosts, default_acl=default_acl, auth_data=auth_data
        ),
    )

    if not __context__["zkconnection"][profile or hosts].connected:
        __context__["zkconnection"][profile or hosts].start()

    return __context__["zkconnection"][profile or hosts]


def create(
    path,
    value="",
    acls=None,
    ephemeral=False,
    sequence=False,
    makepath=False,
    profile=None,
    hosts=None,
    scheme=None,
    username=None,
    password=None,
    default_acl=None,
):
    """
    Create Znode

    path
        path of znode to create

    value
        value to assign to znode (Default: '')

    acls
        list of acl dictionaries to be assigned (Default: None)

    ephemeral
        indicate node is ephemeral (Default: False)

    sequence
        indicate node is suffixed with a unique index (Default: False)

    makepath
        Create parent paths if they do not exist (Default: False)

    profile
        Configured Zookeeper profile to authenticate with (Default: None)

    hosts
        Lists of Zookeeper Hosts (Default: '127.0.0.1:2181)

    scheme
        Scheme to authenticate with (Default: 'digest')

    username
        Username to authenticate (Default: None)

    password
        Password to authenticate (Default: None)

    default_acl
        Default acls to assign if a node is created in this connection (Default: None)

    CLI Example:

    .. code-block:: bash

        salt minion1 zookeeper.create /test/name daniel profile=prod

    """
    if acls is None:
        acls = []
    acls = [make_digest_acl(**acl) for acl in acls]
    conn = _get_zk_conn(
        profile=profile,
        hosts=hosts,
        scheme=scheme,
        username=username,
        password=password,
        default_acl=default_acl,
    )
    return conn.create(
        path,
        salt.utils.stringutils.to_bytes(value),
        acls,
        ephemeral,
        sequence,
        makepath,
    )


def ensure_path(
    path,
    acls=None,
    profile=None,
    hosts=None,
    scheme=None,
    username=None,
    password=None,
    default_acl=None,
):
    """
    Ensure Znode path exists

    path
        Parent path to create

    acls
        list of acls dictionaries to be assigned (Default: None)

    profile
        Configured Zookeeper profile to authenticate with (Default: None)

    hosts
        Lists of Zookeeper Hosts (Default: '127.0.0.1:2181)

    scheme
        Scheme to authenticate with (Default: 'digest')

    username
        Username to authenticate (Default: None)

    password
        Password to authenticate (Default: None)

    default_acl
        Default acls to assign if a node is created in this connection (Default: None)

    CLI Example:

    .. code-block:: bash

        salt minion1 zookeeper.ensure_path /test/name profile=prod

    """
    if acls is None:
        acls = []
    acls = [make_digest_acl(**acl) for acl in acls]
    conn = _get_zk_conn(
        profile=profile,
        hosts=hosts,
        scheme=scheme,
        username=username,
        password=password,
        default_acl=default_acl,
    )
    return conn.ensure_path(path, acls)


def exists(
    path,
    profile=None,
    hosts=None,
    scheme=None,
    username=None,
    password=None,
    default_acl=None,
):
    """
    Check if path exists

    path
        path to check

    profile
        Configured Zookeeper profile to authenticate with (Default: None)

    hosts
        Lists of Zookeeper Hosts (Default: '127.0.0.1:2181)

    scheme
        Scheme to authenticate with (Default: 'digest')

    username
        Username to authenticate (Default: None)

    password
        Password to authenticate (Default: None)

    default_acl
        Default acls to assign if a node is created in this connection (Default: None)

    CLI Example:

    .. code-block:: bash

        salt minion1 zookeeper.exists /test/name profile=prod

    """
    conn = _get_zk_conn(
        profile=profile,
        hosts=hosts,
        scheme=scheme,
        username=username,
        password=password,
        default_acl=default_acl,
    )
    return bool(conn.exists(path))


def get(
    path,
    profile=None,
    hosts=None,
    scheme=None,
    username=None,
    password=None,
    default_acl=None,
):
    """
    Get value saved in znode

    path
        path to check

    profile
        Configured Zookeeper profile to authenticate with (Default: None)

    hosts
        Lists of Zookeeper Hosts (Default: '127.0.0.1:2181)

    scheme
        Scheme to authenticate with (Default: 'digest')

    username
        Username to authenticate (Default: None)

    password
        Password to authenticate (Default: None)

    default_acl
        Default acls to assign if a node is created in this connection (Default: None)

    CLI Example:

    .. code-block:: bash

        salt minion1 zookeeper.get /test/name profile=prod

    """
    conn = _get_zk_conn(
        profile=profile,
        hosts=hosts,
        scheme=scheme,
        username=username,
        password=password,
        default_acl=default_acl,
    )
    ret, _ = conn.get(path)
    return salt.utils.stringutils.to_str(ret)


def get_children(
    path,
    profile=None,
    hosts=None,
    scheme=None,
    username=None,
    password=None,
    default_acl=None,
):
    """
    Get children in znode path

    path
        path to check

    profile
        Configured Zookeeper profile to authenticate with (Default: None)

    hosts
        Lists of Zookeeper Hosts (Default: '127.0.0.1:2181)

    scheme
        Scheme to authenticate with (Default: 'digest')

    username
        Username to authenticate (Default: None)

    password
        Password to authenticate (Default: None)

    default_acl
        Default acls to assign if a node is created in this connection (Default: None)

    CLI Example:

    .. code-block:: bash

        salt minion1 zookeeper.get_children /test profile=prod

    """
    conn = _get_zk_conn(
        profile=profile,
        hosts=hosts,
        scheme=scheme,
        username=username,
        password=password,
        default_acl=default_acl,
    )
    ret = conn.get_children(path)
    return ret or []


def set(
    path,
    value,
    version=-1,
    profile=None,
    hosts=None,
    scheme=None,
    username=None,
    password=None,
    default_acl=None,
):
    """
    Update znode with new value

    path
        znode to update

    value
        value to set in znode

    version
        only update znode if version matches (Default: -1 (always matches))

    profile
        Configured Zookeeper profile to authenticate with (Default: None)

    hosts
        Lists of Zookeeper Hosts (Default: '127.0.0.1:2181)

    scheme
        Scheme to authenticate with (Default: 'digest')

    username
        Username to authenticate (Default: None)

    password
        Password to authenticate (Default: None)

    default_acl
        Default acls to assign if a node is created in this connection (Default: None)

    CLI Example:

    .. code-block:: bash

        salt minion1 zookeeper.set /test/name gtmanfred profile=prod

    """
    conn = _get_zk_conn(
        profile=profile,
        hosts=hosts,
        scheme=scheme,
        username=username,
        password=password,
        default_acl=default_acl,
    )
    return conn.set(path, salt.utils.stringutils.to_bytes(value), version=version)


def get_acls(
    path,
    profile=None,
    hosts=None,
    scheme=None,
    username=None,
    password=None,
    default_acl=None,
):
    """
    Get acls on a znode

    path
        path to znode

    profile
        Configured Zookeeper profile to authenticate with (Default: None)

    hosts
        Lists of Zookeeper Hosts (Default: '127.0.0.1:2181)

    scheme
        Scheme to authenticate with (Default: 'digest')

    username
        Username to authenticate (Default: None)

    password
        Password to authenticate (Default: None)

    default_acl
        Default acls to assign if a node is created in this connection (Default: None)

    CLI Example:

    .. code-block:: bash

        salt minion1 zookeeper.get_acls /test/name profile=prod

    """
    conn = _get_zk_conn(
        profile=profile,
        hosts=hosts,
        scheme=scheme,
        username=username,
        password=password,
        default_acl=default_acl,
    )
    return conn.get_acls(path)[0]


def set_acls(
    path,
    acls,
    version=-1,
    profile=None,
    hosts=None,
    scheme=None,
    username=None,
    password=None,
    default_acl=None,
):
    """
    Set acls on a znode

    path
        path to znode

    acls
        list of acl dictionaries to set on the znode

    version
        only set acls if version matches (Default: -1 (always matches))

    profile
        Configured Zookeeper profile to authenticate with (Default: None)

    hosts
        Lists of Zookeeper Hosts (Default: '127.0.0.1:2181)

    scheme
        Scheme to authenticate with (Default: 'digest')

    username
        Username to authenticate (Default: None)

    password
        Password to authenticate (Default: None)

    default_acl
        Default acls to assign if a node is created in this connection (Default: None)

    CLI Example:

    .. code-block:: bash

        salt minion1 zookeeper.set_acls /test/name acls='[{"username": "gtmanfred", "password": "test", "all": True}]' profile=prod

    """
    conn = _get_zk_conn(
        profile=profile,
        hosts=hosts,
        scheme=scheme,
        username=username,
        password=password,
        default_acl=default_acl,
    )
    if acls is None:
        acls = []
    acls = [make_digest_acl(**acl) for acl in acls]
    conn = _get_zk_conn(
        profile=profile,
        hosts=hosts,
        scheme=scheme,
        username=username,
        password=password,
        default_acl=default_acl,
    )
    return conn.set_acls(path, acls, version)


def delete(
    path,
    version=-1,
    recursive=False,
    profile=None,
    hosts=None,
    scheme=None,
    username=None,
    password=None,
    default_acl=None,
):
    """
    Delete znode

    path
        path to znode

    version
        only delete if version matches (Default: -1 (always matches))

    profile
        Configured Zookeeper profile to authenticate with (Default: None)

    hosts
        Lists of Zookeeper Hosts (Default: '127.0.0.1:2181)

    scheme
        Scheme to authenticate with (Default: 'digest')

    username
        Username to authenticate (Default: None)

    password
        Password to authenticate (Default: None)

    default_acl
        Default acls to assign if a node is created in this connection (Default: None)

    CLI Example:

    .. code-block:: bash

        salt minion1 zookeeper.delete /test/name profile=prod

    """
    conn = _get_zk_conn(
        profile=profile,
        hosts=hosts,
        scheme=scheme,
        username=username,
        password=password,
        default_acl=default_acl,
    )
    return conn.delete(path, version, recursive)


def make_digest_acl(
    username,
    password,
    read=False,
    write=False,
    create=False,
    delete=False,
    admin=False,
    allperms=False,
):
    """
    Generate acl object

    .. note:: This is heavily used in the zookeeper state and probably is not useful as a cli module

    username
        username of acl

    password
        plain text password of acl

    read
        read acl

    write
        write acl

    create
        create acl

    delete
        delete acl

    admin
        admin acl

    allperms
        set all other acls to True

    CLI Example:

    .. code-block:: bash

        salt minion1 zookeeper.make_digest_acl username=daniel password=mypass allperms=True
    """
    return kazoo.security.make_digest_acl(
        username, password, read, write, create, delete, admin, allperms
    )
