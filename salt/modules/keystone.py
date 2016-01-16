# -*- coding: utf-8 -*-
'''
Module for handling openstack keystone calls.

:optdepends:    - keystoneclient Python adapter
:configuration: This module is not usable until the following are specified
    either in a pillar or in the minion's config file:

    .. code-block:: yaml

        keystone.user: admin
        keystone.password: verybadpass
        keystone.tenant: admin
        keystone.tenant_id: f80919baedab48ec8931f200c65a50df
        keystone.auth_url: 'http://127.0.0.1:5000/v2.0/'

    OR (for token based authentication)

    .. code-block:: yaml

        keystone.token: 'ADMIN'
        keystone.endpoint: 'http://127.0.0.1:35357/v2.0'

    If configuration for multiple openstack accounts is required, they can be
    set up as different configuration profiles. For example:

    .. code-block:: yaml

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
    For example:

    .. code-block:: bash

        salt '*' keystone.tenant_list profile=openstack1
'''

# Import Python libs
from __future__ import absolute_import
import logging

# Import Salt Libs
import salt.ext.six as six

# Import third party libs
HAS_SHADE = False
try:
    # pylint: disable=import-error
    import shade
    import keystoneauth1.exceptions
    # pylint: enable=import-error
    HAS_SHADE = True
except ImportError:
    pass

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load this module if keystone
    is installed on this minion.
    '''
    if HAS_SHADE:
        return 'keystone'
    return (False, 'keystone execution module cannot be loaded: shade python library not available.')

__opts__ = {}


def auth(profile=None, **connection_args):
    '''
    Set up keystone credentials. Only intended to be used within Keystone-enabled modules.

    CLI Example:

    .. code-block:: bash

        salt '*' keystone.auth
    '''

    if profile:
        prefix = profile + ":keystone."
    else:
        prefix = "keystone."

    # look in connection_args first, then default to config file
    def get(key, default=None):
        return connection_args.get('connection_' + key,
            __salt__['config.get'](prefix + key, default))

    user = get('user', 'admin')
    password = get('password', 'ADMIN')
    tenant = get('tenant', 'admin')
    tenant_id = get('tenant_id')
    auth_url = get('auth_url', 'http://127.0.0.1:35357/v2.0/')
    insecure = get('insecure', False)
    token = get('token')
    endpoint = get('endpoint', 'http://127.0.0.1:35357/v2.0')
    auth_type = get('auth_type', None)

    if token:
        kwargs = {'token': token,
                  'endpoint': endpoint,
                  'auth_type': auth_type or 'admin_token'}
    else:
        kwargs = {'profile': profile,
                  'username': user,
                  'password': password,
                  'tenant_name': tenant,
                  'tenant_id': tenant_id,
                  'auth_url': auth_url,
                  'auth_type': auth_type or 'password'}
        # 'insecure' keyword not supported by all v2.0 keystone clients
        #   this ensures it's only passed in when defined
        if insecure:
            kwargs['insecure'] = True
    return shade.operator_cloud(**kwargs)


def version(profile=None, **connection_args):
    kstone = auth(profile, **connection_args)
    return kstone.keystone_client.version


def ec2_credentials_create(user_id=None, name=None,
                           tenant_id=None, tenant=None,
                           profile=None, **connection_args):
    '''
    Create EC2-compatible credentials for user per tenant

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.ec2_credentials_create name=admin tenant=admin
        salt '*' keystone.ec2_credentials_create \
user_id=c965f79c4f864eaaa9c3b41904e67082 \
tenant_id=722787eb540849158668370dc627ec5f
    '''
    kstone = auth(profile, **connection_args).keystone_client

    if name:
        user_id = user_get(name=name, profile=profile,
                           **connection_args)[name]['id']
    if not user_id:
        return {'Error': 'Could not resolve User ID'}

    if tenant:
        tenant_id = tenant_get(name=tenant, profile=profile,
                               **connection_args)[tenant]['id']
    if not tenant_id:
        return {'Error': 'Could not resolve Tenant ID'}

    newec2 = kstone.ec2.create(user_id, tenant_id)
    return {'access': newec2.access,
            'secret': newec2.secret,
            'tenant_id': newec2.tenant_id,
            'user_id': newec2.user_id}


def ec2_credentials_delete(user_id=None, name=None, access_key=None,
                           profile=None, **connection_args):
    '''
    Delete EC2-compatible credentials

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.ec2_credentials_delete \
860f8c2c38ca4fab989f9bc56a061a64 access_key=5f66d2f24f604b8bb9cd28886106f442
        salt '*' keystone.ec2_credentials_delete name=admin \
