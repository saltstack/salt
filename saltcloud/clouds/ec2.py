'''
The EC2 Cloud Module
====================

The EC2 cloud module is used to interact with the Amazon Elastic Cloud
Computing. This driver is highly experimental! Use at your own risk!

To use the EC2 cloud module the following configuration parameters need to be
set in the main cloud config:

.. code-block:: yaml

    # The EC2 API authentication id
    EC2.id: GKTADJGHEIQSXMKKRBJ08H
    # The EC2 API authentication key
    EC2.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
    # The ssh keyname to use
    EC2.keyname: default
    # The amazon security group
    EC2.securitygroup: ssh_open
    # The location of the private key which corresponds to the keyname
    EC2.private_key: /root/default.pem

'''

# Import python libs
import os
import sys
import stat
import time
import logging
import pprint

# Import libs for talking to the EC2 API
import hmac
import hashlib
import binascii
import datetime
import urllib
import urllib2
import xml.etree.ElementTree as ET

# Import saltcloud libs
import saltcloud.utils
from saltcloud.utils import namespaced_function
from saltcloud.libcloudfuncs import *

# Import salt libs
import salt.output
from salt.exceptions import SaltException

# Get logging started
log = logging.getLogger(__name__)

size_map = {
    'Micro Instance': 't1.micro',
    'Small Instance': 'm1.small',
    'Medium Instance': 'm1.medium',
    'Large Instance': 'm1.large',
    'Extra Large Instance': 'm1.xlarge',
    'High-CPU Medium Instance': 'c1.medium',
    'High-CPU Extra Large Instance': 'c1.xlarge',
    'High-Memory Extra Large Instance': 'm2.xlarge',
    'High-Memory Double Extra Large Instance': 'm2.2xlarge',
    'High-Memory Quadruple Extra Large Instance': 'm2.4xlarge',
    'Cluster GPU Quadruple Extra Large Instance': 'cg1.4xlarge',
    'Cluster Compute Quadruple Extra Large Instance': 'cc1.4xlarge',
    'Cluster Compute Eight Extra Large Instance': 'cc2.8xlarge',
}

# Only load in this module if the EC2 configurations are in place
def __virtual__():
    '''
    Set up the libcloud funcstions and check for EC2 configs
    '''
    confs = [
        'EC2.id',
        'EC2.key',
        'EC2.keyname',
        'EC2.securitygroup',
        'EC2.private_key',
    ]
    for conf in confs:
        if conf not in __opts__:
            log.warning(
                '{0!r} not found in options. Not loading module.'.format(conf)
            )
            return False

    if not os.path.exists(__opts__['EC2.private_key']):
        raise SaltException(
            'The EC2 key file {0} does not exist\n'.format(
                __opts__['EC2.private_key']
            )
        )
    keymode = str(
        oct(stat.S_IMODE(os.stat(__opts__['EC2.private_key']).st_mode))
    )
    if keymode not in ('0400', '0600'):
        raise SaltException(
            'The EC2 key file {0} needs to be set to mode 0400 or '
            '0600\n'.format(
                __opts__['EC2.private_key']
            )
        )

    global avail_images, avail_sizes, script, destroy
    global list_nodes_select

    # open a connection in a specific region
    conn = get_conn(**{'location': get_location()})

    # Init the libcloud functions
    avail_images = namespaced_function(avail_images, globals(), (conn,))
    avail_sizes = namespaced_function(avail_sizes, globals(), (conn,))
    script = namespaced_function(script, globals(), (conn,))
    list_nodes_select = namespaced_function(list_nodes_select, globals(), (conn,))

    log.debug('Loading EC2 cloud compute module')
    return 'ec2'


EC2_LOCATIONS = {
    'ap-northeast-1': Provider.EC2_AP_NORTHEAST,
    'ap-southeast-1': Provider.EC2_AP_SOUTHEAST,
    'eu-west-1': Provider.EC2_EU_WEST,
    'sa-east-1': Provider.EC2_SA_EAST,
    'us-east-1': Provider.EC2_US_EAST,
    'us-west-1': Provider.EC2_US_WEST,
    'us-west-2': Provider.EC2_US_WEST_OREGON
}
DEFAULT_LOCATION = 'us-east-1'

