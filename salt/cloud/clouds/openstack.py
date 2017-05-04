# -*- coding: utf-8 -*-
'''
'''

# Import Python Libs
import logging

# Import Salt Libs
import salt.config

# Import 3rd-Party Libs
try:
    import shade.openstackcloud
    import os_client_config
    HAS_SHADE = True
except ImportError:
    HAS_SHADE = False

log = logging.getLogger(__name__)

__virtualname__ = 'openstack'


def __virtual__():
    '''
    Check for Openstack dependencies
    '''
    if get_configured_provider() is False:
        return False

    if get_dependencies() is False:
        return False

    return __virtualname__


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return salt.config.is_provider_configured(
        __opts__,
        __active_provider_name__ or __virtualname__,
        ('auth', 'region_name')
    ) or salt.config.is_provider_configured(
        __opts__,
        __active_provider_name__ or __virtualname__,
        ('cloud', 'region_name')
    )


def get_dependencies():
    '''
    Warn if dependencies aren't met.
    '''
    deps = {
        'shade': HAS_SHADE,
        'os_client_config': HAS_SHADE,
    }
    return salt.config.check_driver_dependencies(
        __virtualname__,
        deps
    )


def get_conn():
    '''
    Return a conn object for the passed VM data
    '''
    if __active_provider_name__ in __context__:
        return __context[__active_provider_name__]
    vm_ = get_configured_provider()
    profile = vm_.pop('profile', None)
    if profile is not None:
        vm_ = __utils__['dictupdate.update'](os_client_config.vendors.get_profile(profile), vm_)
    conn = shade.openstackcloud.OpenStackCloud(cloud_config=None, **vm_)
    if __active_provider_name__ is not None:
        __context__[__active_provider_name__] = conn
    return conn


def list_nodes(conn=None, call=None):  # pylint: disable=unused-argument
    '''
    List VMs on this Openstack account
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes function must be called with -f or --function.'
        )

    return get_conn().list_servers()


def list_nodes_min(conn=None, call=None):  # pylint: disable=unused-argument
    '''
    List VMs on this Openstack account
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_min function must be called with -f or --function.'
        )

    return get_conn().list_servers(bare=True)


def list_nodes_full(conn=None, call=None):  # pylint: disable=unused-argument
    '''
    List VMs on this Openstack account
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_full function must be called with -f or --function.'
        )

    return get_conn().list_servers(detailed=True)


def list_nodes_select(conn=None, call=None):  # pylint: disable=unused-argument
    '''
    Return a list of the VMs that are on the provider, with select fields
    '''
    return __utils__['cloud.list_nodes_select'](
        list_nodes(conn, 'function'), __opts__['query.selection'], call,
    )


def show_instance(name, call=None):
    '''
    Get VM on this Openstack account
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The show_instance function must be called with -f or --function.'
        )

    return get_conn().get_server(name, bare=True)


def avail_images(conn=None, call=None):  # pylint: disable=unused-argument
    '''
    List available images for Openstack
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_images function must be called with '
            '-f or --function, or with the --list-images option'
        )

    return get_conn().list_images()


def avail_sizes(conn=None, call=None):  # pylint: disable=unused-argument
    '''
    List available sizes for Openstack
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_sizes function must be called with '
            '-f or --function, or with the --list-images option'
        )

    return get_conn().list_flavors()


def list_networks(call=None, kwargs=None):  # pylint: disable=unused-argument
    '''
    List virtual networks
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_networks function must be called with '
            '-f or --function, or with the --list-sizes option'
        )
    return get_conn().list_networks()
