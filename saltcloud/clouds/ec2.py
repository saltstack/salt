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

    # Be default, service_url is set to amazonaws.com. If you are using this
    # driver for something other than Amazon EC2, change it here:
    EC2.service_url: amazonaws.com

    # The endpoint that is ultimately used is usually formed using the region
    # and the service_url. If you would like to override that entirely, you can
    # explicitly define the endpoint:
    EC2.endpoint: myendpoint.example.com:1138/services/Cloud

'''

# Import python libs
import os
import sys
import stat
import time
import uuid
import logging
import yaml

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
            log.debug(
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
    Convert an XML tree into a dict
    '''
    if len(xmltree.getchildren()) < 1:
        name = xmltree.tag
        if '}' in name:
            comps = name.split('}')
            name = comps[1]
        return {name: xmltree.text}

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


def query(params=None, setname=None, requesturl=None, location=None,
          return_url=False, return_root=False):
    key = __opts__['EC2.key']
    keyid = __opts__['EC2.id']
    if 'EC2.service_url' in __opts__:
        service_url = __opts__['EC2.service_url']
    else:
        service_url = 'amazonaws.com'
    timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

    if not location:
        location = get_location()

    if not requesturl:
        method = 'GET'

        if 'EC2.endpoint' in __opts__:
            endpoint = __opts__['EC2.endpoint']
        else:
            endpoint = 'ec2.{0}.{1}'.format(location, service_url)

        params['AWSAccessKeyId'] = '{0}'.format(keyid)
        params['SignatureVersion'] = '2'
        params['SignatureMethod'] = 'HmacSHA256'
        params['Timestamp'] = '{0}'.format(timestamp)
        params['Version'] = '2010-08-31'
        keys = sorted(params.keys())
        values = map(params.get, keys)
        querystring = urllib.urlencode(list(zip(keys, values)))

        uri = '{0}\n{1}\n/\n{2}'.format(method.encode('utf-8'),
                                        endpoint.encode('utf-8'),
                                        querystring.encode('utf-8'))

        hashed = hmac.new(key, uri, hashlib.sha256)
        sig = binascii.b2a_base64(hashed.digest())
        params['Signature'] = sig.strip()

        querystring = urllib.urlencode(params)
        requesturl = 'https://{0}/?{1}'.format(endpoint, querystring)

    log.debug('EC2 Request: {0}'.format(requesturl))
    try:
        result = urllib2.urlopen(requesturl)
        log.debug('EC2 Response Status Code: {0}'.format(result.getcode()))
    except urllib2.URLError as exc:
        log.error('EC2 Response Status Code: {0} {1}'.format(exc.code,
                                                             exc.msg))
        root = ET.fromstring(exc.read())
        log.error(_xml_to_dict(root))
        return {'error': _xml_to_dict(root)}

    response = result.read()
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


