"""
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
        keystone.verify_ssl: True

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
          keystone.verify_ssl: True

        openstack2:
          keystone.user: admin
          keystone.password: verybadpass
          keystone.tenant: admin
          keystone.tenant_id: f80919baedab48ec8931f200c65a50df
          keystone.auth_url: 'http://127.0.0.2:5000/v2.0/'
          keystone.verify_ssl: True

    With this configuration in place, any of the keystone functions can make use
    of a configuration profile by declaring it explicitly.
    For example:

    .. code-block:: bash

        salt '*' keystone.tenant_list profile=openstack1
"""

import logging

import salt.utils.http

HAS_KEYSTONE = False
try:
    # pylint: disable=import-error
    import keystoneclient.exceptions
    from keystoneclient.v2_0 import client

    HAS_KEYSTONE = True
    from keystoneauth1 import session
    from keystoneauth1.identity import generic
    from keystoneclient import discover
    from keystoneclient.v3 import client as client3

    # pylint: enable=import-error
except ImportError:
    pass

_OS_IDENTITY_API_VERSION = 2
_TENANTS = "tenants"

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load this module if keystone
    is installed on this minion.
    """
    if HAS_KEYSTONE:
        return "keystone"
    return (
        False,
        "keystone execution module cannot be loaded: keystoneclient python library not"
        " available.",
    )


def _get_kwargs(profile=None, **connection_args):
    """
    get connection args
    """
    if profile:
        prefix = profile + ":keystone."
    else:
        prefix = "keystone."

    def get(key, default=None):
        """
        look in connection_args first, then default to config file
        """
        return connection_args.get(
            "connection_" + key, __salt__["config.get"](prefix + key, default)
        )

    user = get("user", "admin")
    password = get("password", "ADMIN")
    tenant = get("tenant", "admin")
    tenant_id = get("tenant_id")
    auth_url = get("auth_url", "http://127.0.0.1:35357/v2.0/")
    insecure = get("insecure", False)
    token = get("token")
    endpoint = get("endpoint", "http://127.0.0.1:35357/v2.0")
    user_domain_name = get("user_domain_name", "Default")
    project_domain_name = get("project_domain_name", "Default")
    verify_ssl = get("verify_ssl", True)
    if token:
        kwargs = {"token": token, "endpoint": endpoint}
    else:
        kwargs = {
            "username": user,
            "password": password,
            "tenant_name": tenant,
            "tenant_id": tenant_id,
            "auth_url": auth_url,
            "user_domain_name": user_domain_name,
            "project_domain_name": project_domain_name,
        }
        # 'insecure' keyword not supported by all v2.0 keystone clients
        #   this ensures it's only passed in when defined
        if insecure:
            kwargs["insecure"] = True
    kwargs["verify_ssl"] = verify_ssl
    return kwargs


def api_version(profile=None, **connection_args):
    """
    Returns the API version derived from endpoint's response.

    CLI Example:

    .. code-block:: bash

        salt '*' keystone.api_version
    """
    kwargs = _get_kwargs(profile=profile, **connection_args)
    auth_url = kwargs.get("auth_url", kwargs.get("endpoint", None))
    try:
        return salt.utils.http.query(
            auth_url, decode=True, decode_type="json", verify_ssl=kwargs["verify_ssl"]
        )["dict"]["version"]["id"]
    except KeyError:
        return None


def auth(profile=None, **connection_args):
    """
    Set up keystone credentials. Only intended to be used within Keystone-enabled modules.

    CLI Example:

    .. code-block:: bash

        salt '*' keystone.auth
    """
    __utils__["versions.warn_until"](
        "Argon",
        "The keystone module has been deprecated and will be removed in {version}.  "
        "Please update to using the keystoneng module",
    )
    kwargs = _get_kwargs(profile=profile, **connection_args)

    disc = discover.Discover(auth_url=kwargs["auth_url"])
    v2_auth_url = disc.url_for("v2.0")
    v3_auth_url = disc.url_for("v3.0")
    if v3_auth_url:
        global _OS_IDENTITY_API_VERSION
        global _TENANTS
        _OS_IDENTITY_API_VERSION = 3
        _TENANTS = "projects"
        kwargs["auth_url"] = v3_auth_url
    else:
        kwargs["auth_url"] = v2_auth_url
        kwargs.pop("user_domain_name")
        kwargs.pop("project_domain_name")
    auth = generic.Password(**kwargs)
    sess = session.Session(auth=auth)
    ks_cl = disc.create_client(session=sess)
    return ks_cl


def ec2_credentials_create(
    user_id=None,
    name=None,
    tenant_id=None,
    tenant=None,
    profile=None,
    **connection_args,
):
    """
    Create EC2-compatible credentials for user per tenant

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.ec2_credentials_create name=admin tenant=admin

        salt '*' keystone.ec2_credentials_create \
        user_id=c965f79c4f864eaaa9c3b41904e67082 \
        tenant_id=722787eb540849158668370dc627ec5f
    """
    kstone = auth(profile, **connection_args)

    if name:
        user_id = user_get(name=name, profile=profile, **connection_args)[name]["id"]
    if not user_id:
        return {"Error": "Could not resolve User ID"}

    if tenant:
        tenant_id = tenant_get(name=tenant, profile=profile, **connection_args)[tenant][
            "id"
        ]
    if not tenant_id:
        return {"Error": "Could not resolve Tenant ID"}

    newec2 = kstone.ec2.create(user_id, tenant_id)
    return {
        "access": newec2.access,
        "secret": newec2.secret,
        "tenant_id": newec2.tenant_id,
        "user_id": newec2.user_id,
    }


def ec2_credentials_delete(
    user_id=None, name=None, access_key=None, profile=None, **connection_args
):
    """
    Delete EC2-compatible credentials

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.ec2_credentials_delete \
        860f8c2c38ca4fab989f9bc56a061a64 access_key=5f66d2f24f604b8bb9cd28886106f442

        salt '*' keystone.ec2_credentials_delete name=admin \
        access_key=5f66d2f24f604b8bb9cd28886106f442
    """
    kstone = auth(profile, **connection_args)

    if name:
        user_id = user_get(name=name, profile=None, **connection_args)[name]["id"]
    if not user_id:
        return {"Error": "Could not resolve User ID"}
    kstone.ec2.delete(user_id, access_key)
    return f'ec2 key "{access_key}" deleted under user id "{user_id}"'


def ec2_credentials_get(
    user_id=None, name=None, access=None, profile=None, **connection_args
):
    """
    Return ec2_credentials for a user (keystone ec2-credentials-get)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.ec2_credentials_get c965f79c4f864eaaa9c3b41904e67082 access=722787eb540849158668370
        salt '*' keystone.ec2_credentials_get user_id=c965f79c4f864eaaa9c3b41904e67082 access=722787eb540849158668370
        salt '*' keystone.ec2_credentials_get name=nova access=722787eb540849158668370dc627ec5f
    """
    kstone = auth(profile, **connection_args)
    ret = {}
    if name:
        for user in kstone.users.list():
            if user.name == name:
                user_id = user.id
                break
    if not user_id:
        return {"Error": "Unable to resolve user id"}
    if not access:
        return {"Error": "Access key is required"}
    ec2_credentials = kstone.ec2.get(
        user_id=user_id, access=access, profile=profile, **connection_args
    )
    ret[ec2_credentials.user_id] = {
        "user_id": ec2_credentials.user_id,
        "tenant": ec2_credentials.tenant_id,
        "access": ec2_credentials.access,
        "secret": ec2_credentials.secret,
    }
    return ret


def ec2_credentials_list(user_id=None, name=None, profile=None, **connection_args):
    """
    Return a list of ec2_credentials for a specific user (keystone ec2-credentials-list)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.ec2_credentials_list 298ce377245c4ec9b70e1c639c89e654
        salt '*' keystone.ec2_credentials_list user_id=298ce377245c4ec9b70e1c639c89e654
        salt '*' keystone.ec2_credentials_list name=jack
    """
    kstone = auth(profile, **connection_args)
    ret = {}
    if name:
        for user in kstone.users.list():
            if user.name == name:
                user_id = user.id
                break
    if not user_id:
        return {"Error": "Unable to resolve user id"}
    for ec2_credential in kstone.ec2.list(user_id):
        ret[ec2_credential.user_id] = {
            "user_id": ec2_credential.user_id,
            "tenant_id": ec2_credential.tenant_id,
            "access": ec2_credential.access,
            "secret": ec2_credential.secret,
        }
    return ret


def endpoint_get(service, region=None, profile=None, interface=None, **connection_args):
    """
    Return a specific endpoint (keystone endpoint-get)

    CLI Example:

    .. code-block:: bash

        salt 'v2' keystone.endpoint_get nova [region=RegionOne]

        salt 'v3' keystone.endpoint_get nova interface=admin [region=RegionOne]
    """
    auth(profile, **connection_args)
    services = service_list(profile, **connection_args)
    if service not in services:
        return {"Error": "Could not find the specified service"}
    service_id = services[service]["id"]
    endpoints = endpoint_list(profile, **connection_args)

    e = [
        _f
        for _f in [
            (
                e
                if e["service_id"] == service_id
                and (e["region"] == region if region else True)
                and (e["interface"] == interface if interface else True)
                else None
            )
            for e in endpoints.values()
        ]
        if _f
    ]
    if len(e) > 1:
        return {
            "Error": (
                "Multiple endpoints found ({}) for the {} service. Please specify"
                " region.".format(e, service)
            )
        }
    if len(e) == 1:
        return e[0]
    return {"Error": "Could not find endpoint for the specified service"}


def endpoint_list(profile=None, **connection_args):
    """
    Return a list of available endpoints (keystone endpoints-list)

    CLI Example:

    .. code-block:: bash

        salt '*' keystone.endpoint_list
    """
    kstone = auth(profile, **connection_args)
    ret = {}

    for endpoint in kstone.endpoints.list():
        ret[endpoint.id] = {
            value: getattr(endpoint, value)
            for value in dir(endpoint)
            if not value.startswith("_")
            and isinstance(getattr(endpoint, value), (str, dict, bool))
        }
    return ret


def endpoint_create(
    service,
    publicurl=None,
    internalurl=None,
    adminurl=None,
    region=None,
    profile=None,
    url=None,
    interface=None,
    **connection_args,
):
    """
    Create an endpoint for an Openstack service

    CLI Examples:

    .. code-block:: bash

        salt 'v2' keystone.endpoint_create nova 'http://public/url' 'http://internal/url' 'http://adminurl/url' region

        salt 'v3' keystone.endpoint_create nova url='http://public/url' interface='public' region='RegionOne'
    """
    kstone = auth(profile, **connection_args)
    keystone_service = service_get(name=service, profile=profile, **connection_args)
    if not keystone_service or "Error" in keystone_service:
        return {"Error": "Could not find the specified service"}

    if _OS_IDENTITY_API_VERSION > 2:
        kstone.endpoints.create(
            service=keystone_service[service]["id"],
            region_id=region,
            url=url,
            interface=interface,
        )
    else:
        kstone.endpoints.create(
            region=region,
            service_id=keystone_service[service]["id"],
            publicurl=publicurl,
            adminurl=adminurl,
            internalurl=internalurl,
        )
    return endpoint_get(service, region, profile, interface, **connection_args)


def endpoint_delete(
    service, region=None, profile=None, interface=None, **connection_args
):
    """
    Delete endpoints of an Openstack service

    CLI Examples:

    .. code-block:: bash

        salt 'v2' keystone.endpoint_delete nova [region=RegionOne]

        salt 'v3' keystone.endpoint_delete nova interface=admin [region=RegionOne]
    """
    kstone = auth(profile, **connection_args)
    endpoint = endpoint_get(service, region, profile, interface, **connection_args)
    if not endpoint or "Error" in endpoint:
        return {"Error": "Could not find any endpoints for the service"}
    kstone.endpoints.delete(endpoint["id"])
    endpoint = endpoint_get(service, region, profile, interface, **connection_args)
    if not endpoint or "Error" in endpoint:
        return True


def role_create(name, profile=None, **connection_args):
    """
    Create a named role.

    CLI Example:

    .. code-block:: bash

        salt '*' keystone.role_create admin
    """

    kstone = auth(profile, **connection_args)
    if "Error" not in role_get(name=name, profile=profile, **connection_args):
        return {"Error": f'Role "{name}" already exists'}
    kstone.roles.create(name)
    return role_get(name=name, profile=profile, **connection_args)


def role_delete(role_id=None, name=None, profile=None, **connection_args):
    """
    Delete a role (keystone role-delete)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.role_delete c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.role_delete role_id=c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.role_delete name=admin
    """
    kstone = auth(profile, **connection_args)

    if name:
        for role in kstone.roles.list():
            if role.name == name:
                role_id = role.id
                break
    if not role_id:
        return {"Error": "Unable to resolve role id"}

    role = kstone.roles.get(role_id)
    kstone.roles.delete(role)

    ret = f"Role ID {role_id} deleted"
    if name:
        ret += f" ({name})"
    return ret


def role_get(role_id=None, name=None, profile=None, **connection_args):
    """
    Return a specific roles (keystone role-get)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.role_get c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.role_get role_id=c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.role_get name=nova
    """
    kstone = auth(profile, **connection_args)
    ret = {}
    if name:
        for role in kstone.roles.list():
            if role.name == name:
                role_id = role.id
                break
    if not role_id:
        return {"Error": "Unable to resolve role id"}
    role = kstone.roles.get(role_id)

    ret[role.name] = {"id": role.id, "name": role.name}
    return ret


def role_list(profile=None, **connection_args):
    """
    Return a list of available roles (keystone role-list)

    CLI Example:

    .. code-block:: bash

        salt '*' keystone.role_list
    """
    kstone = auth(profile, **connection_args)
    ret = {}
    for role in kstone.roles.list():
        ret[role.name] = {
            value: getattr(role, value)
            for value in dir(role)
            if not value.startswith("_")
            and isinstance(getattr(role, value), (str, dict, bool))
        }
    return ret


def service_create(
    name, service_type, description=None, profile=None, **connection_args
):
    """
    Add service to Keystone service catalog

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.service_create nova compute \
'OpenStack Compute Service'
    """
    kstone = auth(profile, **connection_args)
    service = kstone.services.create(name, service_type, description=description)
    return service_get(service.id, profile=profile, **connection_args)


def service_delete(service_id=None, name=None, profile=None, **connection_args):
    """
    Delete a service from Keystone service catalog

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.service_delete c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.service_delete name=nova
    """
    kstone = auth(profile, **connection_args)
    if name:
        service_id = service_get(name=name, profile=profile, **connection_args)[name][
            "id"
        ]
    kstone.services.delete(service_id)
    return f'Keystone service ID "{service_id}" deleted'


def service_get(service_id=None, name=None, profile=None, **connection_args):
    """
    Return a specific services (keystone service-get)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.service_get c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.service_get service_id=c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.service_get name=nova
    """
    kstone = auth(profile, **connection_args)
    ret = {}
    if name:
        for service in kstone.services.list():
            if service.name == name:
                service_id = service.id
                break
    if not service_id:
        return {"Error": "Unable to resolve service id"}
    service = kstone.services.get(service_id)
    ret[service.name] = {
        value: getattr(service, value)
        for value in dir(service)
        if not value.startswith("_")
        and isinstance(getattr(service, value), (str, dict, bool))
    }
    return ret


def service_list(profile=None, **connection_args):
    """
    Return a list of available services (keystone services-list)

    CLI Example:

    .. code-block:: bash

        salt '*' keystone.service_list
    """
    kstone = auth(profile, **connection_args)
    ret = {}
    for service in kstone.services.list():
        ret[service.name] = {
            value: getattr(service, value)
            for value in dir(service)
            if not value.startswith("_")
            and isinstance(getattr(service, value), (str, dict, bool))
        }
    return ret


def tenant_create(
    name, description=None, enabled=True, profile=None, **connection_args
):
    """
    Create a keystone tenant

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.tenant_create nova description='nova tenant'
        salt '*' keystone.tenant_create test enabled=False
    """
    kstone = auth(profile, **connection_args)
    new = getattr(kstone, _TENANTS, None).create(name, description, enabled)
    return tenant_get(new.id, profile=profile, **connection_args)


def project_create(
    name, domain, description=None, enabled=True, profile=None, **connection_args
):
    """
    Create a keystone project.
    Overrides keystone tenant_create form api V2. For keystone api V3.

    .. versionadded:: 2016.11.0

    name
        The project name, which must be unique within the owning domain.

    domain
        The domain name.

    description
        The project description.

    enabled
        Enables or disables the project.

    profile
        Configuration profile - if configuration for multiple openstack accounts required.

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.project_create nova default description='Nova Compute Project'
        salt '*' keystone.project_create test default enabled=False
    """
    kstone = auth(profile, **connection_args)
    new = getattr(kstone, _TENANTS, None).create(
        name=name, domain=domain, description=description, enabled=enabled
    )
    return tenant_get(new.id, profile=profile, **connection_args)


def tenant_delete(tenant_id=None, name=None, profile=None, **connection_args):
    """
    Delete a tenant (keystone tenant-delete)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.tenant_delete c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.tenant_delete tenant_id=c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.tenant_delete name=demo
    """
    kstone = auth(profile, **connection_args)
    if name:
        for tenant in getattr(kstone, _TENANTS, None).list():
            if tenant.name == name:
                tenant_id = tenant.id
                break
    if not tenant_id:
        return {"Error": "Unable to resolve tenant id"}
    getattr(kstone, _TENANTS, None).delete(tenant_id)
    ret = f"Tenant ID {tenant_id} deleted"
    if name:

        ret += f" ({name})"
    return ret


def project_delete(project_id=None, name=None, profile=None, **connection_args):
    """
    Delete a project (keystone project-delete).
    Overrides keystone tenant-delete form api V2. For keystone api V3 only.

    .. versionadded:: 2016.11.0

    project_id
        The project id.

    name
        The project name.

    profile
        Configuration profile - if configuration for multiple openstack accounts required.

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.project_delete c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.project_delete project_id=c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.project_delete name=demo
    """
    auth(profile, **connection_args)

    if _OS_IDENTITY_API_VERSION > 2:
        return tenant_delete(
            tenant_id=project_id, name=name, profile=None, **connection_args
        )
    else:
        return False


def tenant_get(tenant_id=None, name=None, profile=None, **connection_args):
    """
    Return a specific tenants (keystone tenant-get)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.tenant_get c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.tenant_get tenant_id=c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.tenant_get name=nova
    """
    kstone = auth(profile, **connection_args)
    ret = {}

    if name:
        for tenant in getattr(kstone, _TENANTS, None).list():
            if tenant.name == name:
                tenant_id = tenant.id
                break
    if not tenant_id:
        return {"Error": "Unable to resolve tenant id"}
    tenant = getattr(kstone, _TENANTS, None).get(tenant_id)
    ret[tenant.name] = {
        value: getattr(tenant, value)
        for value in dir(tenant)
        if not value.startswith("_")
        and isinstance(getattr(tenant, value), (str, dict, bool))
    }
    return ret


def project_get(project_id=None, name=None, profile=None, **connection_args):
    """
    Return a specific projects (keystone project-get)
    Overrides keystone tenant-get form api V2.
    For keystone api V3 only.

    .. versionadded:: 2016.11.0

    project_id
        The project id.

    name
        The project name.

    profile
        Configuration profile - if configuration for multiple openstack accounts required.

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.project_get c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.project_get project_id=c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.project_get name=nova
    """
    auth(profile, **connection_args)

    if _OS_IDENTITY_API_VERSION > 2:
        return tenant_get(
            tenant_id=project_id, name=name, profile=None, **connection_args
        )
    else:
        return False


def tenant_list(profile=None, **connection_args):
    """
    Return a list of available tenants (keystone tenants-list)

    CLI Example:

    .. code-block:: bash

        salt '*' keystone.tenant_list
    """
    kstone = auth(profile, **connection_args)
    ret = {}

    for tenant in getattr(kstone, _TENANTS, None).list():
        ret[tenant.name] = {
            value: getattr(tenant, value)
            for value in dir(tenant)
            if not value.startswith("_")
            and isinstance(getattr(tenant, value), (str, dict, bool))
        }
    return ret


def project_list(profile=None, **connection_args):
    """
    Return a list of available projects (keystone projects-list).
    Overrides keystone tenants-list form api V2.
    For keystone api V3 only.

    .. versionadded:: 2016.11.0

    profile
        Configuration profile - if configuration for multiple openstack accounts required.

    CLI Example:

    .. code-block:: bash

        salt '*' keystone.project_list
    """
    auth(profile, **connection_args)

    if _OS_IDENTITY_API_VERSION > 2:
        return tenant_list(profile, **connection_args)
    else:
        return False


def tenant_update(
    tenant_id=None,
    name=None,
    description=None,
    enabled=None,
    profile=None,
    **connection_args,
):
    """
    Update a tenant's information (keystone tenant-update)
    The following fields may be updated: name, description, enabled.
    Can only update name if targeting by ID

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.tenant_update name=admin enabled=True
        salt '*' keystone.tenant_update c965f79c4f864eaaa9c3b41904e67082 name=admin email=admin@domain.com
    """
    kstone = auth(profile, **connection_args)

    if not tenant_id:
        for tenant in getattr(kstone, _TENANTS, None).list():
            if tenant.name == name:
                tenant_id = tenant.id
                break
    if not tenant_id:
        return {"Error": "Unable to resolve tenant id"}

    tenant = getattr(kstone, _TENANTS, None).get(tenant_id)
    if not name:
        name = tenant.name
    if not description:
        description = tenant.description
    if enabled is None:
        enabled = tenant.enabled
    updated = getattr(kstone, _TENANTS, None).update(
        tenant_id, name=name, description=description, enabled=enabled
    )

    return {
        value: getattr(updated, value)
        for value in dir(updated)
        if not value.startswith("_")
        and isinstance(getattr(updated, value), (str, dict, bool))
    }


def project_update(
    project_id=None,
    name=None,
    description=None,
    enabled=None,
    profile=None,
    **connection_args,
):
    """
    Update a tenant's information (keystone project-update)
    The following fields may be updated: name, description, enabled.
    Can only update name if targeting by ID

    Overrides keystone tenant_update form api V2.
    For keystone api V3 only.

    .. versionadded:: 2016.11.0

    project_id
        The project id.

    name
        The project name, which must be unique within the owning domain.

    description
        The project description.

    enabled
        Enables or disables the project.

    profile
        Configuration profile - if configuration for multiple openstack accounts required.

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.project_update name=admin enabled=True
        salt '*' keystone.project_update c965f79c4f864eaaa9c3b41904e67082 name=admin email=admin@domain.com
    """
    auth(profile, **connection_args)

    if _OS_IDENTITY_API_VERSION > 2:
        return tenant_update(
            tenant_id=project_id,
            name=name,
            description=description,
            enabled=enabled,
            profile=profile,
            **connection_args,
        )
    else:
        return False


def token_get(profile=None, **connection_args):
    """
    Return the configured tokens (keystone token-get)

    CLI Example:

    .. code-block:: bash

        salt '*' keystone.token_get c965f79c4f864eaaa9c3b41904e67082
    """
    kstone = auth(profile, **connection_args)
    token = kstone.service_catalog.get_token()
    return {
        "id": token["id"],
        "expires": token["expires"],
        "user_id": token["user_id"],
        "tenant_id": token["tenant_id"],
    }


def user_list(profile=None, **connection_args):
    """
    Return a list of available users (keystone user-list)

    CLI Example:

    .. code-block:: bash

        salt '*' keystone.user_list
    """
    kstone = auth(profile, **connection_args)
    ret = {}
    for user in kstone.users.list():
        ret[user.name] = {
            value: getattr(user, value, None)
            for value in dir(user)
            if not value.startswith("_")
            and isinstance(getattr(user, value, None), (str, dict, bool))
        }
        tenant_id = getattr(user, "tenantId", None)
        if tenant_id:
            ret[user.name]["tenant_id"] = tenant_id
    return ret


def user_get(user_id=None, name=None, profile=None, **connection_args):
    """
    Return a specific users (keystone user-get)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.user_get c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.user_get user_id=c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.user_get name=nova
    """
    kstone = auth(profile, **connection_args)
    ret = {}
    if name:
        for user in kstone.users.list():
            if user.name == name:
                user_id = user.id
                break
    if not user_id:
        return {"Error": "Unable to resolve user id"}
    try:
        user = kstone.users.get(user_id)
    except keystoneclient.exceptions.NotFound:
        msg = f"Could not find user '{user_id}'"
        log.error(msg)
        return {"Error": msg}

    ret[user.name] = {
        value: getattr(user, value, None)
        for value in dir(user)
        if not value.startswith("_")
        and isinstance(getattr(user, value, None), (str, dict, bool))
    }

    tenant_id = getattr(user, "tenantId", None)
    if tenant_id:
        ret[user.name]["tenant_id"] = tenant_id
    return ret


def user_create(
    name,
    password,
    email,
    tenant_id=None,
    enabled=True,
    profile=None,
    project_id=None,
    description=None,
    **connection_args,
):
    """
    Create a user (keystone user-create)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.user_create name=jack password=zero email=jack@halloweentown.org \
        tenant_id=a28a7b5a999a455f84b1f5210264375e enabled=True
    """
    kstone = auth(profile, **connection_args)

    if _OS_IDENTITY_API_VERSION > 2:
        if tenant_id and not project_id:
            project_id = tenant_id
        item = kstone.users.create(
            name=name,
            password=password,
            email=email,
            project_id=project_id,
            enabled=enabled,
            description=description,
        )
    else:
        item = kstone.users.create(
            name=name,
            password=password,
            email=email,
            tenant_id=tenant_id,
            enabled=enabled,
        )
    return user_get(item.id, profile=profile, **connection_args)


def user_delete(user_id=None, name=None, profile=None, **connection_args):
    """
    Delete a user (keystone user-delete)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.user_delete c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.user_delete user_id=c965f79c4f864eaaa9c3b41904e67082
        salt '*' keystone.user_delete name=nova
    """
    kstone = auth(profile, **connection_args)
    if name:
        for user in kstone.users.list():
            if user.name == name:
                user_id = user.id
                break
    if not user_id:
        return {"Error": "Unable to resolve user id"}
    kstone.users.delete(user_id)
    ret = f"User ID {user_id} deleted"
    if name:

        ret += f" ({name})"
    return ret


def user_update(
    user_id=None,
    name=None,
    email=None,
    enabled=None,
    tenant=None,
    profile=None,
    project=None,
    description=None,
    **connection_args,
):
    """
    Update a user's information (keystone user-update)
    The following fields may be updated: name, email, enabled, tenant.
    Because the name is one of the fields, a valid user id is required.

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.user_update user_id=c965f79c4f864eaaa9c3b41904e67082 name=newname
        salt '*' keystone.user_update c965f79c4f864eaaa9c3b41904e67082 name=newname email=newemail@domain.com
    """
    kstone = auth(profile, **connection_args)
    if not user_id:
        for user in kstone.users.list():
            if user.name == name:
                user_id = user.id
                break
        if not user_id:
            return {"Error": "Unable to resolve user id"}
    user = kstone.users.get(user_id)
    # Keep previous settings if not updating them
    if not name:
        name = user.name
    if not email:
        email = user.email
    if enabled is None:
        enabled = user.enabled

    if _OS_IDENTITY_API_VERSION > 2:
        if description is None:
            description = getattr(user, "description", None)
        else:
            description = str(description)

        project_id = None
        if project:
            for proj in kstone.projects.list():
                if proj.name == project:
                    project_id = proj.id
                    break
        if not project_id:
            project_id = getattr(user, "project_id", None)

        kstone.users.update(
            user=user_id,
            name=name,
            email=email,
            enabled=enabled,
            description=description,
            project_id=project_id,
        )
    else:
        kstone.users.update(user=user_id, name=name, email=email, enabled=enabled)

        tenant_id = None
        if tenant:
            for tnt in kstone.tenants.list():
                if tnt.name == tenant:
                    tenant_id = tnt.id
                    break
            if tenant_id:
                kstone.users.update_tenant(user_id, tenant_id)

    ret = f"Info updated for user ID {user_id}"
    return ret


def user_verify_password(
    user_id=None, name=None, password=None, profile=None, **connection_args
):
    """
    Verify a user's password

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.user_verify_password name=test password=foobar
        salt '*' keystone.user_verify_password user_id=c965f79c4f864eaaa9c3b41904e67082 password=foobar
    """
    kstone = auth(profile, **connection_args)
    if "connection_endpoint" in connection_args:
        auth_url = connection_args.get("connection_endpoint")
    else:
        if _OS_IDENTITY_API_VERSION > 2:
            auth_url = __salt__["config.option"](
                "keystone.endpoint", "http://127.0.0.1:35357/v3"
            )
        else:
            auth_url = __salt__["config.option"](
                "keystone.endpoint", "http://127.0.0.1:35357/v2.0"
            )

    if user_id:
        for user in kstone.users.list():
            if user.id == user_id:
                name = user.name
                break
    if not name:
        return {"Error": "Unable to resolve user name"}
    kwargs = {"username": name, "password": password, "auth_url": auth_url}
    try:
        if _OS_IDENTITY_API_VERSION > 2:
            client3.Client(**kwargs)
        else:
            client.Client(**kwargs)
    except (
        keystoneclient.exceptions.Unauthorized,
        keystoneclient.exceptions.AuthorizationFailure,
    ):
        return False
    return True


def user_password_update(
    user_id=None, name=None, password=None, profile=None, **connection_args
):
    """
    Update a user's password (keystone user-password-update)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.user_password_update c965f79c4f864eaaa9c3b41904e67082 password=12345
        salt '*' keystone.user_password_update user_id=c965f79c4f864eaaa9c3b41904e67082 password=12345
        salt '*' keystone.user_password_update name=nova password=12345
    """
    kstone = auth(profile, **connection_args)
    if name:
        for user in kstone.users.list():
            if user.name == name:
                user_id = user.id
                break
    if not user_id:
        return {"Error": "Unable to resolve user id"}

    if _OS_IDENTITY_API_VERSION > 2:
        kstone.users.update(user=user_id, password=password)
    else:
        kstone.users.update_password(user=user_id, password=password)
    ret = f"Password updated for user ID {user_id}"
    if name:
        ret += f" ({name})"
    return ret


def user_role_add(
    user_id=None,
    user=None,
    tenant_id=None,
    tenant=None,
    role_id=None,
    role=None,
    profile=None,
    project_id=None,
    project_name=None,
    **connection_args,
):
    """
    Add role for user in tenant (keystone user-role-add)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.user_role_add \
