# -*- coding: utf-8 -*-
'''
Copyright 2013 Google Inc. All Rights Reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Google Compute Engine Module
============================

The Google Compute Engine module.  This module interfaces with Google Compute
Engine.  To authenticate to GCE, you will need to create a Service Account.

Setting up Service Account Authentication:
  - Go to the Cloud Console at: https://cloud.google.com/console.
  - Create or navigate to your desired Project.
  - Make sure Google Compute Engine service is enabled under the Services
    section.
  - Go to "APIs and auth" and then the "Registered apps" section.
  - Click the "REGISTER APP" button and give it a meaningful name.
  - Select "Web Application" and click "Register".
  - Select Certificate, then "Generate Certificate"
  - Copy the Email Address for inclusion in your /etc/salt/cloud file
    in the 'service_account_email_address' setting.
  - Download the Private Key
  - The key that you download is a PKCS12 key.  It needs to be converted to
    the PEM format.
  - Convert the key using OpenSSL (the default password is 'notasecret'):
    C{openssl pkcs12 -in PRIVKEY.p12 -passin pass:notasecret \
    -nodes -nocerts | openssl rsa -out ~/PRIVKEY.pem}
  - Add the full path name of the converted private key to your
    /etc/salt/cloud file as 'service_account_private_key' setting.
  - Consider using a more secure location for your private key.

Supported commands:
  # Create a few instances fro profile_name in /etc/salt/cloud.profiles
  - salt-cloud -p profile_name inst1 inst2 inst3
  # Delete an instance
  - salt-cloud -d inst1
  # Look up data on an instance
  - salt-cloud -a show_instance inst2
  # List available locations (aka 'zones') for provider 'gce'
  - salt-cloud --list-locations gce
  # List available instance sizes (aka 'machine types') for provider 'gce'
  - salt-cloud --list-sizes gce
  # List available images for provider 'gce'
  - salt-cloud --list-images gce

.. code-block:: yaml

    my-gce-config:
      # The Google Cloud Platform Project ID
      project: google.com:erjohnso
      # The Service ACcount client ID
      service_account_email_address: 1234567890@developer.gserviceaccount.com
      # The location of the private key (PEM format)
      service_account_private_key: /home/erjohnso/PRIVKEY.pem
      provider: gce

:maintainer: Eric Johnson <erjohnso@google.com>
:maturity: new
:depends: libcloud >= 0.14.0-beta3
:depends: pycrypto >= 2.1
'''
# custom UA
_UA_PRODUCT = 'salt-cloud'
_UA_VERSION = '0.1.0'

# The import section is mostly libcloud boilerplate
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver

# Import python libs
import copy
import pprint
import logging
import os
import stat
from ast import literal_eval

# Import salt libs
from salt.utils import namespaced_function

# Import saltcloud libs
import salt.utils.cloud
import salt.config as config
from salt.cloud.libcloudfuncs import *  # pylint: disable=W0401,W0614
from salt.cloud.exceptions import (
    SaltCloudException,
    SaltCloudSystemExit,
)


# pylint: disable=C0103,E0602,E0102
# Get logging started
log = logging.getLogger(__name__)

# Redirect GCE functions to this module namespace
avail_locations = namespaced_function(avail_locations, globals())
script = namespaced_function(script, globals())
destroy = namespaced_function(destroy, globals())
list_nodes = namespaced_function(list_nodes, globals())
list_nodes_full = namespaced_function(list_nodes_full, globals())
list_nodes_select = namespaced_function(list_nodes_select, globals())


