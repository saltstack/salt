'''
OpenStack Cloud Module
======================

The OpenStack cloud module. OpenStack is an open source project that is in  use
by a number a cloud providers, each of which have their own ways of using it.

OpenStack provides a number of ways to authenticate. This module uses password-
based authentication, using auth v2.0. It is likely to start supporting other
methods of authentication provided by OpenStack in the future.

This module has been tested to work with HP Cloud and Rackspace. See the
documentation for specific options for either of these providers. Some examples
are provided below:

.. code-block:: yaml

    # The OpenStack identity service url
    OPENSTACK.identity_url: https://region-a.geo-1.identity.hpcloudsvc.com:35357/v2.0/
    # The OpenStack compute region
    OPENSTACK.compute_region: az-1.region-a.geo-1
    # The OpenStack compute service name
    OPENSTACK.compute_name: Compute
    # The OpenStack tenant name (not tenant ID)
    OPENSTACK.tenant: myuser-tenant1
    # The OpenStack user name
    OPENSTACK.user: myuser
    # The OpenStack keypair name
    OPENSTACK.ssh_key_name
    
Either a password or an API key must also be specified:

.. code-block:: yaml

    # The OpenStack password
    OPENSTACK.password: letmein
    # The OpenStack API key
    OPENSTACK.apikey: 901d3f579h23c8v73q9

'''

# The import section is mostly libcloud boilerplate

# Import python libs
import os
import types
import tempfile
import time
import sys
import logging
import socket

# Import libcloud 
from libcloud.compute.base import NodeState
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
from libcloud.compute.deployment import MultiStepDeployment, ScriptDeployment, SSHKeyDeployment

# Import generic libcloud functions
from saltcloud.libcloudfuncs import *
from salt.exceptions import SaltException

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


# Only load in this module is the OPENSTACK configurations are in place
def __virtual__():
    '''
    Set up the libcloud functions and check for OPENSTACK configs
    '''
    if 'OPENSTACK.user' in __opts__:
        log.debug('Loading Openstack cloud module')
        return 'openstack'
    return False


def get_conn():
    '''
    Return a conn object for the passed vm data
    '''
    driver = get_driver(Provider.OPENSTACK)
    authinfo = {
            'ex_force_auth_url': __opts__['OPENSTACK.identity_url'],
            }

    if 'OPENSTACK.compute_name' in __opts__:
        authinfo['ex_force_service_name'] = __opts__['OPENSTACK.compute_name']

    if 'OPENSTACK.compute_region' in __opts__:
        authinfo['ex_force_service_region'] = __opts__['OPENSTACK.compute_region']

    if 'OPENSTACK.tenant' in __opts__:
        authinfo['ex_tenant_name'] = __opts__['OPENSTACK.tenant']

    if 'OPENSTACK.password' in __opts__:
        authinfo['ex_force_auth_version'] = '2.0_password'
        log.debug('OpenStack authenticating using password')
        return driver(
            __opts__['OPENSTACK.user'],
            __opts__['OPENSTACK.password'],
            **authinfo
            )
    elif 'OPENSTACK.apikey' in __opts__:
        authinfo['ex_force_auth_version'] = '2.0_apikey'
        log.debug('OpenStack authenticating using apikey')
        return driver(
            __opts__['OPENSTACK.user'],
            __opts__['OPENSTACK.apikey'],
            **authinfo
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
    saltcloud.utils.check_name(vm_['name'], '[a-z0-9_-]')
    conn = get_conn()
    deploy_script = script(vm_)
    kwargs = {}
    kwargs['name'] = vm_['name']

    try:
        kwargs['image'] = get_image(conn, vm_)
    except Exception as exc:
        err = ('Error creating {0} on OPENSTACK\n\n'
               'Could not find image {1}\n').format(
                       vm_['name'], vm_['image']
                       )
        sys.stderr.write(err)
        log.error(err)
        return False

    try:
        kwargs['size'] = get_size(conn, vm_)
    except Exception as exc:
        err = ('Error creating {0} on OPENSTACK\n\n'
               'Could not find size {1}\n').format(
                       vm_['name'], vm_['size']
                       )
        sys.stderr.write(err)
        return False

    if 'OPENSTACK.ssh_key_name' in __opts__:
        kwargs['ex_keyname'] = __opts__['OPENSTACK.ssh_key_name']

    try:
        data = conn.create_node(**kwargs)
    except Exception as exc:
        err = ('Error creating {0} on OPENSTACK\n\n'
               'The following exception was thrown by libcloud when trying to '
               'run the initial deployment: \n{1}').format(
                       vm_['name'], exc
                       )
        sys.stderr.write(err)
        return False

    not_ready = True
    nr_total = 50
    nr_count = nr_total
    while not_ready:
        log.debug('Looking for IP addresses')
        nodelist = list_nodes(conn)
        private = nodelist[vm_['name']]['private_ips']
        public = nodelist[vm_['name']]['public_ips']
        running = nodelist[vm_['name']]['state'] == NodeState.RUNNING
        if running and private and not public:
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

        if running and public:
            data.public_ips = public
            not_ready = False

        nr_count -= 1
        if nr_count == 0:
            log.warn('Timed out waiting for a public ip, continuing anyway')
            break
        time.sleep(nr_total - nr_count + 5)

    if ssh_interface(vm_) == 'private_ips':
        ip_address = preferred_ip(vm_, data.private_ips)
    else:
        ip_address = preferred_ip(vm_, data.public_ips)
    log.debug('Using IP address {0}'.format(ip_address))

    if not ip_address:
        raise SaltException('A valid IP address was not found')

    deployargs = {
        'host': ip_address,
        'script': deploy_script.script,
        'name': vm_['name'],
        'sock_dir': __opts__['sock_dir'],
        'start_action': __opts__['start_action']
    }

    if 'ssh_username' in vm_:
        deployargs['username'] = vm_['ssh_username']
    else:
        deployargs['username'] = 'root'
    log.debug('Using {0} as SSH username'.format(deployargs['username']))

    if 'OPENSTACK.ssh_key_file' in __opts__:
        deployargs['key_filename'] = __opts__['OPENSTACK.ssh_key_file']
        log.debug('Using {0} as SSH key file'.format(deployargs['key_filename']))
    elif 'password' in data.extra:
        deployargs['password'] = data.extra['password']
        log.debug('Logging into SSH using password')

    if 'sudo' in vm_:
        deployargs['sudo'] = vm_['sudo']
        log.debug('Running root commands using sudo')

    if __opts__['deploy'] is True:
        deployed = saltcloud.utils.deploy_script(**deployargs)
        if deployed:
            log.info('Salt installed on {0}'.format(vm_['name']))
        else:
            log.error('Failed to start Salt on Cloud VM {0}'.format(vm_['name']))

    log.info('Created Cloud VM {0} with the following values:'.format(vm_['name']))
    for key, val in data.__dict__.items():
        log.info('  {0}: {1}'.format(key, val))

