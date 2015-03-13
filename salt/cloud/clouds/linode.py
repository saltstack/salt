# -*- coding: utf-8 -*-
'''
Linode Cloud Module using Apache Libcloud OR linode-python bindings
===================================================================

The Linode cloud module is used to control access to the Linode VPS system

Use of this module only requires the ``apikey`` parameter.

:depends: linode-python >= 1.1.1
OR
:depends: apache-libcloud >= 0.13.2

.. note::

    The linode-python driver will work with earlier versions of linode-python,
    but it is highly recommended to use a minimum version of 1.1.1. Earlier
    versions leak sensitive information into the debug logs.

Set up the cloud configuration at ``/etc/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/linode.conf``:

.. code-block:: yaml

my-linode-config:
  # Linode account api key
  apikey: JVkbSJDGHSDKUKSDJfhsdklfjgsjdkflhjlsdfffhgdgjkenrtuinv
  provider: linode

When used with linode-python, this provider supports cloning existing Linodes.
To clone, add a profile with a ``clonefrom`` key, and a ``script_args: -C``.

``Clonefrom`` should be the name of the that is the source for the clone.
``script_args: -C`` passes a -C to the bootstrap script, which only configures
the minion and doesn't try to install a new copy of salt-minion.  This way the
minion gets new keys and the keys get pre-seeded on the master, and the
/etc/salt/minion file has the right 'id:' declaration.

Cloning requires a post 2015-02-01 salt-bootstrap.

'''
# pylint: disable=E0102
from __future__ import absolute_import

# Import python libs
import pprint
import logging
import time
from os.path import exists, expanduser


# Import salt cloud libs
import salt.config as config
import salt.utils.cloud
from salt.cloud.exceptions import SaltCloudConfigError
from salt.cloud.libcloudfuncs import *   # pylint: disable=W0614,W0401
from salt.utils import namespaced_function


# Get logging started
log = logging.getLogger(__name__)

HAS_LIBCLOUD = False
HAS_LINODEPY = False

try:
    import linode
    import linode.api
    HAS_LINODEPY = True
except ImportError:
    HAS_LINODEPY = False
    try:
        from libcloud.compute.base import NodeAuthPassword
        HAS_LIBCLOUD = True
    except ImportError:
        HAS_LIBCLOUD = False

# Human-readable status fields
LINODE_STATUS = {
    '-2': 'Boot Failed (not in use)',
    '-1': 'Being Created',
     '0': 'Brand New',
     '1': 'Running',
     '2': 'Powered Off',
     '3': 'Shutting Down (not in use)',
     '4': 'Saved to Disk (not in use)',
}


def remove_complex_types(dictionary):
    '''
    Linode-python is now returning some complex types that
    are not serializable by msgpack.  Kill those.
    '''

    for k, v in dictionary.iteritems():
        if isinstance(v, dict):
            dictionary[k] = remove_complex_types(v)
        elif hasattr(v, 'to_eng_string'):
            dictionary[k] = v.to_eng_string()

    return dictionary

if HAS_LINODEPY:
    # Redirect linode functions to this module namespace
    # get_size = namespaced_function(get_size, globals())
    # get_image = namespaced_function(get_image, globals())
    # avail_locations = namespaced_function(avail_locations, globals())
    # avail_images = namespaced_function(avail_distributions, globals())
    # avail_sizes = namespaced_function(avail_sizes, globals())
    script = namespaced_function(script, globals())
    # destroy = namespaced_function(destroy, globals())
    # list_nodes = namespaced_function(list_nodes, globals())
    # list_nodes_full = namespaced_function(list_nodes_full, globals())
    list_nodes_select = namespaced_function(list_nodes_select, globals())
    show_instance = namespaced_function(show_instance, globals())
    # get_node = namespaced_function(get_node, globals())

elif HAS_LIBCLOUD:
    # Redirect linode functions to this module namespace
    get_size = namespaced_function(get_size, globals())
    get_image = namespaced_function(get_image, globals())
    avail_locations = namespaced_function(avail_locations, globals())
    avail_images = namespaced_function(avail_images, globals())
    avail_sizes = namespaced_function(avail_sizes, globals())
    script = namespaced_function(script, globals())
    destroy = namespaced_function(destroy, globals())
    list_nodes = namespaced_function(list_nodes, globals())
    list_nodes_full = namespaced_function(list_nodes_full, globals())
    list_nodes_select = namespaced_function(list_nodes_select, globals())
    show_instance = namespaced_function(show_instance, globals())
    get_node = namespaced_function(get_node, globals())


