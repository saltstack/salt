# -*- coding: utf-8 -*-
'''
'''

# Import Python Libs


# Import Salt Libs
import salt.config
import salt.utils.dictupdate

# Import 3rd-Party Libs
try:
    import shade.openstackcloud
    import os_client_config
    HAS_SHADE = True
except ImportError:
    HAS_SHADE = False


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
        vm_ = salt.utils.dictupdate.update(os_client_config.vendors.get_profile(profile), vm_)
    config = os_client_config.OpenStackConfig().get_one_cloud(**vm_)
    conn = shade.openstackcloud.OpenStackCloud(cloud_config=config)
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

    ret = {}
    conn = get_conn()
    return conn.list_servers()
