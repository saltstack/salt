'''
Module for handling openstack keystone calls.

This module is not usable until the user, password, tenant and auth url are
specified either in a pillar or in the minion's config file. For example:

keystone.user: admin
keystone.password: verybadpass
keystone.tenant: admin
keystone.auth_url: 'http://127.0.0.1:5000/v2.0/'
'''
has_keystone = False
try:
    from keystoneclient.v2_0 import client
    has_keystone = True
except ImportError:
    pass

def __virtual__():
    '''
    Only load this module if keystone
    is installed on this minion.
    '''
    if has_keystone:
        return 'keystone'
    return False

__opts__ = {}


def _auth():
    '''
    Set up keystone credentials
    '''
    user = __salt__['config.option']('keystone.user')
    password = __salt__['config.option']('keystone.password')
    tenant = __salt__['config.option']('keystone.tenant')
    auth_url = __salt__['config.option']('keystone.auth_url')
    nt = client.Client(
        username = user,
        password = password,
        tenant_name = tenant,
        auth_url = auth_url,
        )
    return nt


def ec2_credentials_list(id=None, name=None):
    '''
    Return a list of ec2_credentials for a specific user (keystone ec2-credentials-list)

    CLI Examples::

        salt '*' keystone.ec2_credentials_list 298ce377245c4ec9b70e1c639c89e654
        salt '*' keystone.ec2_credentials_list id=298ce377245c4ec9b70e1c639c89e654
        salt '*' keystone.ec2_credentials_list name=jack
    '''
    nt = _auth()
    ret = {}
    if name:
        for user in nt.users.list():
            if user.name == name:
                id = user.id
                continue
    if not id:
        return {'Error': 'Unable to resolve user id'}
    for ec2_credential in nt.ec2.list(id):
        ret[ec2_credential.user_id] = {
                'user_id': ec2_credential.user_id,
                'tenant_id': ec2_credential.tenant_id,
                'access': ec2_credential.access,
                'secret': ec2_credential.secret,
                }
    return ret


def endpoint_list():
    '''
    Return a list of available endpoints (keystone endpoints-list)

    CLI Example::

        salt '*' keystone.endpoint_list
    '''
    nt = _auth()
    ret = {}
    for endpoint in nt.endpoints.list():
        ret[endpoint.id] = {
                'id': endpoint.id,
                'region': endpoint.region,
                'adminurl': endpoint.adminurl,
                'internalurl': endpoint.internalurl,
                'publicurl': endpoint.publicurl,
                'service_id': endpoint.service_id,
                }
    return ret


def role_list():
    '''
    Return a list of available roles (keystone role-list)

    CLI Example::

        salt '*' keystone.role_list
    '''
    nt = _auth()
    ret = {}
    for role in nt.roles.list():
        ret[role.name] = {
                'id': role.id,
                'name': role.name,
                }
    return ret


def service_list():
    '''
    Return a list of available services (keystone services-list)

    CLI Example::

        salt '*' keystone.service_list
    '''
    nt = _auth()
    ret = {}
    for service in nt.services.list():
        ret[service.name] = {
                'id': service.id,
                'name': service.name,
                'description': service.description,
                'type': service.type,
                }
    return ret


def tenant_list():
    '''
    Return a list of available tenants (keystone tenants-list)

    CLI Example::

        salt '*' keystone.tenant_list
    '''
    nt = _auth()
    ret = {}
    for tenant in nt.tenants.list():
        ret[tenant.name] = {
                'id': tenant.id,
                'name': tenant.name,
                'description': tenant.description,
                'enabled': tenant.enabled,
                }
    return ret


def user_list():
    '''
    Return a list of available users (keystone user-list)

    CLI Example::

        salt '*' keystone.user_list
    '''
    nt = _auth()
    ret = {}
    for user in nt.users.list():
        ret[user.name] = {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'enabled': user.enabled,
                'tenant_id': user.tenantId,
                }
    return ret


def user_get(id=None, name=None):
    '''
    Return a specific users (keystone user-get)

    CLI Examples::

        salt '*' keystone.user_get c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.user_get id=c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.user_get name=nova
    '''
    nt = _auth()
    ret = {}
    if name:
        for user in nt.users.list():
            if user.name == name:
                id = user.id
                continue
    if not id:
        return {'Error': 'Unable to resolve user id'}
    user = nt.users.get(id)
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
    nt = _auth()
    item = nt.users.create(
        name=name,
        password=password,
        email=email,
        tenant_id=tenant_id,
        enabled=enabled,
        )
    return user_get(item.id)


