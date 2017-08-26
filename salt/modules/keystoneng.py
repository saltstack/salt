import salt.utils

HAS_SHADE = False
try:
    import shade
    from shade.exc import OpenStackCloudException
    HAS_SHADE = True
except ImportError:
    pass


def __virtual__():
    if HAS_SHADE:
        return 'keystoneng'
    return False


__opts__ = {}


def compare_changes(obj, **kwargs):
    changes = {}
    for k, v in obj.items():
        if k in kwargs:
            if v != kwargs[k]:
                changes[k] = kwargs[k]
    return changes


def get_entity(cloud, ent_type, **kwargs):
    try:
        func = 'keystoneng.{}_get'.format(ent_type)
        ent = __salt__[func](cloud=cloud, **kwargs)
    except OpenStackCloudException as e:
        # NOTE(SamYaple): If this error was something other than Forbidden we
        # reraise the issue since we are not prepared to handle it
        if 'HTTP 403' not in e.inner_exception[1][0]:
            raise

        # NOTE(SamYaple): The user may not be authorized to perform the action
        # they are trying to do, but not authorized to search. In such a
        # situation we want to trust that the user has passed a valid ID, even
        # though we cannot validate that this is a valid id
        ent = kwargs['name']

    return ent


def _clean_kwargs(keep_name=False, **kwargs):
    if 'name' in kwargs and not keep_name:
        kwargs['name_or_id'] = kwargs.pop('name')

    try:
        clean_func = salt.utils.args.clean_kwargs
    except AttributeError:
        clean_func = salt.utils.clean_kwargs
    return clean_func(**kwargs)


def get_operator_cloud(auth):
    return shade.operator_cloud(**auth)


def get_openstack_cloud(auth):
    return shade.openstack_cloud(**auth)


def group_create(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(keep_name=True, **kwargs)
    return cloud.create_group(**kwargs)


def group_delete(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.delete_group(**kwargs)


def group_update(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.update_group(**kwargs)


def group_list(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.list_groups(**kwargs)


def group_search(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.search_groups(**kwargs)


def group_get(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.get_group(**kwargs)


def project_create(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_openstack_cloud(auth)
    kwargs = _clean_kwargs(keep_name=True, **kwargs)
    return cloud.create_project(**kwargs)


def project_delete(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_openstack_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.delete_project(**kwargs)


def project_update(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_openstack_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.update_project(**kwargs)


def project_list(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_openstack_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.list_projects(**kwargs)


def project_search(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_openstack_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.search_projects(**kwargs)


def project_get(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_openstack_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.get_project(**kwargs)


def domain_create(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(keep_name=True, **kwargs)
    return cloud.create_domain(**kwargs)


def domain_delete(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.delete_domain(**kwargs)


def domain_update(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(keep_name=True, **kwargs)
    # NOTE(SamYaple): name is a valid paramater for domain_update, but
    # name_or_id is a requirement if domain_id is not specified
    if 'name' in kwargs:
        kwargs['name_or_id'] = kwargs['name']
    return cloud.update_domain(**kwargs)


def domain_list(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.list_domains(**kwargs)


def domain_search(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.search_domains(**kwargs)


def domain_get(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.get_domain(**kwargs)


def role_create(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(keep_name=True, **kwargs)
    return cloud.create_role(**kwargs)


def role_delete(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.delete_role(**kwargs)


def role_update(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.update_role(**kwargs)


def role_list(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.list_roles(**kwargs)

def role_search(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.search_roles(**kwargs)


def role_get(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.get_role(**kwargs)


def user_create(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_openstack_cloud(auth)
    kwargs = _clean_kwargs(keep_name=True, **kwargs)
    return cloud.create_user(**kwargs)


def user_delete(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_openstack_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.delete_user(**kwargs)


def user_update(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_openstack_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.update_user(**kwargs)


def user_list(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_openstack_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.list_users(**kwargs)


def user_search(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_openstack_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.search_users(**kwargs)


def user_get(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_openstack_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.get_user(**kwargs)


def endpoint_create(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(keep_name=True, **kwargs)
    return cloud.create_endpoint(**kwargs)


def endpoint_delete(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.delete_endpoint(**kwargs)

def endpoint_update(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.update_endpoint(**kwargs)


def endpoint_list(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.list_endpoints(**kwargs)


def endpoint_search(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.search_endpoints(**kwargs)


def endpoint_get(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.get_endpoint(**kwargs)


def service_create(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(keep_name=True, **kwargs)
    return cloud.create_service(**kwargs)


def service_delete(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.delete_service(**kwargs)


def service_update(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.update_service(**kwargs)


def service_list(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.list_services(**kwargs)


def service_search(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.search_services(**kwargs)


def service_get(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.get_service(**kwargs)


def role_assignment_list(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.list_role_assignments(**kwargs)


def role_grant(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.grant_role(**kwargs)


def role_revoke(auth={}, cloud=None, **kwargs):
    if cloud is None:
        cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.revoke_role(**kwargs)
