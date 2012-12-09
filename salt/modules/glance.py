'''
Module for handling openstack glance calls.

:optdepends:    - glanceclient Python adapter
:configuration: This module is not usable until the following are specified
    either in a pillar or in the minion's config file::

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
    import glanceclient.v1.images
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
    ks = __salt__['keystone.auth']()
    token = ks.auth_token
    endpoint = ks.service_catalog.url_for(
        service_type='image',
        endpoint_type='publicURL',
        )

    nt = client.Client('1', endpoint, token=token)
    return nt


def image_create(**kwargs):
    '''
    Create an image (nova image-create)

    CLI Example::

        salt '*' nova.image_create name=f16-jeos is_public=true \
                 disk_format=qcow2 container_format=ovf \
                 copy_from=http://berrange.fedorapeople.org/images/2012-02-29/f16-x86_64-openstack-sda.qcow2

    For all possible values, run::

        glance help image-create
    '''
    nt = _auth()
    CREATE_PARAMS = glanceclient.v1.images.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, kwargs.items()))

    image = nt.images.create(**fields)
    newimage = image_list(str(image.id))
    return {newimage['name']: newimage}


def image_delete(id=None, name=None):
    '''
    Delete an image (nova image-delete)

    CLI Examples::

        salt '*' nova.image_delete c2eb2eb0-53e1-4a80-b990-8ec887eae7df
        salt '*' nova.image_delete id=c2eb2eb0-53e1-4a80-b990-8ec887eae7df
        salt '*' nova.image_delete name=f16-jeos
    '''
    nt = _auth()
    if name:
        for image in nt.images.list():
            if image.name == name:
                id = image.id
                continue
    if not id:
        return {'Error': 'Unable to resolve image id'}
    nt.images.delete(id)
    ret = 'Deleted image with ID {0}'.format(id)
    if name:
        ret += ' ({0})'.format(name)
    return ret


def image_show(id=None, name=None):
    '''
    Return details about a specific image (nova image-show)

    CLI Example::

        salt '*' nova.image_get
    '''
    nt = _auth()
    ret = {}
    if name:
        for image in nt.images.list():
            if image.name == name:
                id = image.id
                continue
    if not id:
        return {'Error': 'Unable to resolve image id'}
    image = nt.images.get(id)
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


def image_list(id=None):
    '''
    Return a list of available images (nova image-list)

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
        if id == image.id:
            return ret[image.name]
    return ret


def _item_list():
    '''
    Template for writing list functions
    Return a list of available items (nova items-list)

    CLI Example::

        salt '*' nova.item_list
    '''
    nt = _auth()
    ret = []
    for item in nt.items.list():
        ret.append(item.__dict__)
        #ret[item.name] = {
        #        'name': item.name,
        #    }
    return ret

#The following is a list of functions that need to be incorporated in the
#nova module. This list should be updated as functions are added.

#image-download      Download a specific image.
#image-update        Update a specific image.
#member-create       Share a specific image with a tenant.
#member-delete       Remove a shared image from a tenant.
#member-list         Describe sharing permissions by image or tenant.