def avail_sizes():
    '''
    Return a dict of all available VM images on the cloud provider with
    relevant data. Latest version can be found at:

    http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instance-types.html
    '''
    sizes = {
        'Cluster Compute': {
            'cc2.8xlarge': {
                'id': 'cc2.8xlarge',
                'cores': '16 (2 x Intel Xeon E5-2670, eight-core with '
                         'hyperthread)',
                'disk': '3360 GiB (4 x 840 GiB)',
                'ram': '60.5 GiB'},
            'cc1.4xlarge': {
                'id': 'cc1.4xlarge',
                'cores': '8 (2 x Intel Xeon X5570, quad-core with '
                         'hyperthread)',
                'disk': '1690 GiB (2 x 840 GiB)',
                'ram': '22.5 GiB'},
            },
        'Cluster CPU': {
            'cg1.4xlarge': {
                'id': 'cg1.4xlarge',
                'cores': '8 (2 x Intel Xeon X5570, quad-core with '
                         'hyperthread), plus 2 NVIDIA Tesla M2050 GPUs',
                'disk': '1680 GiB (2 x 840 GiB)',
                'ram': '22.5 GiB'},
            },
        'High CPU': {
            'c1.xlarge': {
                'id': 'c1.xlarge',
                'cores': '8 (with 2.5 ECUs each)',
                'disk': '1680 GiB (4 x 420 GiB)',
                'ram': '8 GiB'},
            'c1.medium': {
                'id': 'c1.medium',
                'cores': '2 (with 2.5 ECUs each)',
                'disk': '340 GiB (1 x 340 GiB)',
                'ram': '1.7 GiB'},
            },
        'High I/O': {
            'hi1.4xlarge': {
                'id': 'hi1.4xlarge',
                'cores': '8 (with 4.37 ECUs each)',
                'disk': '2 TiB',
                'ram': '60.5 GiB'},
            },
        'High Memory': {
            'm2.2xlarge': {
                'id': 'm2.2xlarge',
                'cores': '4 (with 3.25 ECUs each)',
                'disk': '840 GiB (1 x 840 GiB)',
                'ram': '34.2 GiB'},
            'm2.xlarge': {
                'id': 'm2.xlarge',
                'cores': '2 (with 3.25 ECUs each)',
                'disk': '410 GiB (1 x 410 GiB)',
                'ram': '17.1 GiB'},
            'm2.4xlarge': {
                'id': 'm2.4xlarge',
                'cores': '8 (with 3.25 ECUs each)',
                'disk': '1680 GiB (2 x 840 GiB)',
                'ram': '68.4 GiB'},
            },
        'High-Memory Cluster': {
            'cr1.8xlarge': {
                'id': 'cr1.8xlarge',
                'cores': '16 (2 x Intel Xeon E5-2670, eight-core)',
                'disk': '240 GiB (2 x 120 GiB SSD)',
                'ram': '244 GiB'},
            },
        'High Storage': {
            'hs1.8xlarge': {
                'id': 'hs1.8xlarge',
                'cores': '16 (8 cores + 8 hyperthreads)',
                'disk': '48 TiB (24 x 2 TiB hard disk drives)',
                'ram': '117 GiB'},
            },
        'Micro': {
            't1.micro': {
                'id': 't1.micro',
                'cores': '1',
                'disk': 'EBS',
                'ram': '615 MiB'},
            },
        'Standard': {
            'm1.xlarge': {
                'id': 'm1.xlarge',
                'cores': '4 (with 2 ECUs each)',
                'disk': '1680 GB (4 x 420 GiB)',
                'ram': '15 GiB'},
            'm1.large': {
                'id': 'm1.large',
                'cores': '2 (with 2 ECUs each)',
                'disk': '840 GiB (2 x 420 GiB)',
                'ram': '7.5 GiB'},
            'm1.medium': {
                'id': 'm1.medium',
                'cores': '1',
                'disk': '400 GiB',
                'ram': '3.75 GiB'},
            'm1.small': {
                'id': 'm1.small',
                'cores': '1',
                'disk': '150 GiB',
                'ram': '1.7 GiB'},
            'm3.2xlarge': {
                'id': 'm3.2xlarge',
                'cores': '8 (with 3.25 ECUs each)',
                'disk': 'EBS',
                'ram': '30 GiB'},
            'm3.xlarge': {
                'id': 'm3.xlarge',
                'cores': '4 (with 3.25 ECUs each)',
                'disk': 'EBS',
                'ram': '15 GiB'},
            }
    }
    return sizes


def avail_images():
    '''
    Return a dict of all available VM images on the cloud provider.
    '''
    ret = {}
    params = {'Action': 'DescribeImages'}
    images = query(params)
    for image in images:
        ret[image['imageId']] = image
    return ret


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


def keyname(vm_):
    '''
    Return the keyname
    '''
    return str(vm_.get('keyname', __opts__.get('EC2.keyname', '')))


def securitygroup(vm_):
    '''
    Return the security group
    '''
    return vm_.get(
        'securitygroup', __opts__.get('EC2.securitygroup', 'default')
    )


def ssh_username(vm_):
    '''
    Return the ssh_username. Defaults to a built-in list of users for trying.
    '''
    usernames = vm_.get('ssh_username', __opts__.get('EC2.ssh_username', []))
    if not isinstance(usernames, list):
        usernames = [usernames]

    # get rid of None's or empty names
    usernames = filter(lambda x: x, usernames)

    # Add common usernames to the list to be tested
    for name in ('ec2-user', 'ubuntu', 'admin', 'bitnami', 'root'):
        if name not in usernames:
            usernames.append(name)
    return usernames


