# -*- coding: utf-8 -*-
'''
Module for handling openstack glance calls.

:optdepends:    - glanceclient Python adapter
:configuration: This module is not usable until the following are specified
    either in a pillar or in the minion's config file::

        glance.user: admin
        glance.password: verybadpass
        glance.tenant: admin
        glance.insecure: False   #(optional)
        glance.auth_url: 'http://127.0.0.1:5000/v2.0/'

    If configuration for multiple openstack accounts is required, they can be
    set up as different configuration profiles:
    For example::

        openstack1:
          glance.user: admin
          glance.password: verybadpass
          glance.tenant: admin
          glance.auth_url: 'http://127.0.0.1:5000/v2.0/'

        openstack2:
          glance.user: admin
          glance.password: verybadpass
          glance.tenant: admin
          glance.auth_url: 'http://127.0.0.2:5000/v2.0/'

    With this configuration in place, any of the keystone functions can make use
    of a configuration profile by declaring it explicitly.
    For example::

        salt '*' glance.image_list profile=openstack1
'''

# Import third party libs
HAS_GLANCE = False
try:
    from glanceclient.v2 import client
    import glanceclient.v2.images
    from glanceclient import exc
    HAS_GLANCE = True
    #import pprint
    import logging
    logging.basicConfig(level=logging.DEBUG)
    log = logging.getLogger(__name__)
    #import pprint
except ImportError:
    pass

# Workaround, as the Glance API v2 requires you to
# already have a keystone token
HAS_KEYSTONE = False
try:
    from keystoneclient.v2_0 import client as kstone
    HAS_KEYSTONE = True
except ImportError:
    pass

def __virtual__():
    '''
    Only load this module if glance
    is installed on this minion.
    '''
    if HAS_GLANCE:
        return 'glance'
    return False

__opts__ = {}


def _auth(profile=None, **connection_args):
    '''
    Set up glance credentials

    Only intended to be used within glance-enabled modules
    '''

    if profile:
        prefix = profile + ":glance."
    else:
        prefix = "glance."

    # look in connection_args first, then default to config file
    def get(key, default=None):
        '''
        TODO
        '''
        return connection_args.get('connection_' + key,
            __salt__['config.get'](prefix + key, default))

    user = get('user', 'admin')
    password = get('password', 'ADMIN')
    tenant = get('tenant', 'admin')
    tenant_id = get('tenant_id')
    auth_url = get('auth_url', 'http://127.0.0.1:35357/v2.0/')
    insecure = get('insecure', False)
    token = get('token')
    region = get('region')
    endpoint = get('endpoint', 'http://127.0.0.1:9292/')

    if token:
        kwargs = {'token': token,
                  'username': user,
                  'endpoint_url': endpoint,
                  'auth_url': auth_url,
                  'region_name': region,
                  'tenant_name': tenant}
    else:
        kwargs = {'username': user,
                  'password': password,
                  'tenant_id': tenant_id,
                  'auth_url': auth_url,
                  'region_name': region,
                  'tenant_name': tenant}
        # 'insecure' keyword not supported by all v2.0 keystone clients
        #   this ensures it's only passed in when defined
        if insecure:
            kwargs['insecure'] = True

    if token:
        log.debug('Calling glanceclient.v2.client.Client(' + \
            '{0}, **{1})'.format(endpoint, kwargs))
        try:
            return client.Client(endpoint, **kwargs)
        except exc.HTTPUnauthorized:
            log.warn('Supplied token is invalid, trying to ' + \
                'get a new one using username and password.')

    if HAS_KEYSTONE:
        # TODO: redact kwargs['password']
        log.debug('Calling keystoneclient.v2_0.client.Client(' + \
            '{0}, **{1})'.format(endpoint, kwargs))
        keystone = kstone.Client(**kwargs)
        log.debug(help(keystone.get_token))
        kwargs['token'] = keystone.get_token(keystone.session)
        kwargs.pop('password')
        log.debug('Calling glanceclient.v2.client.Client(' + \
            '{0}, **{1})'.format(endpoint, kwargs))
        return client.Client(endpoint, **kwargs)
    else:
        raise NotImplementedError(
            "Can't retrieve a auth_token without keystone")

