# -*- coding: utf-8 -*-
'''
Management of Keystone users
============================

:depends:   - keystoneclient Python module
:configuration: See :py:mod:`salt.modules.keystone` for setup instructions.

.. code-block:: yaml

    Keystone tenants:
      keystone.tenant_present:
        - names:
          - admin
          - demo
          - service

    Keystone roles:
      keystone.role_present:
        - names:
          - admin
          - Member

    admin:
      keystone.user_present:
        - password: R00T_4CC3SS
        - email: admin@domain.com
        - roles:
            admin:   # tenants
              - admin  # roles
            service:
              - admin
              - Member
        - require:
          - keystone: Keystone tenants
          - keystone: Keystone roles

    nova:
      keystone.user_present:
        - password: '$up3rn0v4'
        - email: nova@domain.com
        - tenant: service
        - roles:
            service:
              - admin
        - require:
          - keystone: Keystone tenants
          - keystone: Keystone roles

    demo:
      keystone.user_present:
        - password: 'd3m0n$trati0n'
        - email: demo@domain.com
        - tenant: demo
        - roles:
            demo:
              - Member
        - require:
          - keystone: Keystone tenants
          - keystone: Keystone roles

    nova service:
      keystone.service_present:
        - name: nova
        - service_type: compute
        - description: OpenStack Compute Service

'''


def __virtual__():
    '''
    Only load if the keystone module is in __salt__
    '''
    return 'keystone' if 'keystone.auth' in __salt__ else False


