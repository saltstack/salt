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
#import salt.ext.six as six
from salt.exceptions import (
    #CommandExecutionError,
    SaltInvocationError
    )
# pylint: disable=import-error
HAS_GLANCE = False
try:
    from glanceclient import client
    from glanceclient import exc
    HAS_GLANCE = True
    import logging
    logging.basicConfig(level=logging.DEBUG)
    log = logging.getLogger(__name__)
    import pprint
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


def _auth(profile=None, api_version=2, **connection_args):
    '''
    Set up glance credentials, returns
    `glanceclient.client.Client`. Optional parameter
    "api_version" defaults to 2.

    Only intended to be used within glance-enabled modules
    '''

    if profile:
        prefix = profile + ":glance."
    else:
        prefix = "glance."

    # look in connection_args first, then default to config file
    def get(key, default=None):
        '''
        TODO: Add docstring.
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
        log.debug('Calling glanceclient.client.Client(' +
            '{0}, {1}, **{2})'.format(api_version, endpoint, kwargs))
        try:
            return client.Client(api_version, endpoint, **kwargs)
        except exc.HTTPUnauthorized:
            kwargs.pop('token')
            kwargs['password'] = password
            log.warn('Supplied token is invalid, trying to ' +
                'get a new one using username and password.')

    if HAS_KEYSTONE:
        # TODO: redact kwargs['password']
        log.debug('Calling keystoneclient.v2_0.client.Client(' +
            '{0}, **{1})'.format(endpoint, kwargs))
        keystone = kstone.Client(**kwargs)
        log.debug(help(keystone.get_token))
        kwargs['token'] = keystone.get_token(keystone.session)
        kwargs.pop('password')
        log.debug('Calling glanceclient.client.Client(' +
            '{0}, {1}, **{2})'.format(api_version, endpoint, kwargs))
        return client.Client(api_version, endpoint, **kwargs)
    else:
        raise NotImplementedError(
            "Can't retrieve a auth_token without keystone")


def image_create(name, location, profile=None, visibility='public',
            container_format='bare', disk_format='raw'):
    '''
    Create an image (glance image-create)

    CLI Example:

    .. code-block:: bash

        salt '*' glance.image_create name=f16-jeos visibility=public \\
                 disk_format=qcow2 container_format=ovf \\
                 copy_from=http://berrange.fedorapeople.org/\
                    images/2012-02-29/f16-x86_64-openstack-sda.qcow2

    For all possible values, run ``glance help image-create`` on the minion.
    '''
    # valid options for "visibility":
    v_list = ['public', 'private']
    # valid options for "container_format":
    cf_list = ['ami', 'ari', 'aki', 'bare', 'ovf']
    # valid options for "disk_format":
    df_list = ['ami', 'ari', 'aki', 'vhd', 'vmdk',
               'raw', 'qcow2', 'vdi', 'iso']
    if visibility not in v_list:
        raise SaltInvocationError('"visibility" needs to be one ' +
            'of the following: {0}'.format(', '.join(v_list)))
    if container_format not in cf_list:
        raise SaltInvocationError('"container_format" needs to be ' +
            'one of the following: {0}'.format(', '.join(cf_list)))
    if disk_format not in df_list:
        raise SaltInvocationError('"disk_format" needs to be one ' +
            'of the following: {0}'.format(', '.join(df_list)))
    # Icehouse's glanceclient doesn't have add_location() and
    # glanceclient.v2 doesn't implement Client.images.create()
    # in a usable fashion. Thus we have to use v1 for now.
    g_client = _auth(profile, api_version=1)
    image = g_client.images.create(name=name, copy_from=location)
    return image_show(image.id)


def image_delete(id=None, name=None, profile=None):  # pylint: disable=C0103
    '''
    Delete an image (glance image-delete)

    CLI Examples:

    .. code-block:: bash

        salt '*' glance.image_delete c2eb2eb0-53e1-4a80-b990-8ec887eae7df
        salt '*' glance.image_delete id=c2eb2eb0-53e1-4a80-b990-8ec887eae7df
        salt '*' glance.image_delete name=f16-jeos
    '''
    g_client = _auth(profile)
    if name:
        for image in g_client.images.list():
            if image.name == name:
                id = image.id  # pylint: disable=C0103
                continue
    if not id:
        return {'Error': 'Unable to resolve image id'}
    g_client.images.delete(id)
    ret = 'Deleted image with ID {0}'.format(id)
    if name:
        ret += ' ({0})'.format(name)
    return ret


def image_show(id=None, name=None, profile=None):  # pylint: disable=C0103
    '''
    Return details about a specific image (glance image-show)

    CLI Example:

    .. code-block:: bash

        salt '*' glance.image_show
    '''
    g_client = _auth(profile)
    ret = {}
    if name:
        for image in g_client.images.list():
            if image.name == name:
                id = image.id  # pylint: disable=C0103
                continue
    if not id:
        return {'Error': 'Unable to resolve image id'}
    image = g_client.images.get(id)
    pformat = pprint.PrettyPrinter(indent=4).pformat
    log.debug('Properties of image {0}:\n{1}'.format(
        image.name, pformat(image)))
    # TODO: Get rid of the wrapping dict, see #24568
    ret[image.name] = {}
    schema = image_schema(profile=profile)
    if len(schema.keys()) == 1:
        schema = schema['image']
    for key in schema.keys():
        if key in image:
            ret[image.name][key] = image[key]
    return ret


def image_list(id=None, profile=None):  # pylint: disable=C0103
    '''
    Return a list of available images (glance image-list)

    CLI Example:

    .. code-block:: bash

        salt '*' glance.image_list
    '''
    g_client = _auth(profile)
    ret = {}
    # TODO: Get rid of the wrapping dict, see #24568
    for image in g_client.images.list():
        ret[image.name] = {
                'id': image.id,
                'name': image.name,
                'created_at': image.created_at,
                'file': image.file,
                'min_disk': image.min_disk,
                'min_ram': image.min_ram,
                'owner': image.owner,
                'protected': image.protected,
                'status': image.status,
                'tags': image.tags,
                'updated_at': image.updated_at,
                'visibility': image.visibility,
            }
        # Those cause AttributeErrors in Icehouse' glanceclient
        for attr in ['container_format', 'disk_format', 'size']:
            if attr in image:
                ret[image.name][attr] = image[attr]
        if id == image.id:
            return ret[image.name]
    return ret


def image_schema(profile=None):
    '''
    Returns names and descriptions of the schema "image"'s
    properties for this profile's instance of glance
    '''
    return schema_get('image', profile)


def schema_get(name, profile=None):
    '''
    Known valid names of schemas are:
      - image
      - images
      - member
      - members
    '''
    g_client = _auth(profile)
    pformat = pprint.PrettyPrinter(indent=4).pformat
    schema_props = {}
    for prop in g_client.schemas.get(name).properties:
        schema_props[prop.name] = prop.description
    log.debug('Properties of schema {0}:\n{1}'.format(
        name, pformat(schema_props)))
    return {name: schema_props}


def _item_list(profile=None):
    '''
    Template for writing list functions
    Return a list of available items (glance items-list)

    CLI Example:

    .. code-block:: bash

        salt '*' glance.item_list
    '''
    g_client = _auth(profile)
    ret = []
    for item in g_client.items.list():
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