def ssh_interface(vm_):
    '''
    Return the ssh_interface type to connect to. Either 'public_ips' (default)
    or 'private_ips'.
    '''
    return vm_.get(
        'ssh_interface', __opts__.get('EC2.ssh_interface', 'public_ips')
    )


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


def avail_locations():
    '''
    List all available locations
    '''
    ret = {}

    params = {'Action': 'DescribeRegions'}
    result = query(params)

    for region in result:
        ret[region['regionName']] = {
            'name': region['regionName'],
            'endpoint': region['regionEndpoint'],
        }

    return ret


def get_availability_zone(vm_):
    '''
    Return the availability zone to use
    '''
    avz = None
    if 'availability_zone' in vm_:
        avz = vm_['availability_zone']
    elif 'EC2.availability_zone' in __opts__:
        avz = __opts__['EC2.availability_zone']

    if avz is None:
        return None

    zones = list_availability_zones()

    # Validate user-specified AZ
    if avz not in zones.keys():
        raise SaltException(
            'The specified availability zone isn\'t valid in this region: '
            '{0}\n'.format(
                avz
            )
        )

    # check specified AZ is available
    elif zones[avz] != 'available':
        raise SaltException(
            'The specified availability zone isn\'t currently available: '
            '{0}\n'.format(
                avz
            )
        )

    return avz


def list_availability_zones():
    '''
    List all availability zones in the current region
    '''
    ret = {}

    params = {'Action': 'DescribeAvailabilityZones',
              'Filter.0.Name': 'region-name',
              'Filter.0.Value.0': get_location()}
    result = query(params)

    for zone in result:
        ret[zone['zoneName']] = zone['zoneState']

    return ret


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
        params['KeyName'] = ex_keyname
    ex_securitygroup = securitygroup(vm_)
    if ex_securitygroup:
        if not isinstance(ex_securitygroup, list):
            params['SecurityGroup.1'] = ex_securitygroup
        else:
            for (counter, sg) in enumerate(ex_securitygroup):
                params['SecurityGroup.{0}'.format(counter)] = sg

    az = get_availability_zone(vm_)
    if az is not None:
        params['Placement.AvailabilityZone'] = az

    delvol_on_destroy = vm_.get(
        'delvol_on_destroy',            # Grab the value from the VM config
        __opts__.get(
            'EC2.delvol_on_destroy',    # If not available, try from the
            None                        # provider config defaulting to None
        )
    )
    if delvol_on_destroy is not None:
        if not isinstance(delvol_on_destroy, bool):
            raise ValueError('\'delvol_on_destroy\' should be a boolean value')

        params['BlockDeviceMapping.1.DeviceName'] = '/dev/sda1'
        params['BlockDeviceMapping.1.Ebs.DeleteOnTermination'] = str(
            delvol_on_destroy
        ).lower()

    try:
        data = query(params, 'instancesSet', location=location)
        if 'error' in data:
            return data['error']
    except Exception as exc:
        log.error(
            'Error creating {0} on EC2 when trying to run the initial '
            'deployment: \n{1}'.format(
                vm_['name'], exc
            )
        )
        return False

    instance_id = data[0]['instanceId']
    set_tags(
        instance_id, {'Name': vm_['name']}, call='action', location=location
    )
    log.info('Created node {0}'.format(vm_['name']))
    waiting_for_ip = 0

    params = {'Action': 'DescribeInstances',
              'InstanceId.1': instance_id}
    data, requesturl = query(params, location=location, return_url=True)

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
        else:
            return {vm_['name']: 'Failed to authenticate'}

    sudo = True
    if 'sudo' in vm_.keys():
        sudo = vm_['sudo']

    deploy = vm_.get('deploy', __opts__.get('EC2.deploy', __opts__['deploy']))
    if deploy is True:
        deploy_script = script(vm_)
        deploy_kwargs = {
            'host': ip_address,
            'username': username,
            'key_filename': __opts__['EC2.private_key'],
            'deploy_command': 'bash /tmp/deploy.sh',
            'tty': True,
            'script': deploy_script,
            'name': vm_['name'],
            'sudo': sudo,
            'start_action': __opts__['start_action'],
            'conf_file': __opts__['conf_file'],
            'sock_dir': __opts__['sock_dir'],
            'minion_pem': vm_['priv_key'],
            'minion_pub': vm_['pub_key'],
            'keep_tmp': __opts__['keep_tmp'],
        }
        if 'display_ssh_output' in __opts__:
            deploy_kwargs['display_ssh_output'] = __opts__['display_ssh_output']

        deploy_kwargs['minion_conf'] = saltcloud.utils.minion_conf_string(
            __opts__, vm_
        )

        if 'script_args' in vm_:
            deploy_kwargs['script_args'] = vm_['script_args']

        # Deploy salt-master files, if necessary
        if 'make_master' in vm_ and vm_['make_master'] is True:
            deploy_kwargs['make_master'] = True
            deploy_kwargs['master_pub'] = vm_['master_pub']
            deploy_kwargs['master_pem'] = vm_['master_pem']
            master_conf = saltcloud.utils.master_conf_string(__opts__, vm_)
            if master_conf:
                deploy_kwargs['master_conf'] = master_conf

            if 'syndic_master' in master_conf:
                deploy_kwargs['make_syndic'] = True

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
    ret = (data[0]['instancesSet']['item'])

    volumes = vm_.get('map_volumes')
    if volumes:
        log.info('Create and attach volumes to node {0}'.format(vm_['name']))
        created = create_attach_volumes(vm_['name'],
                              {'volumes': volumes,
                               'zone': ret['placement']['availabilityZone'],
                               'instance_id': ret['instanceId']},
                              call='action')

        ret['Attached Volumes'] = created
    return ret


