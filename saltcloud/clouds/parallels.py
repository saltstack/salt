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
            ret[name]['private_ips'] = [node['network']['private-ip']['address']]
        if 'public-ip' in node['network']:
            ret[name]['public_ips'] = [node['network']['public-ip']['address']]

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


def query(action=None, command=None, args=None, method='GET'):
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

    if args:
        path += '?%s'
        params = urllib.urlencode(args)
        req = urllib2.Request(url=path % params)
    else:
        req = urllib2.Request(url=path)

    req.get_method = lambda: method

    try:
        result = urllib2.urlopen(req)
        log.debug(result.geturl())
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


def destroy(name, call=None):
    '''
    Destroy a node.

    CLI Example::

        salt-cloud --destroy mymachine
    '''
    stop(name, call='action')
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
