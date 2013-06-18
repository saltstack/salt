'''
Parallels Cloud Module
======================

The Parallels cloud module is used to control access to cloud providers using
the Parallels VPS system.

Use of this module requires, if using the old salt cloud configuration syntax,
the following PARALLELS parameters to be set in the cloud configuration file.

.. code-block:: yaml

    # Parallels account information
    PARALLELS.user: myuser
    PARALLELS.password: mypassword
    PARALLELS.url: https://api.cloud.xmission.com:4465/paci/v1.0/


Using the new format, set up the cloud configuration at
 ``/etc/salt/cloud.providers`` or
 ``/etc/salt/cloud.providers.d/parallels.conf``:


.. code-block:: yaml

    my-parallels-config:
      # Parallels account information
      user: myuser
      password: mypassword
      url: https://api.cloud.xmission.com:4465/paci/v1.0/
      provider: parallels

'''

# Import python libs
import time
import pprint
import urllib
import urllib2
import logging
import xml.etree.ElementTree as ET

# Import salt libs
import salt.utils

# Import salt cloud libs
import saltcloud.utils
import saltcloud.config as config
from saltcloud.exceptions import (
    SaltCloudNotFound,
    SaltCloudSystemExit,
    SaltCloudExecutionFailure,
    SaltCloudExecutionTimeout
)

# Get logging started
log = logging.getLogger(__name__)


# Only load in this module if the PARALLELS configurations are in place
def __virtual__():
    '''
    Check for PARALLELS configurations
    '''
    if get_configured_provider() is False:
        log.debug(
            'There is no Parallels cloud provider configuration available. '
            'Not loading module.'
        )
        return False

    log.debug('Loading Parallels cloud module')
    return 'parallels'


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or 'parallels',
        ('user',)
    )


def avail_images():
    '''
    Return a list of the images that are on the provider
    '''
    items = query(action='template')
    ret = {}
    for item in items:
        ret[item.attrib['name']] = item.attrib

    return ret


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
            ret[name]['private_ips'] = [
                node['network']['private-ip']['address']
            ]
        if 'public-ip' in node['network']:
            ret[name]['public_ips'] = [
                node['network']['public-ip']['address']
            ]

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
    vm_image = config.get_config_value(
        'image', vm_, __opts__, search_global=False
    )
    for image in images:
        if str(vm_image) in (images[image]['name'], images[image]['id']):
            return images[image]['id']
    raise SaltCloudNotFound('The specified image could not be found.')


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
    desc.text = config.get_config_value(
        'desc', vm_, __opts__, default=vm_['name'], search_global=False
    )

    # How many CPU cores, and how fast they are
    cpu = ET.SubElement(content, 'cpu')
    cpu.attrib['number'] = config.get_config_value(
        'cpu_number', vm_, __opts__, default='1', search_global=False
    )
    cpu.attrib['power'] = config.get_config_value(
        'cpu_power', vm_, __opts__, default='1000', search_global=False
    )

    # How many megabytes of RAM
    ram = ET.SubElement(content, 'ram-size')
    ram.text = config.get_config_value(
        'ram', vm_, __opts__, default='256', search_global=False
    )

    # Bandwidth available, in kbps
    bandwidth = ET.SubElement(content, 'bandwidth')
    bandwidth.text = config.get_config_value(
        'bandwidth', vm_, __opts__, default='100', search_global=False
    )

    # How many public IPs will be assigned to this instance
    ip_num = ET.SubElement(content, 'no-of-public-ip')
    ip_num.text = config.get_config_value(
        'ip_num', vm_, __opts__, default='1', search_global=False
    )

    # Size of the instance disk
    disk = ET.SubElement(content, 've-disk')
    disk.attrib['local'] = 'true'
    disk.attrib['size'] = config.get_config_value(
        'disk_size', vm_, __opts__, default='10', search_global=False
    )

    # Attributes for the image
    vm_image = config.get_config_value(
        'image', vm_, __opts__, search_global=False
    )
    image = show_image({'image': vm_image}, call='function')
    platform = ET.SubElement(content, 'platform')
    template = ET.SubElement(platform, 'template-info')
    template.attrib['name'] = vm_image
    os_info = ET.SubElement(platform, 'os-info')
    os_info.attrib['technology'] = image[vm_image]['technology']
    os_info.attrib['type'] = image[vm_image]['osType']

    # Username and password
    admin = ET.SubElement(content, 'admin')
    admin.attrib['login'] = config.get_config_value(
        'ssh_username', vm_, __opts__, default='root'
    )
    admin.attrib['password'] = config.get_config_value(
        'password', vm_, __opts__, search_global=False
    )

    data = ET.tostring(content, encoding='UTF-8')

    node = query(action='ve', method='POST', data=data)
    return node


