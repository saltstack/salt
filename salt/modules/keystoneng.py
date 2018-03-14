# -*- coding: utf-8 -*-
'''
Keystone module for interacting with OpenStack Keystone

.. versionadded:: 2018.3.0

:depends:shade

Example configuration

.. code-block:: yaml
    keystone:
      cloud: default

.. code-block:: yaml
    keystone:
      auth:
        username: admin
        password: password123
        user_domain_name: mydomain
        project_name: myproject
        project_domain_name: myproject
        auth_url: https://example.org:5000/v3
      identity_api_version: 3
'''

from __future__ import absolute_import, unicode_literals, print_function

HAS_SHADE = False
try:
    import shade
    from shade.exc import OpenStackCloudException
    HAS_SHADE = True
except ImportError:
    pass

__virtualname__ = 'keystoneng'


def __virtual__():
    '''
    Only load this module if shade python module is installed
    '''
    if HAS_SHADE:
        return __virtualname__
    return (False, 'The keystoneng execution module failed to load: shade python module is not available')


def compare_changes(obj, **kwargs):
    '''
    Compare two dicts returning only keys that exist in the first dict and are
    different in the second one
    '''
    changes = {}
    for k, v in obj.items():
        if k in kwargs:
            if v != kwargs[k]:
                changes[k] = kwargs[k]
    return changes


def get_entity(ent_type, **kwargs):
    '''
    Attempt to query Keystone for more information about an entity
    '''
    try:
        func = 'keystoneng.{}_get'.format(ent_type)
        ent = __salt__[func](**kwargs)
    except OpenStackCloudException as e:
        # NOTE(SamYaple): If this error was something other than Forbidden we
        # reraise the issue since we are not prepared to handle it
        if 'HTTP 403' not in e.inner_exception[1][0]:
            raise

        # NOTE(SamYaple): The user may be authorized to perform the function
        # they are trying to do, but not authorized to search. In such a
        # situation we want to trust that the user has passed a valid id, even
        # though we cannot validate that this is a valid id
        ent = kwargs['name']

    return ent


def _clean_kwargs(keep_name=False, **kwargs):
    '''
    Sanatize the the arguments for use with shade
    '''
    if 'name' in kwargs and not keep_name:
        kwargs['name_or_id'] = kwargs.pop('name')

    return __utils__['args.clean_kwargs'](**kwargs)


def setup_clouds(auth=None):
    '''
    Call functions to create Shade cloud objects in __context__ to take
    advantage of Shade's in-memory caching across several states
    '''
    get_operator_cloud(auth)
    get_openstack_cloud(auth)


def get_operator_cloud(auth=None):
    '''
    Return an operator_cloud
    '''
    if auth is None:
        auth = __salt__['config.option']('keystone', {})
    if 'shade_opcloud' in __context__:
        if __context__['shade_opcloud'].auth == auth:
            return __context__['shade_opcloud']
    __context__['shade_opcloud'] = shade.operator_cloud(**auth)
    return __context__['shade_opcloud']


def get_openstack_cloud(auth=None):
    '''
    Return an openstack_cloud
    '''
    if auth is None:
        auth = __salt__['config.option']('keystone', {})
    if 'shade_oscloud' in __context__:
        if __context__['shade_oscloud'].auth == auth:
            return __context__['shade_oscloud']
    __context__['shade_oscloud'] = shade.openstack_cloud(**auth)
    return __context__['shade_oscloud']


def group_create(auth=None, **kwargs):
    '''
    Create a group

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.group_create name=group1
        salt '*' keystoneng.group_create name=group2 domain=domain1 description='my group2'
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(keep_name=True, **kwargs)
    return cloud.create_group(**kwargs)


def group_delete(auth=None, **kwargs):
    '''
    Delete a group

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.group_delete name=group1
        salt '*' keystoneng.group_delete name=group2 domain_id=b62e76fbeeff4e8fb77073f591cf211e
        salt '*' keystoneng.group_delete name=0e4febc2a5ab4f2c8f374b054162506d
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.delete_group(**kwargs)


