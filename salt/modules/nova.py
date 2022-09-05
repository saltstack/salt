"""
Module for handling OpenStack Nova calls

:depends:   - novaclient Python module
:configuration: This module is not usable until the user, password, tenant, and
    auth URL are specified either in a pillar or in the minion's config file.
    For example:

    .. code-block:: yaml

        keystone.user: admin
        keystone.password: verybadpass
        keystone.tenant: admin
        keystone.auth_url: 'http://127.0.0.1:5000/v2.0/'
        # Optional
        keystone.region_name: 'RegionOne'

    If configuration for multiple OpenStack accounts is required, they can be
    set up as different configuration profiles:
    For example:

    .. code-block:: yaml

        openstack1:
          keystone.user: admin
          keystone.password: verybadpass
          keystone.tenant: admin
          keystone.auth_url: 'http://127.0.0.1:5000/v2.0/'

        openstack2:
          keystone.user: admin
          keystone.password: verybadpass
          keystone.tenant: admin
          keystone.auth_url: 'http://127.0.0.2:5000/v2.0/'

    With this configuration in place, any of the nova functions can make use of
    a configuration profile by declaring it explicitly.
    For example:

    .. code-block:: bash

        salt '*' nova.flavor_list profile=openstack1

    To use keystoneauth1 instead of keystoneclient, include the `use_keystoneauth`
    option in the pillar or minion config.

    .. note::
        This is required to use keystone v3 as for authentication.

    .. code-block:: yaml

        keystone.user: admin
        keystone.password: verybadpass
        keystone.tenant: admin
        keystone.auth_url: 'http://127.0.0.1:5000/v3/'
        keystone.use_keystoneauth: true
        keystone.verify: '/path/to/custom/certs/ca-bundle.crt'


    .. note::
        By default the nova module will attempt to verify its connection
        utilizing the system certificates. If you need to verify against
        another bundle of CA certificates or want to skip verification
        altogether you will need to specify the `verify` option. You can
        specify True or False to verify (or not) against system certificates, a
        path to a bundle or CA certs to check against, or None to allow
        keystoneauth to search for the certificates on its own. (defaults to
        True)
"""

import logging

# Get logging started
log = logging.getLogger(__name__)

# Function alias to not shadow built-ins
__func_alias__ = {"list_": "list"}

try:
    import salt.utils.openstack.nova as suon

    HAS_NOVA = True
except NameError as exc:
    HAS_NOVA = False

# Define the module's virtual name
__virtualname__ = "nova"


def __virtual__():
    """
    Only load this module if nova
    is installed on this minion.
    """
    return HAS_NOVA


def _auth(profile=None):
    """
    Set up nova credentials
    """
    if profile:
        credentials = __salt__["config.option"](profile)
        user = credentials["keystone.user"]
        password = credentials["keystone.password"]
        tenant = credentials["keystone.tenant"]
        auth_url = credentials["keystone.auth_url"]
        region_name = credentials.get("keystone.region_name", None)
        api_key = credentials.get("keystone.api_key", None)
        os_auth_system = credentials.get("keystone.os_auth_system", None)
        use_keystoneauth = credentials.get("keystone.use_keystoneauth", False)
        verify = credentials.get("keystone.verify", None)
    else:
        user = __salt__["config.option"]("keystone.user")
        password = __salt__["config.option"]("keystone.password")
        tenant = __salt__["config.option"]("keystone.tenant")
        auth_url = __salt__["config.option"]("keystone.auth_url")
        region_name = __salt__["config.option"]("keystone.region_name")
        api_key = __salt__["config.option"]("keystone.api_key")
        os_auth_system = __salt__["config.option"]("keystone.os_auth_system")
        use_keystoneauth = __salt__["config.option"]("keystone.use_keystoneauth")
        verify = __salt__["config.option"]("keystone.verify")

    if use_keystoneauth is True:
        project_domain_name = credentials["keystone.project_domain_name"]
        user_domain_name = credentials["keystone.user_domain_name"]

        kwargs = {
            "username": user,
            "password": password,
            "project_id": tenant,
            "auth_url": auth_url,
            "region_name": region_name,
            "use_keystoneauth": use_keystoneauth,
            "verify": verify,
            "project_domain_name": project_domain_name,
            "user_domain_name": user_domain_name,
        }
    else:
        kwargs = {
            "username": user,
            "password": password,
            "api_key": api_key,
            "project_id": tenant,
            "auth_url": auth_url,
            "region_name": region_name,
            "os_auth_plugin": os_auth_system,
        }

    return suon.SaltNova(**kwargs)


