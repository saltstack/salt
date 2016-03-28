# -*- coding: utf-8 -*-
'''
Manage CodeCommit repositories 
=================

.. versionadded:: 2016.3.0

Create and destroy CodeCommit repositories. Be aware that this interacts with Amazon's services,
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

    Ensure repository exists:
        boto_codecommit.repository_present:
            - repositoryName: myrepository
            - repositoryDescription: mydescription
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
import salt.utils
from salt.ext.six import string_types

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto_codecommit' if 'boto_codecommit.repository_exists' in __salt__ else False


def repository_present(name, repositoryName, repositoryDescription="",
            region=None, key=None, keyid=None, profile=None):
    '''
    Ensure repository exists.

    name
        The name of the state definition

    repositoryName
        Name of the repository.

    repositoryDescription
        Description of the policy. 

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
    ret = {'name': repositoryName,
           'result': True,
           'comment': '',
           'changes': {}
           }

    r = __salt__['boto_codecommit.repository_exists'](repositoryName=repositoryName,
                              region=region, key=key, keyid=keyid, profile=profile)

    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to create repository: {0}.'.format(r['error']['message'])
        return ret

    if not r.get('exists'):
        if __opts__['test']:
            ret['comment'] = 'Repository {0} is set to be created.'.format(repositoryName)
            ret['result'] = None
            return ret
        r = __salt__['boto_codecommit.create_repository'](repositoryName=repositoryName,
                                               repositoryDescription=repositoryDescription,
                                               region=region, key=key,
                                               keyid=keyid, profile=profile)
        if not r.get('created'):
            ret['result'] = False
            ret['comment'] = 'Failed to create repository: {0}.'.format(r['error']['message'])
            return ret
        _describe = __salt__['boto_codecommit.describe_repositories'](repositoryName,
                                   region=region, key=key, keyid=keyid, profile=profile)

        ret['changes']['old'] = {'repository': None}
        ret['changes']['new'] = _describe['repositories'][0]
        ret['comment'] = 'Repository {0} created.'.format(repositoryName)
        return ret

    ret['comment'] = os.linesep.join([ret['comment'], 'Pository {0} is present.'.format(repositoryName)])
    ret['changes'] = {}

    # repository exists, ensure config matches
    # Well, the only config that seems to editable is description
    # TODO: check and update description if necessary, not going to bother about it yet

    return ret


def repository_absent(name, repositoryName,
                  region=None, key=None, keyid=None, profile=None):
    '''
    Ensure repository with passed properties is absent.

    name
        The name of the state definition.

    repositoryName
        Name of the repository.

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

    ret = {'name': repositoryName,
           'result': True,
           'comment': '',
           'changes': {}
           }

    r = __salt__['boto_codecommit.repository_exists'](repositoryName,
                       region=region, key=key, keyid=keyid, profile=profile)
    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to delete repository: {0}.'.format(r['error']['message'])
        return ret

    if r and not r['exists']:
        ret['comment'] = 'Repository {0} does not exist.'.format(repositoryName)
        return ret

    if __opts__['test']:
        ret['comment'] = 'Repository {0} is set to be removed.'.format(repositoryName)
        ret['result'] = None
        return ret

    r = __salt__['boto_codecommit.delete_repository'](repositoryName,
                                    region=region, key=key,
                                    keyid=keyid, profile=profile)
    if not r['deleted']:
        ret['result'] = False
        ret['comment'] = 'Failed to delete repository: {0}.'.format(r['error']['message'])
        return ret

    ret['changes']['old'] = {'repository': repositoryName}
    ret['changes']['new'] = {'repository': None}
    ret['comment'] = 'Repository {0} deleted.'.format(repositoryName)
    return ret