def group_update(auth=None, **kwargs):
    '''
    Update a group

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.group_update name=group1 description='new description'
        salt '*' keystoneng.group_create name=group2 domain_id=b62e76fbeeff4e8fb77073f591cf211e new_name=newgroupname
        salt '*' keystoneng.group_create name=0e4febc2a5ab4f2c8f374b054162506d new_name=newgroupname
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    if 'new_name' in kwargs:
        kwargs['name'] = kwargs.pop('new_name')
    return cloud.update_group(**kwargs)


def group_list(auth=None, **kwargs):
    '''
    List groups

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.group_list
        salt '*' keystoneng.group_list domain_id=b62e76fbeeff4e8fb77073f591cf211e
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.list_groups(**kwargs)


def group_search(auth=None, **kwargs):
    '''
    Search for groups

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.group_search name=group1
        salt '*' keystoneng.group_search domain_id=b62e76fbeeff4e8fb77073f591cf211e
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.search_groups(**kwargs)


def group_get(auth=None, **kwargs):
    '''
    Get a single group

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.group_get name=group1
        salt '*' keystoneng.group_get name=group2 domain_id=b62e76fbeeff4e8fb77073f591cf211e
        salt '*' keystoneng.group_get name=0e4febc2a5ab4f2c8f374b054162506d
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.get_group(**kwargs)


def project_create(auth=None, **kwargs):
    '''
    Create a project

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.project_create name=project1
        salt '*' keystoneng.project_create name=project2 domain_id=b62e76fbeeff4e8fb77073f591cf211e
        salt '*' keystoneng.project_create name=project3 enabled=False description='my project3'
    '''
    cloud = get_openstack_cloud(auth)
    kwargs = _clean_kwargs(keep_name=True, **kwargs)
    return cloud.create_project(**kwargs)


def project_delete(auth=None, **kwargs):
    '''
    Delete a project

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.project_delete name=project1
        salt '*' keystoneng.project_delete name=project2 domain_id=b62e76fbeeff4e8fb77073f591cf211e
        salt '*' keystoneng.project_delete name=f315afcf12f24ad88c92b936c38f2d5a
    '''
    cloud = get_openstack_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.delete_project(**kwargs)


def project_update(auth=None, **kwargs):
    '''
    Update a project

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.project_update name=project1 new_name=newproject
        salt '*' keystoneng.project_update name=project2 enabled=False description='new description'
    '''
    cloud = get_openstack_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    if 'new_name' in kwargs:
        kwargs['name'] = kwargs.pop('new_name')
    return cloud.update_project(**kwargs)


def project_list(auth=None, **kwargs):
    '''
    List projects

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.project_list
        salt '*' keystoneng.project_list domain_id=b62e76fbeeff4e8fb77073f591cf211e
    '''
    cloud = get_openstack_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.list_projects(**kwargs)


def project_search(auth=None, **kwargs):
    '''
    Search projects

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.project_search
        salt '*' keystoneng.project_search name=project1
        salt '*' keystoneng.project_search domain_id=b62e76fbeeff4e8fb77073f591cf211e
    '''
    cloud = get_openstack_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.search_projects(**kwargs)


def project_get(auth=None, **kwargs):
    '''
    Get a single project

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.project_get name=project1
        salt '*' keystoneng.project_get name=project2 domain_id=b62e76fbeeff4e8fb77073f591cf211e
        salt '*' keystoneng.project_get name=f315afcf12f24ad88c92b936c38f2d5a
    '''
    cloud = get_openstack_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.get_project(**kwargs)


def domain_create(auth=None, **kwargs):
    '''
    Create a domain

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.domain_create name=domain1
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(keep_name=True, **kwargs)
    return cloud.create_domain(**kwargs)


def domain_delete(auth=None, **kwargs):
    '''
    Delete a domain

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.domain_delete name=domain1
        salt '*' keystoneng.domain_delete name=b62e76fbeeff4e8fb77073f591cf211e
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.delete_domain(**kwargs)


def domain_update(auth=None, **kwargs):
    '''
    Update a domain

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.domain_update name=domain1 new_name=newdomain
        salt '*' keystoneng.domain_update name=domain1 enabled=True description='new description'
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    if 'new_name' in kwargs:
        kwargs['name'] = kwargs.pop('new_name')
    return cloud.update_domain(**kwargs)


def domain_list(auth=None, **kwargs):
    '''
    List domains

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.domain_list
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.list_domains(**kwargs)


def domain_search(auth=None, **kwargs):
    '''
    Search domains

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.domain_search
        salt '*' keystoneng.domain_search name=domain1
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.search_domains(**kwargs)


def domain_get(auth=None, **kwargs):
    '''
    Get a single domain

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.domain_get name=domain1
        salt '*' keystoneng.domain_get name=b62e76fbeeff4e8fb77073f591cf211e
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.get_domain(**kwargs)