if not HAS_LIBCLOUD:
    # Borrowed from Apache Libcloud
    class NodeAuthSSHKey(object):
        '''
        An SSH key to be installed for authentication to a node.
        This is the actual contents of the users ssh public key which will
        normally be installed as root's public key on the node.
        >>> pubkey = '...' # read from file
        >>> from libcloud.compute.base import NodeAuthSSHKey
        >>> k = NodeAuthSSHKey(pubkey)
        >>> k
        <NodeAuthSSHKey>
        '''

        def __init__(self, pubkey):
            '''
            :param pubkey: Public key matetiral.
            :type pubkey: ``str``
            '''
            self.pubkey = pubkey

        def __repr__(self):
            return '<NodeAuthSSHKey>'

    class NodeAuthPassword(object):
        '''
        A password to be used for authentication to a node.
        '''
        def __init__(self, password, generated=False):
            '''
            :param password: Password.
            :type password: ``str``
            :type generated: ``True`` if this password was automatically generated,
                             ``False`` otherwise.
            '''
            self.password = password
            self.generated = generated

        def __repr__(self):
            return '<NodeAuthPassword>'


# Only load in this module if the LINODE configurations are in place
def __virtual__():
    '''
    Set up the libcloud functions and check for Linode configurations.
    '''
    if not HAS_LINODEPY and not HAS_LIBCLOUD:
        return False

    if get_configured_provider() is False:
        return False

    return True


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or 'linode',
        ('apikey',)
    )


def get_conn():
    '''
    Return a conn object for the passed VM data
    '''
    if HAS_LINODEPY:
        return linode.api.Api(key=config.get_cloud_config_value(
                                      'apikey',
                                      get_configured_provider(),
                                      __opts__, search_global=False)
                             )
    elif HAS_LIBCLOUD:
        driver = get_driver(Provider.LINODE)
        return driver(
            config.get_cloud_config_value(
                'apikey', get_configured_provider(), __opts__, search_global=False
            )
        )

if HAS_LIBCLOUD:

    def get_location(conn, vm_):
        '''
        Return the node location to use
        '''
        locations = conn.list_locations()
        # Default to Dallas if not otherwise set
        loc = config.get_cloud_config_value('location', vm_, __opts__, default=2)
        for location in locations:
            if str(loc) in (str(location.id), str(location.name)):
                return location

    def get_disk_size(vm_, size, swap):
        '''
        Return the size of of the root disk in MB
        '''
        return config.get_cloud_config_value(
            'disk_size', vm_, __opts__, default=size.disk - swap
        )

# These are the relevant functions out of linode-python.  For Apache Libcloud
# these are handled inside the libcloud driver and thus are referenced in the
# section at the top of this file (where it says "Redirect linode functions
# to this module namespace

