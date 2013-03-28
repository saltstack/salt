'''
Digital Ocean Cloud Module
==========================

The Digital Ocean cloud module is used to control access to the Digital Ocean
VPS system.

Use of this module only requires the DIGITAL_OCEAN.api_key paramater to be set
in the cloud configuration file.

.. code-block:: yaml

    # Digital Ocean account keys
    DIGITAL_OCEAN.client_key: wFGEwgregeqw3435gDger
    DIGITAL_OCEAN.api_key: GDE43t43REGTrkilg43934t34qT43t4dgegerGEgg

'''

# Import python libs
import re
import sys
import time
import yaml
import json
import urllib
import urllib2
import logging

# Import salt libs
import salt.utils.event
import saltcloud.utils

# Get logging started
log = logging.getLogger(__name__)


# Only load in this module if the DIGITAL_OCEAN configurations are in place
def __virtual__():
    '''
    Check for DIGITAL_OCEAN configs
    '''
    if 'DIGITAL_OCEAN.api_key' in __opts__:
        log.debug('Loading Digital Ocean cloud module')
        return 'digital_ocean'
    return False


def avail_locations():
    '''
    Return a dict of all available VM locations on the cloud provider with
    relevant data
    '''
    items = query(method='regions')
    ret = {}
    for region in items['regions']:
        ret[region['name']] = {}
        for item in region.keys():
            ret[region['name']][item] = str(region[item])

    return ret


def avail_images():
    '''
    Return a list of the images that are on the provider
    '''
    items = query(method='images')
    ret = {}
    for image in items['images']:
        ret[image['name']] = {}
        for item in image.keys():
            ret[image['name']][item] = str(image[item])

    return ret


def avail_sizes():
    '''
    Return a list of the image sizes that are on the provider
    '''
    items = query(method='sizes')
    ret = {}
    for size in items['sizes']:
        ret[size['name']] = {}
        for item in size.keys():
            ret[size['name']][item] = str(size[item])

    return ret


def list_nodes():
    '''
    Return a list of the VMs that are on the provider
    '''
    items = query(method='droplets')

    ret = {}
    for node in items['droplets']:
        ret[node['name']] = {
            'id': node['id'],
            'image_id': node['image_id'],
            'public_ips': str(node['ip_address']),
            'size_id': node['size_id'],
            'status': str(node['status']),
        }
    return ret


def list_nodes_full():
    '''
    Return a list of the VMs that are on the provider
    '''
    items = query(method='droplets')

    ret = {}
    for node in items['droplets']:
        ret[node['name']] = {}
        for item in node.keys():
            ret[node['name']][item] = str(node[item])
    return ret


def list_nodes_select():
    '''
    Return a list of the VMs that are on the provider
    '''
    items = query(method='droplets')

    ret = {}
    for node in items['droplets']:
        ret[node['name']] = {}
        for item in node.keys():
            if str(item) in __opts__['query.selection']:
                ret[node['name']][item] = str(node[item])
    return ret


def get_image(vm_):
    '''
    Return the image object to use
    '''
    images = avail_images()
    for image in images:
        if images[image]['name'] == str(vm_['image']):
            return images[image]['id']
        if images[image]['id'] == str(vm_['image']):
            return images[image]['id']
    raise ValueError("The specified image could not be found.")


def get_size(vm_):
    '''
    Return the VM's size. Used by create_node().
    '''
    sizes = avail_sizes()
    for size in sizes:
        if sizes[size]['name'] == str(vm_['size']):
            return sizes[size]['id']
        if sizes[size]['id'] == str(vm_['size']):
            return sizes[size]['id']
    raise ValueError("The specified size could not be found.")


def get_location(vm_):
    '''
    Return the VM's location
    '''
    locations = avail_locations()
    for location in locations:
        if locations[location]['name'] == str(vm_['location']):
            return locations[location]['id']
        if locations[location]['id'] == str(vm_['location']):
            return locations[location]['id']
    raise ValueError("The specified location could not be found.")


def create_node(args):
    '''
    Create a node
    '''
    node = query(method='droplets',
                       command='new',
                       args=args)
    return node