def image_create(profile=None, **kwargs):
    '''
    Create an image (glance image-create)

    CLI Example:

    .. code-block:: bash

        salt '*' glance.image_create name=f16-jeos is_public=true \\
                 disk_format=qcow2 container_format=ovf \\
                 copy_from=http://berrange.fedorapeople.org/images/2012-02-29/f16-x86_64-openstack-sda.qcow2

    For all possible values, run ``glance help image-create`` on the minion.
    '''
    nt_ks = _auth(profile)
    fields = dict(
        filter(
            lambda x: x[0] in glanceclient.v1.images.CREATE_PARAMS,
            kwargs.items()
        )
    )

    image = nt_ks.images.create(**fields)
    newimage = image_list(str(image.id), profile)
    return {newimage['name']: newimage}


def image_delete(id=None, name=None, profile=None):  # pylint: disable=C0103
    '''
    Delete an image (glance image-delete)

    CLI Examples:

    .. code-block:: bash

        salt '*' glance.image_delete c2eb2eb0-53e1-4a80-b990-8ec887eae7df
        salt '*' glance.image_delete id=c2eb2eb0-53e1-4a80-b990-8ec887eae7df
        salt '*' glance.image_delete name=f16-jeos
    '''
    nt_ks = _auth(profile)
    if name:
        for image in nt_ks.images.list():
            if image.name == name:
                id = image.id  # pylint: disable=C0103
                continue
    if not id:
        return {'Error': 'Unable to resolve image id'}
    nt_ks.images.delete(id)
    ret = 'Deleted image with ID {0}'.format(id)
    if name:
        ret += ' ({0})'.format(name)
    return ret


def image_show(id=None, name=None, profile=None):  # pylint: disable=C0103
    '''
    Return details about a specific image (glance image-show)

    CLI Example:

    .. code-block:: bash

        salt '*' glance.image_get
    '''
    nt_ks = _auth(profile)
    ret = {}
    if name:
        for image in nt_ks.images.list():
            if image.name == name:
                id = image.id  # pylint: disable=C0103
                continue
    if not id:
        return {'Error': 'Unable to resolve image id'}
    image = nt_ks.images.get(id)
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


def image_list(id=None, profile=None):  # pylint: disable=C0103
    '''
    Return a list of available images (glance image-list)

    CLI Example:

    .. code-block:: bash

        salt '*' glance.image_list
    '''
    nt_ks = _auth(profile)
    #pformat = pprint.PrettyPrinter(indent=4).pformat
    ret = {}
    for image in nt_ks.images.list():
        #log.debug('Details for image "{0}":'.format(image.name) + \
        #    '\n{0}'.format(pformat(image)))
        #
        # Changes from v1 API:
        # * +file
        # * +tags
        # * -checksum
        # * -deleted
        # * is_public=True -> visibility='public'
        #
        ret[image.name] = {
                'id': image.id,
                'name': image.name,
                'container_format': image.container_format,
                'created_at': image.created_at,
                'disk_format': image.disk_format,
                'file': image.file,
                'min_disk': image.min_disk,
                'min_ram': image.min_ram,
                'owner': image.owner,
                'protected': image.protected,
                'size': image.size,
                'status': image.status,
                'tags': image.tags,
                'updated_at': image.updated_at,
                'visibility': image.visibility,
            }
        if id == image.id:
            return ret[image.name]
    return ret


def _item_list(profile=None):
    '''
    Template for writing list functions
    Return a list of available items (glance items-list)

    CLI Example:

    .. code-block:: bash

        salt '*' glance.item_list
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
#glance module. This list should be updated as functions are added.

#image-download      Download a specific image.
#image-update        Update a specific image.
#member-create       Share a specific image with a tenant.
#member-delete       Remove a shared image from a tenant.
#member-list         Describe sharing permissions by image or tenant.
