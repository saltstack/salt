'''
Module for handling openstack glance calls.

This module is not usable until the following are specified either in a pillar
or in the minion's config file:

keystone.user: admin
keystone.password: verybadpass
keystone.tenant: admin
keystone.tenant_id: f80919baedab48ec8931f200c65a50df
keystone.insecure: False   #(optional)
keystone.auth_url: 'http://127.0.0.1:5000/v2.0/'
'''
has_glance = False
try:
    from glanceclient import client
    from keystoneclient.v2_0 import client as ksclient
    has_glance = True
except ImportError:
    pass

def __virtual__():
    '''
    Only load this module if glance
    is installed on this minion.
    '''
    if has_glance:
        return 'glance'
    return False

__opts__ = {}


def _auth():
    '''
    Set up keystone credentials
    '''
    user = __salt__['config.option']('keystone.user')
    password = __salt__['config.option']('keystone.password')
    tenant = __salt__['config.option']('keystone.tenant')
    tenant_id = __salt__['config.option']('keystone.tenant_id')
    auth_url = __salt__['config.option']('keystone.auth_url')
    insecure = __salt__['config.option']('keystone.insecure')
    kwargs = {
        'username': user,
        'password': password,
        'tenant_name': tenant,
        'tenant_id': tenant_id,
        'auth_url': auth_url,
        'insecure': insecure,
        }
    ks = ksclient.Client(**kwargs)
    token = ks.auth_token
    endpoint = ks.service_catalog.url_for(
        service_type='image',
        endpoint_type='publicURL',
        )

    nt = client.Client('1', endpoint, token=token)
    return nt


def image_list():
    '''
    Return a list of available images (nova images-list)

    CLI Example::

        salt '*' nova.image_list
    '''
    nt = _auth()
    ret = {}
    for image in nt.images.list():
        ret[image.name] = {
                'id': image.id,
                'name': image.name,
                'checksum': image.checksum,
                'container_format': image.container_format,
                'created_at': image.created_at,
                'deleted': image.deleted,
                'disk_format': image.disk_format,
                'is_public': image.is_public,
                'min_disk': image.min_disk,
                'min_ram': image.min_ram,
                'owner': image.owner,
                'protected': image.protected,
                'size': image.size,
                'status': image.status,
                'updated_at': image.updated_at,
            }
    return ret


def _item_list():
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

    image-create        Create a new image.
    image-delete        Delete a specific image.
    image-download      Download a specific image.
    image-list          List images you can access.
    image-show          Describe a specific image.
    image-update        Update a specific image.
    member-create       Share a specific image with a tenant.
    member-delete       Remove a shared image from a tenant.
    member-list         Describe sharing permissions by image or tenant.

    '''
