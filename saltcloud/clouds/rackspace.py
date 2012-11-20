'''
Rackspace Cloud Module
======================

The Rackspace cloud module. This module uses the preferred means to set up a
libcloud based cloud module and should be used as the general template for
setting up additional libcloud based modules.

The rackspace cloud module interfaces with the Rackspace public cloud service
and requires that two configuration paramaters be set for use:

.. code-block:: yaml

    # The Rackspace login user
    RACKSPACE.user: fred
    # The Rackspace user's apikey
    RACKSPACE.apikey: 901d3f579h23c8v73q9

'''

# The import section is mostly libcloud boilerplate

# Import python libs
import os
import types
import tempfile
import logging
import socket
import time

# Import libcloud 
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
from libcloud.compute.deployment import MultiStepDeployment, ScriptDeployment, SSHKeyDeployment

# Import generic libcloud functions
from saltcloud.libcloudfuncs import *

# Get logging started
log = logging.getLogger(__name__)

# Some of the libcloud functions need to be in the same namespace as the
# functions defined in the module, so we create new function objects inside
# this module namespace
avail_locations = types.FunctionType(avail_locations.__code__, globals())
avail_images = types.FunctionType(avail_images.__code__, globals())
avail_sizes = types.FunctionType(avail_sizes.__code__, globals())
script = types.FunctionType(script.__code__, globals())
destroy = types.FunctionType(destroy.__code__, globals())
list_nodes = types.FunctionType(list_nodes.__code__, globals())
list_nodes_full = types.FunctionType(list_nodes_full.__code__, globals())
list_nodes_select = types.FunctionType(list_nodes_select.__code__, globals())


# Only load in this module is the RACKSPACE configurations are in place
def __virtual__():
    '''
    Set up the libcloud funcstions and check for RACKSPACE configs
    '''
    if 'RACKSPACE.user' in __opts__ and 'RACKSPACE.apikey' in __opts__:
        log.debug('Loading Rackspace cloud module')
        return 'rackspace'
    return False


def get_conn():
    '''
    Return a conn object for the passed vm data
    '''
    driver = get_driver(Provider.RACKSPACE)
    return driver(
            __opts__['RACKSPACE.user'],
            __opts__['RACKSPACE.apikey'],
            )


def preferred_ip(vm_, ips):
    '''
    Return the preferred Internet protocol. Either 'ipv4' (default) or 'ipv6'.
    '''
    proto = vm_.get('protocol', __opts__.get('OPENSTACK.protocol', 'ipv4'))
    family = socket.AF_INET
    if proto == 'ipv6':
        family = socket.AF_INET6
    for ip in ips:
        try:
            socket.inet_pton(family, ip)
            return ip
        except:
            continue
    return False


def ssh_interface(vm_):
    '''
    Return the ssh_interface type to connect to. Either 'public_ips' (default) or 'private_ips'.
    '''
    return vm_.get('ssh_interface', __opts__.get('OPENSTACK.ssh_interface', 'public_ips'))


def create(vm_):
    '''
    Create a single vm from a data dict
    '''
    log.info('Creating Cloud VM {0}'.format(vm_['name']))
    conn = get_conn()
    deploy_script = script(vm_)
    kwargs = {}
    kwargs['name'] = vm_['name']
    kwargs['image'] = get_image(conn, vm_)
    kwargs['size'] = get_size(conn, vm_)
    try:
        data = conn.create_node(**kwargs)
    except Exception as exc:
        err = ('Error creating {0} on RACKSPACE\n\n'
               'The following exception was thrown by libcloud when trying to '
               'run the initial deployment: \n{1}').format(
                       vm_['name'], exc
                       )
        sys.stderr.write(err)
        log.error(err)
        return False

    not_ready = True
    nr_count = 0
    log.debug('Looking for IP addresses')
    while not_ready:
        nodelist = list_nodes()
        private = nodelist[vm_['name']]['private_ips']
        public = nodelist[vm_['name']]['public_ips']
        if private and not public:
            log.warn('Private IPs returned, but not public... checking for misidentified IPs')
            for private_ip in private:
                private_ip = preferred_ip(vm_, [private_ip])
                if saltcloud.utils.is_public_ip(private_ip):
                    log.warn('{0} is a public ip'.format(private_ip))
                    data.public_ips.append(private_ip)
                    not_ready = False
                else:
                    log.warn('{0} is a private ip'.format(private_ip))
                    if private_ip not in data.private_ips:
                        data.private_ips.append(private_ip)
            if ssh_interface(vm_) == 'private_ips' and data.private_ips:
                break

        if public:
            data.public_ips = public
            not_ready = False

        nr_count += 1
        if nr_count > 50:
            log.warn('Timed out waiting for a public ip, continuing anyway')
            break
        time.sleep(1)

    if ssh_interface(vm_) == 'private_ips':
        ip_address = preferred_ip(vm_, data.private_ips)
    else:
        ip_address = preferred_ip(vm_, data.public_ips)
    log.debug('Using IP address {0}'.format(ip_address))

    if not ip_address:
        raise

    if __opts__['deploy'] is True:
        deployed = saltcloud.utils.deploy_script(
            host=ip_address,
            username='root',
            password=data.extra['password'],
            script=deploy_script.script,
            name=vm_['name'],
            sock_dir=__opts__['sock_dir'])
        if deployed:
            log.info('Salt installed on {0}'.format(vm_['name']))
        else:
            log.error('Failed to start Salt on Cloud VM {0}'.format(vm_['name']))

    log.info('Created Cloud VM {0} with the following values:'.format(vm_['name']))
    for key, val in data.__dict__.items():
        log.info('  {0}: {1}'.format(key, val))
