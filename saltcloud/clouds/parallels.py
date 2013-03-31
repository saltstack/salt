'''
Parallels Cloud Module
======================

The Parallels cloud module is used to control access to cloud providers using
the Parallels VPS system.

Use of this module requires the following PARALLELS paramaters to be set in the
cloud configuration file.

.. code-block:: yaml

    # Parallels account information
    PARALLELS.user: myuser
    PARALLELS.password: mypassword
    PARALLELS.url: https://api.cloud.xmission.com:4465/paci/v1.0/

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
import xml.etree.ElementTree as ET

# Import salt libs
import salt.utils.event
import salt.utils.xmlutil
import saltcloud.utils

# Get logging started
log = logging.getLogger(__name__)


# Only load in this module if the PARALLELS configurations are in place
def __virtual__():
    '''
    Check for PARALLELS configs
    '''
    if 'PARALLELS.user' in __opts__:
        log.debug('Loading Parallels cloud module')
        return 'parallels'
    return False


def avail_locations():
    '''
    Return a dict of all available VM locations on the cloud provider with
    relevant data
    '''
    return {'Error':
               {'Not Supported':
                   '--list-locations not currently supported by Parallels'
               }
           }


def avail_images():
    '''
    Return a list of the images that are on the provider
    '''
    items = query(action='template')
    ret = {}
    for item in items:
        ret[item.attrib['name']] = item.attrib

    return ret


def avail_sizes():
    '''
    Return a list of the image sizes that are on the provider
    '''
    return {'Error':
               {'Not Supported':
                   '--list-sizes not currently supported by Parallels'
               }
           }


def list_nodes():
    '''
    Return a list of the VMs that are on the provider
    '''
    ret = {}
    items = query(action='ve')

    for item in items:
        name = item.attrib['name']
        node = show_instance(name, call='action')

        ret[name] = {
            'id': node['id'],
            'image': node['platform']['template-info']['name'],
            'state': node['state'],
        }
        if 'private-ip' in node['network']:
            ret[name]['private_ips'] = [node['network']['private-ip']]
        if 'public-ip' in node['network']:
            ret[name]['public_ips'] = [node['network']['public-ip']]

    return ret


def list_nodes_full():
    '''
    Return a list of the VMs that are on the provider
    '''
    ret = {}
    items = query(action='ve')

    for item in items:
        name = item.attrib['name']
        node = show_instance(name, call='action')

        ret[name] = node
        ret[name]['image'] = node['platform']['template-info']['name']
        if 'private-ip' in node['network']:
            ret[name]['private_ips'] = [node['network']['private-ip']['address']]
        if 'public-ip' in node['network']:
            ret[name]['public_ips'] = [node['network']['public-ip']['address']]

    return ret


def list_nodes_select():
    '''
    Return a list of the VMs that are on the provider
    '''
    ret = {}

    nodes = list_nodes_full()
    for node in nodes:
        pairs = {}
        data = nodes[node]
        for key in data:
            if str(key) in __opts__['query.selection']:
                value = data[key]
                pairs[key] = value
        ret[node] = pairs

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


def create_node(vm_):
    '''
    Build and submit the XML to create a node
    '''
    # Start the tree
    content = ET.Element('ve')

    # Name of the instance
    name = ET.SubElement(content, 'name')
    name.text = vm_['name']

    # Description, defaults to name
    desc = ET.SubElement(content, 'description')
    desc.text = vm_.get('desc', vm_['name'])

    # How many CPU cores, and how fast they are
    cpu = ET.SubElement(content, 'cpu')
    cpu.attrib['number'] = vm_.get('cpu_number', '1')
    cpu.attrib['power'] = vm_.get('cpu_power', '1000')

    # How many megabytes of RAM
    ram = ET.SubElement(content, 'ram-size')
    ram.text = vm_.get('ram', '256')

    # Bandwidth available, in kbps
    bandwidth = ET.SubElement(content, 'bandwidth')
    bandwidth.text = vm_.get('bandwidth', '100')

    # How many public IPs will be assigned to this instance
    ip_num = ET.SubElement(content, 'no-of-public-ip')
    ip_num.text = vm_.get('ip_num', '1')

    # Size of the instance disk
    disk = ET.SubElement(content, 've-disk')
    disk.attrib['local'] = 'true'
    disk.attrib['size'] = vm_.get('disk_size', '10')

    # Attributes for the image
    image = show_image({'image': vm_['image']}, call='function')
    platform = ET.SubElement(content, 'platform')
    template = ET.SubElement(platform, 'template-info')
    template.attrib['name'] = vm_['image']
    os = ET.SubElement(platform, 'os-info')
    os.attrib['technology'] = image[vm_['image']]['technology']
    os.attrib['type'] = image[vm_['image']]['osType']

    # Username and password
    admin = ET.SubElement(content, 'admin')
    admin.attrib['login'] = vm_.get('ssh_username', 'root')
    admin.attrib['password'] = __opts__['PARALLELS.password']

    data = ET.tostring(content, encoding='UTF-8')

    node = query(action='ve',
                 method='POST',
                 data=data)
    return node


def create(vm_):
    '''
    Create a single VM from a data dict
    '''
    log.info('Creating Cloud VM {0}'.format(vm_['name']))
    deploy_script = script(vm_)

    try:
        data = create_node(vm_)
    except Exception as exc:
        err = ('Error creating {0} on PARALLELS\n\n'
               'The following exception was thrown when trying to '
               'run the initial deployment: \n{1}').format(
                       vm_['name'], exc.message
                       )
        sys.stderr.write(err)
        log.error(err)
        return False

    name = vm_['name']
    if not wait_until(name, 'CREATED'):
        return {'Error': 'Unable to start {0}, command timed out'.format(name)}
    start(vm_['name'], call='action')

    if not wait_until(name, 'STARTED'):
        return {'Error': 'Unable to start {0}, command timed out'.format(name)}

    data = show_instance(vm_['name'], call='action')

    waiting_for_ip = 0
    while 'public-ip' not in data['network']:
        log.debug('Salt node waiting for IP {0}'.format(waiting_for_ip))
        time.sleep(5)
        waiting_for_ip += 1
        data = show_instance(vm_['name'], call='action')

    comps = data['network']['public-ip']['address'].split('/')
    public_ip = comps[0]

    if __opts__['deploy'] is True:
        deploy_script = script(vm_)
        deploy_kwargs = {
            'host': public_ip,
            'username': 'root',
            'password': __opts__['PARALLELS.password'],
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


def query(action=None, command=None, args=None, method='GET', data=None):
    '''
    Make a web call to a Parallels provider
    '''
    path = __opts__['PARALLELS.url']
    auth_handler = urllib2.HTTPBasicAuthHandler()
    auth_handler.add_password(realm='Parallels Instance Manager',
                              uri=path,
                              user=__opts__['PARALLELS.user'],
                              passwd=__opts__['PARALLELS.password'])
    opener = urllib2.build_opener(auth_handler)
    urllib2.install_opener(opener)

    if action:
        path += action

    if command:
        path += '/{0}'.format(command)

    if type(args) is not dict:
        args = {}

    kwargs = {'data': data}
    if type(data) is str and '<?xml' in data:
        kwargs['headers'] = {
            'Content-type': 'application/xml',
        }

    if args:
        path += '?%s'
        params = urllib.urlencode(args)
        req = urllib2.Request(url=path % params, **kwargs)
    else:
        req = urllib2.Request(url=path, **kwargs)

    req.get_method = lambda: method

    log.debug('{0} {1}'.format(method, req.get_full_url()))
    if data:
        log.debug(data)

    try:
        result = urllib2.urlopen(req)
        log.debug('EC2 Response Status Code: {0}'.format(result.getcode()))

        if 'content-length' in result.headers:
            content = result.read()
            result.close()
            items = ET.fromstring(content)
            return items
        else:
            return {}
    except urllib2.URLError as exc:
        log.error('EC2 Response Status Code: {0} {1}'.format(exc.code,
                                                             exc.msg))
        root = ET.fromstring(exc.read())
        log.error(_xml_to_dict(root))
        return {'error': _xml_to_dict(root)}


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


def show_image(kwargs, call=None):
    '''
    Show the details from Parallels concerning an image
    '''
    if call != 'function':
        log.error(
            'The show_image function must be called with -f or --function.'
        )
        sys.exit(1)

    items = query(action='template', command=kwargs['image'])
    return {items.attrib['name']: items.attrib}


def show_instance(name, call=None):
    '''
    Show the details from Parallels concerning an instance
    '''
    if call != 'action':
        log.error(
            'The show_instance action must be called with -a or --action.'
        )
        sys.exit(1)

    items = query(action='ve', command=name)

    ret = {}
    for item in items:
        if 'text' in item.__dict__:
            ret[item.tag] = item.text
        else:
            ret[item.tag] = item.attrib

        if item._children:
            ret[item.tag] = {}
            children = item._children
            for child in children:
                ret[item.tag][child.tag] = child.attrib
    return ret


def wait_until(name, state, timeout=300):
    '''
    Wait until a specific state has been reached on  a node
    '''
    start = time.time()
    node = show_instance(name, call='action')
    while True:
        if node['state'] == state:
            return True
        time.sleep(1)
        if time.time() - start > timeout:
            return False
        node = show_instance(name, call='action')


def destroy(name, call=None):
    '''
    Destroy a node.

    CLI Example::

        salt-cloud --destroy mymachine
    '''
    node = show_instance(name, call='action')
    if node['state'] == 'STARTED':
        stop(name, call='action')
        if not wait_until(name, 'STOPPED'):
            return {'Error': 'Unable to destroy {0}, command timed out'.format(name)}

    data = query(action='ve', command=name, method='DELETE')

    if 'error' in data:
        return data['error']

    return {'Destroyed': '{0} was destroyed.'.format(name)}


def start(name, call=None):
    '''
    Start a node.

    CLI Example::

        salt-cloud -a start mymachine
    '''
    if call != 'action':
        log.error(
            'The show_instance action must be called with -a or --action.'
        )
        sys.exit(1)

    data = query(action='ve', command='{0}/start'.format(name), method='PUT')

    if 'error' in data:
        return data['error']

    return {'Started': '{0} was started.'.format(name)}


def stop(name, call=None):
    '''
    Stop a node.

    CLI Example::

        salt-cloud -a stop mymachine
    '''
    if call != 'action':
        log.error(
            'The show_instance action must be called with -a or --action.'
        )
        sys.exit(1)

    data = query(action='ve', command='{0}/stop'.format(name), method='PUT')

    if 'error' in data:
        return data['error']

    return {'Stopped': '{0} was stopped.'.format(name)}