def role_create(auth=None, **kwargs):
    '''
    Create a role

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.role_create name=role1
        salt '*' keystoneng.role_create name=role1 domain_id=b62e76fbeeff4e8fb77073f591cf211e
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(keep_name=True, **kwargs)
    return cloud.create_role(**kwargs)


def role_delete(auth=None, **kwargs):
    '''
    Delete a role

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.role_delete name=role1 domain_id=b62e76fbeeff4e8fb77073f591cf211e
        salt '*' keystoneng.role_delete name=1eb6edd5525e4ac39af571adee673559
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.delete_role(**kwargs)


def role_update(auth=None, **kwargs):
    '''
    Update a role

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.role_update name=role1 new_name=newrole
        salt '*' keystoneng.role_update name=1eb6edd5525e4ac39af571adee673559 new_name=newrole
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    if 'new_name' in kwargs:
        kwargs['name'] = kwargs.pop('new_name')
    return cloud.update_role(**kwargs)


def role_list(auth=None, **kwargs):
    '''
    List roles

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.role_list
        salt '*' keystoneng.role_list domain_id=b62e76fbeeff4e8fb77073f591cf211e
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.list_roles(**kwargs)


def role_search(auth=None, **kwargs):
    '''
    Search roles

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.role_search
        salt '*' keystoneng.role_search name=role1
        salt '*' keystoneng.role_search domain_id=b62e76fbeeff4e8fb77073f591cf211e
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.search_roles(**kwargs)


def role_get(auth=None, **kwargs):
    '''
    Get a single role

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.role_get name=role1
        salt '*' keystoneng.role_get name=role1 domain_id=b62e76fbeeff4e8fb77073f591cf211e
        salt '*' keystoneng.role_get name=1eb6edd5525e4ac39af571adee673559
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.get_role(**kwargs)


def user_create(auth=None, **kwargs):
    '''
    Create a user

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.user_create name=user1
        salt '*' keystoneng.user_create name=user2 password=1234 enabled=False
        salt '*' keystoneng.user_create name=user3 domain_id=b62e76fbeeff4e8fb77073f591cf211e
    '''
    cloud = get_openstack_cloud(auth)
    kwargs = _clean_kwargs(keep_name=True, **kwargs)
    return cloud.create_user(**kwargs)


def user_delete(auth=None, **kwargs):
    '''
    Delete a user

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.user_delete name=user1
        salt '*' keystoneng.user_delete name=user2 domain_id=b62e76fbeeff4e8fb77073f591cf211e
        salt '*' keystoneng.user_delete name=a42cbbfa1e894e839fd0f584d22e321f
    '''
    cloud = get_openstack_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.delete_user(**kwargs)


def user_update(auth=None, **kwargs):
    '''
    Update a user

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.user_update name=user1 enabled=False description='new description'
        salt '*' keystoneng.user_update name=user1 new_name=newuser
    '''
    cloud = get_openstack_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    if 'new_name' in kwargs:
        kwargs['name'] = kwargs.pop('new_name')
    return cloud.update_user(**kwargs)


def user_list(auth=None, **kwargs):
    '''
    List users

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.user_list
        salt '*' keystoneng.user_list domain_id=b62e76fbeeff4e8fb77073f591cf211e
    '''
    cloud = get_openstack_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.list_users(**kwargs)


def user_search(auth=None, **kwargs):
    '''
    List users

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.user_list
        salt '*' keystoneng.user_list domain_id=b62e76fbeeff4e8fb77073f591cf211e
    '''
    cloud = get_openstack_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.search_users(**kwargs)


def user_get(auth=None, **kwargs):
    '''
    Get a single user

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.user_get name=user1
        salt '*' keystoneng.user_get name=user1 domain_id=b62e76fbeeff4e8fb77073f591cf211e
        salt '*' keystoneng.user_get name=02cffaa173b2460f98e40eda3748dae5
    '''
    cloud = get_openstack_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.get_user(**kwargs)