if hasattr(Provider, 'EC2_AP_SOUTHEAST2'):
    EC2_LOCATIONS['ap-southeast-2'] = Provider.EC2_AP_SOUTHEAST2


def _xml_to_dict(xmltree):
    ''' 
    Convery an XML tree into a dict
    '''
    xmldict = {}
    for item in xmltree:
        name = item.tag
        if '}' in name:
            comps = name.split('}')
            name = comps[1]
        if not name in xmldict.keys():
            if len(item.getchildren()) > 0:
                xmldict[name] = _xml_to_dict(item)
            else:
                xmldict[name] = item.text
        else:
            if type(xmldict[name]) is not list:
                tempvar = xmldict[name]
                xmldict[name] = []
                xmldict[name].append(tempvar)
            xmldict[name].append(_xml_to_dict(item))
    return xmldict


def query(params=None, setname=None, requesturl=None, return_url=False,
          return_root=False):
    key = __opts__['EC2.key']
    keyid = __opts__['EC2.id']
    timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    
    if not requesturl:
        location = get_location()
        method = 'GET'
        endpoint = 'ec2.{0}.amazonaws.com'.format(location)
        params['AWSAccessKeyId'] = '{0}'.format(keyid)
        params['SignatureVersion'] = '2'
        params['SignatureMethod'] = 'HmacSHA256'
        params['Timestamp'] = '{0}'.format(timestamp)
        params['Version'] = '2010-08-31'
        keys = sorted(params.keys())
        values = map(params.get, keys)
        querystring = urllib.urlencode( list(zip(keys,values)) )
        
        uri = '{0}\n{1}\n/\n{2}'.format(method.encode('utf-8'),
                                       endpoint.encode('utf-8'),
                                       querystring.encode('utf-8'))
        
        hashed = hmac.new(key, uri, hashlib.sha256)
        sig = binascii.b2a_base64(hashed.digest())
        params['Signature'] = sig.strip()
        
        querystring = urllib.urlencode(params)
        requesturl = 'https://{0}/?{1}'.format(endpoint, querystring)

    log.debug('EC2 Request: {0}'.format(requesturl))
    result = urllib2.urlopen(requesturl)
    response = result.read()
    log.debug('EC2 Response Status Code: {0}'.format(result.getcode()))
    result.close()
    
    root = ET.fromstring(response)
    items = root[1]
    if return_root is True:
        items = root

    if setname:
        for item in range(0, len(root.getchildren())):
            comps = root[item].tag.split('}')
            if comps[1] == setname:
                items = root[item]
    
    ret = []
    for item in items:
        ret.append(_xml_to_dict(item))

    if return_url is True:
        return ret, requesturl
    return ret


def get_conn(**kwargs):
    '''
    Return a conn object for the passed VM data
    '''
    if 'location' in kwargs:
        location = kwargs['location']
        if location not in EC2_LOCATIONS:
            raise SaltException(
                'The specified location does not seem to be valid: '
                '{0}\n'.format(
                    location
                )
            )
    else:
        location = DEFAULT_LOCATION

    driver = get_driver(EC2_LOCATIONS[location])
    return driver(
        __opts__['EC2.id'],
        __opts__['EC2.key'],
    )


#NO CHANGES NEEDED
def keyname(vm_):
    '''
    Return the keyname
    '''
    return str(vm_.get('keyname', __opts__.get('EC2.keyname', '')))


#NO CHANGES NEEDED
def securitygroup(vm_):
    '''
    Return the security group
    '''
    return vm_.get(
        'securitygroup', __opts__.get('EC2.securitygroup', 'default')
    )

    # XXX: This code won't get executed. On purpose?
    securitygroups = vm_.get(
        'securitygroup', __opts__.get('EC2.securitygroup', 'default')
    )
    if not isinstance(securitygroups, list):
        securitygroup = securitygroups
        securitygroups = [securitygroup]
    return securitygroups


#NO CHANGES NEEDED
def ssh_username(vm_):
    '''
    Return the ssh_username. Defaults to 'ec2-user'.
    '''
    usernames = vm_.get(
        'ssh_username', __opts__.get('EC2.ssh_username', 'ec2-user')
    )
    if not isinstance(usernames, list):
        username = usernames
        usernames = [username]
    if not 'ec2-user' in usernames:
        usernames.append('ec2-user')
    if not 'ubuntu' in usernames:
        usernames.append('ubuntu')
    if not 'admin' in usernames:
        usernames.append('admin')
    if not 'bitnami' in usernames:
        usernames.append('bitnami')
    if not 'root' in usernames:
        usernames.append('root')
    return usernames


