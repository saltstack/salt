'''
Module for handling openstack keystone calls.

:optdepends:    - keystoneclient Python adapter
:configuration: This module is not usable until the following are specified
    either in a pillar or in the minion's config file::

        keystone.user: admin
        keystone.password: verybadpass
        keystone.tenant: admin
        keystone.tenant_id: f80919baedab48ec8931f200c65a50df
        keystone.insecure: False   #(optional)
        keystone.auth_url: 'http://127.0.0.1:5000/v2.0/'

        OR (for token based authentication)

        keystone.token: 'ADMIN'
        keystone.endpoint: 'http://127.0.0.1:35357/v2.0'
'''

# Import third party libs
HAS_KEYSTONE = False
try:
    from keystoneclient.v2_0 import client
    HAS_KEYSTONE = True
except ImportError:
    pass

def __virtual__():
    '''
    Only load this module if keystone
    is installed on this minion.
    '''
    if HAS_KEYSTONE:
        return 'keystone'
    return False

__opts__ = {}


def auth():
    '''
    Set up keystone credentials

    Only intended to be used within Keystone-enabled modules
    '''
    user = __salt__['config.option']('keystone.user')
    password = __salt__['config.option']('keystone.password')
    tenant = __salt__['config.option']('keystone.tenant')
    tenant_id = __salt__['config.option']('keystone.tenant_id')
    auth_url = __salt__['config.option']('keystone.auth_url')
    insecure = __salt__['config.option']('keystone.insecure')
    token = __salt__['config.option']('keystone.token')
    endpoint = __salt__['config.option']('keystone.endpoint')

    kwargs = {}
    if token:
        kwargs = {
                'token': token,
                'endpoint': endpoint,
                }
    else:
        kwargs = {
                'username': user,
                'password': password,
                'tenant_name': tenant,
                'tenant_id': tenant_id,
                'auth_url': auth_url,
                'insecure': insecure,
                }

    return client.Client(**kwargs)


def ec2_credentials_get(id=None,       # pylint: disable-msg=C0103
                        name=None,
                        access=None):  # pylint: disable-msg=C0103
    '''
    Return ec2_credentials for a user (keystone ec2-credentials-get)

    CLI Examples::

        salt '*' keystone.ec2_credentials_get c965f79c4f864eaaa9c3b41904e67082 access=722787eb540849158668370dc627ec5f
        salt '*' keystone.ec2_credentials_get id=c965f79c4f864eaaa9c3b41904e67082 access=722787eb540849158668370dc627ec5f
        salt '*' keystone.ec2_credentials_get name=nova access=722787eb540849158668370dc627ec5f
    '''
    kstone = auth()
    ret = {}
    if name:
        for user in kstone.users.list():
            if user.name == name:
                id = user.id  # pylint: disable-msg=C0103
                continue
    if not id:
        return {'Error': 'Unable to resolve user id'}
    if not access:
        return {'Error': 'Access key is required'}
    ec2_credentials = kstone.ec2.get(user_id=id, access=access)
    ret[ec2_credentials.user_id] = {
            'user_id': ec2_credentials.user_id,
            'tenant': ec2_credentials.tenant_id,
            'access': ec2_credentials.access,
            'secret': ec2_credentials.secret,
            }
    return ret


def ec2_credentials_list(id=None, name=None):  # pylint: disable-msg=C0103
    '''
    Return a list of ec2_credentials for a specific user (keystone ec2-credentials-list)

    CLI Examples::

        salt '*' keystone.ec2_credentials_list 298ce377245c4ec9b70e1c639c89e654
        salt '*' keystone.ec2_credentials_list id=298ce377245c4ec9b70e1c639c89e654
        salt '*' keystone.ec2_credentials_list name=jack
    '''
    kstone = auth()
    ret = {}
    if name:
        for user in kstone.users.list():
            if user.name == name:
                id = user.id  # pylint: disable-msg=C0103
                continue
    if not id:
        return {'Error': 'Unable to resolve user id'}
    for ec2_credential in kstone.ec2.list(id):
        ret[ec2_credential.user_id] = {
                'user_id': ec2_credential.user_id,
                'tenant_id': ec2_credential.tenant_id,
                'access': ec2_credential.access,
                'secret': ec2_credential.secret,
                }
    return ret


def endpoint_get(service):
    '''
    Return a specific endpoint (keystone endpoint-get)

    CLI Example::

        salt '*' keystone.endpoint_get ec2
    '''
    kstone = auth()
    return kstone.service_catalog.url_for(service_type=service)


def endpoint_list():
    '''
    Return a list of available endpoints (keystone endpoints-list)

    CLI Example::

        salt '*' keystone.endpoint_list
    '''
    kstone = auth()
    ret = {}
    for endpoint in kstone.endpoints.list():
        ret[endpoint.id] = {
                'id': endpoint.id,
                'region': endpoint.region,
                'adminurl': endpoint.adminurl,
                'internalurl': endpoint.internalurl,
                'publicurl': endpoint.publicurl,
                'service_id': endpoint.service_id,
                }
    return ret