# Only load in this module if the GCE configurations are in place
def __virtual__():
    '''
    Set up the libcloud functions and check for GCE configurations.
    '''
    if get_configured_provider() is False:
        log.debug(
            'There is no GCE cloud provider configuration available. Not '
            'loading module.'
        )
        return False

    for provider, details in __opts__['providers'].iteritems():
        if 'provider' not in details or details['provider'] != 'gce':
            continue

        pathname = os.path.expanduser(details['service_account_private_key'])
        if not os.path.exists(pathname):
            raise SaltCloudException(
                'The GCE service account private key {0!r} used in '
                'the {0!r} provider configuration does not exist\n'.format(
                    details['service_account_private_key'], provider
                )
            )
        keymode = str(
            oct(stat.S_IMODE(os.stat(pathname).st_mode))
        )
        if keymode not in ('0400', '0600'):
            raise SaltCloudException(
                'The GCE service account private key {0!r} used in '
                'the {0!r} provider configuration needs to be set to '
                'mode 0400 or 0600\n'.format(
                    details['service_account_private_key'], provider
                )
            )

    log.debug('Loading GCE cloud module')
    return True


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or 'gce',
        ('project',
         'service_account_email_address',
         'service_account_private_key')
    )


def get_conn():
    '''
    Return a conn object for the passed VM data
    '''
    driver = get_driver(Provider.GCE)
    provider = get_configured_provider()
    project = config.get_cloud_config_value('project', provider, __opts__)
    email = config.get_cloud_config_value('service_account_email_address',
            provider, __opts__)
    private_key = config.get_cloud_config_value('service_account_private_key',
            provider, __opts__)
    gce = driver(email, private_key, project=project)
    gce.connection.user_agent_append('{0}/{1}'.format(_UA_PRODUCT,
                                                      _UA_VERSION))
    return gce


def _expand_node(node):
    '''
    Convert the libcloud Node object into something more serializable.
    '''
    ret = {}
    ret.update(node.__dict__)
    zone = ret['extra']['zone']
    ret['extra']['zone'] = {}
    ret['extra']['zone'].update(zone.__dict__)
    return ret