def user_present(name,
                 password,
                 email,
                 tenant=None,
                 enabled=True,
                 roles=None,
                 profile=None,
                 **connection_args):
    '''
    Ensure that the keystone user is present with the specified properties.

    name
        The name of the user to manage

    password
        The password to use for this user

    email
        The email address for this user

    tenant
        The tenant for this user

    enabled
        Availability state for this user

    roles
        The roles the user should have under tenants
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'User "{0}" will be updated'.format(name)}

    # Validate tenant if set
    if tenant is not None:
        tenantdata = __salt__['keystone.tenant_get'](name=tenant,
                                                     profile=profile,
                                                     **connection_args)
        if 'Error' in tenantdata:
            ret['result'] = False
            ret['comment'] = 'Tenant "{0}" does not exist'.format(tenant)
            return ret
        tenant_id = tenantdata[tenant]['id']
    else:
        tenant_id = None

    # Check if user is already present
    user = __salt__['keystone.user_get'](name=name, profile=profile,
                                         **connection_args)
    if 'Error' not in user:
        ret['comment'] = 'User "{0}" is already present'.format(name)
        if user[name]['email'] != email:
            if __opts__['test']:
                ret['result'] = None
                ret['changes']['Email'] = 'Will be updated'
                return ret
            __salt__['keystone.user_update'](name=name, email=email,
                                             profile=profile, **connection_args)
            ret['comment'] = 'User "{0}" has been updated'.format(name)
            ret['changes']['Email'] = 'Updated'
        if user[name]['enabled'] != enabled:
            if __opts__['test']:
                ret['result'] = None
                ret['changes']['Enabled'] = 'Will be {0}'.format(enabled)
                return ret
            __salt__['keystone.user_update'](name=name,
                                             enabled=enabled,
                                             profile=profile,
                                             **connection_args)
            ret['comment'] = 'User "{0}" has been updated'.format(name)
            ret['changes']['Enabled'] = 'Now {0}'.format(enabled)
        if tenant and ('tenant_id' not in user[name] or
                       user[name]['tenant_id'] != tenant_id):
            if __opts__['test']:
                ret['result'] = None
                ret['changes']['Tenant'] = 'Will be added to "{0}" tenant'.format(tenant)
                return ret
            __salt__['keystone.user_update'](name=name, tenant=tenant,
                                             profile=profile,
                                             **connection_args)
            ret['comment'] = 'User "{0}" has been updated'.format(name)
            ret['changes']['Tenant'] = 'Added to "{0}" tenant'.format(tenant)
        if not __salt__['keystone.user_verify_password'](name=name,
                                                         password=password,
                                                         profile=profile,
                                                         **connection_args):
            if __opts__['test']:
                ret['result'] = None
                ret['changes']['Password'] = 'Will be updated'
                return ret
            __salt__['keystone.user_password_update'](name=name,
                                                      password=password,
                                                      profile=profile,
                                                      **connection_args)
            ret['comment'] = 'User "{0}" has been updated'.format(name)
            ret['changes']['Password'] = 'Updated'
        if roles:
            for tenant_role in roles:
                args = dict({'user_name': name, 'tenant_name':
                             tenant_role, 'profile': profile}, **connection_args)
                tenant_roles = __salt__['keystone.user_role_list'](**args)
                for role in roles[tenant_role]:
                    if role not in tenant_roles:
                        if __opts__['test']:
                            ret['result'] = None
                            if 'roles' in ret['changes']:
                                ret['changes']['roles'].append(role)
                            else:
                                ret['changes']['roles'] = [role]
                            continue
                        addargs = dict({'user': name, 'role': role,
                                        'tenant': tenant_role,
                                        'profile': profile},
                                       **connection_args)
                        newrole = __salt__['keystone.user_role_add'](**addargs)
                        if 'roles' in ret['changes']:
                            ret['changes']['roles'].append(newrole)
                        else:
                            ret['changes']['roles'] = [newrole]
                roles_to_remove = list(set(tenant_roles) - set(roles[tenant_role]))
                for role in roles_to_remove:
                    if __opts__['test']:
                        ret['result'] = None
                        if 'roles' in ret['changes']:
                            ret['changes']['roles'].append(role)
                        else:
                            ret['changes']['roles'] = [role]
                        continue
                    addargs = dict({'user': name, 'role': role,
                                    'tenant': tenant_role,
                                    'profile': profile},
                                   **connection_args)
                    oldrole = __salt__['keystone.user_role_remove'](**addargs)
                    if 'roles' in ret['changes']:
                        ret['changes']['roles'].append(oldrole)
                    else:
                        ret['changes']['roles'] = [oldrole]
    else:
        # Create that user!
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Keystone user "{0}" will be added'.format(name)
            ret['changes']['User'] = 'Will be created'
            return ret
        __salt__['keystone.user_create'](name=name,
                                         password=password,
                                         email=email,
                                         tenant_id=tenant_id,
                                         enabled=enabled,
                                         profile=profile,
                                         **connection_args)
        if roles:
            for tenant_role in roles:
                for role in roles[tenant_role]:
                    __salt__['keystone.user_role_add'](user=name,
                                                       role=role,
                                                       tenant=tenant_role,
                                                       profile=profile,
                                                       **connection_args)
        ret['comment'] = 'Keystone user {0} has been added'.format(name)
        ret['changes']['User'] = 'Created'

    return ret


def user_absent(name, profile=None, **connection_args):
    '''
    Ensure that the keystone user is absent.

    name
        The name of the user that should not exist
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'User "{0}" is already absent'.format(name)}

    # Check if user is present
    user = __salt__['keystone.user_get'](name=name, profile=profile,
                                         **connection_args)
    if 'Error' not in user:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'User "{0}" will be deleted'.format(name)
            ret['changes']['User'] = 'Will be deleted'
            return ret
        # Delete that user!
        __salt__['keystone.user_delete'](name=name, profile=profile,
                                         **connection_args)
        ret['comment'] = 'User "{0}" has been deleted'.format(name)
        ret['changes']['User'] = 'Deleted'

    return ret