def role_get(id=None, name=None):  # pylint: disable-msg=C0103
    '''
    Return a specific roles (keystone role-get)

    CLI Examples::

        salt '*' keystone.role_get c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.role_get id=c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.role_get name=nova
    '''
    kstone = auth()
    ret = {}
    if name:
        for role in kstone.roles.list():
            if role.name == name:
                id = role.id  # pylint: disable-msg=C0103
                continue
    if not id:
        return {'Error': 'Unable to resolve role id'}
    role = kstone.roles.get(id)
    ret[role.name] = {
            'id': role.id,
            'name': role.name,
            }
    return ret


def role_list():
    '''
    Return a list of available roles (keystone role-list)

    CLI Example::

        salt '*' keystone.role_list
    '''
    kstone = auth()
    ret = {}
    for role in kstone.roles.list():
        ret[role.name] = {
                'id': role.id,
                'name': role.name,
                }
    return ret


def service_get(id=None, name=None):  # pylint: disable-msg=C0103
    '''
    Return a specific services (keystone service-get)

    CLI Examples::

        salt '*' keystone.service_get c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.service_get id=c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.service_get name=nova
    '''
    kstone = auth()
    ret = {}
    if name:
        for service in kstone.services.list():
            if service.name == name:
                id = service.id  # pylint: disable-msg=C0103
                continue
    if not id:
        return {'Error': 'Unable to resolve service id'}
    service = kstone.services.get(id)
    ret[service.name] = {
            'id': service.id,
            'name': service.name,
            'type': service.type,
            'description': service.description,
            }
    return ret


def service_list():
    '''
    Return a list of available services (keystone services-list)

    CLI Example::

        salt '*' keystone.service_list
    '''
    kstone = auth()
    ret = {}
    for service in kstone.services.list():
        ret[service.name] = {
                'id': service.id,
                'name': service.name,
                'description': service.description,
                'type': service.type,
                }
    return ret


def tenant_get(id=None, name=None):  # pylint: disable-msg=C0103
    '''
    Return a specific tenants (keystone tenant-get)

    CLI Examples::

        salt '*' keystone.tenant_get c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.tenant_get id=c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.tenant_get name=nova
    '''
    kstone = auth()
    ret = {}
    if name:
        for tenant in kstone.tenants.list():
            if tenant.name == name:
                id = tenant.id  # pylint: disable-msg=C0103
                continue
    if not id:
        return {'Error': 'Unable to resolve tenant id'}
    tenant = kstone.tenants.get(id)
    ret[tenant.name] = {
            'id': tenant.id,
            'name': tenant.name,
            'description': tenant.description,
            'enabled': tenant.enabled,
            }
    return ret


def tenant_list():
    '''
    Return a list of available tenants (keystone tenants-list)

    CLI Example::

        salt '*' keystone.tenant_list
    '''
    kstone = auth()
    ret = {}
    for tenant in kstone.tenants.list():
        ret[tenant.name] = {
                'id': tenant.id,
                'name': tenant.name,
                'description': tenant.description,
                'enabled': tenant.enabled,
                }
    return ret


def token_get():
    '''
    Return the configured tokens (keystone token-get)

    CLI Example::

        salt '*' keystone.token_get c965f79c4f864eaaa9c3b41904e67082
    '''
    kstone = auth()
    token = kstone.service_catalog.get_token()
    return {
            'id': token['id'],
            'expires': token['expires'],
            'user_id': token['user_id'],
            'tenant_id': token['tenant_id'],
            }


def user_list():
    '''
    Return a list of available users (keystone user-list)

    CLI Example::

        salt '*' keystone.user_list
    '''
    kstone = auth()
    ret = {}
    for user in kstone.users.list():
        ret[user.name] = {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'enabled': user.enabled,
                'tenant_id': user.tenantId,
                }
    return ret


def user_get(id=None, name=None):  # pylint: disable-msg=C0103
    '''
    Return a specific users (keystone user-get)

    CLI Examples::

        salt '*' keystone.user_get c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.user_get id=c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.user_get name=nova
    '''
    kstone = auth()
    ret = {}
    if name:
        for user in kstone.users.list():
            if user.name == name:
                id = user.id  # pylint: disable-msg=C0103
                continue
    if not id:
        return {'Error': 'Unable to resolve user id'}
    user = kstone.users.get(id)
    ret[user.name] = {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'enabled': user.enabled,
            'tenant_id': user.tenantId,
            }
    return ret


def user_create(name, password, email, tenant_id=None, enabled=True):
    '''
    Create a user (keystone user-create)

    CLI Examples::

        salt '*' keystone.user_create name=jack password=zero email=jack@halloweentown.org tenant_id=a28a7b5a999a455f84b1f5210264375e enabled=True
    '''
    kstone = auth()
    item = kstone.users.create(
        name=name,
        password=password,
        email=email,
        tenant_id=tenant_id,
        enabled=enabled,
        )
    return user_get(item.id)