def show_instance(vm_name, call=None):
    '''
    Show the details of the existing instance.
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The show_instance action must be called with -a or --action.'
        )
    conn = get_conn()
    return _expand_node(conn.ex_get_node(vm_name))


def avail_sizes(conn=None):
    '''
    Return a dict of available instances sizes (a.k.a machine types) and
    convert them to something more serializable.
    '''
    if not conn:
        conn = get_conn()
    raw_sizes = conn.list_sizes('all')  # get *all* the machine types!
    sizes = []
    for size in raw_sizes:
        zone = size.extra['zone']
        size.extra['zone'] = {}
        size.extra['zone'].update(zone.__dict__)
        mtype = {}
        mtype.update(size.__dict__)
        sizes.append(mtype)
    return sizes


def avail_images(conn=None):
    '''
    Return a dict of all available VM images on the cloud provider with
    relevant data

    Note that for GCE, there are custom images within the project, but the
    generic images are in other projects.  This returns a dict of images in
    the project plus images in 'debian-cloud' and 'centos-cloud' (If there is
    overlap in names, the one in the current project is used.)
    '''
    if not conn:
        conn = get_conn()

    project_images = conn.list_images()
    debian_images = conn.list_images('debian-cloud')
    centos_images = conn.list_images('centos-cloud')

    all_images = debian_images + centos_images + project_images

    ret = {}
    for img in all_images:
        ret[img.name] = {}
        for attr in dir(img):
            if attr.startswith('_'):
                continue
            ret[img.name][attr] = getattr(img, attr)
    return ret


def __get_image(conn, vm_):
    '''
    The get_image for GCE allows partial name matching and returns a
    libcloud object.
    '''
    img = config.get_cloud_config_value(
        'image', vm_, __opts__, default='debian-7', search_global=False)
    return conn.ex_get_image(img)


def __get_location(conn, vm_):
    '''
    Need to override libcloud to find the zone.
    '''
    location = config.get_cloud_config_value(
        'location', vm_, __opts__)
    return conn.ex_get_zone(location)


def __get_size(conn, vm_):
    '''
    Need to override libcloud to find the machine type in the proper zone.
    '''
    size = config.get_cloud_config_value(
        'size', vm_, __opts__, default='n1-standard-1', search_global=False)
    return conn.ex_get_size(size, __get_location(conn, vm_))


def __get_tags(vm_):
    '''
    Get configured tags.
    '''
    t = config.get_cloud_config_value(
        'tags', vm_, __opts__,
        default='[]', search_global=False)
    # Consider warning the user that the tags in the cloud profile
    # could not be interpreted, bad formatting?
    try:
        tags = literal_eval(t)
    except Exception:  # pylint: disable=W0703
        tags = None
    if not tags or not isinstance(tags, list):
        tags = None
    return tags


def __get_metadata(vm_):
    '''
    Get configured metadata and add 'salt-cloud-profile'.
    '''
    md = config.get_cloud_config_value(
        'metadata', vm_, __opts__,
        default='{}', search_global=False)
    # Consider warning the user that the metadata in the cloud profile
    # could not be interpreted, bad formatting?
    try:
        metadata = literal_eval(md)
    except Exception:  # pylint: disable=W0703
        metadata = None
    if not metadata or not isinstance(metadata, dict):
        metadata = {'items': [{
            'key': 'salt-cloud-profile',
            'value': vm_['profile']
        }]}
    else:
        metadata['salt-cloud-profile'] = vm_['profile']
        items = []
        for k, v in metadata.items():
            items.append({'key': k, 'value': v})
        metadata = {'items': items}
    return metadata


def __get_network(conn, vm_):
    '''
    Return a GCE libcloud network object with matching name
    '''
    network = config.get_cloud_config_value(
        'network', vm_, __opts__,
        default='default', search_global=False)
    return conn.ex_get_network(network)


def __get_pd(vm_):
    '''
    Return boolean setting for using a persistent disk
    '''
    return config.get_cloud_config_value(
        'use_persistent_disk', vm_, __opts__,
        default=True, search_global=False)


def __get_ssh_credentials(vm_):
    '''
    Get configured SSH credentials.
    '''
    ssh_user = config.get_cloud_config_value(
        'ssh_username', vm_, __opts__, default=os.getenv('USER'))
    ssh_key = config.get_cloud_config_value(
        'ssh_keyfile', vm_, __opts__,
        default=os.getenv('HOME') + '/.ssh/google_compute_engine')
    return ssh_user, ssh_key


def reboot(vm_name, call=None):
    '''
    Call GCE 'reset' on the instance.
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The reboot action must be called with -a or --action.'
        )
    conn = get_conn()
    return conn.reboot_node(
        conn.ex_get_node(vm_name)
    )