access_key=5f66d2f24f604b8bb9cd28886106f442
    '''
    kstone = auth(profile, **connection_args).keystone_client

    if name:
        user_id = user_get(name=name, profile=None, **connection_args)[name]['id']
    if not user_id:
        return {'Error': 'Could not resolve User ID'}
    kstone.ec2.delete(user_id, access_key)
    return 'ec2 key "{0}" deleted under user id "{1}"'.format(access_key,
                                                              user_id)


def ec2_credentials_get(user_id=None, name=None, access=None,
                        profile=None, **connection_args):
    '''
    Return ec2_credentials for a user (keystone ec2-credentials-get)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.ec2_credentials_get c965f79c4f864eaaa9c3b41904e67082 access=722787eb540849158668370dc627ec5f
        salt '*' keystone.ec2_credentials_get user_id=c965f79c4f864eaaa9c3b41904e67082 access=722787eb540849158668370dc627ec5f
        salt '*' keystone.ec2_credentials_get name=nova access=722787eb540849158668370dc627ec5f
    '''
    kstone = auth(profile, **connection_args).keystone_client
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
    ec2_credentials = kstone.ec2.get(user_id=user_id, access=access,
                                     profile=profile, **connection_args)
    ret[ec2_credentials.user_id] = {'user_id': ec2_credentials.user_id,
                                    'tenant': ec2_credentials.tenant_id,
                                    'access': ec2_credentials.access,
                                    'secret': ec2_credentials.secret}
    return ret


def ec2_credentials_list(user_id=None, name=None, profile=None,
                         **connection_args):
    '''
    Return a list of ec2_credentials for a specific user (keystone ec2-credentials-list)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.ec2_credentials_list 298ce377245c4ec9b70e1c639c89e654
        salt '*' keystone.ec2_credentials_list user_id=298ce377245c4ec9b70e1c639c89e654
        salt '*' keystone.ec2_credentials_list name=jack
    '''
    kstone = auth(profile, **connection_args).keystone_client
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


def endpoint_search(service, filters=None, profile=None, **connection_args):
    '''
    Return a specific endpoint (keystone endpoint-get)

    CLI Example:

    .. code-block:: bash

        salt '*' keystone.endpoint_search keystone '{"interface": "public"}'
    '''
    filters = filters or {}
    kstone = auth(profile, **connection_args)
    service = kstone.get_service(service)
    if not service:
        return {'Error': 'Could not find the specified service'}
    filters['service_id'] = service.id
    ret = kstone.search_endpoints(filters=filters)
    return ret


def endpoint_get(service, profile=None, interface=None, **connection_args):
    '''
    Return a specific endpoint (keystone endpoint-get)

    CLI Example:

    .. code-block:: bash

        salt '*' keystone.endpoint_get nova
    '''
    kstone = auth(profile, **connection_args)
    service = kstone.get_service(service)
    if not service:
        return {'Error': 'Could not find the specified service'}
    ret = kstone.search_endpoints(
        filters={'service_id': service.id, 'interface': interface} if interface else {'service_id': service.id}
    )
    if not ret:
        return {'Error': 'Could not find endpoint for the specified service'}
    elif len(ret) == 1:
        return ret[0]
    else:
        return ret


def endpoint_list(profile=None, interface=None, **connection_args):
    '''
    Return a list of available endpoints (keystone endpoints-list)

    CLI Example:

    .. code-block:: bash

        salt '*' keystone.endpoint_list
    '''
    kstone = auth(profile, **connection_args)
    ret = {}
    for endpoint in kstone.search_endpoints(filters={'interface': interface} if interface else {}):
        ret[endpoint.id] = endpoint
    return ret


def endpoint_create(service, publicurl=None, internalurl=None, adminurl=None,
                    region=None, enabled=True, profile=None, **connection_args):
    '''
    Create an endpoint for an Openstack service

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.endpoint_create nova 'http://public/url'
            'http://internal/url' 'http://adminurl/url' region
    '''
    kstone = auth(profile, **connection_args)
    keystone_service = kstone.get_service(service)
    if not keystone_service:
        return {'Error': 'Could not find the specified service'}
    kstone.create_endpoint(keystone_service.id,
                           region=region,
                           public_url=publicurl,
                           admin_url=adminurl,
                           internal_url=internalurl,
                           enabled=enabled)
    return endpoint_get(service, profile, **connection_args)


def endpoint_delete(service, profile=None, **connection_args):
    '''
    Delete endpoints of an Openstack service

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.endpoint_delete nova
    '''
    kstone = auth(profile, **connection_args)
    service = kstone.get_service(service)
    endpoints = kstone.search_endpoints(filters={'service_id': service.id})
    if not endpoints:
        return {'Error': 'Could not find any endpoints for the service'}
    for endpoint in endpoints:
        kstone.delete_endpoint(endpoint.id)
    endpoints = kstone.search_endpoints(filters={'service_id': service.id})
    if not endpoints:
        return True
    return False


def role_create(name, profile=None, **connection_args):
    '''
    Create a named role.

    CLI Example:

    .. code-block:: bash

        salt '*' keystone.role_create admin
    '''

    kstone = auth(profile, **connection_args)
    if kstone.get_role(name):
        return {'Error': 'Role "{0}" already exists'.format(name)}
    role = kstone.create_role(name)
    return kstone.get_role(name)


def role_delete(role_id=None, name=None, profile=None,
                **connection_args):
    '''
    Delete a role (keystone role-delete)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.role_delete c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.role_delete role_id=c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.role_delete name=admin
    '''
    kstone = auth(profile, **connection_args)
    return kstone.delete_role(role_id or name)


def role_get(role_id=None, name=None, profile=None, **connection_args):
    '''
    Return a specific roles (keystone role-get)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.role_get c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.role_get role_id=c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.role_get name=nova
    '''
    kstone = auth(profile, **connection_args)
    role = kstone.get_role(role_id or name)
    if not role:
        return {'Error': 'Unable to resolve role id'}
    return {role.name: role}


def role_list(profile=None, **connection_args):
    '''
    Return a list of available roles (keystone role-list)

    CLI Example:

    .. code-block:: bash

        salt '*' keystone.role_list
    '''
    kstone = auth(profile, **connection_args)
    ret = {}
    for role in kstone.list_roles():
        ret[role.name] = role
    return ret


def service_create(name, service_type, description=None, profile=None,
                   **connection_args):
    '''
    Add service to Keystone service catalog

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.service_create nova compute \
'OpenStack Compute Service'
    '''
    kstone = auth(profile, **connection_args)
    service = kstone.create_service(name, service_type=service_type, description=description)
    return kstone.get_service(service.id)


def service_delete(service_id=None, name=None, profile=None, **connection_args):
    '''
    Delete a service from Keystone service catalog

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.service_delete c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.service_delete name=nova
    '''
    kstone = auth(profile, **connection_args)
    return kstone.delete_service(service_id or name)


def service_get(service_id=None, name=None, profile=None, **connection_args):
    '''
    Return a specific services (keystone service-get)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.service_get c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.service_get service_id=c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.service_get name=nova
    '''
    kstone = auth(profile, **connection_args)
    service = kstone.get_service(service_id or name)
    if not service:
        return {'Error': 'Unable to resolve service id'}
    return {service.name: service}


def service_list(profile=None, **connection_args):
    '''
    Return a list of available services (keystone services-list)

    CLI Example:

    .. code-block:: bash

        salt '*' keystone.service_list
    '''
    kstone = auth(profile, **connection_args)
    ret = {}
    for service in kstone.list_services():
        ret[service.name] = service
    return ret


def tenant_create(name, description=None, enabled=True, domain_id=None, profile=None,
                  **connection_args):
    '''
    Create a keystone tenant

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.tenant_create nova description='nova tenant'
        salt '*' keystone.tenant_create test enabled=False
    '''
    kstone = auth(profile, **connection_args)
    kstone.create_project(name, description=description, enabled=enabled, domain_id=domain_id or 'default')
    return kstone.get_project(name)


project_create = tenant_create


def tenant_delete(tenant_id=None, name=None, profile=None, **connection_args):
    '''
    Delete a tenant (keystone tenant-delete)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.tenant_delete c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.tenant_delete tenant_id=c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.tenant_delete name=demo
    '''
    kstone = auth(profile, **connection_args)
    return kstone.delete_project(tenant_id or name)


project_delete = tenant_delete


def tenant_get(tenant_id=None, name=None, profile=None,
               **connection_args):
    '''
    Return a specific tenants (keystone tenant-get)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.tenant_get c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.tenant_get tenant_id=c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.tenant_get name=nova
    '''
    kstone = auth(profile, **connection_args)
    tenant = kstone.get_project(tenant_id or name)
    if not tenant:
        return False
    return {tenant.name: tenant}


project_get = tenant_get


def tenant_list(profile=None, **connection_args):
    '''
    Return a list of available tenants (keystone tenants-list)

    CLI Example:

    .. code-block:: bash

        salt '*' keystone.tenant_list
    '''
    kstone = auth(profile, **connection_args)
    ret = {}
    for tenant in kstone.list_projects():
        ret[tenant.name] = tenant
    return ret


project_list = tenant_list


def tenant_update(tenant_id=None, name=None, description=None,
                  enabled=None, profile=None, **connection_args):
    '''
    Update a tenant's information (keystone tenant-update)
    The following fields may be updated: name, email, enabled.
    Can only update name if targeting by ID

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.tenant_update name=admin enabled=True
        salt '*' keystone.tenant_update c965f79c4f864eaaa9c3b41904e67082 name=admin email=admin@domain.com
    '''
    kstone = auth(profile, **connection_args)
    return kstone.update_project(tenant_id or name, description, enabled)


project_update = tenant_update


def token_get(profile=None, **connection_args):
    '''
    Return the configured tokens (keystone token-get)

    CLI Example:

    .. code-block:: bash

        salt '*' keystone.token_get c965f79c4f864eaaa9c3b41904e67082
    '''
    kstone = auth(profile, **connection_args)
    return {'id': kstone.get_token(),
            'user_id': kstone.get_user_id(),
            'tenant_id': kstone.get_project_id()}


def user_list(profile=None, **connection_args):
    '''
    Return a list of available users (keystone user-list)

    CLI Example:

    .. code-block:: bash

        salt '*' keystone.user_list
    '''
    kstone = auth(profile, **connection_args)
    ret = {}
    for user in kstone.list_users():
        ret[user.name] = user
    return ret


def user_get(user_id=None, name=None, profile=None, **connection_args):
    '''
    Return a specific users (keystone user-get)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.user_get c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.user_get user_id=c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.user_get name=nova
    '''
    kstone = auth(profile, **connection_args)
    user = kstone.get_user(user_id or name)
    if not user:
        return {'Error': 'Unable to resolve user id'}
    return {user.name: user}


def user_create(name, password=None, email=None, tenant_id=None,
                enabled=True, domain_id=None, profile=None, **connection_args):
    '''
    Create a user (keystone user-create)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.user_create name=jack password=zero email=jack@halloweentown.org tenant_id=a28a7b5a999a455f84b1f5210264375e enabled=True
    '''
    kstone = auth(profile, **connection_args)
    kstone.create_user(name=name,
                       password=password,
                       email=email,
                       default_project=tenant_id,
                       enabled=enabled,
                       domain_id=domain_id)
    return kstone.get_user(name)


def user_delete(user_id=None, name=None, profile=None, **connection_args):
    '''
    Delete a user (keystone user-delete)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.user_delete c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.user_delete user_id=c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.user_delete name=nova
    '''
    kstone = auth(profile, **connection_args)
    return kstone.delete_user(user_id or name)


def user_update(user_id=None, name=None, email=None, enabled=None,
                tenant_id=None, profile=None, **connection_args):
    '''
    Update a user's information (keystone user-update)
    The following fields may be updated: name, email, enabled, tenant.
    Because the name is one of the fields, a valid user id is required.

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.user_update user_id=c965f79c4f864eaaa9c3b41904e67082 name=newname
        salt '*' keystone.user_update c965f79c4f864eaaa9c3b41904e67082 name=newname email=newemail@domain.com
    '''
    kstone = auth(profile, **connection_args).keystone_client
    return kstone.update_user(user=user_id or name, name=name, email=email,
                              enabled=enabled, default_project_id=tenant_id)


def user_verify_password(user_id=None, name=None, password=None,
                         profile=None, **connection_args):
    '''
    Verify a user's password

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.user_verify_password name=test password=foobar
        salt '*' keystone.user_verify_password user_id=c965f79c4f864eaaa9c3b41904e67082 password=foobar
    '''
    kstone = auth(profile, **connection_args)
    if 'connection_endpoint' in connection_args:
        auth_url = connection_args.get('connection_endpoint')
    else:
        auth_url = __salt__['config.option']('keystone.endpoint',
                                         'http://127.0.0.1:35357/v2.0')

    user = kstone.get_user(user_id or name)
    if not user:
        return None
    kwargs = {'username': user.name,
              'password': password,
              'auth_url': auth_url}
    try:
        userauth = auth(**kwargs).auth_token
    except (keystoneauth1.exceptions.http.Unauthorized,
            keystoneauth1.exceptions.AuthorizationFailure):
        return False
    return True


def user_password_update(user_id=None, name=None, password=None,
                         profile=None, **connection_args):
    '''
    Update a user's password (keystone user-password-update)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.user_password_update c965f79c4f864eaaa9c3b41904e67082 password=12345
        salt '*' keystone.user_password_update user_id=c965f79c4f864eaaa9c3b41904e67082 password=12345
        salt '*' keystone.user_password_update name=nova password=12345
    '''
    kstone = auth(profile, **connection_args)
    user = kstone.get_user(user_id or name)
    if not user:
        return None
    kstone.update_password(user.user_id, password=password)
    return True


def user_role_add(user_id=None, user=None, tenant_id=None, tenant=None, role_id=None, role=None,
                  domain_id=None, domain=None, profile=None, **connection_args):
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
    kstone = auth(profile, **connection_args).keystone_client
    user = kstone.get_user(user_id or user)
    role = kstone.get_role(role_id or role)
    if not user or not role:
        return {'Error': 'must specify `user` and `role`'}

    tenant = kstone.get_project(tenant_id or tenant)

    if kstone.cloud_config.get_api_version('identity') == '2':
        kstone.keystone_client.roles.add_user_role(user=user.id, role=role.id, tenant=tenant_id)
    else:
        domain = kstone.get_domain(domain_id or domain)
        if domain and tenant:
            return {'Error': 'only specify one of `domain` or `tenant`'}
        elif not domain and not tenant:
            return {'Error': 'must specify one of `domain` or `tenant`'}
        kstone.keystone_client.roles.grant(
            user=user.id, role=role.id,
            project=tenant.id if tenant else None,
            domain=domain.id if domain else None
        )
    return True


def user_role_remove(user_id=None, user=None, tenant_id=None, tenant=None, role_id=None, role=None,
                     domain_id=None, domain=None, profile=None, **connection_args):
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
    kstone = auth(profile, **connection_args)
    user = kstone.get_user(user_id or user)
    tenant = kstone.get_tenant(tenant_id or tenant)
    role = kstone.get_role(role_id or role)

    if not user or not role:
        return None

    if kstone.cloud_config.get_api_version('identity') == '2':
        if not tenant:
            return None
        kstone.keystone_client.roles.remove_user_role(user_id, role_id, tenant_id)
    else:
        domain = kstone.get_domain(domain_id or domain)
        if domain and tenant:
            return {'Error': 'only specify one of `domain` or `tenant`'}
        elif not domain and not tenant:
            return {'Error': 'must specify one of `domain` or `tenant`'}
        kstone.keystone_client.roles.revoke(
            role=role.id, user=user.id,
            domain=domain.id if domain else None,
            project=project.id if project else None
        )

    ret_msg = '"{0}" role removed for user "{1}" under "{2}" tenant'
    return ret_msg.format(role, user, tenant)


def user_role_list(user_id=None, user_name=None, tenant_id=None, tenant_name=None,
                   domain_id=None, domain=None, profile=None, **connection_args):
    '''
    Return a list of available user_roles (keystone user-roles-list)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.user_role_list \