#NO CHANGES NEEDED
def ssh_interface(vm_):
    '''
    Return the ssh_interface type to connect to. Either 'public_ips' (default)
    or 'private_ips'.
    '''
    return vm_.get(
        'ssh_interface', __opts__.get('EC2.ssh_interface', 'public_ips')
    )


#NO CHANGES NEEDED
def get_location(vm_=None):
    '''
    Return the EC2 region to use, in this order:
        - CLI parameter
        - Cloud profile setting
        - Global salt-cloud config
    '''
    if __opts__['location'] != '':
        return __opts__['location']
    elif vm_ is not None and 'location' in vm_:
        return vm_['location']
    else:
        return __opts__.get('EC2.location', DEFAULT_LOCATION)


#NO CHANGES NEEDED
def get_availability_zone(conn, vm_):
    '''
    Return the availability zone to use
    '''
    locations = conn.list_locations()
    avz = None
    if 'availability_zone' in vm_:
        avz = vm_['availability_zone']
    elif 'EC2.availability_zone' in __opts__:
        avz = __opts__['EC2.availability_zone']

    if avz is None:
        # Default to first zone
        return locations[0]
    for loc in locations:
        if loc.availability_zone.name == avz:
            return loc


def create(vm_=None, call=None):
    '''
    Create a single VM from a data dict
    '''
    if call:
        log.error('You cannot create an instance with -a or -f.')
        sys.exit(1)

    location = get_location(vm_)
    log.info('Creating Cloud VM {0} in {1}'.format(vm_['name'], location))
    usernames = ssh_username(vm_)
    kwargs = {'ssh_key': __opts__['EC2.private_key']}
    params = {'Action': 'RunInstances',
              'MinCount': '1',
              'MaxCount': '1'}
    params['ImageId'] = vm_['image']
    if vm_['size'] in size_map:
        params['InstanceType'] = size_map[vm_['size']]
    else:
        params['InstanceType'] = vm_['size']
    ex_keyname = keyname(vm_)
    if ex_keyname:
        kwargs['ex_keyname'] = ex_keyname
        params['KeyName'] = ex_keyname
    ex_securitygroup = securitygroup(vm_)
    if ex_securitygroup:
        kwargs['ex_securitygroup'] = ex_securitygroup
        params['SecurityGroup.1'] = ex_securitygroup

    if 'delvol_on_destroy' in vm_:
        value = vm_['delvol_on_destroy']
        if value is True:
            value = 'true'
        elif value is False:
            value = 'false'

        params['BlockDeviceMapping.1.DeviceName'] = '/dev/sda1'
        params['BlockDeviceMapping.1.Ebs.DeleteOnTermination'] = value

    try:
        data = query(params, 'instancesSet')
    except Exception as exc:
        err = (
            'Error creating {0} on EC2\n\n'
            'The following exception was thrown by libcloud when trying to '
            'run the initial deployment: \n{1}').format(
                vm_['name'], exc
        )
        sys.stderr.write(err)
        log.error(err)
        return False

    instance_id = data[0]['instanceId']
    set_tags(instance_id, {'Name': vm_['name']}, call='action')
    log.info('Created node {0}'.format(vm_['name']))
    waiting_for_ip = 0

    params = {'Action': 'DescribeInstances',
              'InstanceId.1': instance_id}
    data, requesturl = query(params, return_url=True)

    while 'ipAddress' not in data[0]['instancesSet']['item']:
        log.debug('Salt node waiting for IP {0}'.format(waiting_for_ip))
        time.sleep(5)
        waiting_for_ip += 1
        data = query(params, requesturl=requesturl)

    if ssh_interface(vm_) == "private_ips":
        ip_address = data[0]['instancesSet']['item']['privateIpAddress']
        log.info('Salt node data. Private_ip: {0}'.format(ip_address))
    else:
        ip_address = data[0]['instancesSet']['item']['ipAddress']
        log.info('Salt node data. Public_ip: {0}'.format(ip_address))

    if saltcloud.utils.wait_for_ssh(ip_address):
        for user in usernames:
            if saltcloud.utils.wait_for_passwd(
                    host=ip_address, username=user, ssh_timeout=60,
                    key_filename=__opts__['EC2.private_key']):
                username = user
                break
    sudo = True
    if 'sudo' in vm_.keys():
        sudo = vm_['sudo']

    if __opts__['deploy'] is True:
        deploy_script = script(vm_)
        deploy_kwargs = {
            'host': ip_address,
            'username': username,
            'key_filename': __opts__['EC2.private_key'],
            'deploy_command': 'bash /tmp/deploy.sh',
            'tty': True,
            'script': deploy_script.script,
            'name': vm_['name'],
            'sudo': sudo,
            'start_action': __opts__['start_action'],
            'conf_file': __opts__['conf_file'],
            'sock_dir': __opts__['sock_dir'],
            'minion_pem': vm_['priv_key'],
            'minion_pub': vm_['pub_key'],
            'keep_tmp': __opts__['keep_tmp'],
        }
        deploy_kwargs['minion_conf'] = saltcloud.utils.minion_conf_string(
            __opts__, vm_
        )

        if 'script_args' in vm_:
            deploy_kwargs['script_args'] = vm_['script_args']

        # Deploy salt-master files, if necessary
        if 'make_master' in vm_ and vm_['make_master'] is True:
            deploy_kwargs['master_pub'] = vm_['master_pub']
            deploy_kwargs['master_pem'] = vm_['master_pem']
            master_conf = saltcloud.utils.master_conf_string(__opts__, vm_)
            if master_conf:
                deploy_kwargs['master_conf'] = master_conf

        if username == 'root':
            deploy_kwargs['deploy_command'] = '/tmp/deploy.sh'

        deployed = saltcloud.utils.deploy_script(**deploy_kwargs)
        if deployed:
            log.info('Salt installed on {name}'.format(**vm_))
        else:
            log.error('Failed to start Salt on Cloud VM {name}'.format(**vm_))

    log.info(
        'Created Cloud VM {name} with the following values:'.format(**vm_)
    )
    pprint.pprint(data[0]['instancesSet']['item'])
    volumes = vm_.get('map_volumes')
    if volumes:
        log.info('Create and attach volumes to node {0}'.format(data.name))
        create_attach_volumes(volumes, location, data)


