# -*- coding: utf-8 -*-
'''
Azure (ARM) Utilities

.. versionadded:: Fluorine

:maintainer: <devops@decisionlab.io>
:maturity: new
:depends:
    * `Microsoft Azure SDK for Python <https://pypi.python.org/pypi/azure>`_ >= 2.0rc6
    * `AutoRest swagger generator Python client runtime (Azure-specific module) <https://pypi.python.org/pypi/msrestazure>`_ >= 0.4
:platform: linux

'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import importlib
import logging
import sys

# Import Salt libs
import salt.config
import salt.loader
import salt.version
from salt.exceptions import (
    SaltInvocationError, SaltSystemExit
)

# Import third party libs
try:
    from azure.common.credentials import (
        UserPassCredentials,
        ServicePrincipalCredentials,
    )
    from msrestazure.azure_cloud import (
        MetadataEndpointError,
        get_cloud_from_metadata_endpoint,
    )
    from msrestazure.azure_exceptions import CloudError
    HAS_AZURE = True
except ImportError:
    HAS_AZURE = False

__opts__ = salt.config.minion_config('/etc/salt/minion')
__salt__ = salt.loader.minion_mods(__opts__)

log = logging.getLogger(__name__)


def __virtual__():
    if not HAS_AZURE:
        return False
    else:
        return True


def _determine_auth(**kwargs):
    '''
    Acquire Azure ARM Credentials
    '''
    if 'profile' in kwargs.keys():
        azure_credentials = __salt__['config.option'](kwargs['profile'])
        kwargs.update(azure_credentials)

    service_principal_creds_kwargs = ['client_id', 'secret', 'tenant']
    user_pass_creds_kwargs = ['username', 'password']

    try:
        if kwargs.get('cloud_environment') and kwargs.get('cloud_environment').startswith('http'):
            cloud_env = get_cloud_from_metadata_endpoint(kwargs['cloud_environment'])
        else:
            cloud_env_module = importlib.import_module('msrestazure.azure_cloud')
            cloud_env = getattr(cloud_env_module, kwargs.get('cloud_environment', 'AZURE_PUBLIC_CLOUD'))
    except (AttributeError, ImportError, MetadataEndpointError):
        raise sys.exit('The Azure cloud environment {0} is not available.'.format(kwargs['cloud_environment']))

    if set(service_principal_creds_kwargs).issubset(kwargs):
        credentials = ServicePrincipalCredentials(kwargs['client_id'],
                                                  kwargs['secret'],
                                                  tenant=kwargs['tenant'],
                                                  cloud_environment=cloud_env)
    elif set(user_pass_creds_kwargs).issubset(kwargs):
        credentials = UserPassCredentials(kwargs['username'],
                                          kwargs['password'],
                                          cloud_environment=cloud_env)
    else:
        raise SaltInvocationError(
            'Unable to do determine credentials. '
            'A subscription_id with username and password, '
            'or client_id, secret, and tenant or a profile with the '
            'required parameters populated'
        )

    if 'subscription_id' not in kwargs.keys():
        raise SaltInvocationError(
            'A subscription_id must be specified'
        )

    subscription_id = kwargs['subscription_id']

    return credentials, subscription_id, cloud_env


def get_client(client_type, **kwargs):
    '''
    Dynamically load the selected client and return a management client object
    '''
    client_map = {'compute': 'ComputeManagement',
                  'storage': 'StorageManagement',
                  'network': 'NetworkManagement',
                  'resource': 'ResourceManagement',
                  'subscription': 'Subscription',
                  'web': 'WebSiteManagement'}

    if client_type not in client_map.keys():
        raise SaltSystemExit(
            'The Azure ARM client_type {0} specified can not be found.'.format(
                client_type)
        )

    map_value = client_map[client_type]

    if client_type == 'subscription':
        module_name = 'resource'
    else:
        module_name = client_type

    try:
        client_module = importlib.import_module('azure.mgmt.'+module_name)
        # pylint: disable=invalid-name
        Client = getattr(client_module,
                         '{0}Client'.format(map_value))
    except ImportError:
        raise sys.exit(
                  'The azure {0} client is not available.'.format(client_type)
        )

    credentials, subscription_id, cloud_env = _determine_auth(**kwargs)

    if client_type == 'subscription':
        client = Client(
            credentials=credentials,
            base_url=cloud_env.endpoints.resource_manager,
        )
    else:
        client = Client(
            credentials=credentials,
            subscription_id=subscription_id,
            base_url=cloud_env.endpoints.resource_manager,
        )

    client.config.add_user_agent('Salt/{0}'.format(salt.version.__version__))

    return client


def log_cloud_error(client, message):
    '''
    Log an azurearm cloud error exception
    '''
    log.error(
         'An AzureARM %s CloudError has occurred: %s',
         client.capitalize(),
         message
    )

    return


def paged_object_to_list(paged_object):
    '''
    Extract all pages within a paged object as a list of dictionaries
    '''
    paged_return = []
    while True:
        try:
            page = next(paged_object)
            paged_return.append(page.as_dict())
        except CloudError:
            raise
        except StopIteration:
            break

    return paged_return