user_id=298ce377245c4ec9b70e1c639c89e654 \
tenant_id=7167a092ece84bae8cead4bf9d15bb3b
        salt '*' keystone.user_role_list user_name=admin tenant_name=admin
    '''
    kstone = auth(profile, **connection_args)
    ret = {}
    user = kstone.get_user(user_id or user_name)
    tenant = kstone.get_project(tenant_id or tenant_name)
    if not user:
        return None
    if kstone.cloud_config.get_api_version('identity') == '2':
        if not tenant:
            return None
        for role in kstone.keystone_client.roles.roles_for_user(user=user_id, tenant=tenant_id):
            ret[role.name] = {'id': role.id,
                              'name': role.name,
                              'user_id': user.id,
                              'tenant_id': tenant.id}
    else:
        domain = kstone.get_domain(domain_id or domain)
        if domain and tenant:
            return {'Error': 'only specify one of `domain` or `tenant`'}
        elif not domain and not tenant:
            return {'Error': 'must specify one of `domain` or `tenant`'}
        filters = {'user': user.id}
        if domain:
            filters['domain'] = domain.id
        elif tenant:
            filters['project'] = tenant.id
        for assignment in kstone.list_role_assignments(filters):
            role = kstone.get_role(assignment.id)
            ret[role.name] = {'id': role.id,
                              'name': role.name,
                              'user_id': user.id,
                              'project_id': tenant.id}
    return ret
