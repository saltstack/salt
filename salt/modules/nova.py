# -*- coding: utf-8 -*-
'''
Module for handling OpenStack Nova calls.

:depends:   - novaclient Python module
:configuration: This module is not usable until the user, password, tenant, and
    auth URL are specified either in a pillar or in the minion's config file.
    For example::

        keystone.user: admin
        keystone.password: verybadpass
        keystone.tenant: admin
        keystone.auth_url: 'http://127.0.0.1:5000/v2.0/'
        # Optional
        keystone.region_name: 'regionOne'

    If configuration for multiple OpenStack accounts is required, they can be
    set up as different configuration profiles:
    For example::

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
    For example::

        salt '*' nova.flavor_list profile=openstack1
'''

# Import third party libs
HAS_NOVA = False
try:
    from novaclient.v1_1 import client
    HAS_NOVA = True
except ImportError:
    pass

# Import python libs
import time
import logging

# Import salt libs
import salt.utils

# Get logging started
log = logging.getLogger(__name__)

# Function alias to not shadow built-ins
__func_alias__ = {
    'list_': 'list'
}


def __virtual__():
    '''
    Only load this module if nova
    is installed on this minion.
    '''
    if HAS_NOVA:
        return 'nova'
    return False


__opts__ = {}


def _auth(profile=None):
    '''
    Set up nova credentials
    '''
    if profile:
        credentials = __salt__['config.option'](profile)
        user = credentials['keystone.user']
        password = credentials['keystone.password']
        tenant = credentials['keystone.tenant']
        auth_url = credentials['keystone.auth_url']
        region_name = credentials.get('keystone.region_name', None)
    else:
        user = __salt__['config.option']('keystone.user')
        password = __salt__['config.option']('keystone.password')
        tenant = __salt__['config.option']('keystone.tenant')
        auth_url = __salt__['config.option']('keystone.auth_url')
        region_name = __salt__['config.option']('keystone.region_name')
    kwargs = {
        'username': user,
        'api_key': password,
        'project_id': tenant,
        'auth_url': auth_url,
        'service_type': 'compute',
    }
    if region_name:
        kwargs['region_name'] = region_name
    return client.Client(**kwargs)


def boot(name, flavor_id=0, image_id=0, profile=None, timeout=300):
    '''
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

        .. versionadded:: Hydrogen

    CLI Example:

    .. code-block:: bash

        salt '*' nova.boot myinstance flavor_id=4596 image_id=2

    The flavor_id and image_id are obtained from nova.flavor_list and
    nova.image_list

    .. code-block:: bash

        salt '*' nova.flavor_list
        salt '*' nova.image_list
    '''
    nt_ks = _auth(profile)
    response = nt_ks.servers.create(
        name=name, flavor=flavor_id, image=image_id
    )

    start = time.time()
    trycount = 0
    while True:
        trycount += 1
        try:
            return server_show(response.id, profile=profile)
        except Exception as exc:
            log.debug('Server information not yet available: {0}'.format(exc))
            time.sleep(1)
            if time.time() - start > timeout:
                log.error('Timed out after {0} seconds '
                          'while waiting for data'.format(timeout))
                return False

            log.debug(
                'Retrying server_show() (try {0})'.format(trycount)
            )


def suspend(instance_id, profile=None):
    '''
    Suspend an instance

    instance_id
        ID of the instance to be suspended

    CLI Example:

    .. code-block:: bash

        salt '*' nova.suspend 1138

    '''
    nt_ks = _auth(profile)
    response = nt_ks.servers.suspend(instance_id)
    return True


def resume(instance_id, profile=None):
    '''
    Resume an instance

    instance_id
        ID of the instance to be resumed

    CLI Example:

    .. code-block:: bash

        salt '*' nova.resume 1138

    '''
    nt_ks = _auth(profile)
    response = nt_ks.servers.resume(instance_id)
    return True


def lock(instance_id, profile=None):
    '''
    Lock an instance

    instance_id
        ID of the instance to be locked

    CLI Example:

    .. code-block:: bash

        salt '*' nova.lock 1138

    '''
    nt_ks = _auth(profile)
    response = nt_ks.servers.lock(instance_id)
    return True