def boot(name, flavor_id=0, image_id=0, profile=None, timeout=300):
    """
    Boot (create) a new instance

    name
        Name of the new instance (must be first)

    flavor_id
        Unique integer ID for the flavor

    image_id
        Unique integer ID for the image

    timeout
        How long to wait, after creating the instance, for the provider to
        return information about it (default 300 seconds).

        .. versionadded:: 2014.1.0

    CLI Example:

    .. code-block:: bash

        salt '*' nova.boot myinstance flavor_id=4596 image_id=2

    The flavor_id and image_id are obtained from nova.flavor_list and
    nova.image_list

    .. code-block:: bash

        salt '*' nova.flavor_list
        salt '*' nova.image_list
    """
    conn = _auth(profile)
    return conn.boot(name, flavor_id, image_id, timeout)


def volume_list(search_opts=None, profile=None):
    """
    List storage volumes

    search_opts
        Dictionary of search options

    profile
        Profile to use

    CLI Example:

    .. code-block:: bash

        salt '*' nova.volume_list search_opts='{"display_name": "myblock"}' profile=openstack

    """
    conn = _auth(profile)
    return conn.volume_list(search_opts=search_opts)


def volume_show(name, profile=None):
    """
    Create a block storage volume

    name
        Name of the volume

    profile
        Profile to use

    CLI Example:

    .. code-block:: bash

        salt '*' nova.volume_show myblock profile=openstack

    """
    conn = _auth(profile)
    return conn.volume_show(name)


def volume_create(name, size=100, snapshot=None, voltype=None, profile=None):
    """
    Create a block storage volume

    name
        Name of the new volume (must be first)

    size
        Volume size

    snapshot
        Block storage snapshot id

    voltype
        Type of storage

    profile
        Profile to build on

    CLI Example:

    .. code-block:: bash

        salt '*' nova.volume_create myblock size=300 profile=openstack

    """
    conn = _auth(profile)
    return conn.volume_create(name, size, snapshot, voltype)


def volume_delete(name, profile=None):
    """
    Destroy the volume

    name
        Name of the volume

    profile
        Profile to build on

    CLI Example:

    .. code-block:: bash

        salt '*' nova.volume_delete myblock profile=openstack

    """
    conn = _auth(profile)
    return conn.volume_delete(name)


def volume_detach(name, profile=None, timeout=300):
    """
    Attach a block storage volume

    name
        Name of the new volume to attach

    server_name
        Name of the server to detach from

    profile
        Profile to build on

    CLI Example:

    .. code-block:: bash

        salt '*' nova.volume_detach myblock profile=openstack

    """
    conn = _auth(profile)
    return conn.volume_detach(name, timeout)


def volume_attach(name, server_name, device="/dev/xvdb", profile=None, timeout=300):
    """
    Attach a block storage volume

    name
        Name of the new volume to attach

    server_name
        Name of the server to attach to

    device
        Name of the device on the server

    profile
        Profile to build on

    CLI Example:

    .. code-block:: bash

        salt '*' nova.volume_attach myblock slice.example.com profile=openstack
        salt '*' nova.volume_attach myblock server.example.com device='/dev/xvdb' profile=openstack

    """
    conn = _auth(profile)
    return conn.volume_attach(name, server_name, device, timeout)


def suspend(instance_id, profile=None):
    """
    Suspend an instance

    instance_id
        ID of the instance to be suspended

    CLI Example:

    .. code-block:: bash

        salt '*' nova.suspend 1138

    """
    conn = _auth(profile)
    return conn.suspend(instance_id)


def resume(instance_id, profile=None):
    """
    Resume an instance

    instance_id
        ID of the instance to be resumed

    CLI Example:

    .. code-block:: bash

        salt '*' nova.resume 1138

    """
    conn = _auth(profile)
    return conn.resume(instance_id)


def lock(instance_id, profile=None):
    """
    Lock an instance

    instance_id
        ID of the instance to be locked

    CLI Example:

    .. code-block:: bash

        salt '*' nova.lock 1138

    """
    conn = _auth(profile)
    return conn.lock(instance_id)


def delete(instance_id, profile=None):
    """
    Delete an instance

    instance_id
        ID of the instance to be deleted

    CLI Example:

    .. code-block:: bash

        salt '*' nova.delete 1138

    """
    conn = _auth(profile)
    return conn.delete(instance_id)


def flavor_list(profile=None):
    """
    Return a list of available flavors (nova flavor-list)

    CLI Example:

    .. code-block:: bash

        salt '*' nova.flavor_list
    """
    conn = _auth(profile)
    return conn.flavor_list()


