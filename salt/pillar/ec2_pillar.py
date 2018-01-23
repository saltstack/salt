# -*- coding: utf-8 -*-
'''
Retrieve EC2 instance data for minions.

The minion id must be the instance-id retrieved from AWS.  As an
option, use_grain can be set to True.  This allows the use of an
instance-id grain instead of the minion-id.  Since this is a potential
security risk, the configuration can be further expanded to include
a list of minions that are trusted to only allow the alternate id
of the instances to specific hosts.  There is no glob matching at
this time.

.. code-block:: yaml

    ext_pillar:
      - ec2_pillar:
          use_grain: True
          minion_ids:
            - trusted-minion-1
            - trusted-minion-2
            - trusted-minion-3

This is a very simple pillar that simply retrieves the instance data
from AWS.  Currently the only portion implemented are EC2 tags, which
returns a list of key/value pairs for all of the EC2 tags assigned to
the instance.

'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import re
import logging

# Import salt libs
from salt.utils.versions import StrictVersion as _StrictVersion

# Import AWS Boto libs
try:
    import boto.ec2
    import boto.utils
    import boto.exception
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

# Set up logging
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Check for required version of boto and make this pillar available
    depending on outcome.
    '''
    if not HAS_BOTO:
        return False
    boto_version = _StrictVersion(boto.__version__)
    required_boto_version = _StrictVersion('2.8.0')
    if boto_version < required_boto_version:
        log.error("%s: installed boto version %s < %s, can't retrieve instance data",
                __name__, boto_version, required_boto_version)
        return False
    return True


def _get_instance_info():
    '''
    Helper function to return the instance ID and region of the master where
    this pillar is run.
    '''
    identity = boto.utils.get_instance_identity()['document']
    return (identity['instanceId'], identity['region'])


def ext_pillar(minion_id,
               pillar,  # pylint: disable=W0613
               use_grain=False,
               minion_ids=None):
    '''
    Execute a command and read the output as YAML
    '''

    log.debug("Querying EC2 tags for minion id %s", minion_id)

    # If minion_id is not in the format of an AWS EC2 instance, check to see
    # if there is a grain named 'instance-id' use that.  Because this is a
    # security risk, the master config must contain a use_grain: True option
    # for this external pillar, which defaults to no
    if re.search(r'^i-([0-9a-z]{17}|[0-9a-z]{8})$', minion_id) is None:
        if 'instance-id' not in __grains__:
            log.debug("Minion-id is not in AWS instance-id formation, and there "
                      "is no instance-id grain for minion %s", minion_id)
            return {}
        if not use_grain:
            log.debug("Minion-id is not in AWS instance-id formation, and option "
                      "not set to use instance-id grain, for minion %s, use_grain "
                      "is %s", minion_id, use_grain)
            return {}
        log.debug("use_grain set to %s", use_grain)
        if minion_ids is not None and minion_id not in minion_ids:
            log.debug("Minion-id is not in AWS instance ID format, and minion_ids "
                      "is set in the ec2_pillar configuration, but minion %s is "
                      "not in the list of allowed minions %s", minion_id, minion_ids)
            return {}
        if re.search(r'^i-([0-9a-z]{17}|[0-9a-z]{8})$', __grains__['instance-id']) is not None:
            minion_id = __grains__['instance-id']
            log.debug("Minion-id is not in AWS instance ID format, but a grain"
                      " is, so using %s as the minion ID", minion_id)
        else:
            log.debug("Nether minion id nor a grain named instance-id is in "
                      "AWS format, can't query EC2 tags for minion %s", minion_id)
            return {}

    m = boto.utils.get_instance_metadata(timeout=0.1, num_retries=1)
    if len(m.keys()) < 1:
        log.info("%s: not an EC2 instance, skipping", __name__)
        return None

    # Get the Master's instance info, primarily the region
    (instance_id, region) = _get_instance_info()

    try:
        conn = boto.ec2.connect_to_region(region)
    except boto.exception as e:  # pylint: disable=E0712
        log.error("%s: invalid AWS credentials.", __name__)
        return None

    tags = {}
    try:
        _tags = conn.get_all_tags(filters={'resource-type': 'instance',
                'resource-id': minion_id})
        for tag in _tags:
            tags[tag.name] = tag.value
    except IndexError as e:
        log.error("Couldn't retrieve instance information: %s", e)
        return None

    return {'ec2_tags': tags}