def create(vm_):
    '''
    Create a single VM from a data dict
    '''
    deploy = config.get_config_value('deploy', vm_, __opts__)
    if deploy is True and salt.utils.which('sshpass') is None:
        raise SaltCloudSystemExit(
            'Cannot deploy salt in a VM if the \'sshpass\' binary is not '
            'present on the system.'
        )

    log.info('Creating Cloud VM {0}'.format(vm_['name']))

    try:
        data = create_node(vm_)
    except Exception as exc:
        log.error(
            'Error creating {0} on PARALLELS\n\n'
            'The following exception was thrown when trying to '
            'run the initial deployment: \n{1}'.format(
                vm_['name'], exc.message
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info=log.isEnabledFor(logging.DEBUG)
        )
        return False

    name = vm_['name']
    if not wait_until(name, 'CREATED'):
        return {'Error': 'Unable to start {0}, command timed out'.format(name)}
    start(vm_['name'], call='action')

    if not wait_until(name, 'STARTED'):
        return {'Error': 'Unable to start {0}, command timed out'.format(name)}

    def __query_node_data(vm_name):
        data = show_instance(vm_name, call='action')
        if 'public-ip' not in data['network']:
            # Trigger another iteration
            return
        return data

    try:
        data = saltcloud.utils.wait_for_ip(
            __query_node_data,
            update_args=(vm_['name'],),
        )
    except (SaltCloudExecutionTimeout, SaltCloudExecutionFailure) as exc:
        try:
            # It might be already up, let's destroy it!
            destroy(vm_['name'])
        except SaltCloudSystemExit:
            pass
        finally:
            raise SaltCloudSystemExit(exc.message)

    comps = data['network']['public-ip']['address'].split('/')
    public_ip = comps[0]

    if config.get_config_value('deploy', vm_, __opts__) is True:
        deploy_script = script(vm_)
        deploy_kwargs = {
            'host': public_ip,
            'username': 'root',
            'password': config.get_config_value(
                'password', vm_, __opts__, search_global=False
            ),
            'script': deploy_script,
            'name': vm_['name'],
            'deploy_command': '/tmp/deploy.sh',
            'start_action': __opts__['start_action'],
            'sock_dir': __opts__['sock_dir'],
            'conf_file': __opts__['conf_file'],
            'minion_pem': vm_['priv_key'],
            'minion_pub': vm_['pub_key'],
            'keep_tmp': __opts__['keep_tmp'],
            'preseed_minion_keys': vm_.get('preseed_minion_keys', None),
            'display_ssh_output': config.get_config_value(
                'display_ssh_output', vm_, __opts__, default=True
            ),
            'script_args': config.get_config_value(
                'script_args', vm_, __opts__
            ),
            'script_env': config.get_config_value('script_env', vm_, __opts__),
            'minion_conf': saltcloud.utils.minion_conf_string(__opts__, vm_)
        }

        # Deploy salt-master files, if necessary
        if config.get_config_value('make_master', vm_, __opts__) is True:
            deploy_kwargs['make_master'] = True
            deploy_kwargs['master_pub'] = vm_['master_pub']
            deploy_kwargs['master_pem'] = vm_['master_pem']
            master_conf = saltcloud.utils.master_config(__opts__, vm_)
            deploy_kwargs['master_conf'] = saltcloud.utils.salt_config_to_yaml(
                master_conf
            )

            if master_conf.get('syndic_master', None):
                deploy_kwargs['make_syndic'] = True

        deploy_kwargs['make_minion'] = config.get_config_value(
            'make_minion', vm_, __opts__, default=True
        )

        # Store what was used to the deploy the VM
        data['deploy_kwargs'] = deploy_kwargs

        deployed = saltcloud.utils.deploy_script(**deploy_kwargs)
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
            vm_, pprint.pformat(data)
        )
    )

    return data


def query(action=None, command=None, args=None, method='GET', data=None):
    '''
    Make a web call to a Parallels provider
    '''
    path = config.get_config_value(
        'url', get_configured_provider(), __opts__, search_global=False
    )
    auth_handler = urllib2.HTTPBasicAuthHandler()
    auth_handler.add_password(
        realm='Parallels Instance Manager',
        uri=path,
        user=config.get_config_value(
            'user', get_configured_provider(), __opts__, search_global=False
        ),
        passwd=config.get_config_value(
            'password', get_configured_provider(), __opts__,
            search_global=False
        )
    )
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
        log.debug(
            'PARALLELS Response Status Code: {0}'.format(
                result.getcode()
            )
        )

        if 'content-length' in result.headers:
            content = result.read()
            result.close()
            items = ET.fromstring(content)
            return items

        return {}
    except urllib2.URLError as exc:
        log.error(
            'PARALLELS Response Status Code: {0} {1}'.format(
                exc.code,
                exc.msg
            )
        )
        root = ET.fromstring(exc.read())
        log.error(root)
        return {'error': root}


def script(vm_):
    '''
    Return the script deployment object
    '''
    minion = saltcloud.utils.minion_conf_string(__opts__, vm_)
    return saltcloud.utils.os_script(
        config.get_config_value('script', vm_, __opts__),
        vm_, __opts__, minion
    )


def show_image(kwargs, call=None):
    '''
    Show the details from Parallels concerning an image
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The show_image function must be called with -f or --function.'
        )

    items = query(action='template', command=kwargs['image'])
    return {items.attrib['name']: items.attrib}


def show_instance(name, call=None):
    '''
    Show the details from Parallels concerning an instance
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The show_instance action must be called with -a or --action.'
        )

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
    start_time = time.time()
    node = show_instance(name, call='action')
    while True:
        if node['state'] == state:
            return True
        time.sleep(1)
        if time.time() - start_time > timeout:
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
            return {
                'Error': 'Unable to destroy {0}, command timed out'.format(
                    name
                )
            }

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
        raise SaltCloudSystemExit(
            'The show_instance action must be called with -a or --action.'
        )

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
        raise SaltCloudSystemExit(
            'The show_instance action must be called with -a or --action.'
        )

    data = query(action='ve', command='{0}/stop'.format(name), method='PUT')

    if 'error' in data:
        return data['error']

    return {'Stopped': '{0} was stopped.'.format(name)}