def delete(instance_id, profile=None):
    '''
    Delete an instance

    instance_id
        ID of the instance to be deleted

    CLI Example:

    .. code-block:: bash

        salt '*' nova.delete 1138

    '''
    nt_ks = _auth(profile)
    response = nt_ks.servers.delete(instance_id)
    return True


def flavor_list(profile=None):
    '''
    Return a list of available flavors (nova flavor-list)

    CLI Example:

    .. code-block:: bash

        salt '*' nova.flavor_list
    '''
    nt_ks = _auth(profile)
    ret = {}
    for flavor in nt_ks.flavors.list():
        links = {}
        for link in flavor.links:
            links[link['rel']] = link['href']
        ret[flavor.name] = {
                'disk': flavor.disk,
                'id': flavor.id,
                'name': flavor.name,
                'ram': flavor.ram,
                'swap': flavor.swap,
                'vcpus': flavor.vcpus,
                'links': links,
            }
        if hasattr(flavor, 'rxtx_factor'):
            ret[flavor.name]['rxtx_factor'] = flavor.rxtx_factor
    return ret


def flavor_create(name,      # pylint: disable=C0103
                  id=0,      # pylint: disable=C0103
                  ram=0,
                  disk=0,
                  vcpus=1,
                  profile=None):
    '''
    Add a flavor to nova (nova flavor-create). The following parameters are
    required:

    name
        Name of the new flavor (must be first)
    id
        Unique integer ID for the new flavor
    ram
        Memory size in MB
    disk
        Disk size in GB
    vcpus
        Number of vcpus

    CLI Example:

    .. code-block:: bash

        salt '*' nova.flavor_create myflavor id=6 ram=4096 disk=10 vcpus=1
    '''
    nt_ks = _auth(profile)
    nt_ks.flavors.create(
        name=name, flavorid=id, ram=ram, disk=disk, vcpus=vcpus
    )
    return {'name': name,
            'id': id,
            'ram': ram,
            'disk': disk,
            'vcpus': vcpus}


def flavor_delete(id, profile=None):  # pylint: disable=C0103
    '''
    Delete a flavor from nova by id (nova flavor-delete)

    CLI Example:

    .. code-block:: bash

        salt '*' nova.flavor_delete 7
    '''
    nt_ks = _auth(profile)
    nt_ks.flavors.delete(id)
    return 'Flavor deleted: {0}'.format(id)


def keypair_list(profile=None):
    '''
    Return a list of available keypairs (nova keypair-list)

    CLI Example:

    .. code-block:: bash

        salt '*' nova.keypair_list
    '''
    nt_ks = _auth(profile)
    ret = {}
    for keypair in nt_ks.keypairs.list():
        ret[keypair.name] = {
                'name': keypair.name,
                'fingerprint': keypair.fingerprint,
                'public_key': keypair.public_key,
            }
    return ret


def keypair_add(name, pubfile=None, pubkey=None, profile=None):
    '''
    Add a keypair to nova (nova keypair-add)

    CLI Examples:

    .. code-block:: bash

        salt '*' nova.keypair_add mykey pubfile='/home/myuser/.ssh/id_rsa.pub'
        salt '*' nova.keypair_add mykey pubkey='ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAuGj4A7HcPLPl/etc== myuser@mybox'
    '''
    nt_ks = _auth(profile)
    if pubfile:
        ifile = salt.utils.fopen(pubfile, 'r')
        pubkey = ifile.read()
    if not pubkey:
        return False
    nt_ks.keypairs.create(name, public_key=pubkey)
    ret = {'name': name, 'pubkey': pubkey}
    return ret


def keypair_delete(name, profile=None):
    '''
    Add a keypair to nova (nova keypair-delete)

    CLI Example:

    .. code-block:: bash

        salt '*' nova.keypair_delete mykey'
    '''
    nt_ks = _auth(profile)
    nt_ks.keypairs.delete(name)
    return 'Keypair deleted: {0}'.format(name)