def create_attach_volumes(volumes, location, data):
    '''
    Create and attach volumes to created node
    '''
    conn = get_conn(location=location)
    node_avz = data.__dict__.get('extra').get('availability')
    avz = None
    for avz in conn.list_locations():
        if avz.availability_zone.name == node_avz:
            break
    for volume in volumes:
        volume_name = '{0} on {1}'.format(volume['device'], data.name)
        created_volume = conn.create_volume(volume['size'], volume_name, avz)
        attach = conn.attach_volume(data, created_volume, volume['device'])
        if attach:
            log.info(
                '{0} attached to {1} (aka {2}) as device {3}'.format(
                    created_volume.id, data.id, data.name, volume['device']
                )
            )


def stop(name, call=None):
    '''
    Stop a node
    '''
    if call != 'action':
        print('The stop action must be called with -a or --action.')
        sys.exit(1)

    log.info('Stopping node {0}'.format(name))

    instances = list_nodes_full()
    instance_id = instances[name]['instanceId']

    params = {'Action': 'StopInstances',
              'InstanceId.1': instance_id}
    result = query(params)

    pprint.pprint(result)


def start(name, call=None):
    '''
    Start a node
    '''
    if call != 'action':
        print('The start action must be called with -a or --action.')
        sys.exit(1)

    log.info('Starting node {0}'.format(name))

    instances = list_nodes_full()
    instance_id = instances[name]['instanceId']

    params = {'Action': 'StartInstances',
              'InstanceId.1': instance_id}
    result = query(params)

    pprint.pprint(result)


def set_tags(name, tags, call=None):
    '''
    Set tags for a node

    CLI Example::

        salt-cloud -a set_tags mymachine tag1=somestuff tag2='Other stuff'
    '''
    if call != 'action':
        print('The set_tags action must be called with -a or --action.')
        sys.exit(1)

    instances = list_nodes_full()
    instance_id = instances[name]['instanceId']
    params = {'Action': 'CreateTags',
              'ResourceId.1': instance_id}
    count = 1
    for tag in tags:
        params['Tag.{0}.Key'.format(count)] = tag
        params['Tag.{0}.Value'.format(count)] = tags[tag]
        count += 1
    result = query(params, setname='tagSet')

    if 'Name' in tags:
        return get_tags(tags['Name'], call='action')

    return get_tags(name)