def flavor_create(
    name,  # pylint: disable=C0103
    flavor_id=0,  # pylint: disable=C0103
    ram=0,
    disk=0,
    vcpus=1,
    profile=None,
):
    """
    Add a flavor to nova (nova flavor-create). The following parameters are
    required:

    name
        Name of the new flavor (must be first)
    flavor_id
        Unique integer ID for the new flavor
    ram
        Memory size in MB
    disk
        Disk size in GB
    vcpus
        Number of vcpus

    CLI Example:

    .. code-block:: bash

        salt '*' nova.flavor_create myflavor flavor_id=6 ram=4096 disk=10 vcpus=1
    """
    conn = _auth(profile)
    return conn.flavor_create(name, flavor_id, ram, disk, vcpus)


def flavor_delete(flavor_id, profile=None):  # pylint: disable=C0103
    """
    Delete a flavor from nova by id (nova flavor-delete)

    CLI Example:

    .. code-block:: bash

        salt '*' nova.flavor_delete 7
    """
    conn = _auth(profile)
    return conn.flavor_delete(flavor_id)


def keypair_list(profile=None):
    """
    Return a list of available keypairs (nova keypair-list)

    CLI Example:

    .. code-block:: bash

        salt '*' nova.keypair_list
    """
    conn = _auth(profile)
    return conn.keypair_list()


def keypair_add(name, pubfile=None, pubkey=None, profile=None):
    """
    Add a keypair to nova (nova keypair-add)

    CLI Examples:

    .. code-block:: bash

        salt '*' nova.keypair_add mykey pubfile=/home/myuser/.ssh/id_rsa.pub
        salt '*' nova.keypair_add mykey pubkey='ssh-rsa <key> myuser@mybox'
    """
    conn = _auth(profile)
    return conn.keypair_add(name, pubfile, pubkey)


def keypair_delete(name, profile=None):
    """
    Add a keypair to nova (nova keypair-delete)

    CLI Example:

    .. code-block:: bash

        salt '*' nova.keypair_delete mykey
    """
    conn = _auth(profile)
    return conn.keypair_delete(name)


def image_list(name=None, profile=None):
    """
    Return a list of available images (nova images-list + nova image-show)
    If a name is provided, only that image will be displayed.

    CLI Examples:

    .. code-block:: bash

        salt '*' nova.image_list
        salt '*' nova.image_list myimage
    """
    conn = _auth(profile)
    return conn.image_list(name)


def image_meta_set(
    image_id=None, name=None, profile=None, **kwargs
):  # pylint: disable=C0103
    """
    Sets a key=value pair in the metadata for an image (nova image-meta set)

    CLI Examples:

    .. code-block:: bash

        salt '*' nova.image_meta_set 6f52b2ff-0b31-4d84-8fd1-af45b84824f6 cheese=gruyere
        salt '*' nova.image_meta_set name=myimage salad=pasta beans=baked
    """
    conn = _auth(profile)
    return conn.image_meta_set(image_id, name, **kwargs)


def image_meta_delete(
    image_id=None, name=None, keys=None, profile=None  # pylint: disable=C0103
):
    """
    Delete a key=value pair from the metadata for an image
    (nova image-meta set)

    CLI Examples:

    .. code-block:: bash

        salt '*' nova.image_meta_delete 6f52b2ff-0b31-4d84-8fd1-af45b84824f6 keys=cheese
        salt '*' nova.image_meta_delete name=myimage keys=salad,beans
    """
    conn = _auth(profile)
    return conn.image_meta_delete(image_id, name, keys)


def list_(profile=None):
    """
    To maintain the feel of the nova command line, this function simply calls
    the server_list function.

    CLI Example:

    .. code-block:: bash

        salt '*' nova.list
    """
    return server_list(profile=profile)


def server_list(profile=None):
    """
    Return list of active servers

    CLI Example:

    .. code-block:: bash

        salt '*' nova.server_list
    """
    conn = _auth(profile)
    return conn.server_list()


def show(server_id, profile=None):
    """
    To maintain the feel of the nova command line, this function simply calls
    the server_show function.

    CLI Example:

    .. code-block:: bash

        salt '*' nova.show
    """
    return server_show(server_id, profile)


def server_list_detailed(profile=None):
    """
    Return detailed list of active servers

    CLI Example:

    .. code-block:: bash

        salt '*' nova.server_list_detailed
    """
    conn = _auth(profile)
    return conn.server_list_detailed()


def server_show(server_id, profile=None):
    """
    Return detailed information for an active server

    CLI Example:

    .. code-block:: bash

        salt '*' nova.server_show <server_id>
    """
    conn = _auth(profile)
    return conn.server_show(server_id)


def secgroup_create(name, description, profile=None):
    """
    Add a secgroup to nova (nova secgroup-create)

    CLI Example:

    .. code-block:: bash

        salt '*' nova.secgroup_create mygroup 'This is my security group'
    """
    conn = _auth(profile)
    return conn.secgroup_create(name, description)