def create_attach_volumes(name, kwargs, call=None):
    '''
    Create and attach volumes to created node
    '''
    if call != 'action':
        log.error('The set_tags action must be called with -a or --action.')
        sys.exit(1)

    if not 'instance_id' in kwargs:
        kwargs['instance_id'] = _get_node(name)['instanceId']

    if type(kwargs['volumes']) is str:
        volumes = yaml.safe_load(kwargs['volumes'])
    else:
        volumes = kwargs['volumes']

    ret = []
    for volume in volumes:
        volume_name = '{0} on {1}'.format(volume['device'], name)
        created_volume = create_volume({'size': volume['size'],
                                        'volume_name': volume_name,
                                        'zone': kwargs['zone']},
                                       call='function')
        for item in created_volume:
            if 'volumeId' in item:
                volume_id = item['volumeId']
        attach = attach_volume(name,
                               {'volume_id': volume_id,
                                'device': volume['device']},
                               instance_id=kwargs['instance_id'],
                               call='action')
        if attach:
            msg = (
                '{0} attached to {1} (aka {2}) as device {3}'.format(
                    volume_id, kwargs['instance_id'], name, volume['device']
                )
            )
            log.info(msg)
            ret.append(msg)
    return ret


def stop(name, call=None):
    '''
    Stop a node
    '''
    if call != 'action':
        log.error('The stop action must be called with -a or --action.')
        sys.exit(1)

    log.info('Stopping node {0}'.format(name))

    instance_id = _get_node(name)['instanceId']

    params = {'Action': 'StopInstances',
              'InstanceId.1': instance_id}
    result = query(params)

    return result


def start(name, call=None):
    '''
    Start a node
    '''
    if call != 'action':
        log.error('The start action must be called with -a or --action.')
        sys.exit(1)

    log.info('Starting node {0}'.format(name))

    instance_id = _get_node(name)['instanceId']

    params = {'Action': 'StartInstances',
              'InstanceId.1': instance_id}
    result = query(params)

    return result