def user_delete(id=None, name=None):
    '''
    Delete a user (keystone user-delete)

    CLI Examples::

        salt '*' keystone.user_delete c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.user_delete id=c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.user_delete name=nova
    '''
    nt = _auth()
    ret = {}
    if name:
        for user in nt.users.list():
            if user.name == name:
                id = user.id
                continue
    if not id:
        return {'Error': 'Unable to resolve user id'}
    nt.users.delete(id)
    ret = 'User ID {0} deleted'.format(id)
    if name:
        ret += ' ({0})'.format(name)
    return ret


def user_update(id=None, name=None, email=None, enabled=None):
    '''
    Update a user's information (keystone user-update)
    The following fields may be updated: name, email, enabled.
    Because the name is one of the fields, a valid user id is required.

    CLI Examples::

        salt '*' keystone.user_update id=c965f79c4f864eaaa9c3b41904e67082 name=newname
        salt '*' keystone.user_update c965f79c4f864eaaa9c3b41904e67082 name=newname email=newemail@domain.com
    '''
    nt = _auth()
    ret = {}
    if not id:
        return {'Error': 'Unable to resolve user id'}
    nt.users.update(user=id, name=name, email=email, enabled=enabled)
    ret = 'Info updated for user ID {0}'.format(id)
    return ret


def user_password_update(id=None, name=None, password=None):
    '''
    Update a user's password (keystone user-password-update)

    CLI Examples::

        salt '*' keystone.user_delete c965f79c4f864eaaa9c3b41904e67082 password=12345
        salt '*' keystone.user_delete id=c965f79c4f864eaaa9c3b41904e67082 password=12345
        salt '*' keystone.user_delete name=nova pasword=12345
    '''
    nt = _auth()
    ret = {}
    if name:
        for user in nt.users.list():
            if user.name == name:
                id = user.id
                continue
    if not id:
        return {'Error': 'Unable to resolve user id'}
    nt.users.update_password(user=id, password=password)
    ret = 'Password updated for user ID {0}'.format(id)
    if name:
        ret += ' ({0})'.format(name)
    return ret


def user_role_list(user_id=None, tenant_id=None, user_name=None, tenant_name=None):
    '''
    Return a list of available user_roles (keystone user_roles-list)

    CLI Examples::

        salt '*' keystone.user_role_list user_id=298ce377245c4ec9b70e1c639c89e654
        salt '*' keystone.user_role_list tenant_id=7167a092ece84bae8cead4bf9d15bb3b
        salt '*' keystone.user_role_list user_name=admin
        salt '*' keystone.user_role_list tenant_name=admin
    '''
    nt = _auth()
    ret = {}
    if user_name:
        for user in nt.users.list():
            if user.name == user_name:
                user_id = user.id
                continue
    if tenant_name:
        for tenant in nt.tenants.list():
            if tenant.name == tenant_name:
                tenant_id = tenant.id
                continue
    if not user_id and not tenant_id:
        return {'Error': 'Unable to resolve user or tenant id'}
    #ret = []
    for role in nt.roles.roles_for_user(user=user_id, tenant=tenant_id):
        #ret.append(role.__dict__)
        ret[role.name] = {
                'id': role.id,
                'name': role.name,
                'user_id': role.user_id,
                'tenant_id': role.tenant_id,
                }
    return ret


def _item_list():
    '''
    Template for writing list functions
    Return a list of available items (keystone items-list)

    CLI Example::

        salt '*' keystone.item_list
    '''
    nt = _auth()
    ret = {}
    ret = []
    for item in nt.items.list():
        ret.append(item.__dict__)
        #ret[item.name] = {
        #        'id': item.id,
        #        'name': item.name,
        #        }
    return ret


    '''
    The following is a list of functions that need to be incorporated in the
    keystone module. This list should be updated as functions are added.

    ec2-credentials-create
                        Create EC2-compatibile credentials for user per tenant
    ec2-credentials-delete
                        Delete EC2-compatibile credentials
    ec2-credentials-get
                        Display EC2-compatibile credentials
    endpoint-create     Create a new endpoint associated with a service
    endpoint-delete     Delete a service endpoint
    endpoint-get
    role-create         Create new role
    role-delete         Delete role
    role-get            Display role details
    service-create      Add service to Service Catalog
    service-delete      Delete service from Service Catalog
    service-get         Display service from Service Catalog
    tenant-create       Create new tenant
    tenant-delete       Delete tenant
    tenant-get          Display tenant details
    tenant-update       Update tenant name, description, enabled status
    token-get
    user-role-add       Add role to user
    user-role-remove    Remove role from user
    discover            Discover Keystone servers and show authentication
                        protocols and
    bootstrap           Grants a new role to a new user on a new tenant, after
                        creating each.
    bash-completion     Prints all of the commands and options to stdout.

    '''
