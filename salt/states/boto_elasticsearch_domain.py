# -*- coding: utf-8 -*-
'''
Manage Elasticsearch Domains
=================

.. versionadded:: Carbon

Create and destroy Elasticsearch domains. Be aware that this interacts with Amazon's services,
and so may incur charges.

This module uses ``boto3``, which can be installed via package, or pip.

This module accepts explicit vpc credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

If IAM roles are not used you need to specify them either in a pillar file or
in the minion's config file:

.. code-block:: yaml

    vpc.keyid: GKTADJGHEIQSXMKKRBJ08H
    vpc.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

It's also possible to specify ``key``, ``keyid`` and ``region`` via a profile,
either passed in as a dict, or as a string to pull from pillars or minion
config:

.. code-block:: yaml

    myprofile:
        keyid: GKTADJGHEIQSXMKKRBJ08H
        key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

.. code-block:: yaml

    Ensure domain exists:
        boto_elasticsearch_domain.present:
            - DomainName: mydomain
            - profile='user-credentials'
            - ElasticsearchClusterConfig:
                InstanceType": "t2.micro.elasticsearch"
                InstanceCount: 1
                DedicatedMasterEnabled: False
                ZoneAwarenessEnabled: False
            - EBSOptions:
                EBSEnabled: True
                VolumeType: "gp2"
                VolumeSize: 10
                Iops: 0
            - AccessPolicies:
                Version: "2012-10-17"
                Statement:
                  - Effect: "Allow"
                  - Principal:
                      AWS: "*"
                  - Action:
                    - "es:*"
                  - Resource: "arn:aws:es:*:111111111111:domain/mydomain/*
                  - Condition:
                      IpAddress:
                        "aws:SourceIp":
                          - "127.0.0.1",
                          - "127.0.0.2",
            - SnapshotOptions:
                AutomatedSnapshotStartHour: 0
            - AdvancedOptions:
                rest.action.multi.allow_explicit_index": "true"
            - Tags:
                a: "b"
            - region: us-east-1
            - keyid: GKTADJGHEIQSXMKKRBJ08H
            - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

'''

# Import Python Libs
from __future__ import absolute_import
import logging
import os
import os.path
import json

# Import Salt Libs
from salt.ext.six import string_types

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto_elasticsearch_domain' if 'boto_elasticsearch_domain.exists' in __salt__ else False