def destroy(vm_name, call=None):
    '''
    Call 'destroy' on the instance.  Can be called with "-a destroy" or -d
    '''
    if call and call != 'action':
        raise SaltCloudSystemExit(
            'The destroy action must be called with -d or "-a destroy".'
        )

    conn = get_conn()

    try:
        node = conn.ex_get_node(vm_name)
    except Exception as exc:  # pylint: disable=W0703
        log.error(
            'Could not locate instance {0}\n\n'
            'The following exception was thrown by libcloud when trying to '
            'run the initial deployment: \n{1}'.format(
                vm_name, exc.message
            ),
            exc_info=log.isEnabledFor(logging.DEBUG)
        )
        raise SaltCloudSystemExit(
            'Could not find instance {0}.'.format(vm_name)
        )

    salt.utils.cloud.fire_event(
        'event',
        'destroying instance',
        'salt/cloud/{0}/destroying'.format(vm_name),
        {'name': vm_name},
    )

    # Use the instance metadata to see if it's salt cloud profile was
    # preserved during instance create.  If so, use the profile value
    # to see if the 'delete_boot_pd' value is set to delete the disk
    # along with the instance.
    profile = None
    if node.extra['metadata'] and 'items' in node.extra['metadata']:
        for md in node.extra['metadata']['items']:
            if md['key'] == 'salt-cloud-profile':
                profile = md['value']
    vm_ = get_configured_provider()
    delete_boot_pd = False
    if profile is not None and profile in vm_['profiles']:
        if 'delete_boot_pd' in vm_['profiles'][profile]:
            delete_boot_pd = vm_['profiles'][profile]['delete_boot_pd']

    try:
        inst_deleted = conn.destroy_node(node)
    except Exception as exc:  # pylint: disable=W0703
        log.error(
            'Could not destroy instance {0}\n\n'
            'The following exception was thrown by libcloud when trying to '
            'run the initial deployment: \n{1}'.format(
                vm_name, exc.message
            ),
            exc_info=log.isEnabledFor(logging.DEBUG)
        )
        raise SaltCloudSystemExit(
            'Could not destroy instance {0}.'.format(vm_name)
        )
    if delete_boot_pd:
        salt.utils.cloud.fire_event(
            'event',
            'destroying persistent disk',
            'salt/cloud/{0}/destroying-disk'.format(vm_name),
            {'name': vm_name},
        )
        try:
            conn.destroy_volume(conn.ex_get_volume(vm_name))
        except Exception as exc:  # pylint: disable=W0703
            # Note that we don't raise a SaltCloudSystemExit here in order
            # to allow completion of instance deletion.  Just log the error
            # and keep going.
            log.error(
                'Could not destroy disk {0}\n\n'
                'The following exception was thrown by libcloud when trying '
                'to run the initial deployment: \n{1}'.format(
                    vm_name, exc.message
                ),
                exc_info=log.isEnabledFor(logging.DEBUG)
            )
        salt.utils.cloud.fire_event(
            'event',
            'destroyed persistent disk',
            'salt/cloud/{0}/destroyed-disk'.format(vm_name),
            {'name': vm_name},
        )

    salt.utils.cloud.fire_event(
        'event',
        'destroyed instance',
        'salt/cloud/{0}/destroyed'.format(vm_name),
        {'name': vm_name},
    )

    return inst_deleted