def image_list(name=None, profile=None):
    '''
    Return a list of available images (nova images-list + nova image-show)
    If a name is provided, only that image will be displayed.

    CLI Examples:

    .. code-block:: bash

        salt '*' nova.image_list
        salt '*' nova.image_list myimage
    '''
    nt_ks = _auth(profile)
    ret = {}
    for image in nt_ks.images.list():
        links = {}
        for link in image.links:
            links[link['rel']] = link['href']
        ret[image.name] = {
                'name': image.name,
                'id': image.id,
                'status': image.status,
                'progress': image.progress,
                'created': image.created,
                'updated': image.updated,
                'metadata': image.metadata,
                'links': links,
            }
        if hasattr(image, 'minDisk'):
            ret[image.name]['minDisk'] = image.minDisk
        if hasattr(image, 'minRam'):
            ret[image.name]['minRam'] = image.minRam
    if name:
        return {name: ret[name]}
    return ret


def image_meta_set(id=None, name=None, profile=None, **kwargs):  # pylint: disable=C0103
    '''
    Sets a key=value pair in the metadata for an image (nova image-meta set)

    CLI Examples:

    .. code-block:: bash

        salt '*' nova.image_meta_set id=6f52b2ff-0b31-4d84-8fd1-af45b84824f6 cheese=gruyere
        salt '*' nova.image_meta_set name=myimage salad=pasta beans=baked
    '''
    nt_ks = _auth(profile)
    if name:
        for image in nt_ks.images.list():
            if image.name == name:
                id = image.id  # pylint: disable=C0103
    if not id:
        return {'Error': 'A valid image name or id was not specified'}
    nt_ks.images.set_meta(id, kwargs)
    return {id: kwargs}


def image_meta_delete(id=None,     # pylint: disable=C0103
                      name=None,
                      keys=None,
                      profile=None):
    '''
    Delete a key=value pair from the metadata for an image (nova image-meta set)

    CLI Examples:

    .. code-block:: bash

        salt '*' nova.image_meta_delete id=6f52b2ff-0b31-4d84-8fd1-af45b84824f6 keys=cheese
        salt '*' nova.image_meta_delete name=myimage keys=salad,beans
    '''
    nt_ks = _auth(profile)
    if name:
        for image in nt_ks.images.list():
            if image.name == name:
                id = image.id  # pylint: disable=C0103
    pairs = keys.split(',')
    if not id:
        return {'Error': 'A valid image name or id was not specified'}
    nt_ks.images.delete_meta(id, pairs)
    return {id: 'Deleted: {0}'.format(pairs)}


def list_(profile=None):
    '''
    To maintain the feel of the nova command line, this function simply calls
    the server_list function.
    '''
    return server_list(profile=profile)


def server_list(profile=None):
    '''
    Return list of active servers

    CLI Example:

    .. code-block:: bash

        salt '*' nova.show
    '''
    nt_ks = _auth(profile)
    ret = {}
    for item in nt_ks.servers.list():
        ret[item.name] = {
            'id': item.id,
            'name': item.name,
            'status': item.status,
            'accessIPv4': item.accessIPv4,
            'accessIPv6': item.accessIPv6,
            'flavor': {'id': item.flavor['id'],
                       'links': item.flavor['links']},
            'image': {'id': item.image['id'],
                      'links': item.image['links']},
            }
    return ret


def show(server_id, profile=None):
    '''
    To maintain the feel of the nova command line, this function simply calls
    the server_show function.

    CLI Example:

    .. code-block:: bash

        salt '*' nova.show
    '''
    return server_show(server_id, profile)