def tenant_present(name, description=None, enabled=True, profile=None,
                   **connection_args):
    '''
    Ensures that the keystone tenant exists

    name
        The name of the tenant to manage

    description
        The description to use for this tenant

    enabled
        Availability state for this tenant
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'Tenant "{0}" already exists'.format(name)}

    # Check if tenant is already present
    tenant = __salt__['keystone.tenant_get'](name=name,
                                             profile=profile,
                                             **connection_args)

    if 'Error' not in tenant:
        if tenant[name]['description'] != description:
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] = 'Tenant "{0}" will be updated'.format(name)
                ret['changes']['Description'] = 'Will be updated'
                return ret
            __salt__['keystone.tenant_update'](name=name,
                                               description=description,
                                               enabled=enabled,
                                               profile=profile,
                                               **connection_args)
            ret['comment'] = 'Tenant "{0}" has been updated'.format(name)
            ret['changes']['Description'] = 'Updated'
        if tenant[name]['enabled'] != enabled:
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] = 'Tenant "{0}" will be updated'.format(name)
                ret['changes']['Enabled'] = 'Will be {0}'.format(enabled)
                return ret
            __salt__['keystone.tenant_update'](name=name,
                                               description=description,
                                               enabled=enabled,
                                               profile=profile,
                                               **connection_args)
            ret['comment'] = 'Tenant "{0}" has been updated'.format(name)
            ret['changes']['Enabled'] = 'Now {0}'.format(enabled)
    else:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Tenant "{0}" will be added'.format(name)
            ret['changes']['Tenant'] = 'Will be created'
            return ret
        # Create tenant
        __salt__['keystone.tenant_create'](name, description, enabled,
                                           profile=profile,
                                           **connection_args)
        ret['comment'] = 'Tenant "{0}" has been added'.format(name)
        ret['changes']['Tenant'] = 'Created'
    return ret


def tenant_absent(name, profile=None, **connection_args):
    '''
    Ensure that the keystone tenant is absent.

    name
        The name of the tenant that should not exist
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'Tenant "{0}" is already absent'.format(name)}

    # Check if tenant is present
    tenant = __salt__['keystone.tenant_get'](name=name,
                                             profile=profile,
                                             **connection_args)
    if 'Error' not in tenant:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Tenant "{0}" will be deleted'.format(name)
            ret['changes']['Tenant'] = 'Will be deleted'
            return ret
        # Delete tenant
        __salt__['keystone.tenant_delete'](name=name, profile=profile,
                                           **connection_args)
        ret['comment'] = 'Tenant "{0}" has been deleted'.format(name)
        ret['changes']['Tenant'] = 'Deleted'

    return ret


def role_present(name, profile=None, **connection_args):
    ''''
    Ensures that the keystone role exists

    name
        The name of the role that should be present
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'Role "{0}" already exists'.format(name)}

    # Check if role is already present
    role = __salt__['keystone.role_get'](name=name, profile=profile,
                                         **connection_args)

    if 'Error' not in role:
        return ret
    else:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Role "{0}" will be added'.format(name)
            ret['changes']['Role'] = 'Will be created'
            return ret
        # Create role
        __salt__['keystone.role_create'](name, profile=profile,
                                         **connection_args)
        ret['comment'] = 'Role "{0}" has been added'.format(name)
        ret['changes']['Role'] = 'Created'
    return ret


def role_absent(name, profile=None, **connection_args):
    '''
    Ensure that the keystone role is absent.

    name
        The name of the role that should not exist
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'Role "{0}" is already absent'.format(name)}

    # Check if role is present
    role = __salt__['keystone.role_get'](name=name, profile=profile,
                                         **connection_args)
    if 'Error' not in role:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Role "{0}" will be deleted'.format(name)
            ret['changes']['Role'] = 'Will be deleted'
            return ret
        # Delete role
        __salt__['keystone.role_delete'](name=name, profile=profile,
                                         **connection_args)
        ret['comment'] = 'Role "{0}" has been deleted'.format(name)
        ret['changes']['Role'] = 'Deleted'

    return ret