def set_tags(name, tags, call=None, location=None):
    '''
    Set tags for a node

    CLI Example::

        salt-cloud -a set_tags mymachine tag1=somestuff tag2='Other stuff'
    '''
    if call != 'action':
        log.error('The set_tags action must be called with -a or --action.')
        sys.exit(1)

    instance_id = _get_node(name, location)['instanceId']
    params = {'Action': 'CreateTags',
              'ResourceId.1': instance_id}
    count = 1
    for tag in tags:
        params['Tag.{0}.Key'.format(count)] = tag
        params['Tag.{0}.Value'.format(count)] = tags[tag]
        count += 1
    result = query(params, setname='tagSet', location=location)

    return get_tags(name, call='action', location=location)


def get_tags(name, call=None, location=None):
    '''
    Retrieve tags for a node
    '''
    if call != 'action':
        log.error('The get_tags action must be called with -a or --action.')
        sys.exit(1)

    if ',' in name:
        names = name.split(',')
    else:
        names = [name]

    instances = list_nodes_full(location)
    if name in instances:
        instance_id = instances[name]['instanceId']
        params = {'Action': 'DescribeTags',
                  'Filter.1.Name': 'resource-id',
                  'Filter.1.Value': instance_id}
        return query(params, setname='tagSet', location=location)
    return []


def del_tags(name, kwargs, call=None):
    '''
    Delete tags for a node

    CLI Example::

        salt-cloud -a del_tags mymachine tag1,tag2,tag3
    '''
    if call != 'action':
        log.error('The del_tags action must be called with -a or --action.')
        sys.exit(1)

    instance_id = _get_node(name)['instanceId']
    params = {'Action': 'DeleteTags',
              'ResourceId.1': instance_id}
    count = 1
    for tag in kwargs['tags'].split(','):
        params['Tag.{0}.Key'.format(count)] = tag
        count += 1
    result = query(params, setname='tagSet')

    return get_tags(name, call='action')


def rename(name, kwargs, call=None):
    '''
    Properly rename a node. Pass in the new name as "new name".

    CLI Example::

        salt-cloud -a rename mymachine newname=yourmachine
    '''
    if call != 'action':
        log.error('The rename action must be called with -a or --action.')
        sys.exit(1)

    log.info('Renaming {0} to {1}'.format(name, kwargs['newname']))

    instance_id = _get_node(name)['instanceId']

    set_tags(name, {'Name': kwargs['newname']}, call='action')
    saltcloud.utils.rename_key(
        __opts__['pki_dir'], name, kwargs['newname']
    )


def destroy(name, call=None):
    '''
    Destroy a node. Will check termination protection and warn if enabled.

    CLI Example::

        salt-cloud --destroy mymachine
    '''
    instance_id = _get_node(name)['instanceId']
    protected = show_term_protect(instance_id=instance_id,
                             call='action',
                             quiet=True)
    if protected == 'true':
        log.error('This instance has been protected from being destroyed. '
                  'Use the following command to disable protection:\n\n'
                  'salt-cloud -a disable_term_protect {0}'.format(name))
        exit(1)

    if 'EC2.rename_on_destroy' in __opts__:
        if __opts__['EC2.rename_on_destroy'] is True:
            newname = '{0}-DEL{1}'.format(name, uuid.uuid4().hex)
            rename(name, kwargs={'newname': newname}, call='action')
            log.info(
                'Machine will be identified as {0} until it has been '
                'cleaned up.'.format(
                    newname
                )
            )

    params = {'Action': 'TerminateInstances',
              'InstanceId.1': instance_id}
    result = query(params)
    log.info(result)

    return result


def reboot(name, call=None):
    '''
    Reboot a node.

    CLI Example::

        salt-cloud -a reboot mymachine
    '''
    instance_id = _get_node(name)['instanceId']
    params = {'Action': 'RebootInstances',
              'InstanceId.1': instance_id}
    result = query(params)
    if result == []:
        log.info("Complete")

    return {'Reboot': 'Complete'}


def show_image(kwargs, call=None):
    '''
    Show the details from EC2 concerning an AMI
    '''
    if call != 'function':
        log.error(
            'The show_image function must be called with -f or --function.'
        )
        sys.exit(1)

    params = {'ImageId.1': kwargs['image'],
              'Action': 'DescribeImages'}
    result = query(params)
    log.info(result)

    return result