def server_list_detailed(profile=None):
    '''
    Return detailed list of active servers

    CLI Example:

    .. code-block:: bash

        salt '*' nova.server_list_detailed
    '''
    nt_ks = _auth(profile)
    ret = {}
    for item in nt_ks.servers.list():
        ret[item.name] = {
            'OS-EXT-SRV-ATTR': {},
            'OS-EXT-STS': {},
            'accessIPv4': item.accessIPv4,
            'accessIPv6': item.accessIPv6,
            'addresses': item.addresses,
            'config_drive': item.config_drive,
            'created': item.created,
            'flavor': {'id': item.flavor['id'],
                       'links': item.flavor['links']},
            'hostId': item.hostId,
            'id': item.id,
            'image': {'id': item.image['id'],
                      'links': item.image['links']},
            'key_name': item.key_name,
            'links': item.links,
            'metadata': item.metadata,
            'name': item.name,
            'progress': item.progress,
            'status': item.status,
            'tenant_id': item.tenant_id,
            'updated': item.updated,
            'user_id': item.user_id,
        }
        if hasattr(item.__dict__, 'OS-DCF:diskConfig'):
            ret[item.name]['OS-DCF'] = {
                'diskConfig': item.__dict__['OS-DCF:diskConfig']
            }
        if hasattr(item.__dict__, 'OS-EXT-SRV-ATTR:host'):
            ret[item.name]['OS-EXT-SRV-ATTR']['host'] = \
                item.__dict__['OS-EXT-SRV-ATTR:host']
        if hasattr(item.__dict__, 'OS-EXT-SRV-ATTR:hypervisor_hostname'):
            ret[item.name]['OS-EXT-SRV-ATTR']['hypervisor_hostname'] = \
                item.__dict__['OS-EXT-SRV-ATTR:hypervisor_hostname']
        if hasattr(item.__dict__, 'OS-EXT-SRV-ATTR:instance_name'):
            ret[item.name]['OS-EXT-SRV-ATTR']['instance_name'] = \
                item.__dict__['OS-EXT-SRV-ATTR:instance_name']
        if hasattr(item.__dict__, 'OS-EXT-STS:power_state'):
            ret[item.name]['OS-EXT-STS']['power_state'] = \
                item.__dict__['OS-EXT-STS:power_state']
        if hasattr(item.__dict__, 'OS-EXT-STS:task_state'):
            ret[item.name]['OS-EXT-STS']['task_state'] = \
                item.__dict__['OS-EXT-STS:task_state']
        if hasattr(item.__dict__, 'OS-EXT-STS:vm_state'):
            ret[item.name]['OS-EXT-STS']['vm_state'] = \
                item.__dict__['OS-EXT-STS:vm_state']
        if hasattr(item.__dict__, 'security_groups'):
            ret[item.name]['security_groups'] = \
                item.__dict__['security_groups']
    return ret


def server_show(server_id, profile=None):
    '''
    Return detailed information for an active server

    CLI Example:

    .. code-block:: bash

        salt '*' nova.server_show <server_id>
    '''
    ret = {}
    servers = server_list_detailed(profile)
    for server_name, server in servers.iteritems():
        if str(server['id']) == server_id:
            ret[server_name] = server
    return ret


def secgroup_create(name, description, profile=None):
    '''
    Add a secgroup to nova (nova secgroup-create)

    CLI Example:

    .. code-block:: bash

        salt '*' nova.secgroup_create mygroup 'This is my security group'
    '''
    nt_ks = _auth(profile)
    nt_ks.security_groups.create(name, description)
    ret = {'name': name, 'description': description}
    return ret


def secgroup_delete(name, profile=None):
    '''
    Delete a secgroup to nova (nova secgroup-delete)

    CLI Example:

    .. code-block:: bash

        salt '*' nova.secgroup_delete mygroup
    '''
    nt_ks = _auth(profile)
    for item in nt_ks.security_groups.list():
        if item.name == name:
            nt_ks.security_groups.delete(item.id)
            return {name: 'Deleted security group: {0}'.format(name)}
    return 'Security group not found: {0}'.format(name)


def secgroup_list(profile=None):
    '''
    Return a list of available security groups (nova items-list)

    CLI Example:

    .. code-block:: bash

        salt '*' nova.secgroup_list
    '''
    nt_ks = _auth(profile)
    ret = {}
    for item in nt_ks.security_groups.list():
        ret[item.name] = {
                'name': item.name,
                'description': item.description,
                'id': item.id,
                'tenant_id': item.tenant_id,
                'rules': item.rules,
            }
    return ret


def _item_list(profile=None):
    '''
    Template for writing list functions
    Return a list of available items (nova items-list)

    CLI Example:

    .. code-block:: bash

        salt '*' nova.item_list
    '''
    nt_ks = _auth(profile)
    ret = []
    for item in nt_ks.items.list():
        ret.append(item.__dict__)
        #ret[item.name] = {
        #        'name': item.name,
        #    }
    return ret