if HAS_LINODEPY:
    def get_image(conn, vm_):
        '''
        Return a single image from the Linode API
        '''
        images = avail_images(conn)
        return images[vm_['image']]['id']

    def get_size(conn, vm_):
        '''
        Return available size from Linode (Linode calls them "plans")
        '''
        sizes = avail_sizes(conn)
        return sizes[vm_['size']]

    def avail_sizes(conn=None):
        '''
        Return available sizes ("plans" in LinodeSpeak)
        '''
        if not conn:
            conn = get_conn()
        sizes = {}
        for plan in conn.avail_linodeplans():
            key = plan['LABEL']
            sizes[key] = {}
            sizes[key]['id'] = plan['PLANID']
            sizes[key]['extra'] = plan
            sizes[key]['bandwidth'] = plan['XFER']
            sizes[key]['disk'] = plan['DISK']
            sizes[key]['price'] = plan['HOURLY']*24*30
            sizes[key]['ram'] = plan['RAM']

        return remove_complex_types(sizes)

    def avail_locations(conn=None):
        '''
        return available datacenter locations
        '''
        if not conn:
            conn = get_conn()
        locations = {}
        for dc in conn.avail_datacenters():
            key = dc['LOCATION']
            locations[key] = {}
            locations[key]['id'] = dc['DATACENTERID']
            locations[key]['abbreviation'] = dc['ABBR']

        return locations

    def avail_images(conn=None):
        '''
        Return available images
        '''
        if not conn:
            conn = get_conn()
        images = {}
        for d in conn.avail_distributions():
            images[d['LABEL']] = {}
            images[d['LABEL']]['id'] = d['DISTRIBUTIONID']
            images[d['LABEL']]['extra'] = d
        return images

    def get_ips(conn=None, LinodeID=None):
        '''
        Return IP addresses, both public and provate
        '''

        if not conn:
            conn = get_conn()
        ips = conn.linode_ip_list(LinodeID=LinodeID)

        all_ips = {'public_ips': [], 'private_ips': []}

        for i in ips:
            if i['ISPUBLIC']:
                key = 'public_ips'
            else:
                key = 'private_ips'
            all_ips[key].append(i['IPADDRESS'])

        return all_ips

    def linodes(full=False, include_ips=False, conn=None):
        '''
        Return data on all nodes
        '''
        if not conn:
            conn = get_conn()

        nodes = conn.linode_list()

        results = {}
        for n in nodes:
            thisnode = {}
            thisnode['id'] = n['LINODEID']
            thisnode['image'] = None
            thisnode['name'] = n['LABEL']
            thisnode['size'] = n['TOTALRAM']
            thisnode['state'] = n['STATUS']
            thisnode['private_ips'] = []
            thisnode['public_ips'] = []
            thisnode['state'] = LINODE_STATUS[str(n['STATUS'])]

            if include_ips:
                thisnode = dict(thisnode.items() +
                                get_ips(conn, n['LINODEID']).items())

            if full:
                thisnode['extra'] = n
            results[n['LABEL']] = thisnode
        return results

    def stop(*args, **kwargs):
        '''
        Execute a "stop" action on a VM in Linode.
        '''

        conn = get_conn()

        node = get_node(name=args[0])
        if not node:
            node = get_node(LinodeID=args[0])

        if node['state'] == 'Powered Off':
            return {'success': True, 'state': 'Stopped',
                    'msg': 'Machine already stopped'}

        result = conn.linode_shutdown(LinodeID=node['id'])

        if waitfor_job(LinodeID=node['id'], JobID=result['JobID']):
            return {'state': 'Stopped',
                    'action': 'stop',
                    'success': True}
        else:
            return {'action': 'stop',
                    'success': False}

    def start(*args, **kwargs):
        '''
        Execute a "start" action on a VM in Linode.
        '''

        conn = get_conn()
        node = get_node(name=args[0])
        if not node:
            node = get_node(LinodeID=args[0])

        if not node:
            return False

        if node['state'] == 'Running':
            return {'success': True,
                    'action': 'start',
                    'state': 'Running',
                    'msg': 'Machine already running'}

        result = conn.linode_boot(LinodeID=node['id'])

        if waitfor_job(LinodeID=node['id'], JobID=result['JobID']):
            return {'state': 'Running',
                    'action': 'start',
                    'success': True}
        else:
            return {'action': 'start',
                    'success': False}

    def clone(*args, **kwargs):
        '''
        Clone an existing Linode
        '''

        conn = get_conn()

        node = get_node(name=args[0], full=True)
        if not node:
            node = get_node(LinodeID=args[0], full=True)

        if len(args) > 1:
            actionargs = args[1]

        if 'target' not in actionargs:
            log.debug('Tried to clone but target not specified.')
            return False

        result = conn.linode_clone(LinodeID=node['id'],
                                DatacenterID=node['extra']['DATACENTERID'],
                                PlanID=node['extra']['PLANID'])

        conn.linode_update(LinodeID=result['LinodeID'],
                        Label=actionargs['target'])

        # Boot!
        if 'boot' not in actionargs:
            bootit = True
        else:
            bootit = actionargs['boot']

        if bootit:
            bootjob_status = conn.linode_boot(LinodeID=result['LinodeID'])

            waitfor_job(LinodeID=result['LinodeID'], JobID=bootjob_status['JobID'])

        node_data = get_node(name=actionargs['target'], full=True)

        log.info('Cloned Cloud VM {0} to {1}'.format(args[0], actionargs['target']))
        log.debug(
            '{0!r} VM creation details:\n{1}'.format(
                args[0], pprint.pformat(node_data)
            )
        )

        return node_data

    def list_nodes():
        '''
        Return basic data on nodes
        '''
        return linodes(full=False, include_ips=True)

    def list_nodes_full():
        '''
        Return all data on nodes
        '''
        return linodes(full=True, include_ips=True)

    def get_node(LinodeID=None, name=None, full=False):
        '''
        Return information on a single node
        '''
        c = get_conn()

        linode_list = linodes(full=full, conn=c)

        for l, d in linode_list.iteritems():
            if LinodeID:
                if d['id'] == LinodeID:
                    d = dict(d.items() + get_ips(conn=c, LinodeID=d['id']).items())
                    return d
            if name:
                if d['name'] == name:
                    d = dict(d.items() + get_ips(conn=c, LinodeID=d['id']).items())
                    return d

        return None

    def destroy(vm_):
        conn = get_conn()
        machines = linodes(full=False, include_ips=False)
        return conn.linode_delete(LinodeID=machines[vm_]['id'], skipChecks=True)

    def get_location(conn, vm_):
        '''
        Return the node location to use.
        Linode wants a location id, which is an integer, when creating a new VM
        To be flexible, let the user specify any of location id, abbreviation, or
        full name of the location ("Fremont, CA, USA") in the config file)
        '''

        locations = avail_locations(conn)
        # Default to Dallas if not otherwise set
        loc = config.get_cloud_config_value(
            'location', vm_, __opts__, default=2
        )

        # Was this an id that matches something in locations?
        if str(loc) not in [locations[k]['id'] for k in locations]:
            # No, let's try to match it against the full
            # name and the abbreviation and return the id
            for key in locations:
                if str(loc).lower() in (key,
                                        str(locations[key]['id']).lower(),
                                        str(locations[key]['abbreviation']).
                                          lower()):
                    return locations[key]['id']
        else:
            return loc

        # No match.  Return None, cloud provider will
        # use a default or throw an exception
        return None

    def get_disk_size(vm_, size, swap):
        '''
        Return the size of of the root disk in MB
        '''
        conn = get_conn()
        vmsize = get_size(conn, vm_)
        disksize = int(vmsize['disk']) * 1024
        return config.get_cloud_config_value(
            'disk_size', vm_, __opts__, default=disksize - swap
        )