def get_tags(name, call=None):
    '''
    Retrieve tags for a node
    '''
    if call != 'action':
        print('The get_tags action must be called with -a or --action.')
        sys.exit(1)

    if ',' in name:
        names = name.split(',')
    else:
        names = [name]

    instances = list_nodes_full()
    instance_id = instances[name]['instanceId']
    params = {'Action': 'DescribeTags',
              'Filter.1.Name': 'resource-id',
              'Filter.1.Value': instance_id}
    result = query(params, setname='tagSet')
    pprint.pprint(result)
    return result


def del_tags(name, kwargs, call=None):
    '''
    Delete tags for a node

    CLI Example::

        salt-cloud -a del_tags mymachine tag1,tag2,tag3
    '''
    if call != 'action':
        print('The del_tags action must be called with -a or --action.')
        sys.exit(1)

    instances = list_nodes_full()
    instance_id = instances[name]['instanceId']
    params = {'Action': 'DeleteTags',
              'ResourceId.1': instance_id}
    count = 1
    for tag in kwargs['tags'].split(','):
        params['Tag.{0}.Key'.format(count)] = tag
        count += 1
    result = query(params, setname='tagSet')
    return get_tags(name)


def rename(name, kwargs, call=None):
    '''
    Properly rename a node. Pass in the new name as "new name".

    CLI Example::

        salt-cloud -a rename mymachine newname=yourmachine
    '''
    if call != 'action':
        print('The rename action must be called with -a or --action.')
        sys.exit(1)

    log.info('Renaming {0} to {1}'.format(name, kwargs['newname']))

    instances = list_nodes_full()
    instance_id = instances[name]['instanceId']

    set_tags(name, {'Name': kwargs['newname']})
    saltcloud.utils.rename_key(
        __opts__['pki_dir'], name, kwargs['newname']
    )


def destroy(name, call=None):
    '''
    Wrap core libcloudfuncs destroy method, adding check for termination
    protection
    '''
    nodes = list_nodes_full()
    instance_id = nodes[name]['instanceId']

    params = {'Action': 'TerminateInstances',
              'InstanceId.1': instance_id}
    result = query(params)
    log.info(result)
    pprint.pprint(result)


def show_image(kwargs, call=None):
    '''
    Show the details from EC2 concerning an AMI
    '''
    if call != 'function':
        print('This function must be called with -f or --function.')
        sys.exit(1)

    params = {'ImageId.1': kwargs['image'],
              'Action': 'DescribeImages'}
    result = query(params)
    log.info(result)
    pprint.pprint(result)


def show_instance(name, call=None):
    '''
    Show the details from EC2 concerning an AMI
    '''
    if call != 'action':
        print('The show_instance action must be called with -a or --action.')
        sys.exit(1)

    nodes = list_nodes_full()
    pprint.pprint(nodes[name])
    return nodes[name]


def list_nodes_full():
    '''
    Return a list of the VMs that are on the provider
    '''
    ret = {}

    params = {'Action': 'DescribeInstances'}
    instances = query(params)

    for instance in instances:
        if 'tagSet' in instance['instancesSet']['item']:
            tagset = instance['instancesSet']['item']['tagSet']
            if type(tagset['item']) is list:
                for tag in tagset['item']:
                    if tag['key'] == 'Name':
                        name = tag['value']
            else:
                name = instance['instancesSet']['item']['tagSet']['item']['value']
        else:
            name = instance['instancesSet']['item']['instanceId']
        ret[name] = instance['instancesSet']['item']
        ret[name]['id'] = instance['instancesSet']['item']['instanceId'],
        ret[name]['image'] = instance['instancesSet']['item']['imageId'],
        ret[name]['size'] = instance['instancesSet']['item']['instanceType'],
        ret[name]['state'] = instance['instancesSet']['item']['instanceState']['name']
        ret[name]['private_ips'] = []
        ret[name]['public_ips'] = []
        if 'privateIpAddress' in instance['instancesSet']['item']:
            ret[name]['private_ips'].append(instance['instancesSet']['item']['privateIpAddress'])
        if 'ipAddress' in instance['instancesSet']['item']:
            ret[name]['public_ips'].append(instance['instancesSet']['item']['ipAddress'])
    return ret


