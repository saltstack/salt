# -*- coding: utf-8 -*-
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

    If configuration for multiple openstack accounts is required, they can be
    set up as different configuration profiles:
    For example::

        openstack1:
          keystone.user: admin
          keystone.password: verybadpass
          keystone.tenant: admin
          keystone.tenant_id: f80919baedab48ec8931f200c65a50df
          keystone.auth_url: 'http://127.0.0.1:5000/v2.0/'

        openstack2:
          keystone.user: admin
          keystone.password: verybadpass
          keystone.tenant: admin
          keystone.tenant_id: f80919baedab48ec8931f200c65a50df
          keystone.auth_url: 'http://127.0.0.2:5000/v2.0/'

    With this configuration in place, any of the keystone functions can make use
    of a configuration profile by declaring it explicitly.
    For example::

        salt '*' keystone.tenant_list profile=openstack1
'''

# Import third party libs
HAS_KEYSTONE = False
try:
    from keystoneclient.v2_0 import client
    import keystoneclient.exceptions
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


def auth(profile=None):
    '''
    Set up keystone credentials

    Only intended to be used within Keystone-enabled modules
    '''
    if profile:
        user = __salt__['config.get']('{0}:keystone.user'.format(profile), 'admin')
        password = __salt__['config.get']('{0}:keystone.password'.format(profile), 'ADMIN')
        tenant = __salt__['config.get']('{0}:keystone.tenant'.format(profile), 'admin')
        tenant_id = __salt__['config.get']('{0}:keystone.tenant_id'.format(profile))
        auth_url = __salt__['config.get']('{0}:keystone.auth_url'.format(profile),
                                             'http://127.0.0.1:35357/v2.0/')
        insecure = __salt__['config.get']('{0}:keystone.insecure'.format(profile), False)
        token = __salt__['config.get']('{0}:keystone.token'.format(profile))
        endpoint = __salt__['config.get']('{0}:keystone.endpoint'.format(profile),
                                             'http://127.0.0.1:35357/v2.0')
    else:
        user = __salt__['config.get']('keystone.user', 'admin')
        password = __salt__['config.get']('keystone.password', 'ADMIN')
        tenant = __salt__['config.get']('keystone.tenant', 'admin')
        tenant_id = __salt__['config.get']('keystone.tenant_id')
        auth_url = __salt__['config.get']('keystone.auth_url',
                                             'http://127.0.0.1:35357/v2.0/')
        insecure = __salt__['config.get']('keystone.insecure', False)
        token = __salt__['config.get']('keystone.token')
        endpoint = __salt__['config.get']('keystone.endpoint',
                                             'http://127.0.0.1:35357/v2.0')

    kwargs = {}
    if token:
        kwargs = {'token': token,
                  'endpoint': endpoint}
    else:
        kwargs = {'username': user,
                  'password': password,
                  'tenant_name': tenant,
                  'tenant_id': tenant_id,
                  'auth_url': auth_url}
        # 'insecure' keyword not supported by all v2.0 keystone clients
        #   this ensures it's only passed in when defined
        if insecure:
            kwargs[insecure] = True

    return client.Client(**kwargs)


def ec2_credentials_create(user_id=None, name=None,
                           tenant_id=None, tenant=None,
                           profile=None):
    '''
    Create EC2-compatibile credentials for user per tenant

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.ec2_credentials_create name=admin tenant=admin
        salt '*' keystone.ec2_credentials_create \
            user_id=c965f79c4f864eaaa9c3b41904e67082 \
            tenant_id=722787eb540849158668370dc627ec5f
    '''
    kstone = auth(profile)

    if name:
        user_id = user_get(name=name)[name]['id']
    if not user_id:
        return {'Error': 'Could not resolve User ID'}

    if tenant:
        tenant_id = tenant_get(name=tenant)[tenant]['id']
    if not tenant_id:
        return {'Error': 'Could not resolve Tenant ID'}

    newec2 = kstone.ec2.create(user_id, tenant_id)
    return {'access': newec2.access,
            'secret': newec2.secret,
            'tenant_id': newec2.tenant_id,
            'user_id': newec2.user_id}


def ec2_credentials_delete(user_id=None, name=None,
                           access_key=None, profile=None):
    '''
    Delete EC2-compatibile credentials

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.ec2_credentials_delete \
            860f8c2c38ca4fab989f9bc56a061a64
            access_key=5f66d2f24f604b8bb9cd28886106f442
        salt '*' keystone.ec2_credentials_delete name=admin \
            access_key=5f66d2f24f604b8bb9cd28886106f442
    '''
    kstone = auth(profile)

    if name:
        user_id = user_get(name=name)[name]['id']
    if not user_id:
        return {'Error': 'Could not resolve User ID'}
    kstone.ec2.delete(user_id, access_key)
    return 'ec2 key "{0}" deleted under user id "{1}"'.format(access_key,
                                                              user_id)


def ec2_credentials_get(user_id=None,
                        name=None,
                        access=None,
                        profile=None):
    '''
    Return ec2_credentials for a user (keystone ec2-credentials-get)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.ec2_credentials_get c965f79c4f864eaaa9c3b41904e67082 access=722787eb540849158668370dc627ec5f
        salt '*' keystone.ec2_credentials_get user_id=c965f79c4f864eaaa9c3b41904e67082 access=722787eb540849158668370dc627ec5f
        salt '*' keystone.ec2_credentials_get name=nova access=722787eb540849158668370dc627ec5f
    '''
    kstone = auth(profile)
    ret = {}
    if name:
        for user in kstone.users.list():
            if user.name == name:
                user_id = user.id
                break
    if not user_id:
        return {'Error': 'Unable to resolve user id'}
    if not access:
        return {'Error': 'Access key is required'}
    ec2_credentials = kstone.ec2.get(user_id=user_id, access=access)
    ret[ec2_credentials.user_id] = {'user_id': ec2_credentials.user_id,
                                    'tenant': ec2_credentials.tenant_id,
                                    'access': ec2_credentials.access,
                                    'secret': ec2_credentials.secret}
    return ret


def ec2_credentials_list(user_id=None, name=None, profile=None):
    '''
    Return a list of ec2_credentials for a specific user (keystone ec2-credentials-list)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.ec2_credentials_list 298ce377245c4ec9b70e1c639c89e654
        salt '*' keystone.ec2_credentials_list user_id=298ce377245c4ec9b70e1c639c89e654
        salt '*' keystone.ec2_credentials_list name=jack
    '''
    kstone = auth(profile)
    ret = {}
    if name:
        for user in kstone.users.list():
            if user.name == name:
                user_id = user.id
                break
    if not user_id:
        return {'Error': 'Unable to resolve user id'}
    for ec2_credential in kstone.ec2.list(user_id):
        ret[ec2_credential.user_id] = {'user_id': ec2_credential.user_id,
                                       'tenant_id': ec2_credential.tenant_id,
                                       'access': ec2_credential.access,
                                       'secret': ec2_credential.secret}
    return ret


def endpoint_get(service, profile=None):
    '''
    Return a specific endpoint (keystone endpoint-get)

    CLI Example:

    .. code-block:: bash

        salt '*' keystone.endpoint_get ec2
    '''
    kstone = auth(profile)
    return kstone.service_catalog.url_for(service_type=service)


def endpoint_list(profile=None):
    '''
    Return a list of available endpoints (keystone endpoints-list)

    CLI Example:

    .. code-block:: bash

        salt '*' keystone.endpoint_list
    '''
    kstone = auth(profile)
    ret = {}
    for endpoint in kstone.endpoints.list():
        ret[endpoint.id] = {'id': endpoint.id,
                            'region': endpoint.region,
                            'adminurl': endpoint.adminurl,
                            'internalurl': endpoint.internalurl,
                            'publicurl': endpoint.publicurl,
                            'service_id': endpoint.service_id}
    return ret


def role_create(name, profile=None):
    '''
    Create named role

    .. code-block:: bash

        salt '*' keystone.role_create admin
    '''

    kstone = auth(profile)
    if 'Error' not in role_get(name=name):
        return {'Error': 'Role "{0}" already exists'.format(name)}
    role = kstone.roles.create(name)
    return role_get(name=name)


def role_delete(role_id=None, name=None, profile=None):
    '''
    Delete a role (keystone role-delete)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.role_delete c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.role_delete role_id=c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.role_delete name=admin
    '''
    kstone = auth(profile)

    if name:
        for role in kstone.roles.list():
            if role.name == name:
                role_id = role.id
                break
    if not role_id:
        return {'Error': 'Unable to resolve role id'}
    role = role_get(role_id)
    kstone.roles.delete(role)
    ret = 'Role ID {0} deleted'.format(role_id)
    if name:
        ret += ' ({0})'.format(name)
    return ret


def role_get(role_id=None, name=None, profile=None):
    '''
    Return a specific roles (keystone role-get)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.role_get c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.role_get role_id=c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.role_get name=nova
    '''
    kstone = auth(profile)
    ret = {}
    if name:
        for role in kstone.roles.list():
            if role.name == name:
                role_id = role.id
                break
    if not role_id:
        return {'Error': 'Unable to resolve role id'}
    role = kstone.roles.get(role_id)
    ret[role.name] = {'id': role.id,
                      'name': role.name}
    return ret


def role_list(profile=None):
    '''
    Return a list of available roles (keystone role-list)

    CLI Example:

    .. code-block:: bash

        salt '*' keystone.role_list
    '''
    kstone = auth(profile)
    ret = {}
    for role in kstone.roles.list():
        ret[role.name] = {'id': role.id,
                          'name': role.name}
    return ret


def service_create(name, service_type, description=None, profile=None):
    '''
    Add service to Keystone service catalog

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.service_create nova compute \
                'OpenStack Compute Service'
    '''
    kstone = auth(profile)
    service = kstone.services.create(name, service_type, description)
    return service_get(service.id)


def service_delete(service_id=None, name=None, profile=None):
    '''
    Delete a service from Keystone service catalog

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.service_delete c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.service_delete name=nova
    '''
    kstone = auth(profile)
    if name:
        service_id = service_get(name=name)[name]['id']
    service = kstone.services.delete(service_id)
    return 'Keystone service ID "{0}" deleted'.format(service_id)


def service_get(service_id=None, name=None, profile=None):
    '''
    Return a specific services (keystone service-get)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.service_get c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.service_get service_id=c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.service_get name=nova
    '''
    kstone = auth(profile)
    ret = {}
    if name:
        for service in kstone.services.list():
            if service.name == name:
                service_id = service.id
                break
    if not service_id:
        return {'Error': 'Unable to resolve service id'}
    service = kstone.services.get(service_id)
    ret[service.name] = {'id': service.id,
                         'name': service.name,
                         'type': service.type,
                         'description': service.description}
    return ret


def service_list(profile=None):
    '''
    Return a list of available services (keystone services-list)

    CLI Example:

    .. code-block:: bash

        salt '*' keystone.service_list
    '''
    kstone = auth(profile)
    ret = {}
    for service in kstone.services.list():
        ret[service.name] = {'id': service.id,
                             'name': service.name,
                             'description': service.description,
                             'type': service.type}
    return ret


def tenant_create(name, description=None, enabled=True, profile=None):
    '''
    Create a keystone tenant

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.tenant_create nova description='nova tenant'
        salt '*' keystone.tenant_create test enabled=False
    '''
    kstone = auth(profile)
    new = kstone.tenants.create(name, description, enabled)
    return tenant_get(new.id)


def tenant_delete(tenant_id=None, name=None, profile=None):
    '''
    Delete a tenant (keystone tenant-delete)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.tenant_delete c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.tenant_delete tenant_id=c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.tenant_delete name=demo
    '''
    kstone = auth(profile)
    if name:
        for tenant in kstone.tenants.list():
            if tenant.name == name:
                tenant_id = tenant.id
                break
    if not tenant_id:
        return {'Error': 'Unable to resolve tenant id'}
    kstone.tenants.delete(tenant_id)
    ret = 'Tenant ID {0} deleted'.format(tenant_id)
    if name:
        ret += ' ({0})'.format(name)
    return ret


def tenant_get(tenant_id=None, name=None, profile=None):
    '''
    Return a specific tenants (keystone tenant-get)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.tenant_get c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.tenant_get tenant_id=c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.tenant_get name=nova
    '''
    kstone = auth(profile)
    ret = {}
    if name:
        for tenant in kstone.tenants.list():
            if tenant.name == name:
                tenant_id = tenant.id
                break
    if not tenant_id:
        return {'Error': 'Unable to resolve tenant id'}
    tenant = kstone.tenants.get(tenant_id)
    ret[tenant.name] = {'id': tenant.id,
                        'name': tenant.name,
                        'description': tenant.description,
                        'enabled': tenant.enabled}
    return ret


def tenant_list(profile=None):
    '''
    Return a list of available tenants (keystone tenants-list)

    CLI Example:

    .. code-block:: bash

        salt '*' keystone.tenant_list
    '''
    kstone = auth(profile)
    ret = {}
    for tenant in kstone.tenants.list():
        ret[tenant.name] = {'id': tenant.id,
                            'name': tenant.name,
                            'description': tenant.description,
                            'enabled': tenant.enabled}
    return ret


def tenant_update(tenant_id=None, name=None, email=None,
                  enabled=None, profile=None):
    '''
    Update a tenant's information (keystone tenant-update)
    The following fields may be updated: name, email, enabled.
    Can only update name if targeting by ID

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.tenant_update name=admin enabled=True
        salt '*' keystone.tenant_update c965f79c4f864eaaa9c3b41904e67082 name=admin email=admin@domain.com
    '''
    kstone = auth(profile)
    if not tenant_id:
        for tenant in kstone.tenants.list():
            if tenant.name == name:
                tenant_id = tenant.id
                break
    if not tenant_id:
        return {'Error': 'Unable to resolve tenant id'}

    tenant = kstone.tenants.get(tenant_id)
    if not name:
        name = tenant.name
    if not email:
        email = tenant.email
    if enabled is None:
        enabled = tenant.enabled
    kstone.tenants.update(tenant_id, name, email, enabled)


def token_get(profile=None):
    '''
    Return the configured tokens (keystone token-get)

    CLI Example:

    .. code-block:: bash

        salt '*' keystone.token_get c965f79c4f864eaaa9c3b41904e67082
    '''
    kstone = auth(profile)
    token = kstone.service_catalog.get_token()
    return {'id': token['id'],
            'expires': token['expires'],
            'user_id': token['user_id'],
            'tenant_id': token['tenant_id']}


def user_list(profile=None):
    '''
    Return a list of available users (keystone user-list)

    CLI Example:

    .. code-block:: bash

        salt '*' keystone.user_list
    '''
    kstone = auth(profile)
    ret = {}
    for user in kstone.users.list():
        ret[user.name] = {'id': user.id,
                          'name': user.name,
                          'email': user.email,
                          'enabled': user.enabled}
        if hasattr(user.__dict__, 'tenantId'):
            ret[user.name]['tenant_id'] = user.__dict__['tenantId']
    return ret


def user_get(user_id=None, name=None, profile=None):
    '''
    Return a specific users (keystone user-get)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.user_get c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.user_get user_id=c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.user_get name=nova
    '''
    kstone = auth(profile)
    ret = {}
    if name:
        for user in kstone.users.list():
            if user.name == name:
                user_id = user.id
                break
    if not user_id:
        return {'Error': 'Unable to resolve user id'}
    user = kstone.users.get(user_id)
    ret[user.name] = {'id': user.id,
                      'name': user.name,
                      'email': user.email,
                      'enabled': user.enabled}
    if hasattr(user.__dict__, 'tenantId'):
        ret[user.name]['tenant_id'] = user.__dict__['tenantId']
    return ret


def user_create(name, password, email, tenant_id=None,
                enabled=True, profile=None):
    '''
    Create a user (keystone user-create)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.user_create name=jack password=zero email=jack@halloweentown.org tenant_id=a28a7b5a999a455f84b1f5210264375e enabled=True
    '''
    kstone = auth(profile)
    item = kstone.users.create(name=name,
                               password=password,
                               email=email,
                               tenant_id=tenant_id,
                               enabled=enabled)
    return user_get(item.id)


def user_delete(user_id=None, name=None, profile=None):
    '''
    Delete a user (keystone user-delete)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.user_delete c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.user_delete user_id=c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.user_delete name=nova
    '''
    kstone = auth(profile)
    if name:
        for user in kstone.users.list():
            if user.name == name:
                user_id = user.id
                break
    if not user_id:
        return {'Error': 'Unable to resolve user id'}
    kstone.users.delete(user_id)
    ret = 'User ID {0} deleted'.format(user_id)
    if name:
        ret += ' ({0})'.format(name)
    return ret


def user_update(user_id=None,
                name=None,
                email=None,
                enabled=None,
                tenant=None,
                profile=None):
    '''
    Update a user's information (keystone user-update)
    The following fields may be updated: name, email, enabled, tenant.
    Because the name is one of the fields, a valid user id is required.

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.user_update user_id=c965f79c4f864eaaa9c3b41904e67082 name=newname
        salt '*' keystone.user_update c965f79c4f864eaaa9c3b41904e67082 name=newname email=newemail@domain.com
    '''
    kstone = auth(profile)
    if not user_id:
        for user in kstone.users.list():
            if user.name == name:
                user_id = user.id
                break
        if not user_id:
            return {'Error': 'Unable to resolve user id'}
    user = kstone.users.get(user_id)
    # Keep previous settings if not updating them
    if not name:
        name = user.name
    if not email:
        email = user.email
    if enabled is None:
        enabled = user.enabled
    kstone.users.update(user=user_id, name=name, email=email, enabled=enabled)
    if tenant:
        for t in kstone.tenants.list():
            if t.name == tenant:
                tenant_id = t.id
                break
        kstone.users.update_tenant(user_id, tenant_id)
    ret = 'Info updated for user ID {0}'.format(user_id)
    return ret


def user_verify_password(user_id=None,
                         name=None,
                         password=None,
                         profile=None):
    '''
    Verify a user's password

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.user_verify_password name=test password=foobar
        salt '*' keystone.user_verify_password user_id=c965f79c4f864eaaa9c3b41904e67082 password=foobar
    '''
    kstone = auth(profile)
    auth_url = __salt__['config.option']('keystone.endpoint',
                                         'http://127.0.0.1:35357/v2.0')
    if user_id:
        for user in kstone.users.list():
            if user.id == user_id:
                name = user.name
                break
    if not name:
        return {'Error': 'Unable to resolve user name'}
    kwargs = {'username': name,
              'password': password,
              'auth_url': auth_url}
    try:
        userauth = client.Client(**kwargs)
    except keystoneclient.exceptions.Unauthorized:
        return False
    return True


def user_password_update(user_id=None,
                         name=None,
                         password=None,
                         profile=None):
    '''
    Update a user's password (keystone user-password-update)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.user_delete c965f79c4f864eaaa9c3b41904e67082 password=12345
        salt '*' keystone.user_delete user_id=c965f79c4f864eaaa9c3b41904e67082 password=12345
        salt '*' keystone.user_delete name=nova password=12345
    '''
    kstone = auth(profile)
    if name:
        for user in kstone.users.list():
            if user.name == name:
                user_id = user.id
                break
    if not user_id:
        return {'Error': 'Unable to resolve user id'}
    kstone.users.update_password(user=user_id, password=password)
    ret = 'Password updated for user ID {0}'.format(user_id)
    if name:
        ret += ' ({0})'.format(name)
    return ret


def user_role_add(user_id=None, user=None,
                  tenant_id=None, tenant=None,
                  role_id=None, role=None,
                  profile=None):
    '''
    Add role for user in tenant (keystone user-role-add)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.user_role_add \
            user_id=298ce377245c4ec9b70e1c639c89e654 \
            tenant_id=7167a092ece84bae8cead4bf9d15bb3b \
            role_id=ce377245c4ec9b70e1c639c89e8cead4
        salt '*' keystone.user_role_add user=admin tenant=admin role=admin
    '''
    kstone = auth(profile)
    if user:
        user_id = user_get(name=user)[user]['id']
    else:
        user = user_get(user_id).keys()[0]['name']
    if not user_id:
        return {'Error': 'Unable to resolve user id'}

    if tenant:
        tenant_id = tenant_get(name=tenant)[tenant]['id']
    else:
        tenant = tenant_get(tenant_id).keys()[0]['name']
    if not tenant_id:
        return {'Error': 'Unable to resolve tenant id'}

    if role:
        role_id = role_get(name=role)[role]['id']
    else:
        role = role_get(role_id).keys()[0]['name']
    if not role_id:
        return {'Error': 'Unable to resolve role id'}

    kstone.roles.add_user_role(user_id, role_id, tenant_id)
    ret_msg = '"{0}" role added for user "{1}" for "{2}" tenant'
    return ret_msg.format(role, user, tenant)


def user_role_remove(user_id=None, user=None,
                     tenant_id=None, tenant=None,
                     role_id=None, role=None,
                     profile=None):
    '''
    Remove role for user in tenant (keystone user-role-remove)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.user_role_remove \
            user_id=298ce377245c4ec9b70e1c639c89e654 \
            tenant_id=7167a092ece84bae8cead4bf9d15bb3b \
            role_id=ce377245c4ec9b70e1c639c89e8cead4
        salt '*' keystone.user_role_remove user=admin tenant=admin role=admin
    '''
    kstone = auth(profile)
    if user:
        user_id = user_get(name=user)[user]['id']
    else:
        user = user_get(user_id).keys()[0]['name']
    if not user_id:
        return {'Error': 'Unable to resolve user id'}

    if tenant:
        tenant_id = tenant_get(name=tenant)[tenant]['id']
    else:
        tenant = tenant_get(tenant_id).keys()[0]['name']
    if not tenant_id:
        return {'Error': 'Unable to resolve tenant id'}

    if role:
        role_id = role_get(name=role)[role]['id']
    else:
        role = role_get(role_id).keys()[0]['name']
    if not role_id:
        return {'Error': 'Unable to resolve role id'}

    kstone.roles.remove_user_role(user_id, role_id, tenant_id)
    ret_msg = '"{0}" role removed for user "{1}" under "{2}" tenant'
    return ret_msg.format(role, user, tenant)


def user_role_list(user_id=None,
                   tenant_id=None,
                   user_name=None,
                   tenant_name=None,
                   profile=None):
    '''
    Return a list of available user_roles (keystone user-roles-list)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.user_role_list \
            user_id=298ce377245c4ec9b70e1c639c89e654 \
            tenant_id=7167a092ece84bae8cead4bf9d15bb3b
        salt '*' keystone.user_role_list user_name=admin tenant_name=admin
    '''
    kstone = auth(profile)
    ret = {}
    if user_name:
        for user in kstone.users.list():
            if user.name == user_name:
                user_id = user.id
                break
    if tenant_name:
        for tenant in kstone.tenants.list():
            if tenant.name == tenant_name:
                tenant_id = tenant.id
                break
    if not user_id or not tenant_id:
        return {'Error': 'Unable to resolve user or tenant id'}
    for role in kstone.roles.roles_for_user(user=user_id, tenant=tenant_id):
        ret[role.name] = {'id': role.id,
                          'name': role.name,
                          'user_id': user_id,
                          'tenant_id': tenant_id}
    return ret


def _item_list(profile=None):
    '''
    Template for writing list functions
    Return a list of available items (keystone items-list)

    CLI Example:

    .. code-block:: bash

        salt '*' keystone.item_list
    '''
    kstone = auth(profile)
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
    #endpoint-create     Create a new endpoint associated with a service
    #endpoint-delete     Delete a service endpoint
    #discover            Discover Keystone servers and show authentication
    #                    protocols and
    #bootstrap           Grants a new role to a new user on a new tenant, after
    #                    creating each.