def present(name, DomainName,
            ElasticsearchClusterConfig=None,
            EBSOptions=None,
            AccessPolicies=None,
            SnapshotOptions=None,
            AdvancedOptions=None,
            Tags=None,
            region=None, key=None, keyid=None, profile=None):
    '''
    Ensure domain exists.

    name
        The name of the state definition

    DomainName
        Name of the domain.

    ElasticsearchClusterConfig
        Configuration options for an Elasticsearch domain. Specifies the
        instance type and number of instances in the domain cluster.

        InstanceType (string) --
        The instance type for an Elasticsearch cluster.

        InstanceCount (integer) --
        The number of instances in the specified domain cluster.

        DedicatedMasterEnabled (boolean) --
        A boolean value to indicate whether a dedicated master node is enabled.
        See About Dedicated Master Nodes for more information.

        ZoneAwarenessEnabled (boolean) --
        A boolean value to indicate whether zone awareness is enabled. See About
        Zone Awareness for more information.

        DedicatedMasterType (string) --
        The instance type for a dedicated master node.

        DedicatedMasterCount (integer) --
        Total number of dedicated master nodes, active and on standby, for the
        cluster.

    EBSOptions
        Options to enable, disable and specify the type and size of EBS storage
        volumes.

        EBSEnabled (boolean) --
        Specifies whether EBS-based storage is enabled.

        VolumeType (string) --
        Specifies the volume type for EBS-based storage.

        VolumeSize (integer) --
        Integer to specify the size of an EBS volume.

        Iops (integer) --
        Specifies the IOPD for a Provisioned IOPS EBS volume (SSD).

    AccessPolicies
        IAM access policy

    SnapshotOptions
        Option to set time, in UTC format, of the daily automated snapshot.
        Default value is 0 hours.

        AutomatedSnapshotStartHour (integer) --
        Specifies the time, in UTC format, when the service takes a daily
        automated snapshot of the specified Elasticsearch domain. Default value
        is 0 hours.

    AdvancedOptions
        Option to allow references to indices in an HTTP request body. Must be
        false when configuring access to individual sub-resources. By default,
        the value is true .

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.
    '''
    ret = {'name': DomainName,
           'result': True,
           'comment': '',
           'changes': {}
           }

    if ElasticsearchClusterConfig is None:
        ElasticsearchClusterConfig = {
            'DedicatedMasterEnabled': False,
            'InstanceCount': 1,
            'InstanceType': 'm3.medium.elasticsearch',
            'ZoneAwarenessEnabled': False
        }
    if EBSOptions is None:
        EBSOptions = {
            'EBSEnabled': False,
        }
    if SnapshotOptions is None:
        SnapshotOptions = {
            'AutomatedSnapshotStartHour': 0
        }
    if AdvancedOptions is None:
        AdvancedOptions = {
            'rest.action.multi.allow_explicit_index': 'true'
        }
    if Tags is None:
        Tags = {}
    if AccessPolicies is not None and isinstance(AccessPolicies, string_types):
        try:
            AccessPolicies = json.loads(AccessPolicies)
        except ValueError as e:
            ret['result'] = False
            ret['comment'] = 'Failed to create domain: {0}.'.format(e.message)
            return ret
    r = __salt__['boto_elasticsearch_domain.exists'](DomainName=DomainName,
                              region=region, key=key, keyid=keyid, profile=profile)

    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to create domain: {0}.'.format(r['error']['message'])
        return ret

    if not r.get('exists'):
        if __opts__['test']:
            ret['comment'] = 'Domain {0} is set to be created.'.format(DomainName)
            ret['result'] = None
            return ret
        r = __salt__['boto_elasticsearch_domain.create'](DomainName=DomainName,
                                                     ElasticsearchClusterConfig=ElasticsearchClusterConfig,
                                                     EBSOptions=EBSOptions,
                                                     AccessPolicies=AccessPolicies,
                                                     SnapshotOptions=SnapshotOptions,
                                                     AdvancedOptions=AdvancedOptions,
                                               region=region, key=key,
                                               keyid=keyid, profile=profile)
        if not r.get('created'):
            ret['result'] = False
            ret['comment'] = 'Failed to create domain: {0}.'.format(r['error']['message'])
            return ret
        _describe = __salt__['boto_elasticsearch_domain.describe'](DomainName,
                                   region=region, key=key, keyid=keyid, profile=profile)
        ret['changes']['old'] = {'domain': None}
        ret['changes']['new'] = _describe
        ret['comment'] = 'Domain {0} created.'.format(DomainName)
        return ret

    ret['comment'] = os.linesep.join([ret['comment'], 'Domain {0} is present.'.format(DomainName)])
    ret['changes'] = {}
    # domain exists, ensure config matches
    _describe = __salt__['boto_elasticsearch_domain.describe'](DomainName=DomainName,
                                  region=region, key=key, keyid=keyid,
                                  profile=profile)['domain']
    _describe['AccessPolicies'] = json.loads(_describe['AccessPolicies'])

    # When EBSEnabled is false, describe returns extra values that can't be set
    if not _describe.get('EBSOptions', {}).get('EBSEnabled'):
        opts = _describe.get('EBSOptions', {})
        opts.pop('VolumeSize', None)
        opts.pop('VolumeType', None)

    comm_args = {}
    need_update = False
    for k, v in {
        'ElasticsearchClusterConfig': ElasticsearchClusterConfig,
        'EBSOptions': EBSOptions,
        'AccessPolicies': AccessPolicies,
        'SnapshotOptions': SnapshotOptions,
        'AdvancedOptions': AdvancedOptions
    }.iteritems():
        if v != _describe[k]:
            need_update = True
            comm_args[k] = v
            ret['changes'].setdefault('new', {})[k] = v
            ret['changes'].setdefault('old', {})[k] = _describe[k]
    if need_update:
        if __opts__['test']:
            msg = 'Domain {0} set to be modified.'.format(DomainName)
            ret['comment'] = msg
            ret['result'] = None
            return ret

        ret['comment'] = os.linesep.join([ret['comment'], 'Domain to be modified'])

        r = __salt__['boto_elasticsearch_domain.update'](DomainName=DomainName,
                                               region=region, key=key,
                                               keyid=keyid, profile=profile,
                                               **comm_args)
        if not r.get('updated'):
            ret['result'] = False
            ret['comment'] = 'Failed to update domain: {0}.'.format(r['error'])
            ret['changes'] = {}
            return ret
    return ret


def absent(name, DomainName,
                  region=None, key=None, keyid=None, profile=None):
    '''
    Ensure domain with passed properties is absent.

    name
        The name of the state definition.

    DomainName
        Name of the domain.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.
    '''

    ret = {'name': DomainName,
           'result': True,
           'comment': '',
           'changes': {}
           }

    r = __salt__['boto_elasticsearch_domain.exists'](DomainName,
                       region=region, key=key, keyid=keyid, profile=profile)
    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to delete domain: {0}.'.format(r['error']['message'])
        return ret

    if r and not r['exists']:
        ret['comment'] = 'Domain {0} does not exist.'.format(DomainName)
        return ret

    if __opts__['test']:
        ret['comment'] = 'Domain {0} is set to be removed.'.format(DomainName)
        ret['result'] = None
        return ret

    r = __salt__['boto_elasticsearch_domain.delete'](DomainName,
                                    region=region, key=key,
                                    keyid=keyid, profile=profile)
    if not r['deleted']:
        ret['result'] = False
        ret['comment'] = 'Failed to delete domain: {0}.'.format(r['error']['message'])
        return ret
    ret['changes']['old'] = {'domain': DomainName}
    ret['changes']['new'] = {'domain': None}
    ret['comment'] = 'Domain {0} deleted.'.format(DomainName)
    return ret
