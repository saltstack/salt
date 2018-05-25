# -*- coding: utf-8 -*-
'''
Manage Athena queries with Boto 3

Create and delete Athena queries. Be aware that this interacts with Amazon's
services, and so may incur charges.

This module uses ``boto3``, which can be installed via package, or pip.

This module accepts explicit Athena credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

If IAM roles are not used you need to specify them either in a pillar file or
in the minion's config file:

.. code-block:: yaml
    athena.keyid: GKTADJGHEIQSXMKKRBJ08H
    athena.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

It's also possible to specify ``key``, ``keyid`` and ``region`` via a profile, either
passed in as a dict, or as a string to pull from pillars or minion config:

.. code-block:: yaml
    myprofile:
      keyid: GKTADJGHEIQSXMKKRBJ08H
      key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
      region: us-east-1

.. code-block:: yaml
    An engaging new AWS Athena Named Query:
      boto_athena.named_query_present:
      - Name: slackFest
      - Description: My favorite query EVAR
      - Database: someDBlikeThingInS3
      - QueryString: |
          SELECT bobDobbs
          FROM churchOfTheSubGeniusMembers
          WHERE slack_level >= '200'
          GROUP BY dues_paid
          ORDER BY slack_level DESC;
      - region: us-east-1
      - keyid: GKTADJGHEIQSXMKKRBJ08H
      - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

'''
# keep lint from choking
#pylint: disable=W0106
#pylint: disable=E1320

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import hashlib

# Import Salt Libs
import salt.utils.dictupdate as dictupdate
from salt.exceptions import SaltInvocationError
import logging
log = logging.getLogger(__name__)  # pylint: disable=W1699


def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto3_athena' if 'boto3_athena.list_named_queries' in __salt__ else False


def named_query_present(name, Name=None, Description=None, Database=None, QueryString=None,
                        region=None, key=None, keyid=None, profile=None):
    '''
    Ensure a named query exists with the given attributes.

    name
        The name of the state definition.

    Name
        The plain language name for the query.  If not provided, the value of `name` will be used.

    Description
        A brief explanation of the query. 

    Database
        The database to which the query belongs.  This should have been created (most likely
        via Hive) before calling this function.

    QueryString
        The (SQL) text of the query itself.

    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    Name = Name if Name else name
    args = {'Name': Name, 'region': region, 'key': key, 'keyid': keyid, 'profile': profile}
    query = __salt__['boto3_athena.get_named_query_by_name'](**args)
    new_md5 = hashlib.md5('%s%s%s%s' % (Name, Description, Database, QueryString)).hexdigest()
    if query:
        old_md5 = query.get('NamedQuery', {}).get('ClientRequestToken')
        if old_md5 == new_md5:
            ret['comment'] = 'Athena Named Query `%s` already in the correct state' % Name
            log.info(ret['comment'])
            return ret
        action = 'update'
    else:
        action = 'create'

    if __opts__['test']:
        ret['comment'] = 'Athena Named Query `%s` would be %sd' % (Name, action)
        ret['result'] = None
        return ret

    if action == 'update':
        args = {'NamedQueryId': NamedQueryId, 'region': region, 'key': key, 'keyid': keyid,
                'profile': profile}
        res = __salt__['boto3_athena.delete_named_query'](**args)
        if res is None:
            ret['comment'] = 'Failed to delete Athena Named Query `%s` for updating' % Name
            log.error(ret['comment'])
            ret['result'] = False
            return ret
        log.debug('Athena Named Query `%s` deleted for updating' %

    args = {'Name': Name, 'Description': Description, 'Database': Database,
            'QueryString': QueryString, 'ClientRequestToken': new_md5,
            'region': region, 'key': key, 'keyid': keyid, 'profile': profile}
    res = __salt__['boto3_athena.create_named_query'](**args)
    if res is None:
        ret['comment'] = 'Failed to %s Athena Named Query `%s`' % (action, Name)
        log.error(ret['comment'])
        ret['result'] = False
        return ret
    nqid = res.get('NamedQueryId')
    ret['comment'] = 'Athena Named Query `%s` (ID: %s) %sd' % (Name, nqid, action)
    log.error(ret['comment'])
    args = {'NamedQueryId': nqid, 'region': region, 'key': key, 'keyid': keyid, 'profile': profile}
    nquery = __salt__['boto3_athena.get_named_query'](**args)
    ret['changes']['old'] = query
    ret['changes']['new'] = nquery
    return ret


def named_query_absent(name, Name=None, NamedQueryId=None,
                       region=None, key=None, keyid=None, profile=None):
    '''
    Ensure the given named query does not exist.

    name
        The name of the state definition.

    Name
        The name of the query to delete.  If neither `Name` nor `NamedQueryId` is provided, the
        value of `name` will be used and assumed to be a query Name.

    NamedQueryId
        The ID of the query to delete.  Overrides any value computed from `Name` or `name`.

    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    Name = Name if Name else name
    if NamedQueryId is None:
        args = {'Name': Name, 'region': region, 'key': key, 'keyid': keyid, 'profile': profile}
        query = __salt__['boto3_athena.get_named_query_by_name'](**args)
    else:
        args = {'NamedQueryId': NamedQueryId, 'region': region, 'key': key, 'keyid': keyid,
                'profile': profile}
        query = __salt__['boto3_athena.get_named_query'](**args)
    NamedQueryId = query.get('NamedQuery').get('NamedQueryId') if query else None
    if NamedQueryId is None:
        ret['comment'] = 'Athena Named Query `%s` already absent' % Name
        log.info(ret['comment'])
        return ret

    if __opts__['test']:
        ret['comment'] = 'Athena Named Query `%s` would be deleted' % NamedQueryId
        ret['result'] = None
        return ret

    args = {'NamedQueryId': NamedQueryId, 'region': region, 'key': key, 'keyid': keyid,
            'profile': profile}
    res = __salt__['boto3_athena.delete_named_query'](**args)
    if res is None:
        ret['comment'] = 'Failed to delete Athena Named Query `%s`' % NamedQueryId
        log.error(ret['comment'])
        ret['result'] = False
    else:
        ret['comment'] = 'Athena Named Query `%s` deleted' % NamedQueryId
        log.info(ret['comment'])
        ret['changes']['old'] = query
        ret['changes']['new'] = None
    return ret
