'''
OpenStack Cloud Module
======================

The OpenStack cloud module. OpenStack is an open source project that is in  use
by a number a cloud providers, each of which have their own ways of using it.

OpenStack provides a number of ways to authenticate. This module uses password-
based authentication, using auth v2.0. It is likely to start supporting other
methods of authentication provided by OpenStack in the future.

This module has been tested to work with HP Cloud. Testing for Rackspace's
implementation is still under way. With the HP Cloud, the following parameters
are required, and can be found under the API Keys section of the Account tab in
their web interface:

.. code-block:: yaml

    # The OpenStack identity service url
    OPENSTACK.identity_url: https://region-a.geo-1.identity.hpcloudsvc.com:35357/v2.0/
    # The OpenStack compute region
    OPENSTACK.compute_region: az-1.region-a.geo-1
    # The OpenStack tenant name (not tenant ID)
    OPENSTACK.tenant: myuser-tenant1
    # The OpenStack user name
    OPENSTACK.user: myuser
    # The OpenStack password
    OPENSTACK.password: letmein
    # The OpenStack keypair name
    OPENSTACK.ssh_key_name

'''

# The import section is mostly libcloud boilerplate

# Import python libs
import os
import types
import tempfile
import time
import sys

# Import libcloud 
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
from libcloud.compute.deployment import MultiStepDeployment, ScriptDeployment, SSHKeyDeployment

# Import generic libcloud functions
from saltcloud.libcloudfuncs import *

# Some of the libcloud functions need to be in the same namespace as the
# functions defined in the module, so we create new function objects inside
# this module namespace
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
    if 'OPENSTACK.user' in __opts__ and 'OPENSTACK.password' in __opts__:
        return 'openstack'
    return False


def get_conn():
    '''
    Return a conn object for the passed vm data
    '''
    driver = get_driver(Provider.OPENSTACK)
    authinfo = {
            'ex_force_auth_url': __opts__['OPENSTACK.identity_url'],
            'ex_force_auth_version': '2.0_password',
            'ex_force_service_name': 'Compute',
    }

    if 'OPENSTACK.compute_region' in __opts__:
        authinfo['ex_force_service_region'] = __opts__['OPENSTACK.compute_region']

    if 'OPENSTACK.tenant' in __opts__:
        authinfo['ex_tenant_name'] = __opts__['OPENSTACK.tenant']

    return driver(
            __opts__['OPENSTACK.user'],
            __opts__['OPENSTACK.password'],
            **authinfo
    )


def create(vm_):
    '''
    Create a single vm from a data dict
    '''
    print('Creating Cloud VM {0}'.format(vm_['name']))
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
    nr_count = 0
    while not_ready:
        print('Looking for IP addresses')
        nodelist = list_nodes()
        private = nodelist[vm_['name']]['private_ips']
        public = nodelist[vm_['name']]['public_ips']
        if private and not public:
            print('Private IPs returned, but not public... checking for misidentified IPs')
            for private_ip in private:
                if saltcloud.utils.is_public_ip(private_ip):
                    print('{0} is a public ip'.format(private_ip))
                    data.public_ips.append(private_ip)
                    not_ready = False
                else:
                    print('{0} is a private ip'.format(private_ip))
                    if private_ip not in data.private_ips:
                        data.private_ips.append(private_ip)
        nr_count += 1
        if nr_count > 50:
            not_ready = False
        time.sleep(1)

    deployargs = {
        'host': data.public_ips[0],
        'script': deploy_script.script,
        'name': vm_['name'],
	'sock_dir': __opts__['sock_dir']
    }

    if 'ssh_username' in vm_:
	deployargs['username'] = vm_['ssh_username']
    else:
        deployargs['username'] = 'root'

    if 'OPENSTACK.ssh_key_file' in __opts__:
	deployargs['key_filename'] = __opts__['OPENSTACK.ssh_key_file']
    elif 'password' in data.extra:
	deployargs['password'] = data.extra['password']

    if 'sudo' in vm_:
        deployargs['sudo'] = vm_['sudo']

    print('Running deploy script')
    deployed = saltcloud.utils.deploy_script(**deployargs)
    if deployed:
        print('Salt installed on {0}'.format(vm_['name']))
    else:
        print('Failed to start Salt on Cloud VM {0}'.format(vm_['name']))

    print('Created Cloud VM {0} with the following values:'.format(
        vm_['name']
        ))
    for key, val in data.__dict__.items():
        print('  {0}: {1}'.format(key, val))