def create(vm_):
    '''
    Create a single VM from a data dict
    '''
    log.info('Creating Cloud VM {0}'.format(vm_['name']))
    deploy_script = script(vm_)
    kwargs = {}
    kwargs['name'] = vm_['name']
    kwargs['size_id'] = get_size(vm_)
    kwargs['image_id'] = get_image(vm_)
    kwargs['region_id'] = get_location(vm_)
    kwargs['ssh_key_ids'] = get_keyid(__opts__['DIGITAL_OCEAN.ssh_key_name'])

    try:
        data = create_node(kwargs)
    except Exception as exc:
        err = ('Error creating {0} on DIGITAL_OCEAN\n\n'
               'The following exception was thrown when trying to '
               'run the initial deployment: \n{1}').format(
                       vm_['name'], exc.message
                       )
        sys.stderr.write(err)
        log.error(err)
        return False

    waiting_for_ip = 0
    while 'ip_address' not in data:
        log.debug('Salt node waiting for IP {0}'.format(waiting_for_ip))
        time.sleep(5)
        waiting_for_ip += 1
        data = _get_node(vm_['name'])

    if __opts__['deploy'] is True:
        deploy_script = script(vm_)
        deploy_kwargs = {
            'host': data['ip_address'],
            'username': 'root',
            'key_filename': __opts__['DIGITAL_OCEAN.ssh_key_file'],
            'script': deploy_script,
            'name': vm_['name'],
            'deploy_command': '/tmp/deploy.sh',
            'start_action': __opts__['start_action'],
            'sock_dir': __opts__['sock_dir'],
            'conf_file': __opts__['conf_file'],
            'minion_pem': vm_['priv_key'],
            'minion_pub': vm_['pub_key'],
            'keep_tmp': __opts__['keep_tmp'],
            }

        if 'script_args' in vm_:
            deploy_kwargs['script_args'] = vm_['script_args']

        deploy_kwargs['minion_conf'] = saltcloud.utils.minion_conf_string(__opts__, vm_)

        deployed = saltcloud.utils.deploy_script(**deploy_kwargs)
        if deployed:
            log.info('Salt installed on {0}'.format(vm_['name']))
        else:
            log.error('Failed to start Salt on Cloud VM {0}'.format(vm_['name']))

    log.info('Created Cloud VM {0} with the following values:'.format(vm_['name']))

    return data


def query(method='droplets', droplet_id=None, command=None, args=None):
    '''
    Make a web call to Digital Ocean
    '''
    path = 'https://api.digitalocean.com/{0}/'.format(method)

    if droplet_id:
        path = '{0}/'.format(droplet_id)

    if command:
        path += command

    if type(args) is not dict:
        args = {}

    args['client_id'] = __opts__['DIGITAL_OCEAN.client_key']
    args['api_key'] = __opts__['DIGITAL_OCEAN.api_key']

    path += '?%s'
    params = urllib.urlencode(args)
    result = urllib2.urlopen(path % params)
    log.debug(result.geturl())
    content = result.read()
    result.close()

    return json.loads(content)


def script(vm_):
    '''
    Return the script deployment object
    '''
    minion = saltcloud.utils.minion_conf_string(__opts__, vm_)
    script = saltcloud.utils.os_script(
        saltcloud.utils.get_option(
            'script',
            __opts__,
            vm_
        ),
        vm_,
        __opts__,
        minion,
    )
    return script


def show_instance(name, call=None):
    '''
    Show the details from Digital Ocean concerning a droplet
    '''
    if call != 'action':
        log.error(
            'The show_instance action must be called with -a or --action.'
        )
        sys.exit(1)

    return _get_node(name)


def _get_node(name, location=None):
    attempts = 10
    while attempts >= 0:
        try:
            return list_nodes_full()[name]
        except KeyError:
            attempts -= 1
            log.debug(
                'Failed to get the data for the node {0!r}. Remaining '
                'attempts {1}'.format(
                    name, attempts
                )
            )
            # Just a little delay between attempts...
            time.sleep(0.5)
    return {}


def list_keypairs(call=None):
    '''
    Return a dict of all available VM locations on the cloud provider with
    relevant data
    '''
    if call != 'function':
        log.error('The list_keypairs function must be called with '
                  '-f or --function.')
        return False

    items = query(method='ssh_keys')
    ret = {}
    for keypair in items['ssh_keys']:
        ret[keypair['name']] = {}
        for item in keypair.keys():
            ret[keypair['name']][item] = str(keypair[item])

    return ret


def show_keypair(kwargs=None, call=None):
    '''
    Show the details of an SSH keypair
    '''
    if call != 'function':
        log.error('The show_keypair function must be called with '
                  '-f or --function.')
        return False

    if not kwargs:
        kwargs = {}

    if not 'keyname' in kwargs:
        log.error('A keyname is required.')
        return False

    keypairs = list_keypairs(call='function')
    keyid = keypairs[kwargs['keyname']]['id']
    log.debug('Key ID is {0}'.format(keyid))

    details = query(method='ssh_keys', command=keyid)

    return details


def get_keyid(keyname):
    '''
    Return the ID of the keyname
    '''
    keypairs = list_keypairs(call='function')
    keyid = keypairs[keyname]['id']
    if keyid:
        return keyid
    raise ValueError("The specified ssh key could not be found.")


def destroy(name, call=None):
    '''
    Destroy a node. Will check termination protection and warn if enabled.

    CLI Example::

        salt-cloud --destroy mymachine
    '''
    data = show_instance(name, call='action')
    node = query(method='droplets',
                       command='{0}/destroy'.format(data['id']))

    return node
