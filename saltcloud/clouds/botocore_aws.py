'''
The AWS Cloud Module
====================

The AWS cloud module is used to interact with the Amazon Web Services system.

To use the AWS cloud module the following configuration parameters need to be
set in the main cloud config:

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

'''

# Import python libs
import os
import stat
import logging

# Import saltcloud libs
import saltcloud.utils
from saltcloud.utils import namespaced_function
from saltcloud.libcloudfuncs import *

# Import libcloud_aws, required to latter patch __opts__
from saltcloud.clouds import libcloud_aws
# Import libcloud_aws, storing pre and post locals so we can namespace any
# callable to this module.
PRE_IMPORT_LOCALS_KEYS = locals().copy()
from saltcloud.clouds.libcloud_aws import *
POST_IMPORT_LOCALS_KEYS = locals().copy()

# Import salt libs
from salt.exceptions import SaltException

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
        return False

    # "Patch" the imported libcloud_aws to have the current __opts__
    libcloud_aws.__opts__ = __opts__

    confs = [
        'AWS.id',
        'AWS.key',
        'AWS.keyname',
        'AWS.securitygroup',
        'AWS.private_key',
    ]
    for conf in confs:
        if conf not in __opts__:
            log.warning(
                '{0!r} not found in options. Not loading module.'.format(conf)
            )
            return False

    if not os.path.exists(__opts__['AWS.private_key']):
        raise SaltException(
            'The AWS key file {0} does not exist\n'.format(
                __opts__['AWS.private_key']
            )
        )
    keymode = str(
        oct(stat.S_IMODE(os.stat(__opts__['AWS.private_key']).st_mode))
    )
    if keymode not in ('0400', '0600'):
        raise SaltException(
            'The AWS key file {0} needs to be set to mode 0400 or '
            '0600\n'.format(
                __opts__['AWS.private_key']
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
    list_nodes_select = namespaced_function(list_nodes_select, globals(), (conn,))

    log.debug('Loading AWS botocore cloud module')
    return 'aws'


def enable_term_protect(name):
    '''
    Enable termination protection on a node

    CLI Example::

        salt-cloud -a enable_term_protect mymachine
    '''
    _toggle_term_protect(name, True)


def disable_term_protect(name):
    '''
    Disable termination protection on a node

    CLI Example::

        salt-cloud -a disable_term_protect mymachine
    '''
    _toggle_term_protect(name, False)


def _toggle_term_protect(name, enabled):
    '''
    Toggle termination protection on a node
    '''
    # region is required for all boto queries
    region = get_location(None)

    # init botocore
    session = botocore.session.get_session()
    session.set_credentials(
        access_key=__opts__['AWS.id'],
        secret_key=__opts__['AWS.key'],
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
        log.info(
            'Termination protection successfully {0} on {1}'.format(
                enabled and 'enabled' or 'disabled',
                name
            )
        )
    else:
        log.error(
            'Bad response from AWS: {0}'.format(
                http_response.status_code
            )
        )
