'''
Module for handling openstack nova calls.

This module is not usable until the user, password, tenant and auth url are
specified either in a pillar or in the minion's config file. For example:

nova.user: admin
nova.password: verybadpass
nova.tenant: admin
nova.auth_url: 'http://127.0.0.1:5000/v2.0/'
'''

from novaclient.v1_1 import client

__opts__ = {}


def _auth():
    '''
    Set up nova credentials
    '''
    user = __salt__['config.option']('nova.user')
    password = __salt__['config.option']('nova.password')
    tenant = __salt__['config.option']('nova.tenant')
    auth_url = __salt__['config.option']('nova.auth_url')
    nt = client.Client(user, password, tenant, auth_url, service_type="compute")
    return nt

def flavor_list():
    '''
    Return a list of available flavors (nova flavor-list)

    CLI Example::

        salt '*' nova.flavor_list
    '''
    nt = _auth()
    ret = {}
    for flavor in nt.flavors.list():
        links = []
        for link in flavor.links:
            links.append(link['href'])
        ret[flavor.name] = {
                'disk': flavor.disk,
                'id': flavor.id,
                'name': flavor.name,
                'ram': flavor.ram,
                'rxtx_factor': flavor.rxtx_factor,
                'swap': flavor.swap,
                'vcpus': flavor.vcpus,
                'links': links,
            }
    return ret

def keypair_list():
    '''
    Return a list of available keypairs (nova keypair-list)

    CLI Example::

        salt '*' nova.keypair_list
    '''
    nt = _auth()
    ret = {}
    for keypair in nt.keypairs.list():
        ret[keypair.name] = {
                'name': keypair.name,
                'fingerprint': keypair.fingerprint,
                'public_key': keypair.public_key,
            }
    return ret

def keypair_add(name, pubfile=None, pubkey=None):
    '''
    Add a keypair to nova (nova keypair-add)

    CLI Examples::

        salt '*' nova.keypair_add mykey pubfile='/home/myuser/.ssh/id_rsa.pub'
        salt '*' nova.keypair_add mykey pubkey='ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAuGj4A7HcPLPl/etc== myuser@mybox'
    '''
    nt = _auth()
    if pubfile:
        f = open(pubfile, 'r')
        pubkey = f.read()
    if not pubkey:
        return False
    nt.keypairs.create(name, public_key=pubkey)
    ret = { 'name': name, 'pubkey': pubkey }
    return ret

def keypair_delete(name):
    '''
    Add a keypair to nova (nova keypair-delete)

    CLI Example::

        salt '*' nova.keypair_delete mykey'
    '''
    nt = _auth()
    nt.keypairs.delete(name)
    return '{0} deleted'.format(name)

def item_list():
    '''
    Template for writing list functions
    Return a list of available items (nova items-list)

    CLI Example::

        salt '*' nova.item_list
    '''
    nt = _auth()
    ret = {}
    ret = []
    for item in nt.items.list():
        ret.append(item.__dict__)
        #ret[item.name] = {
        #        'name': item.name,
        #    }
    return ret

    '''
    The following is a list of functions that need to be incorporated in the
    nova module. This list should be updated as functions are added.

    absolute-limits     Print a list of absolute limits for a user
    actions             Retrieve server actions.
    add-fixed-ip        Add new IP address to network.
    add-floating-ip     Add a floating IP address to a server.
    aggregate-add-host  Add the host to the specified aggregate.
    aggregate-create    Create a new aggregate with the specified details.
    aggregate-delete    Delete the aggregate by its id.
    aggregate-details   Show details of the specified aggregate.
    aggregate-list      Print a list of all aggregates.
    aggregate-remove-host
                        Remove the specified host from the specfied aggregate.
    aggregate-set-metadata
                        Update the metadata associated with the aggregate.
    aggregate-update    Update the aggregate's name and optionally
                        availability zone.
    boot                Boot a new server.
    cloudpipe-create    Create a cloudpipe instance for the given project
    cloudpipe-list      Print a list of all cloudpipe instances.
    console-log         Get console log output of a server.
    credentials         Show user credentials returned from auth
    delete              Immediately shut down and delete a server.
    describe-resource   Show details about a resource
    diagnostics         Retrieve server diagnostics.
    dns-create          Create a DNS entry for domain, name and ip.
    dns-create-private-domain
                        Create the specified DNS domain.
    dns-create-public-domain
                        Create the specified DNS domain.
    dns-delete          Delete the specified DNS entry.
    dns-delete-domain   Delete the specified DNS domain.
    dns-domains         Print a list of available dns domains.
    dns-list            List current DNS entries for domain and ip or domain
                        and name.
    endpoints           Discover endpoints that get returned from the
                        authenticate services
    flavor-create       Create a new flavor
    flavor-delete       Delete a specific flavor
    floating-ip-create  Allocate a floating IP for the current tenant.
    floating-ip-delete  De-allocate a floating IP.
    floating-ip-list    List floating ips for this tenant.
    floating-ip-pool-list
                        List all floating ip pools.
    get-vnc-console     Get a vnc console to a server.
    host-action         Perform a power action on a host.
    host-update         Update host settings.
    image-create        Create a new image by taking a snapshot of a running
                        server.
    image-delete        Delete an image.
    image-list          Print a list of available images to boot from.
    image-meta          Set or Delete metadata on an image.
    image-show          Show details about the given image.
    list                List active servers.
    live-migration      Migrates a running instance to a new machine.
    lock                Lock a server.
    meta                Set or Delete metadata on a server.
    migrate             Migrate a server.
    pause               Pause a server.
    rate-limits         Print a list of rate limits for a user
    reboot              Reboot a server.
    rebuild             Shutdown, re-image, and re-boot a server.
    remove-fixed-ip     Remove an IP address from a server.
    remove-floating-ip  Remove a floating IP address from a server.
    rename              Rename a server.
    rescue              Rescue a server.
    resize              Resize a server.
    resize-confirm      Confirm a previous resize.
    resize-revert       Revert a previous resize (and return to the previous
                        VM).
    resume              Resume a server.
    root-password       Change the root password for a server.
    secgroup-add-group-rule
                        Add a source group rule to a security group.
    secgroup-add-rule   Add a rule to a security group.
    secgroup-create     Create a security group.
    secgroup-delete     Delete a security group.
    secgroup-delete-group-rule
                        Delete a source group rule from a security group.
    secgroup-delete-rule
                        Delete a rule from a security group.
    secgroup-list       List security groups for the curent tenant.
    secgroup-list-rules
                        List rules for a security group.
    show                Show details about the given server.
    ssh                 SSH into a server.
    suspend             Suspend a server.
    unlock              Unlock a server.
    unpause             Unpause a server.
    unrescue            Unrescue a server.
    usage-list          List usage data for all tenants
    volume-attach       Attach a volume to a server.
    volume-create       Add a new volume.
    volume-delete       Remove a volume.
    volume-detach       Detach a volume from a server.
    volume-list         List all the volumes.
    volume-show         Show details about a volume.
    volume-snapshot-create
                        Add a new snapshot.
    volume-snapshot-delete
                        Remove a snapshot.
    volume-snapshot-list
                        List all the snapshots.
    volume-snapshot-show
                        Show details about a snapshot.
    volume-type-create  Create a new volume type.
    volume-type-delete  Delete a specific flavor
    volume-type-list    Print a list of available 'volume types'.
    x509-create-cert    Create x509 cert for a user in tenant
    x509-get-root-cert  Fetches the x509 root cert.
    bash-completion     Prints all of the commands and options to stdout so
                        that the
    '''