def show_instance(name, call=None):
    '''
    Show the details from EC2 concerning an AMI
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
            return list_nodes_full(location)[name]
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


def list_nodes_full(location=None):
    '''
    Return a list of the VMs that are on the provider
    '''
    if not location:
        ret = {}
        locations = set(
            get_location(vm_) for vm_ in __opts__['vm']
            if _vm_provider(vm_) == 'ec2'
        )
        for loc in locations:
            ret.update(_list_nodes_full(loc))
        return ret

    return _list_nodes_full(location)


def _vm_provider(vm_):
    return vm_.get('provider', __opts__['provider'])


def _extract_name_tag(item):
    if 'tagSet' in item:
        tagset = item['tagSet']
        if type(tagset['item']) is list:
            for tag in tagset['item']:
                if tag['key'] == 'Name':
                    return tag['value']
        else:
            return (item['tagSet']['item']['value'])
    else:
        return item['instanceId']

def _list_nodes_full(location=None):
    '''
    Return a list of the VMs that in this location
    '''

    ret = {}
    params = {'Action': 'DescribeInstances'}
    instances = query(params, location=location)

    for instance in instances:
        # items could be type dict or list (for stopped EC2 instances)
        if isinstance(instance['instancesSet']['item'], list):
            for item in instance['instancesSet']['item']:
                name = _extract_name_tag(item)
                ret[name] = item
                ret[name].update(dict(id=item['instanceId'], 
                                      image=item['imageId'], 
                                      size=item['instanceType'], 
                                      state=item['instanceState']['name'], 
                                      private_ips=item.get('privateIpAddress', []), 
                                      public_ips=item.get('ipAddress', [])))
        else:
            item = instance['instancesSet']['item']
            name = _extract_name_tag(item)
            ret[name] = item
            ret[name].update(dict(id=item['instanceId'], 
                                  image=item['imageId'], 
                                  size=item['instanceType'], 
                                  state=item['instanceState']['name'], 
                                  private_ips=item.get('privateIpAddress', []), 
                                  public_ips=item.get('ipAddress', [])))
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


def list_nodes_select():
    '''
    Return a list of the VMs that are on the provider, with select fields
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