def create(vm_=None, call=None):
    '''
    Create a single GCE instance from a data dict.
    '''
    if call:
        raise SaltCloudSystemExit(
            'You cannot create an instance with -a or -f.'
        )

    salt.utils.cloud.fire_event(
        'event',
        'starting create',
        'salt/cloud/{0}/creating'.format(vm_['name']),
        {
            'name': vm_['name'],
            'profile': vm_['profile'],
            'provider': vm_['provider'],
        },
    )

    conn = get_conn()

    kwargs = {
        'name': vm_['name'],
        'size': __get_size(conn, vm_),
        'image': __get_image(conn, vm_),
        'location': __get_location(conn, vm_),
        'ex_network': __get_network(conn, vm_),
        'ex_tags': __get_tags(vm_),
        'ex_metadata': __get_metadata(vm_),
        'ex_persistent_disk': __get_pd(vm_),
    }

    log.info('Creating GCE instance {0} in {1}'.format(vm_['name'],
        kwargs['location'].name)
    )
    log.debug('Create instance kwargs {0}'.format(str(kwargs)))

    salt.utils.cloud.fire_event(
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(vm_['name']),
        {
            'name': vm_['name'],
            'location': kwargs['location'].name,
            'size': kwargs['size'].name,
            'image': kwargs['image'].name,
        },
    )

    try:
        node_data = conn.create_node(**kwargs)  # pylint: disable=W0142
    except Exception as exc:  # pylint: disable=W0703
        log.error(
            'Error creating {0} on GCE\n\n'
            'The following exception was thrown by libcloud when trying to '
            'run the initial deployment: \n{1}'.format(
                vm_['name'], exc.message
            ),
            exc_info=log.isEnabledFor(logging.DEBUG)
        )
        return False

    node_dict = _expand_node(node_data)

    if config.get_cloud_config_value('deploy', vm_, __opts__) is True:
        deploy_script = script(vm_)
        ssh_user, ssh_key = __get_ssh_credentials(vm_)
        deploy_kwargs = {
            'host': node_data.public_ips[0],
            'username': ssh_user,
            'key_filename': ssh_key,
            'script': deploy_script.script,
            'name': vm_['name'],
            'tmp_dir': config.get_cloud_config_value(
                'tmp_dir', vm_, __opts__, default='/tmp/.saltcloud'
            ),
            'deploy_command': config.get_cloud_config_value(
                'deploy_command', vm_, __opts__,
                default='/tmp/.saltcloud/deploy.sh',
            ),
            'start_action': __opts__['start_action'],
            'sock_dir': __opts__['sock_dir'],
            'conf_file': __opts__['conf_file'],
            'minion_pem': vm_['priv_key'],
            'minion_pub': vm_['pub_key'],
            'keep_tmp': __opts__['keep_tmp'],
            'preseed_minion_keys': vm_.get('preseed_minion_keys', None),
            'sudo': config.get_cloud_config_value(
                'sudo', vm_, __opts__, default=(ssh_user != 'root')
            ),
            'sudo_password': config.get_cloud_config_value(
                'sudo_password', vm_, __opts__, default=None
            ),
            'tty': config.get_cloud_config_value(
                'tty', vm_, __opts__, default=(ssh_user != 'root')
            ),
            'display_ssh_output': config.get_cloud_config_value(
                'display_ssh_output', vm_, __opts__, default=True
            ),
            'script_args': config.get_cloud_config_value(
                'script_args', vm_, __opts__
            ),
            'script_env': config.get_cloud_config_value(
                'script_env', vm_, __opts__
            ),
            'minion_conf': salt.utils.cloud.minion_config(__opts__, vm_)
        }

        # Deploy salt-master files, if necessary
        if config.get_cloud_config_value('make_master', vm_, __opts__) is True:
            deploy_kwargs['make_master'] = True
            deploy_kwargs['master_pub'] = vm_['master_pub']
            deploy_kwargs['master_pem'] = vm_['master_pem']
            master_conf = salt.utils.cloud.master_config(__opts__, vm_)
            deploy_kwargs['master_conf'] = master_conf

            if master_conf.get('syndic_master', None):
                deploy_kwargs['make_syndic'] = True

        deploy_kwargs['make_minion'] = config.get_cloud_config_value(
            'make_minion', vm_, __opts__, default=True
        )

        # Store what was used to the deploy the VM
        event_kwargs = copy.deepcopy(deploy_kwargs)
        del event_kwargs['minion_pem']
        del event_kwargs['minion_pub']
        del event_kwargs['sudo_password']
        if 'password' in event_kwargs:
            del event_kwargs['password']
        node_dict['deploy_kwargs'] = event_kwargs

        salt.utils.cloud.fire_event(
            'event',
            'executing deploy script',
            'salt/cloud/{0}/deploying'.format(vm_['name']),
            {'kwargs': deploy_kwargs},
        )

        # pylint: disable=W0142
        deployed = salt.utils.cloud.deploy_script(**deploy_kwargs)
        if deployed:
            log.info('Salt installed on {0}'.format(vm_['name']))
        else:
            log.error(
                'Failed to start Salt on Cloud VM {0}'.format(
                    vm_['name']
                )
            )

    log.info('Created Cloud VM {0[name]!r}'.format(vm_))
    log.debug(
        '{0[name]!r} VM creation details:\n{1}'.format(
            vm_, pprint.pformat(node_dict)
        )
    )

    salt.utils.cloud.fire_event(
        'event',
        'created instance',
        'salt/cloud/{0}/created'.format(vm_['name']),
        {
            'name': vm_['name'],
            'profile': vm_['profile'],
            'provider': vm_['provider'],
        },
    )

    return node_dict