def endpoint_create(auth=None, **kwargs):
    '''
    Create an endpoint

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.endpoint_create interface=admin service=glance url=https://example.org:9292
        salt '*' keystoneng.endpoint_create interface=public service=glance region=RegionOne url=https://example.org:9292
        salt '*' keystoneng.endpoint_create interface=admin service=glance url=https://example.org:9292 enabled=True
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(keep_name=True, **kwargs)
    return cloud.create_endpoint(**kwargs)


def endpoint_delete(auth=None, **kwargs):
    '''
    Delete an endpoint

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.endpoint_delete id=3bee4bd8c2b040ee966adfda1f0bfca9
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.delete_endpoint(**kwargs)


def endpoint_update(auth=None, **kwargs):
    '''
    Update an endpoint

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.endpoint_update endpoint_id=4f961ad09d2d48948896bbe7c6a79717 interface=public enabled=False
        salt '*' keystoneng.endpoint_update endpoint_id=4f961ad09d2d48948896bbe7c6a79717 region=newregion
        salt '*' keystoneng.endpoint_update endpoint_id=4f961ad09d2d48948896bbe7c6a79717 service_name_or_id=glance url=https://example.org:9292
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.update_endpoint(**kwargs)


def endpoint_list(auth=None, **kwargs):
    '''
    List endpoints

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.endpoint_list
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.list_endpoints(**kwargs)


def endpoint_search(auth=None, **kwargs):
    '''
    Search endpoints

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.endpoint_search
        salt '*' keystoneng.endpoint_search id=02cffaa173b2460f98e40eda3748dae5
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.search_endpoints(**kwargs)


def endpoint_get(auth=None, **kwargs):
    '''
    Get a single endpoint

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.endpoint_get id=02cffaa173b2460f98e40eda3748dae5
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.get_endpoint(**kwargs)


def service_create(auth=None, **kwargs):
    '''
    Create a service

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.service_create name=glance type=image
        salt '*' keystoneng.service_create name=glance type=image description="Image"
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(keep_name=True, **kwargs)
    return cloud.create_service(**kwargs)


def service_delete(auth=None, **kwargs):
    '''
    Delete a service

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.service_delete name=glance
        salt '*' keystoneng.service_delete name=39cc1327cdf744ab815331554430e8ec
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.delete_service(**kwargs)


def service_update(auth=None, **kwargs):
    '''
    Update a service

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.service_update name=cinder type=volumev2
        salt '*' keystoneng.service_update name=cinder description='new description'
        salt '*' keystoneng.service_update name=ab4d35e269f147b3ae2d849f77f5c88f enabled=False
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.update_service(**kwargs)


def service_list(auth=None, **kwargs):
    '''
    List services

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.service_list
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.list_services(**kwargs)


def service_search(auth=None, **kwargs):
    '''
    Search services

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.service_search
        salt '*' keystoneng.service_search name=glance
        salt '*' keystoneng.service_search name=135f0403f8e544dc9008c6739ecda860
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.search_services(**kwargs)


def service_get(auth=None, **kwargs):
    '''
    Get a single service

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.service_get name=glance
        salt '*' keystoneng.service_get name=75a5804638944b3ab54f7fbfcec2305a
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.get_service(**kwargs)


def role_assignment_list(auth=None, **kwargs):
    '''
    List role assignments

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.role_assignment_list
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.list_role_assignments(**kwargs)


def role_grant(auth=None, **kwargs):
    '''
    Grant a role in a project/domain to a user/group

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.role_grant name=role1 user=user1 project=project1
        salt '*' keystoneng.role_grant name=ddbe3e0ed74e4c7f8027bad4af03339d group=user1 project=project1 domain=domain1
        salt '*' keystoneng.role_grant name=ddbe3e0ed74e4c7f8027bad4af03339d group=19573afd5e4241d8b65c42215bae9704 project=1dcac318a83b4610b7a7f7ba01465548
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.grant_role(**kwargs)


def role_revoke(auth=None, **kwargs):
    '''
    Grant a role in a project/domain to a user/group

    CLI Example:

    .. code-block:: bash

        salt '*' keystoneng.role_revoke name=role1 user=user1 project=project1
        salt '*' keystoneng.role_revoke name=ddbe3e0ed74e4c7f8027bad4af03339d group=user1 project=project1 domain=domain1
        salt '*' keystoneng.role_revoke name=ddbe3e0ed74e4c7f8027bad4af03339d group=19573afd5e4241d8b65c42215bae9704 project=1dcac318a83b4610b7a7f7ba01465548
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.revoke_role(**kwargs)