def show_term_protect(name=None, instance_id=None, call=None, quiet=False):
    '''
    Show the details from EC2 concerning an AMI
    '''
    if call != 'action':
        log.error('The show_term_protect action must be called with '
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

    log.log(
        logging.DEBUG if quiet is True else logging.INFO,
        'Termination Protection is {0} for {1}'.format(
            disable_protect == 'true' and 'enabled' or 'disabled',
            name
        )
    )

    return disable_protect


def enable_term_protect(name, call=None):
    '''
    Enable termination protection on a node

    CLI Example::

        salt-cloud -a enable_term_protect mymachine
    '''
    if call != 'action':
        log.error('The enable_term_protect action must be called with '
              '-a or --action.')
        sys.exit(1)

    return _toggle_term_protect(name, 'true')


def disable_term_protect(name, call=None):
    '''
    Disable termination protection on a node

    CLI Example::

        salt-cloud -a disable_term_protect mymachine
    '''
    if call != 'action':
        log.error('The disable_term_protect action must be called with '
              '-a or --action.')
        sys.exit(1)

    return _toggle_term_protect(name, 'false')


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

    return show_term_protect(name, instance_id, call='action')


def keepvol_on_destroy(name, call=None):
    '''
    Do not delete root EBS volume upon instance termination

    CLI Example::

        salt-cloud -a keepvol_on_destroy mymachine
    '''
    if call != 'action':
        log.error('The keepvol_on_destroy action must be called with '
              '-a or --action.')
        sys.exit(1)

    return _toggle_delvol(name=name, value='false')


def delvol_on_destroy(name, call=None):
    '''
    Delete root EBS volume upon instance termination

    CLI Example::

        salt-cloud -a delvol_on_destroy mymachine
    '''
    if call != 'action':
        log.error('The delvol_on_destroy action must be called with '
              '-a or --action.')
        sys.exit(1)

    return _toggle_delvol(name=name, value='true')


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

    return query(requesturl=requesturl)


def create_volume(kwargs=None, call=None):
    '''
    Create a volume
    '''
    if call != 'function':
        log.error('The create_volume function must be called with '
                  '-f or --function.')
        return False

    if not 'zone' in kwargs:
        log.error('An availability zone must be specified to create a volume.')
        return False

    if not 'size' in kwargs and not 'snapshot' in kwargs:
        # This number represents GiB
        kwargs['size'] = '10'

    params = {'Action': 'CreateVolume',
              'AvailabilityZone': kwargs['zone']}

    if 'size' in kwargs:
        params['Size'] = kwargs['size']

    if 'snapshot' in kwargs:
        params['SnapshotId'] = kwargs['snapshot']

    log.debug(params)

    data = query(params, return_root=True)
    return data


def attach_volume(name=None, kwargs=None, instance_id=None, call=None):
    '''
    Attach a volume to an instance
    '''
    if call != 'action':
        log.error('The attach_volume action must be called with '
                  '-a or --action.')
        sys.exit(1)

    if not kwargs:
        kwargs = {}

    if 'instance_id' in kwargs:
        instance_id = kwargs['instance_id']

    if name and not instance_id:
        instances = list_nodes_full()
        instance_id = instances[name]['instanceId']

    if not name and not instance_id:
        log.error('Either a name or an instance_id is required.')
        return False

    if not 'volume_id' in kwargs:
        log.error('A volume_id is required.')
        return False

    if not 'device' in kwargs:
        log.error('A device is required (ex. /dev/sdb1).')
        return False

    params = {'Action': 'AttachVolume',
              'VolumeId': kwargs['volume_id'],
              'InstanceId': instance_id,
              'Device': kwargs['device']}

    data = query(params, return_root=True)
    return data


def show_volume(name=None, kwargs=None, instance_id=None, call=None):
    '''
    Show volume details
    '''
    if not kwargs:
        kwargs = {}

    if not 'volume_id' in kwargs:
        log.error('A volume_id is required.')
        return False

    params = {'Action': 'DescribeVolumes',
              'VolumeId.1': kwargs['volume_id']}

    data = query(params, return_root=True)
    return data


def detach_volume(name=None, kwargs=None, instance_id=None, call=None):
    '''
    Detach a volume from an instance
    '''
    if call != 'action':
        log.error('The detach_volume action must be called with '
                  '-a or --action.')
        sys.exit(1)

    if not kwargs:
        kwargs = {}

    if not 'volume_id' in kwargs:
        log.error('A volume_id is required.')
        return False

    params = {'Action': 'DetachVolume',
              'VolumeId': kwargs['volume_id']}

    data = query(params, return_root=True)
    return data


def delete_volume(name=None, kwargs=None, instance_id=None, call=None):
    '''
    Delete a volume
    '''
    if not kwargs:
        kwargs = {}

    if not 'volume_id' in kwargs:
        log.error('A volume_id is required.')
        return False

    params = {'Action': 'DeleteVolume',
              'VolumeId': kwargs['volume_id']}

    data = query(params, return_root=True)
    return data


def create_keypair(kwargs=None, call=None):
    '''
    Create an SSH keypair
    '''
    if call != 'function':
        log.error('The create_keypair function must be called with '
                  '-f or --function.')
        return False

    if not kwargs:
        kwargs = {}

    if not 'keyname' in kwargs:
        log.error('A keyname is required.')
        return False

    params = {'Action': 'CreateKeyPair',
              'KeyName': kwargs['keyname']}

    data = query(params, return_root=True)
    return data


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

    params = {'Action': 'DescribeKeyPairs',
              'KeyName.1': kwargs['keyname']}

    data = query(params, return_root=True)
    return data


def delete_keypair(kwargs=None, call=None):
    '''
    Delete an SSH keypair
    '''
    if call != 'function':
        log.error('The delete_keypair function must be called with '
                  '-f or --function.')
        return False

    if not kwargs:
        kwargs = {}

    if not 'keyname' in kwargs:
        log.error('A keyname is required.')
        return False

    params = {'Action': 'DeleteKeyPair',
              'KeyName.1': kwargs['keyname']}

    data = query(params, return_root=True)
    return data
