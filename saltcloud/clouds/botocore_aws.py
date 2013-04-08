'''
The AWS Cloud Module
====================

The AWS cloud module is used to interact with the Amazon Web Services system.

To use the AWS cloud module, using the old cloud providers configuration
syntax, the following configuration parameters need to be set in the main cloud
configuration file:

.. code-block:: yaml

    # The AWS API authentication id
    AWS.id: GKTADJGHEIQSXMKKRBJ08H
    # The AWS API authentication key
    AWS.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
    # The ssh keyname to use
    AWS.keyname: default
    # The amazon security group
    AWS.securitygroup: ssh_open
    # The location of the private key which corresponds to the keyname
    AWS.private_key: /root/default.pem


Using the new format, set up the cloud configuration at
 ``/etc/salt/cloud.providers`` or ``/etc/salt/cloud.providers.d/aws.conf``:

.. code-block:: yaml

    my-aws-botocore-config:
      # The AWS API authentication id
      id: GKTADJGHEIQSXMKKRBJ08H
      # The AWS API authentication key
      key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
      # The ssh keyname to use
      keyname: default
      # The amazon security group
      securitygroup: ssh_open
      # The location of the private key which corresponds to the keyname
      private_key: /root/default.pem
      provider: aws

'''

# Import python libs
import os
import stat
import logging

# Import saltcloud libs
import saltcloud.config as config
from saltcloud.utils import namespaced_function
from saltcloud.libcloudfuncs import *
from saltcloud.exceptions import SaltCloudException, SaltCloudSystemExit

# Import libcloud_aws, required to latter patch __opts__
from saltcloud.clouds import libcloud_aws
# Import libcloud_aws, storing pre and post locals so we can namespace any
# callable to this module.
PRE_IMPORT_LOCALS_KEYS = locals().copy()
from saltcloud.clouds.libcloud_aws import *
POST_IMPORT_LOCALS_KEYS = locals().copy()

# Get logging started
log = logging.getLogger(__name__)


# Only load in this module if the AWS configurations are in place
def __virtual__():
    '''
    Set up the libcloud funcstions and check for AWS configs
    '''
    try:
        # Import botocore
        import botocore.session
    except ImportError:
        # Botocore is not available, the Libcloud AWS module will be loaded
        # instead.
        log.debug(
            'The \'botocore\' library is not installed. The libcloud AWS '
            'support will be loaded instead.'
        )
        return False

    # "Patch" the imported libcloud_aws to have the current __opts__
    libcloud_aws.__opts__ = __opts__

    if get_configured_provider() is False:
        log.info(
            'There is no AWS cloud provider configuration available. Not '
            'loading module'
        )
        return False

    for provider, details in __opts__['providers'].iteritems():
        if 'provider' not in details or details['provider'] != 'aws':
            continue

        if not os.path.exists(details['private_key']):
            raise SaltCloudException(
                'The AWS key file {0!r} used in the {1!r} provider '
                'configuration does not exist\n'.format(
                    details['private_key'],
                    provider
                )
            )

        keymode = str(
            oct(stat.S_IMODE(os.stat(details['private_key']).st_mode))
        )
        if keymode not in ('0400', '0600'):
            raise SaltCloudException(
                'The AWS key file {0!r} used in the {1!r} provider '
                'configuration needs to be set to mode 0400 or 0600\n'.format(
                    details['private_key'],
                    provider
                )
            )

    # Let's bring the functions imported from libcloud_aws to the current
    # namespace.
    keysdiff = set(POST_IMPORT_LOCALS_KEYS.keys()).difference(
        PRE_IMPORT_LOCALS_KEYS
    )
    for key in keysdiff:
        if not callable(POST_IMPORT_LOCALS_KEYS[key]):
            continue
        # skip callables that might be exceptions
        if any(['Error' in POST_IMPORT_LOCALS_KEYS[key].__name__,
                'Exception' in POST_IMPORT_LOCALS_KEYS[key].__name__]):
            continue
        globals().update(
            {
                key: namespaced_function(
                    POST_IMPORT_LOCALS_KEYS[key], globals(), ()
                )
            }
        )

    global avail_images, avail_sizes, script, destroy, list_nodes
    global list_nodes_full, list_nodes_select

    # open a connection in a specific region
    conn = get_conn(**{'location': get_location()})

    # Init the libcloud functions
    avail_images = namespaced_function(avail_images, globals(), (conn,))
    avail_sizes = namespaced_function(avail_sizes, globals(), (conn,))
    script = namespaced_function(script, globals(), (conn,))
    list_nodes = namespaced_function(list_nodes, globals(), (conn,))
    list_nodes_full = namespaced_function(list_nodes_full, globals(), (conn,))
    list_nodes_select = namespaced_function(
        list_nodes_select, globals(), (conn,)
    )

    log.debug('Loading AWS botocore cloud module')
    return 'aws'


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        'aws',
        ('id', 'key', 'keyname', 'securitygroup', 'private_key')
    )


def enable_term_protect(name, call=None):
    '''
    Enable termination protection on a node

    CLI Example::

        salt-cloud -a enable_term_protect mymachine
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'This action must be called with -a or --action.'
        )

    return _toggle_term_protect(name, True)


def disable_term_protect(name, call=None):
    '''
    Disable termination protection on a node

    CLI Example::

        salt-cloud -a disable_term_protect mymachine
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'This action must be called with -a or --action.'
        )

    return _toggle_term_protect(name, False)


def _toggle_term_protect(name, enabled):
    '''
    Toggle termination protection on a node
    '''
    # region is required for all boto queries
    region = get_location(None)

    # init botocore
    vm_ = get_configured_provider()
    session = botocore.session.get_session()
    session.set_credentials(
        access_key=config.get_config_value(
            'id', vm_, __opts__, search_global=False
        ),
        secret_key=config.get_config_value(
            'key', vm_, __opts__, search_global=False
        )
    )

    service = session.get_service('ec2')
    endpoint = service.get_endpoint(region)

    # get the instance-id for the supplied node name
    conn = get_conn(location=region)
    node = get_node(conn, name)

    params = {
        'instance_id': node.id,
        'attribute': 'disableApiTermination',
        'value': 'true' if enabled else 'false',
    }

    # get instance information
    operation = service.get_operation('modify-instance-attribute')
    http_response, response_data = operation.call(endpoint, **params)

    if http_response.status_code == 200:
        msg = 'Termination protection successfully {0} on {1}'.format(
            enabled and 'enabled' or 'disabled',
            name
        )
        log.info(msg)
        return msg

    # No proper HTTP response!?
    msg = 'Bad response from AWS: {0}'.format(http_response.status_code)
    log.error(msg)
    return msg