def list_nodes():
    '''
    Return a list of the VMs that are on the provider
    '''
    ret = {}

    nodes = list_nodes_full()
    for node in nodes:
        ret[node] = {
            'id': nodes[node]['id'],
            'image': nodes[node]['image'],
            'size': nodes[node]['size'],
            'state': nodes[node]['state'],
            'private_ips': nodes[node]['private_ips'],
            'public_ips': nodes[node]['public_ips'],
        }

    return ret


def show_term_protect(name, instance_id=None, call=None):
    '''
    Show the details from EC2 concerning an AMI
    '''
    if call != 'action':
        print('The show_term_protect action must be called with '
              '-a or --action.')
        sys.exit(1)

    if not instance_id:
        instances = list_nodes_full()
        instance_id = instances[name]['instanceId']
    params = {'Action': 'DescribeInstanceAttribute',
              'InstanceId': instance_id,
              'Attribute': 'disableApiTermination'}
    result = query(params, return_root=True)

    disable_protect = False
    for item in result:
        if 'value' in item:
            disable_protect = item['value']
            break
    
    if disable_protect == 'true':
        print('Termination Protection is enabled for {0}'.format(name))
    else:
        print('Termination Protection is disabled for {0}'.format(name))


def enable_term_protect(name, call=None):
    '''
    Enable termination protection on a node

    CLI Example::

        salt-cloud -a enable_term_protect mymachine
    '''
    if call != 'action':
        print('The enable_term_protect action must be called with '
              '-a or --action.')
        sys.exit(1)

    _toggle_term_protect(name, 'true')


def disable_term_protect(name, call=None):
    '''
    Disable termination protection on a node

    CLI Example::

        salt-cloud -a disable_term_protect mymachine
    '''
    if call != 'action':
        print('The disable_term_protect action must be called with '
              '-a or --action.')
        sys.exit(1)

    _toggle_term_protect(name, 'false')


def _toggle_term_protect(name, value):
    '''
    Disable termination protection on a node

    CLI Example::

        salt-cloud -a disable_term_protect mymachine
    '''
    instances = list_nodes_full()
    instance_id = instances[name]['instanceId']
    params = {'Action': 'ModifyInstanceAttribute',
              'InstanceId': instance_id,
              'DisableApiTermination.Value': value}
    result = query(params, return_root=True)

    show_term_protect(name, instance_id, call='action')


def keepvol_on_destroy(name, call=None):
    '''
    Do not delete root EBS volume upon instance termination

    CLI Example::

        salt-cloud -a keepvol_on_destroy mymachine
    '''
    if call != 'action':
        print('The keepvol_on_destroy action must be called with '
              '-a or --action.')
        sys.exit(1)

    _toggle_delvol(name=name, value='false')


def delvol_on_destroy(name, call=None):
    '''
    Delete root EBS volume upon instance termination

    CLI Example::

        salt-cloud -a delvol_on_destroy mymachine
    '''
    if call != 'action':
        print('The delvol_on_destroy action must be called with '
              '-a or --action.')
        sys.exit(1)

    _toggle_delvol(name=name, value='true')


def _toggle_delvol(name=None, instance_id=None, value=None, requesturl=None):
    '''
    Disable termination protection on a node

    CLI Example::

        salt-cloud -a disable_term_protect mymachine
    '''
    if not instance_id:
        instances = list_nodes_full()
        instance_id = instances[name]['instanceId']

    if requesturl:
        data = query(requesturl=requesturl)
    else:
        params = {'Action': 'DescribeInstances',
                  'InstanceId.1': instance_id}
        data, requesturl = query(params, return_url=True)

    blockmap = data[0]['instancesSet']['item']['blockDeviceMapping']
    device_name = blockmap['item']['deviceName']

    params = {'Action': 'ModifyInstanceAttribute',
              'InstanceId': instance_id,
              'BlockDeviceMapping.1.DeviceName': device_name,
              'BlockDeviceMapping.1.Ebs.DeleteOnTermination': value}
    result = query(params, return_root=True)

    pprint.pprint(query(requesturl=requesturl))