# End of linode-python specific functions.  The following are
# usable by both Apache Libcloud and Linode-python, or just Linode-python.
# Linode-python functions almost all take a LinodeID.


def get_password(vm_):
    '''
    Return the password to use
    '''
    return config.get_cloud_config_value(
        'password', vm_, __opts__, default=config.get_cloud_config_value(
            'passwd', vm_, __opts__, search_global=False
        ), search_global=False
    )


def get_pubkey(vm_):
    '''
    Return the SSH pubkey to use
    '''
    return config.get_cloud_config_value(
        'ssh_pubkey', vm_, __opts__, search_global=False)


def get_auth(vm_):
    '''
    Return either NodeAuthSSHKey or NodeAuthPassword, preferring
    NodeAuthSSHKey if both are provided.
    '''
    if HAS_LINODEPY:
        if get_pubkey(vm_) is not None:
            return NodeAuthSSHKey(get_pubkey(vm_))
        elif get_password(vm_) is not None:
            return NodeAuthPassword(get_password(vm_))
        else:
            raise SaltCloudConfigError(
                'The Linode driver requires either a password or ssh_pubkey with '
                'corresponding ssh_private_key.')
    if HAS_LIBCLOUD:
        return NodeAuthPassword(get_password(vm_))


def get_ssh_key_filename(vm_):
    '''
    Return path to filename if get_auth() returns a NodeAuthSSHKey.
    '''
    key_filename = config.get_cloud_config_value(
        'ssh_key_file', vm_, __opts__,
        default=config.get_cloud_config_value(
            'ssh_pubkey', vm_, __opts__, search_global=False
        ), search_global=False)
    if key_filename is not None and exists(expanduser(key_filename)):
        return expanduser(key_filename)
    return None


