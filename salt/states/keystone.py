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


_OS_IDENTITY_API_VERSION = 2
_TENANT_ID = 'tenant_id'


def _api_version(profile=None, **connection_args):
    '''
    Sets global variables _OS_IDENTITY_API_VERSION and _TENANT_ID
    depending on API version.
    '''
    global _TENANT_ID
    global _OS_IDENTITY_API_VERSION
    try:
        if float(__salt__['keystone.api_version'](profile=profile, **connection_args).strip('v')) >= 3:
            _TENANT_ID = 'project_id'
            _OS_IDENTITY_API_VERSION = 3
    except KeyError:
        pass


def user_present(name,
                 password,
                 email,
                 tenant=None,
                 enabled=True,
                 roles=None,
                 profile=None,
                 password_reset=True,
                 project=None,
                 **connection_args):
    '''
    Ensure that the keystone user is present with the specified properties.

    name
        The name of the user to manage

    password
        The password to use for this user.

        .. note::

            If the user already exists and a different password was set for
            the user than the one specified here, the password for the user
            will be updated. Please set the ``password_reset`` option to
            ``False`` if this is not the desired behavior.

    password_reset
        Whether or not to reset password after initial set. Defaults to
        ``True``.

    email
        The email address for this user

    tenant
        The tenant (name) for this user

    project
        The project (name) for this user (overrides tenant in api v3)

    enabled
        Availability state for this user

    roles
        The roles the user should have under given tenants.
        Passed as a dictionary mapping tenant names to a list
        of roles in this tenant, i.e.::

            roles:
                admin:   # tenant
                  - admin  # role
                service:
                  - admin
                  - Member
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'User "{0}" will be updated'.format(name)}

    _api_version(profile=profile, **connection_args)

    if project and not tenant:
        tenant = project

    # Validate tenant if set
    if tenant is not None:
        tenantdata = __salt__['keystone.tenant_get'](name=tenant,
                                                     profile=profile,
                                                     **connection_args)
        if 'Error' in tenantdata:
            ret['result'] = False
            ret['comment'] = 'Tenant / project "{0}" does not exist'.format(tenant)
            return ret
        tenant_id = tenantdata[tenant]['id']
    else:
        tenant_id = None

    # Check if user is already present
    user = __salt__['keystone.user_get'](name=name, profile=profile,
                                         **connection_args)
    if 'Error' not in user:

        change_email = False
        change_enabled = False
        change_tenant = False
        change_password = False

        if user[name].get('email', None) != email:
            change_email = True

        if user[name].get('enabled', None) != enabled:
            change_enabled = True

        if tenant and (_TENANT_ID not in user[name] or
                       user[name].get(_TENANT_ID, None) != tenant_id):
            change_tenant = True

        if (password_reset is True and
            not __salt__['keystone.user_verify_password'](name=name,
                                                          password=password,
                                                          profile=profile,
                                                          **connection_args)):
            change_password = True

        if __opts__.get('test') and (change_email or change_enabled or change_tenant or change_password):
            ret['result'] = None
            ret['comment'] = 'User "{0}" will be updated'.format(name)
            if change_email is True:
                ret['changes']['Email'] = 'Will be updated'
            if change_enabled is True:
                ret['changes']['Enabled'] = 'Will be True'
            if change_tenant is True:
                ret['changes']['Tenant'] = 'Will be added to "{0}" tenant'.format(tenant)
            if change_password is True:
                ret['changes']['Password'] = 'Will be updated'
            return ret

        ret['comment'] = 'User "{0}" is already present'.format(name)

        if change_email:
            __salt__['keystone.user_update'](name=name, email=email, profile=profile, **connection_args)
            ret['comment'] = 'User "{0}" has been updated'.format(name)
            ret['changes']['Email'] = 'Updated'

        if change_enabled:
            __salt__['keystone.user_update'](name=name, enabled=enabled, profile=profile, **connection_args)
            ret['comment'] = 'User "{0}" has been updated'.format(name)
            ret['changes']['Enabled'] = 'Now {0}'.format(enabled)

        if change_tenant:
            __salt__['keystone.user_update'](name=name, tenant=tenant, profile=profile, **connection_args)
            ret['comment'] = 'User "{0}" has been updated'.format(name)
            ret['changes']['Tenant'] = 'Added to "{0}" tenant'.format(tenant)

        if change_password:
            __salt__['keystone.user_password_update'](name=name, password=password, profile=profile,
                                                      **connection_args)
            ret['comment'] = 'User "{0}" has been updated'.format(name)
            ret['changes']['Password'] = 'Updated'

        if roles:
            for tenant in roles.keys():
                args = dict({'user_name': name, 'tenant_name':
                             tenant, 'profile': profile}, **connection_args)
                tenant_roles = __salt__['keystone.user_role_list'](**args)
                for role in roles[tenant]:
                    if role not in tenant_roles:
                        if __opts__.get('test'):
                            ret['result'] = None
                            ret['comment'] = 'User roles "{0}" will been updated'.format(name)
                            return ret
                        addargs = dict({'user': name, 'role': role,
                                        'tenant': tenant,
                                        'profile': profile},
                                       **connection_args)
                        newrole = __salt__['keystone.user_role_add'](**addargs)
                        if 'roles' in ret['changes']:
                            ret['changes']['roles'].append(newrole)
                        else:
                            ret['changes']['roles'] = [newrole]
                roles_to_remove = list(set(tenant_roles) - set(roles[tenant]))
                for role in roles_to_remove:
                    if __opts__.get('test'):
                        ret['result'] = None
                        ret['comment'] = 'User roles "{0}" will been updated'.format(name)
                        return ret
                    addargs = dict({'user': name, 'role': role,
                                    'tenant': tenant,
                                    'profile': profile},
                                   **connection_args)
                    oldrole = __salt__['keystone.user_role_remove'](**addargs)
                    if 'roles' in ret['changes']:
                        ret['changes']['roles'].append(oldrole)
                    else:
                        ret['changes']['roles'] = [oldrole]
    else:
        # Create that user!
        if __opts__.get('test'):
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
            for tenant in roles.keys():
                for role in roles[tenant]:
                    __salt__['keystone.user_role_add'](user=name,
                                                       role=role,
                                                       tenant=tenant,
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
        if __opts__.get('test'):
            ret['result'] = None
            ret['comment'] = 'User "{0}" will be deleted'.format(name)
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
           'comment': 'Tenant / project "{0}" already exists'.format(name)}

    _api_version(profile=profile, **connection_args)

    # Check if tenant is already present
    tenant = __salt__['keystone.tenant_get'](name=name,
                                             profile=profile,
                                             **connection_args)

    if 'Error' not in tenant:
        if tenant[name].get('description', None) != description:
            if __opts__.get('test'):
                ret['result'] = None
                ret['comment'] = 'Tenant / project "{0}" will be updated'.format(name)
                ret['changes']['Description'] = 'Will be updated'
                return ret
            __salt__['keystone.tenant_update'](name=name,
                                               description=description,
                                               enabled=enabled,
                                               profile=profile,
                                               **connection_args)
            ret['comment'] = 'Tenant / project "{0}" has been updated'.format(name)
            ret['changes']['Description'] = 'Updated'
        if tenant[name].get('enabled', None) != enabled:
            if __opts__.get('test'):
                ret['result'] = None
                ret['comment'] = 'Tenant / project "{0}" will be updated'.format(name)
                ret['changes']['Enabled'] = 'Will be {0}'.format(enabled)
                return ret
            __salt__['keystone.tenant_update'](name=name,
                                               description=description,
                                               enabled=enabled,
                                               profile=profile,
                                               **connection_args)
            ret['comment'] = 'Tenant / project "{0}" has been updated'.format(name)
            ret['changes']['Enabled'] = 'Now {0}'.format(enabled)
    else:
        if __opts__.get('test'):
            ret['result'] = None
            ret['comment'] = 'Tenant / project "{0}" will be added'.format(name)
            ret['changes']['Tenant'] = 'Will be created'
            return ret
        # Create tenant
        if _OS_IDENTITY_API_VERSION > 2:
            created = __salt__['keystone.project_create'](name=name, domain='default', description=description,
                                                          enabled=enabled, profile=profile, **connection_args)
        else:
            created = __salt__['keystone.tenant_create'](name=name, description=description, enabled=enabled,
                                                         profile=profile, **connection_args)
        ret['changes']['Tenant'] = 'Created' if created is True else 'Failed'
        ret['result'] = created
        ret['comment'] = 'Tenant / project "{0}" has been added'.format(name)
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
           'comment': 'Tenant / project "{0}" is already absent'.format(name)}

    # Check if tenant is present
    tenant = __salt__['keystone.tenant_get'](name=name,
                                             profile=profile,
                                             **connection_args)
    if 'Error' not in tenant:
        if __opts__.get('test'):
            ret['result'] = None
            ret['comment'] = 'Tenant / project "{0}" will be deleted'.format(name)
            return ret
        # Delete tenant
        __salt__['keystone.tenant_delete'](name=name, profile=profile,
                                           **connection_args)
        ret['comment'] = 'Tenant / project "{0}" has been deleted'.format(name)
        ret['changes']['Tenant/Project'] = 'Deleted'

    return ret


def project_present(name, description=None, enabled=True, profile=None,
                    **connection_args):
    '''
    Ensures that the keystone project exists
    Alias for tenant_present from V2 API to fulfill
    V3 API naming convention.

    .. versionadded:: 2016.11.0

    name
        The name of the project to manage

    description
        The description to use for this project

    enabled
        Availability state for this project

    .. code-block:: yaml

        nova:
            keystone.project_present:
                - enabled: True
                - description: 'Nova Compute Service'

    '''

    return tenant_present(name, description=description, enabled=enabled, profile=profile,
                          **connection_args)


def project_absent(name, profile=None, **connection_args):
    '''
    Ensure that the keystone project is absent.
    Alias for tenant_absent from V2 API to fulfill
    V3 API naming convention.

    .. versionadded:: 2016.11.0

    name
        The name of the project that should not exist

    .. code-block:: yaml

        delete_nova:
            keystone.project_absent:
                - name: nova
    '''

    return tenant_absent(name, profile=profile, **connection_args)


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
        if __opts__.get('test'):
            ret['result'] = None
            ret['comment'] = 'Role "{0}" will be added'.format(name)
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
        if __opts__.get('test'):
            ret['result'] = None
            ret['comment'] = 'Role "{0}" will be deleted'.format(name)
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
        if __opts__.get('test'):
            ret['result'] = None
            ret['comment'] = 'Service "{0}" will be added'.format(name)
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
        if __opts__.get('test'):
            ret['result'] = None
            ret['comment'] = 'Service "{0}" will be deleted'.format(name)
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
                     region=None,
                     profile=None,
                     url=None,
                     interface=None, **connection_args):
    '''
    Ensure the specified endpoints exists for service

    name
        The Service name

    publicurl
        The public url of service endpoint (for V2 API)

    internalurl
        The internal url of service endpoint (for V2 API)

    adminurl
        The admin url of the service endpoint (for V2 API)

    region
        The region of the endpoint

    url
        The endpoint URL (for V3 API)

    interface
        The interface type, which describes the visibility
        of the endpoint. (for V3 API)

    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    _api_version(profile=profile, **connection_args)

    endpoint = __salt__['keystone.endpoint_get'](name, region,
                                                 profile=profile,
                                                 **connection_args)
    def _changes(desc):
        return ret.get('comment', '') + desc + '\n'

    def _createEndpoint():
        if _OS_IDENTITY_API_VERSION > 2:
            ret['changes'] = __salt__['keystone.endpoint_create'](
                name,
                region=region,
                url=url,
                interface=interface,
                profile=profile,
                **connection_args)
        else:
            ret['changes'] = __salt__['keystone.endpoint_create'](
                name,
                region=region,
                publicurl=publicurl,
                adminurl=adminurl,
                internalurl=internalurl,
                profile=profile,
                **connection_args)


    if endpoint and 'Error' not in endpoint and endpoint.get('region') == region:

        if _OS_IDENTITY_API_VERSION > 2:

            change_url = False
            change_interface = False

            if endpoint.get('url', None) != url:
                ret['comment'] = _changes('URL changes from "{0}" to "{1}"'.format(endpoint.get('url', None), url))
                change_url = True

            if endpoint.get('interface', None) != interface:
                ret['comment'] = _changes('Interface changes from "{0}" to "{1}"'.format(endpoint.get('interface', None), interface))
                change_interface = True

            if __opts__.get('test') and (change_url or change_interface):
                ret['result'] = None
                ret['changes']['Endpoint'] = 'Will be updated'
                ret['comment'] += 'Endpoint for service "{0}" will be updated'.format(name)
                return ret

            if change_url:
                ret['changes']['url'] = url

            if change_interface:
                ret['changes']['interface'] = interface

        else:
            change_publicurl = False
            change_adminurl = False
            change_internalurl = False

            if endpoint.get('publicurl', None) != publicurl:
                change_publicurl = True
                ret['comment'] = _changes('Public URL changes from "{0}" to "{1}"'.format(endpoint.get('publicurl', None), publicurl))

            if endpoint.get('adminurl', None) != adminurl:
                change_adminurl = True
                ret['comment'] = _changes('Admin URL changes from "{0}" to "{1}"'.format(endpoint.get('adminurl', None), adminurl))

            if endpoint.get('internalurl', None) != internalurl:
                change_internalurl = True
                ret['comment'] = _changes('Internal URL changes from "{0}" to "{1}"'.format(endpoint.get('internal', None), internal))

            if __opts__.get('test') and (change_publicurl or change_adminurl or change_internalurl):
                ret['result'] = None
                ret['comment'] += 'Endpoint for service "{0}" will be updated'.format(name)
                ret['changes']['Endpoint'] = 'Will be updated'
                return ret

            if change_publicurl:
                ret['changes']['publicurl'] = publicurl

            if change_adminurl:
                ret['changes']['adminurl'] = adminurl

            if change_internalurl:
                ret['changes']['internalurl'] = internalurl

        if ret['comment']: # changed
            __salt__['keystone.endpoint_delete'](name, region, profile=profile, **connection_args)
            _createEndpoint()
            ret['comment'] += 'Endpoint for service "{0}" has been updated'.format(name)

    else:
        # Add new endpoint
        if __opts__.get('test'):
            ret['result'] = None
            ret['changes']['Endpoint'] = 'Will be created'
            ret['comment'] = 'Endpoint for service "{0}" will be added'.format(name)
            return ret
        _createEndpoint()
        ret['comment'] = 'Endpoint for service "{0}" has been added'.format(name)

    if ret['comment'] == '': #=> no changes
        ret['result'] = None
        ret['comment'] = 'Endpoint for service "{0}" already exists'.format(name)
    return ret


def endpoint_absent(name, region=None, profile=None, **connection_args):
    '''
    Ensure that the endpoint for a service doesn't exist in Keystone catalog

    name
        The name of the service whose endpoints should not exist
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'Endpoint for service "{0}" is already absent'.format(name)}

    # Check if service is present
    endpoint = __salt__['keystone.endpoint_get'](name, region,
                                                 profile=profile,
                                                 **connection_args)
    if not endpoint:
        return ret
    else:
        if __opts__.get('test'):
            ret['result'] = None
            ret['comment'] = 'Endpoint for service "{0}" will be deleted'.format(name)
            return ret
        # Delete service
        __salt__['keystone.endpoint_delete'](name, region,
                                             profile=profile,
                                             **connection_args)
        ret['comment'] = 'Endpoint for service "{0}" has been deleted'.format(name)
        ret['changes']['endpoint'] = 'Deleted'
    return ret