user_id=298ce377245c4ec9b70e1c639c89e654 \
tenant_id=7167a092ece84bae8cead4bf9d15bb3b \
role_id=ce377245c4ec9b70e1c639c89e8cead4
        salt '*' keystone.user_role_add user=admin tenant=admin role=admin
    """
    kstone = auth(profile, **connection_args)

    if project_id and not tenant_id:
        tenant_id = project_id
    elif project_name and not tenant:
        tenant = project_name

    if user:
        user_id = user_get(name=user, profile=profile, **connection_args)[user].get(
            "id"
        )
    else:
        user = next(iter(user_get(user_id, profile=profile, **connection_args).keys()))[
            "name"
        ]
    if not user_id:
        return {"Error": "Unable to resolve user id"}

    if tenant:
        tenant_id = tenant_get(name=tenant, profile=profile, **connection_args)[
            tenant
        ].get("id")
    else:
        tenant = next(
            iter(tenant_get(tenant_id, profile=profile, **connection_args).keys())
        )["name"]
    if not tenant_id:
        return {"Error": "Unable to resolve tenant/project id"}

    if role:
        role_id = role_get(name=role, profile=profile, **connection_args)[role]["id"]
    else:
        role = next(iter(role_get(role_id, profile=profile, **connection_args).keys()))[
            "name"
        ]
    if not role_id:
        return {"Error": "Unable to resolve role id"}

    if _OS_IDENTITY_API_VERSION > 2:
        kstone.roles.grant(role_id, user=user_id, project=tenant_id)
    else:
        kstone.roles.add_user_role(user_id, role_id, tenant_id)
    ret_msg = '"{0}" role added for user "{1}" for "{2}" tenant/project'
    return ret_msg.format(role, user, tenant)


def user_role_remove(
    user_id=None,
    user=None,
    tenant_id=None,
    tenant=None,
    role_id=None,
    role=None,
    profile=None,
    project_id=None,
    project_name=None,
    **connection_args,
):
    """
    Remove role for user in tenant (keystone user-role-remove)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.user_role_remove \