def get_private_ip(vm_):
    '''
    Return True if a private ip address is requested
    '''
    return config.get_cloud_config_value(
        'private_ip', vm_, __opts__, default=False
    )


def get_swap(vm_):
    '''
    Return the amount of swap space to use in MB
    '''
    return config.get_cloud_config_value(
        'swap', vm_, __opts__, default=128
    )


def get_kernels(conn=None):
    '''
    Get Linode's list of kernels available
    '''
    if not conn:
        conn = get_conn()

    kernel_response = conn.avail_kernels()
    if len(kernel_response['ERRORARRAY']) == 0:
        kernels = {}
        for k in kernel_response['DATA']:
            key = k['LABEL']
            kernels[key] = {}
            kernels[key]['id'] = k['KERNELID']
            kernels[key]['name'] = k['LABEL']
            kernels[key]['isvops'] = k['ISVOPS']
            kernels[key]['isxen'] = k['ISXEN']
        return kernels
    else:
        log.error("Linode avail_kernels returned {0}".format(kernel_response['ERRORARRAY']))
        return None


def get_one_kernel(conn=None, name=None):
    '''
    Return data on one kernel
    name=None returns latest kernel
    '''

    if not conn:
        conn = get_conn()

    kernels = get_kernels(conn)
    if not name:
        name = 'latest 64 bit'
    else:
        name = name.lower()

    for k, v in kernels:
        if name in k.lower():
            return v

    log.error('Did not find a kernel matching {0}'.format(name))
    return None


def waitfor_status(conn=None, LinodeID=None, status=None,
                   timeout=300, quiet=True):
    '''
    Wait for a certain status
    '''
    if not conn:
        conn = get_conn()

    if status is None:
        status = 'Brand New'

    interval = 5
    iterations = int(timeout / interval)

    for i in range(0, iterations):
        result = get_node(LinodeID)

        if result['state'] == status:
            return True

        time.sleep(interval)
        if not quiet:
            log.info('Status for {0} is {1}'.format(LinodeID, result['state']))
        else:
            log.debug('Status for {0} is {1}'.format(LinodeID, result))

    return False


def waitfor_job(conn=None, LinodeID=None, JobID=None, timeout=300, quiet=True):

    if not conn:
        conn = get_conn()

    interval = 5
    iterations = int(timeout / interval)

    for i in range(0, iterations):
        try:
            result = conn.linode_job_list(LinodeID=LinodeID, JobID=JobID)
        except linode.ApiError as exc:
            log.info('Waiting for job {0} on host {1} returned {2}'.
                         format(LinodeID, JobID, exc))
            return False

        if result[0]['HOST_SUCCESS'] == 1:
            return True

        time.sleep(interval)
        if not quiet:
            log.info('Still waiting on Job {0} for {1}'.format(JobID,
                                                               LinodeID))
        else:
            log.debug('Still waiting on Job {0} for {1}'.format(JobID,
                                                                LinodeID))
    return False


def boot(LinodeID=None, configid=None):
    '''
    Execute a boot sequence on a linode
    '''
    conn = get_conn()

    return conn.linode_boot(LinodeID=LinodeID, ConfigID=configid)


def create_swap_disk(vm_=None, LinodeID=None, swapsize=None):
    '''
    Create the disk for the linode
    '''
    conn = get_conn()
    if not swapsize:
        swapsize = get_swap(vm_)

    result = conn.linode_disk_create(LinodeID=LinodeID,
                                     Label='swap',
                                     Size=swapsize,
                                     Type='swap')
    return result


def create_disk_from_distro(vm_=None, LinodeID=None, swapsize=None):
    '''
    Create the disk for the linode
    '''
    conn = get_conn()

    pubkey = get_pubkey(vm_)
    rootpass = get_password(vm_)

    kwargs = {}
    if pubkey:
        kwargs.update({'rootSSHKey': pubkey})
    if rootpass:
        kwargs.update({'rootPass': rootpass})
    else:
        raise SaltCloudConfigError(
            'The Linode driver requires a password.')

    result = conn.linode_disk_createfromdistribution(
        LinodeID=LinodeID,
        DistributionID=get_image(conn, vm_),
        Label='root',
        Size=get_disk_size(vm_, get_size(conn, vm_)['disk'], get_swap(vm_)),
        **kwargs
    )
    return result