def secgroup_delete(name, profile=None):
    """
    Delete a secgroup to nova (nova secgroup-delete)

    CLI Example:

    .. code-block:: bash

        salt '*' nova.secgroup_delete mygroup
    """
    conn = _auth(profile)
    return conn.secgroup_delete(name)


def secgroup_list(profile=None):
    """
    Return a list of available security groups (nova items-list)

    CLI Example:

    .. code-block:: bash

        salt '*' nova.secgroup_list
    """
    conn = _auth(profile)
    return conn.secgroup_list()


def server_by_name(name, profile=None):
    """
    Return information about a server

    name
        Server Name

    CLI Example:

    .. code-block:: bash

        salt '*' nova.server_by_name myserver profile=openstack
    """
    conn = _auth(profile)
    return conn.server_by_name(name)


# The following is a list of functions that need to be incorporated in the
# nova module. This list should be updated as functions are added.
#
# absolute-limits     Print a list of absolute limits for a user
# actions             Retrieve server actions.
# add-fixed-ip        Add new IP address to network.
# add-floating-ip     Add a floating IP address to a server.
# aggregate-add-host  Add the host to the specified aggregate.
# aggregate-create    Create a new aggregate with the specified details.
# aggregate-delete    Delete the aggregate by its id.
# aggregate-details   Show details of the specified aggregate.
# aggregate-list      Print a list of all aggregates.
# aggregate-remove-host
#                    Remove the specified host from the specified aggregate.
# aggregate-set-metadata
#                    Update the metadata associated with the aggregate.
# aggregate-update    Update the aggregate's name and optionally
#                    availability zone.
# cloudpipe-create    Create a cloudpipe instance for the given project
# cloudpipe-list      Print a list of all cloudpipe instances.
# console-log         Get console log output of a server.
# credentials         Show user credentials returned from auth
# describe-resource   Show details about a resource
# diagnostics         Retrieve server diagnostics.
# dns-create          Create a DNS entry for domain, name and ip.
# dns-create-private-domain
#                    Create the specified DNS domain.
# dns-create-public-domain
#                    Create the specified DNS domain.
# dns-delete          Delete the specified DNS entry.
# dns-delete-domain   Delete the specified DNS domain.
# dns-domains         Print a list of available dns domains.
# dns-list            List current DNS entries for domain and ip or domain
#                    and name.
# endpoints           Discover endpoints that get returned from the
#                    authenticate services
# floating-ip-create  Allocate a floating IP for the current tenant.
# floating-ip-delete  De-allocate a floating IP.
# floating-ip-list    List floating ips for this tenant.
# floating-ip-pool-list
#                    List all floating ip pools.
# get-vnc-console     Get a vnc console to a server.
# host-action         Perform a power action on a host.
# host-update         Update host settings.
# image-create        Create a new image by taking a snapshot of a running
#                    server.
# image-delete        Delete an image.
# live-migration      Migrates a running instance to a new machine.
# meta                Set or Delete metadata on a server.
# migrate             Migrate a server.
# pause               Pause a server.
# rate-limits         Print a list of rate limits for a user
# reboot              Reboot a server.
# rebuild             Shutdown, re-image, and re-boot a server.
# remove-fixed-ip     Remove an IP address from a server.
# remove-floating-ip  Remove a floating IP address from a server.
# rename              Rename a server.
# rescue              Rescue a server.
# resize              Resize a server.
# resize-confirm      Confirm a previous resize.
# resize-revert       Revert a previous resize (and return to the previous
#                    VM).
# root-password       Change the root password for a server.
# secgroup-add-group-rule
#                    Add a source group rule to a security group.
# secgroup-add-rule   Add a rule to a security group.
# secgroup-delete-group-rule
#                    Delete a source group rule from a security group.
# secgroup-delete-rule
#                    Delete a rule from a security group.
# secgroup-list-rules
#                    List rules for a security group.
# ssh                 SSH into a server.
# unlock              Unlock a server.
# unpause             Unpause a server.
# unrescue            Unrescue a server.
# usage-list          List usage data for all tenants
# volume-list         List all the volumes.
# volume-snapshot-create
#                    Add a new snapshot.
# volume-snapshot-delete
#                    Remove a snapshot.
# volume-snapshot-list
#                    List all the snapshots.
# volume-snapshot-show
#                    Show details about a snapshot.
# volume-type-create  Create a new volume type.
# volume-type-delete  Delete a specific flavor
# volume-type-list    Print a list of available 'volume types'.
# x509-create-cert    Create x509 cert for a user in tenant
# x509-get-root-cert  Fetches the x509 root cert.