#The following is a list of functions that need to be incorporated in the
#nova module. This list should be updated as functions are added.
#
#absolute-limits     Print a list of absolute limits for a user
#actions             Retrieve server actions.
#add-fixed-ip        Add new IP address to network.
#add-floating-ip     Add a floating IP address to a server.
#aggregate-add-host  Add the host to the specified aggregate.
#aggregate-create    Create a new aggregate with the specified details.
#aggregate-delete    Delete the aggregate by its id.
#aggregate-details   Show details of the specified aggregate.
#aggregate-list      Print a list of all aggregates.
#aggregate-remove-host
#                    Remove the specified host from the specified aggregate.
#aggregate-set-metadata
#                    Update the metadata associated with the aggregate.
#aggregate-update    Update the aggregate's name and optionally
#                    availability zone.
#cloudpipe-create    Create a cloudpipe instance for the given project
#cloudpipe-list      Print a list of all cloudpipe instances.
#console-log         Get console log output of a server.
#credentials         Show user credentials returned from auth
#describe-resource   Show details about a resource
#diagnostics         Retrieve server diagnostics.
#dns-create          Create a DNS entry for domain, name and ip.
#dns-create-private-domain
#                    Create the specified DNS domain.
#dns-create-public-domain
#                    Create the specified DNS domain.
#dns-delete          Delete the specified DNS entry.
#dns-delete-domain   Delete the specified DNS domain.
#dns-domains         Print a list of available dns domains.
#dns-list            List current DNS entries for domain and ip or domain
#                    and name.
#endpoints           Discover endpoints that get returned from the
#                    authenticate services
#floating-ip-create  Allocate a floating IP for the current tenant.
#floating-ip-delete  De-allocate a floating IP.
#floating-ip-list    List floating ips for this tenant.
#floating-ip-pool-list
#                    List all floating ip pools.
#get-vnc-console     Get a vnc console to a server.
#host-action         Perform a power action on a host.
#host-update         Update host settings.
#image-create        Create a new image by taking a snapshot of a running
#                    server.
#image-delete        Delete an image.
#live-migration      Migrates a running instance to a new machine.
#meta                Set or Delete metadata on a server.
#migrate             Migrate a server.
#pause               Pause a server.
#rate-limits         Print a list of rate limits for a user
#reboot              Reboot a server.
#rebuild             Shutdown, re-image, and re-boot a server.
#remove-fixed-ip     Remove an IP address from a server.
#remove-floating-ip  Remove a floating IP address from a server.
#rename              Rename a server.
#rescue              Rescue a server.
#resize              Resize a server.
#resize-confirm      Confirm a previous resize.
#resize-revert       Revert a previous resize (and return to the previous
#                    VM).
#root-password       Change the root password for a server.
#secgroup-add-group-rule
#                    Add a source group rule to a security group.
#secgroup-add-rule   Add a rule to a security group.
#secgroup-delete-group-rule
#                    Delete a source group rule from a security group.
#secgroup-delete-rule
#                    Delete a rule from a security group.
#secgroup-list-rules
#                    List rules for a security group.
#ssh                 SSH into a server.
#unlock              Unlock a server.
#unpause             Unpause a server.
#unrescue            Unrescue a server.
#usage-list          List usage data for all tenants
#volume-attach       Attach a volume to a server.
#volume-create       Add a new volume.
#volume-delete       Remove a volume.
#volume-detach       Detach a volume from a server.
#volume-list         List all the volumes.
#volume-show         Show details about a volume.
#volume-snapshot-create
#                    Add a new snapshot.
#volume-snapshot-delete
#                    Remove a snapshot.
#volume-snapshot-list
#                    List all the snapshots.
#volume-snapshot-show
#                    Show details about a snapshot.
#volume-type-create  Create a new volume type.
#volume-type-delete  Delete a specific flavor
#volume-type-list    Print a list of available 'volume types'.
#x509-create-cert    Create x509 cert for a user in tenant
#x509-get-root-cert  Fetches the x509 root cert.
