# -*- coding: utf-8 -*-
"""
ec2_metadata.py - exports all instance metadata in an 'ec2_metadata' grain

To use it:

  1. Place ec2_metadata.py in <salt_root>/_grains/
  2. Test it

    $ salt '*' saltutil.sync_grains
    $ salt '*' grains.get ec2_metadata

Author: Fred Reimer <freimer@freimer.org>
Licensed under Apache License (https://raw.github.com/saltstack/salt/develop/LICENSE)

"""

import logging
import requests

log = logging.getLogger(__name__)


def _get_instance_data(uri=None):
    baseuri = "http://169.254.169.254/latest/meta-data/"
    try:
        log.debug("Requesting instance metadata {0}{1}".format(baseuri, uri))
        result = requests.get("{0}{1}".format(baseuri, uri))
        log.debug('Response Status Code: {0}'.format(result.status_code))
        log.trace('Response Text: {0}'.format(result.text))
        if result.status_code == 200:
            return result.text
        else:
            return None
    except requests.exceptions.HTTPError as e:
        return None


def ec2_metadata():
    mdata = {
        'ami-id' : 'ami-id',
        'ami-launch-index': 'ami-launch-index',
        'ami-mainfest-path': 'ami-mainfest-path',
        'ancestor-ami-ids': 'ancestor-ami-ids',
        'block-device-mapping': 'block-device-mapping',
        'hostname': 'hostname',
        'iam-role': 'iam/security-credentials/',
        'instance-action': 'instance-action',
        'instance-id': 'instance-id',
        'instance-type': 'instance-type',
        'kernel-id': 'kernel-id',
        'local-hostname': 'local-hostname',
        'local-ipv4': 'local-ipv4',
        'mac': 'mac',
        'availability-zone': 'palcement/availability-zone',
        'product-codes': 'product-codes',
        'public-ipv4': 'public-ipv4',
        'openssh-key': 'public-keys/0/openssh-key',
        'ramdisk-id': 'ramdisk-id',
        'reservation-id': 'reservation-id',
        'security-groups': 'security-groups',
        'aws-services-domain': 'services/domain',
        'spot-termination-time': 'spot/termination-time'
    }
    metadata = {'ec2_metadata': {}}
    for key, url in mdata.items():
        value = _get_instance_data(url)
        if value != None:
            metadata['ec2_metadata'][key] = value

    return metadata

if __name__ == '__main__':
    print ec2_metadata()