user_id=298ce377245c4ec9b70e1c639c89e654 \
tenant_id=7167a092ece84bae8cead4bf9d15bb3b \
role_id=ce377245c4ec9b70e1c639c89e8cead4
        salt '*' keystone.user_role_remove user=admin tenant=admin role=admin
    """
    kstone = auth(profile, **connection_args)

    if project_id and not tenant_id:
        tenant_id = project_id
    elif project_name and not tenant:
        tenant = project_name

    if user:
        user_id = user_get(name=user, profile=profile, **connection_args)[user].get(
            "id"
        )
    else:
        user = next(iter(user_get(user_id, profile=profile, **connection_args).keys()))[
            "name"
        ]
    if not user_id:
        return {"Error": "Unable to resolve user id"}

    if tenant:
        tenant_id = tenant_get(name=tenant, profile=profile, **connection_args)[
            tenant
        ].get("id")
    else:
        tenant = next(
            iter(tenant_get(tenant_id, profile=profile, **connection_args).keys())
        )["name"]
    if not tenant_id:
        return {"Error": "Unable to resolve tenant/project id"}

    if role:
        role_id = role_get(name=role, profile=profile, **connection_args)[role]["id"]
    else:
        role = next(iter(role_get(role_id).keys()))["name"]
    if not role_id:
        return {"Error": "Unable to resolve role id"}

    if _OS_IDENTITY_API_VERSION > 2:
        kstone.roles.revoke(role_id, user=user_id, project=tenant_id)
    else:
        kstone.roles.remove_user_role(user_id, role_id, tenant_id)
    ret_msg = '"{0}" role removed for user "{1}" under "{2}" tenant'
    return ret_msg.format(role, user, tenant)


def user_role_list(
    user_id=None,
    tenant_id=None,
    user_name=None,
    tenant_name=None,
    profile=None,
    project_id=None,
    project_name=None,
    **connection_args,
):
    """
    Return a list of available user_roles (keystone user-roles-list)

    CLI Examples:

    .. code-block:: bash

        salt '*' keystone.user_role_list \