def user_delete(id=None, name=None):  # pylint: disable-msg=C0103
    '''
    Delete a user (keystone user-delete)

    CLI Examples::

        salt '*' keystone.user_delete c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.user_delete id=c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.user_delete name=nova
    '''
    kstone = auth()
    if name:
        for user in kstone.users.list():
            if user.name == name:
                id = user.id  # pylint: disable-msg=C0103
                continue
    if not id:
        return {'Error': 'Unable to resolve user id'}
    kstone.users.delete(id)
    ret = 'User ID {0} deleted'.format(id)
    if name:
        ret += ' ({0})'.format(name)
    return ret


def user_update(id=None,        # pylint: disable-msg=C0103
                name=None,
                email=None,
                enabled=None):  # pylint: disable-msg=C0103
    '''
    Update a user's information (keystone user-update)
    The following fields may be updated: name, email, enabled.
    Because the name is one of the fields, a valid user id is required.

    CLI Examples::

        salt '*' keystone.user_update id=c965f79c4f864eaaa9c3b41904e67082 name=newname
        salt '*' keystone.user_update c965f79c4f864eaaa9c3b41904e67082 name=newname email=newemail@domain.com
    '''
    kstone = auth()
    if not id:
        return {'Error': 'Unable to resolve user id'}
    kstone.users.update(user=id, name=name, email=email, enabled=enabled)
    ret = 'Info updated for user ID {0}'.format(id)
    return ret


def user_password_update(id=None,         # pylint: disable-msg=C0103
                         name=None,
                         password=None):  # pylint: disable-msg=C0103
    '''
    Update a user's password (keystone user-password-update)

    CLI Examples::

        salt '*' keystone.user_delete c965f79c4f864eaaa9c3b41904e67082 password=12345
        salt '*' keystone.user_delete id=c965f79c4f864eaaa9c3b41904e67082 password=12345
        salt '*' keystone.user_delete name=nova password=12345
    '''
    kstone = auth()
    if name:
        for user in kstone.users.list():
            if user.name == name:
                id = user.id  # pylint: disable-msg=C0103
                continue
    if not id:
        return {'Error': 'Unable to resolve user id'}
    kstone.users.update_password(user=id, password=password)
    ret = 'Password updated for user ID {0}'.format(id)
    if name:
        ret += ' ({0})'.format(name)
    return ret


def user_role_list(user_id=None,
                   tenant_id=None,
                   user_name=None,
                   tenant_name=None):
    '''
    Return a list of available user_roles (keystone user_roles-list)

    CLI Examples::

        salt '*' keystone.user_role_list \
            user_id=298ce377245c4ec9b70e1c639c89e654 \
            tenant_id=7167a092ece84bae8cead4bf9d15bb3b
        salt '*' keystone.user_role_list user_name=admin tenant_name=admin
    '''
    kstone = auth()
    ret = {}
    if user_name:
        for user in kstone.users.list():
            if user.name == user_name:
                user_id = user.id
                continue
    if tenant_name:
        for tenant in kstone.tenants.list():
            if tenant.name == tenant_name:
                tenant_id = tenant.id
                continue
    if not user_id and not tenant_id:
        return {'Error': 'Unable to resolve user or tenant id'}
    for role in kstone.roles.roles_for_user(user=user_id, tenant=tenant_id):
        ret[role.name] = {
                'id': role.id,
                'name': role.name,
                'user_id': user_id,
                'tenant_id': tenant_id,
                }
    return ret


def _item_list():
    '''
    Template for writing list functions
    Return a list of available items (keystone items-list)

    CLI Example::

        salt '*' keystone.item_list
    '''
    kstone = auth()
    ret = []
    for item in kstone.items.list():
        ret.append(item.__dict__)
        #ret[item.name] = {
        #        'id': item.id,
        #        'name': item.name,
        #        }
    return ret


    #The following is a list of functions that need to be incorporated in the
    #keystone module. This list should be updated as functions are added.
    #
    #ec2-credentials-create
    #                    Create EC2-compatible credentials for user per tenant
    #ec2-credentials-delete
    #                    Delete EC2-compatible credentials
    #endpoint-create     Create a new endpoint associated with a service
    #endpoint-delete     Delete a service endpoint
    #role-create         Create new role
    #role-delete         Delete role
    #service-create      Add service to Service Catalog
    #service-delete      Delete service from Service Catalog
    #tenant-create       Create new tenant
    #tenant-delete       Delete tenant
    #tenant-update       Update tenant name, description, enabled status
    #user-role-add       Add role to user
    #user-role-remove    Remove role from user
    #discover            Discover Keystone servers and show authentication
    #                    protocols and
    #bootstrap           Grants a new role to a new user on a new tenant, after
    #                    creating each.