def service_present(name, service_type, description=None,
                    profile=None, **connection_args):
    '''
    Ensure service present in Keystone catalog

    name
        The name of the service

    service_type
        The type of Openstack Service

    description (optional)
        Description of the service
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'Service "{0}" already exists'.format(name)}

    # Check if service is already present
    role = __salt__['keystone.service_get'](name=name,
                                            profile=profile,
                                            **connection_args)

    if 'Error' not in role:
        return ret
    else:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Service "{0}" will be added'.format(name)
            ret['changes']['Service'] = 'Will be created'
            return ret
        # Create service
        __salt__['keystone.service_create'](name, service_type,
                                            description,
                                            profile=profile,
                                            **connection_args)
        ret['comment'] = 'Service "{0}" has been added'.format(name)
        ret['changes']['Service'] = 'Created'
    return ret


def service_absent(name, profile=None, **connection_args):
    '''
    Ensure that the service doesn't exist in Keystone catalog

    name
        The name of the service that should not exist
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'Service "{0}" is already absent'.format(name)}

    # Check if service is present
    role = __salt__['keystone.service_get'](name=name,
                                            profile=profile,
                                            **connection_args)
    if 'Error' not in role:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Service "{0}" will be deleted'.format(name)
            ret['changes']['Service'] = 'Will be deleted'
            return ret
        # Delete service
        __salt__['keystone.service_delete'](name=name,
                                            profile=profile,
                                            **connection_args)
        ret['comment'] = 'Service "{0}" has been deleted'.format(name)
        ret['changes']['Service'] = 'Deleted'

    return ret


def endpoint_present(name,
                     publicurl=None,
                     internalurl=None,
                     adminurl=None,
                     region='RegionOne', profile=None, **connection_args):
    '''
    Ensure the specified endpoints exists for service

    name
        The Service name

    public url
        The public url of service endpoint

    internal url
        The internal url of service endpoint

    admin url
        The admin url of the service endpoint

    region
        The region of the endpoint
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'endpoint for service "{0}" already exists'.format(name)}
    endpoint = __salt__['keystone.endpoint_get'](name,
                                                 profile=profile,
                                                 **connection_args)
    cur_endpoint = dict(region=region,
                        publicurl=publicurl,
                        adminurl=adminurl,
                        internalurl=internalurl)
    if endpoint and 'Error' not in endpoint:
        endpoint.pop('id')
        endpoint.pop('service_id')
        if endpoint == cur_endpoint:
            return ret
        else:
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] = 'Endpoint for service "{0}" will be updated'.format(name)
                ret['changes']['endpoint'] = 'Will be updated'
                return ret
            __salt__['keystone.endpoint_delete'](name,
                                                 profile=profile,
                                                 **connection_args)
            ret['comment'] = 'Endpoint for service "{0}" has been updated'.format(name)
    else:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Endpoint for service "{0}" will be added'.format(name)
            ret['changes']['endpoint'] = 'Will be created'
            return ret
        ret['comment'] = 'Endpoint for service "{0}" has been added'.format(name)

    if not __opts__['test']:
        ret['changes'] = __salt__['keystone.endpoint_create'](
            name,
            region=region,
            publicurl=publicurl,
            adminurl=adminurl,
            internalurl=internalurl,
            profile=profile,
            **connection_args)
    return ret


def endpoint_absent(name, profile=None, **connection_args):
    '''
    Ensure that the endpoint for a service doesn't exist in Keystone catalog

    name
        The name of the service whose endpoints should not exist
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'endpoint for service "{0}" is already absent'.format(name)}

    # Check if service is present
    endpoint = __salt__['keystone.endpoint_get'](name,
                                                 profile=profile,
                                                 **connection_args)
    if not endpoint:
        return ret
    else:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Endpoint for service "{0}" will be deleted'.format(name)
            ret['changes']['endpoint'] = 'Will be deleted'
            return ret
        # Delete service
        __salt__['keystone.endpoint_delete'](name,
                                             profile=profile,
                                             **connection_args)
        ret['comment'] = 'Endpoint for service "{0}" has been deleted'.format(name)
        ret['changes']['endpoint'] = 'Deleted'
    return ret