user_id=298ce377245c4ec9b70e1c639c89e654 \
tenant_id=7167a092ece84bae8cead4bf9d15bb3b
        salt '*' keystone.user_role_list user_name=admin tenant_name=admin
    """
    kstone = auth(profile, **connection_args)
    ret = {}

    if project_id and not tenant_id:
        tenant_id = project_id
    elif project_name and not tenant_name:
        tenant_name = project_name

    if user_name:
        for user in kstone.users.list():
            if user.name == user_name:
                user_id = user.id
                break
    if tenant_name:
        for tenant in getattr(kstone, _TENANTS, None).list():
            if tenant.name == tenant_name:
                tenant_id = tenant.id
                break
    if not user_id or not tenant_id:
        return {"Error": "Unable to resolve user or tenant/project id"}

    if _OS_IDENTITY_API_VERSION > 2:
        for role in kstone.roles.list(user=user_id, project=tenant_id):
            ret[role.name] = {
                value: getattr(role, value)
                for value in dir(role)
                if not value.startswith("_")
                and isinstance(getattr(role, value), (str, dict, bool))
            }
    else:
        for role in kstone.roles.roles_for_user(user=user_id, tenant=tenant_id):
            ret[role.name] = {
                "id": role.id,
                "name": role.name,
                "user_id": user_id,
                "tenant_id": tenant_id,
            }
    return ret


def _item_list(profile=None, **connection_args):
    """
    Template for writing list functions
    Return a list of available items (keystone items-list)

    CLI Example:

    .. code-block:: bash

        salt '*' keystone.item_list
    """
    kstone = auth(profile, **connection_args)
    ret = []
    for item in kstone.items.list():
        ret.append(item.__dict__)
        # ret[item.name] = {
        #         'id': item.id,
        #         'name': item.name,
        #         }
    return ret

    # The following is a list of functions that need to be incorporated in the
    # keystone module. This list should be updated as functions are added.
    #
    # endpoint-create     Create a new endpoint associated with a service
    # endpoint-delete     Delete a service endpoint
    # discover            Discover Keystone servers and show authentication
    #                     protocols and
    # bootstrap           Grants a new role to a new user on a new tenant, after
    #                     creating each.