def create_config(vm_, LinodeID=None, root_disk_id=None, swap_disk_id=None):
    '''
    Create a Linode Config
    '''
    conn = get_conn()

# 138 appears to always be the latest 64-bit kernel for Linux
    kernelid = 138

    result = conn.linode_config_create(LinodeID=LinodeID,
                                       Label=vm_['name'],
                                       Disklist='{0},{1}'.format(root_disk_id,
                                                                 swap_disk_id),
                                       KernelID=kernelid,
                                       RootDeviceNum=1,
                                       RootDeviceRO=True,
                                       RunLevel='default',
                                       helper_disableUpdateDB=True,
                                       helper_xen=True,
                                       helper_depmod=True)
    return result


def create(vm_):
    '''
    Create a single VM from a data dict
    '''

    salt.utils.cloud.fire_event(
        'event',
        'starting create',
        'salt/cloud/{0}/creating'.format(vm_['name']),
        {
            'name': vm_['name'],
            'profile': vm_['profile'],
            'provider': vm_['provider'],
        },
        transport=__opts__['transport']
    )

    log.info('Creating Cloud VM {0}'.format(vm_['name']))
    conn = get_conn()

    ssh_username = config.get_cloud_config_value(
        'ssh_username', vm_, __opts__, default='root'
    )
    if 'clonefrom' in vm_:
        if HAS_LIBCLOUD:
            if 'clonefrom' in vm_:
                log.error('Error: Linode via Apache Libcloud cannot clone.')
                return False

        clonesource = get_node(name=vm_['clonefrom'])

        kwargs = {
            'name': vm_['name'],
            'clonefrom': vm_['clonefrom'],
            'image': 'Clone of {0}'.format(vm_['clonefrom']),
            'size': clonesource['size'],
            'auth': get_auth(vm_),
            'ex_private': get_private_ip(vm_),
        }

        node_data = clone(vm_['clonefrom'], {'target': vm_['name']})

        salt.utils.cloud.fire_event(
            'event',
            'requesting instance',
            'salt/cloud/{0}/requesting'.format(vm_['name']),
            {'kwargs': {'name': kwargs['name'],
                        'image': kwargs['image'],
                        'size': kwargs['size'],
                        'ex_private': kwargs['ex_private']}},
            transport=__opts__['transport']
        )
    else:
        if HAS_LIBCLOUD:
            kwargs = {
                'name': vm_['name'],
                'image': get_image(conn, vm_),
                'size': get_size(conn, vm_),
                'location': get_location(conn, vm_),
                'auth': get_auth(vm_),
                'ex_private': get_private_ip(vm_),
                'ex_rsize': get_disk_size(vm_, get_size(conn, vm_), get_swap(vm_)),
                'ex_swap': get_swap(vm_)
            }

            salt.utils.cloud.fire_event(
                'event',
                'requesting instance',
                'salt/cloud/{0}/requesting'.format(vm_['name']),
                {'kwargs': {'name': kwargs['name'],
                                'image': kwargs['image'].name,
                                'size': kwargs['size'].name,
                                'location': kwargs['location'].name,
                                'ex_private': kwargs['ex_private'],
                                'ex_rsize': kwargs['ex_rsize'],
                                'ex_swap': kwargs['ex_swap']}},
                    transport=__opts__['transport']
                )

        if HAS_LINODEPY:
            kwargs = {
                'name': vm_['name'],
                'image': get_image(conn, vm_),
                'size': get_size(conn, vm_),
                'location': get_location(conn, vm_),
                'auth': get_auth(vm_),
                'ex_private': get_private_ip(vm_),
                'ex_rsize': get_disk_size(vm_, get_size(conn, vm_), get_swap(vm_)),
                'ex_swap': get_swap(vm_)
            }

            salt.utils.cloud.fire_event(
                'event',
                'requesting instance',
                'salt/cloud/{0}/requesting'.format(vm_['name']),
                {'kwargs': {'name': kwargs['name'],
                                'image': kwargs['image'],
                                'size': kwargs['size'],
                                'location': kwargs['location'],
                                'ex_private': kwargs['ex_private'],
                                'ex_rsize': kwargs['ex_rsize'],
                                'ex_swap': kwargs['ex_swap']}},
                    transport=__opts__['transport']
                )

        if 'libcloud_args' in vm_:
            kwargs.update(vm_['libcloud_args'])

        if HAS_LIBCLOUD:
            try:
                node_data = conn.create_node(**kwargs)
            except Exception as exc:
                log.error(
                    'Error creating {0} on Linode via Apache Libcloud\n\n'
                    'The following exception was thrown by libcloud when trying to '
                    'run the initial deployment: \n{1}'.format(
                        vm_['name'], str(exc)
                    ),
                    # Show the traceback if the debug logging level is enabled
                    exc_info_on_loglevel=logging.DEBUG
                )
                return False

        if HAS_LINODEPY:
            # linode-python version
            try:
                node_data = conn.linode_create(DatacenterID=get_location(conn, vm_),
                                               PlanID=kwargs['size']['extra']['PLANID'], PaymentTerm=1)
            except Exception as exc:
                log.error(
                    'Error creating {0} on Linode via linode-python\n\n'
                    'The following exception was thrown by linode-python when trying to '
                    'run the initial deployment: \n{1}'.format(
                        vm_['name'], str(exc)
                    ),
                    # Show the traceback if the debug logging level is enabled
                    exc_info_on_loglevel=logging.DEBUG
                )
                return False

            if not waitfor_status(conn=conn, LinodeID=node_data['LinodeID'], status='Brand New'):
                log.error('Error creating {0} on LINODE\n\n'
                    'while waiting for initial ready status'.format(
                        vm_['name']
                    ),
                    # Show the traceback if the debug logging level is enabled
                    exc_info_on_loglevel=logging.DEBUG
                )

            # Set linode name
            set_name_result = conn.linode_update(LinodeID=node_data['LinodeID'],
                                                 Label=vm_['name'])
            log.debug('Set name action for {0} was {1}'.format(vm_['name'],
                                                              set_name_result))

            # Create disks
            log.debug('Creating disks for {0}'.format(node_data['LinodeID']))
            swap_result = create_swap_disk(LinodeID=node_data['LinodeID'], swapsize=get_swap(vm_))

            root_result = create_disk_from_distro(vm_, LinodeID=node_data['LinodeID'],
                                                 swapsize=get_swap(vm_))

            # Create config
            config_result = create_config(vm_, LinodeID=node_data['LinodeID'],
                                          root_disk_id=root_result['DiskID'],
                                          swap_disk_id=swap_result['DiskID'])

            # Boot!
            boot_result = boot(LinodeID=node_data['LinodeID'],
                               configid=config_result['ConfigID'])

            if not waitfor_job(conn, LinodeID=node_data['LinodeID'],
                               JobID=boot_result['JobID']):
                log.error('Boot failed for {0}.'.format(node_data))
                return False

            node_data.update(get_node(node_data['LinodeID']))

    if HAS_LINODEPY:
        if get_private_ip(vm_) and config.get_cloud_config_value(
                                             'ssh_interface',
                                             get_configured_provider(),
                                             __opts__, search_global=False,
                                             default='public') == 'private':
            vm_['ssh_host'] = node_data['private_ips'][0]
        else:
            vm_['ssh_host'] = node_data['public_ips'][0]

    if HAS_LIBCLOUD:
        if get_private_ip(vm_) and config.get_cloud_config_value(
                                             'ssh_interface',
                                             get_configured_provider(),
                                             __opts__, search_global=False,
                                             default='public') == 'private':
            vm_['ssh_host'] = node_data.private_ips[0]
        else:
            vm_['ssh_host'] = node_data.public_ips[0]

    # If a password wasn't supplied in the profile or provider config, set it now.
    vm_['password'] = get_password(vm_)

    # Bootstrap, either apache-libcloud or linode-python
    ret = salt.utils.cloud.bootstrap(vm_, __opts__)

    if HAS_LINODEPY:
        ret.update(node_data)

    if HAS_LIBCLOUD:
        ret.update(node_data.__dict__)

    log.info('Created Cloud VM {0[name]!r}'.format(vm_))
    log.debug(
        '{0[name]!r} VM creation details:\n{1}'.format(
        vm_, pprint.pformat(node_data)
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
        transport=__opts__['transport']
    )

    return ret
