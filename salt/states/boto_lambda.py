# -*- coding: utf-8 -*-
'''
Manage Lambda Functions
=================

.. versionadded:: 2016.3.0

Create and destroy Lambda Functions. Be aware that this interacts with Amazon's services,
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

    Ensure function exists:
        boto_lambda.function_present:
            - FunctionName: myfunction
            - Runtime: python2.7
            - Role: iam_role_name
            - Handler: entry_function
            - ZipFile: code.zip
            - S3Bucket: bucketname
            - S3Key: keyname
            - S3ObjectVersion: version
            - Description: "My Lambda Function"
            - Timeout: 3
            - MemorySize: 128
            - region: us-east-1
            - keyid: GKTADJGHEIQSXMKKRBJ08H
            - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

'''

# Import Python Libs
from __future__ import absolute_import
import logging
import os
import os.path
import hashlib
import json

# Import Salt Libs
import salt.utils.dictupdate as dictupdate
import salt.utils
from salt.exceptions import SaltInvocationError
from salt.ext.six import string_types

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto_lambda' if 'boto_lambda.function_exists' in __salt__ else False


def function_present(name, FunctionName, Runtime, Role, Handler, ZipFile=None, S3Bucket=None,
            S3Key=None, S3ObjectVersion=None,
            Description='', Timeout=3, MemorySize=128,
            Permissions=None, RoleRetries=5,
            region=None, key=None, keyid=None, profile=None):
    '''
    Ensure function exists.

    name
        The name of the state definition

    FunctionName
        Name of the Function.

    Runtime
        The Runtime environment for the function. One of
        'nodejs', 'java8', or 'python2.7'

    Role
        The name or ARN of the IAM role that the function assumes when it executes your
        function to access any other AWS resources.

    Handler
        The function within your code that Lambda calls to begin execution. For Node.js it is the
        module-name.*export* value in your function. For Java, it can be package.classname::handler or
        package.class-name.

    ZipFile
        A path to a .zip file containing your deployment package. If this is
        specified, S3Bucket and S3Key must not be specified.

    S3Bucket
        Amazon S3 bucket name where the .zip file containing your package is
        stored. If this is specified, S3Key must be specified and ZipFile must
        NOT be specified.

    S3Key
        The Amazon S3 object (the deployment package) key name you want to
        upload. If this is specified, S3Key must be specified and ZipFile must
        NOT be specified.

    S3ObjectVersion
        The version of S3 object to use. Optional, should only be specified if
        S3Bucket and S3Key are specified.

    Description
        A short, user-defined function description. Lambda does not use this value. Assign a meaningful
        description as you see fit.

    Timeout
        The function execution time at which Lambda should terminate this function. Because the execution
        time has cost implications, we recommend you set this value based on your expected execution time.
        The default is 3 seconds.

    MemorySize
        The amount of memory, in MB, your function is given. Lambda uses this memory size to infer
        the amount of CPU and memory allocated to your function. Your function use-case determines your
        CPU and memory requirements. For example, a database operation might need less memory compared
        to an image processing function. The default value is 128 MB. The value must be a multiple of
        64 MB.

    Permissions
        A list of permission definitions to be added to the function's policy

    RoleRetries
        IAM Roles may take some time to propagate to all regions once created.
        During that time function creation may fail; this state will
        atuomatically retry this number of times. The default is 5.

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
    ret = {'name': FunctionName,
           'result': True,
           'comment': '',
           'changes': {}
           }

    if Permissions is not None:
        if isinstance(Permissions, string_types):
            Permissions = json.loads(Permissions)
        required_keys = set(('Action', 'Principal'))
        optional_keys = set(('SourceArn', 'SourceAccount'))
        for sid, permission in Permissions.iteritems():
            keyset = set(permission.keys())
            if not keyset.issuperset(required_keys):
                raise SaltInvocationError('{0} are required for each permission '
                           'specification'.format(', '.join(required_keys)))
            keyset = keyset - required_keys
            keyset = keyset - optional_keys
            if bool(keyset):
                raise SaltInvocationError('Invalid permission value {0}'.format(', '.join(keyset)))

    r = __salt__['boto_lambda.function_exists'](FunctionName=FunctionName, region=region,
                                    key=key, keyid=keyid, profile=profile)

    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to create function: {0}.'.format(r['error']['message'])
        return ret

    if not r.get('exists'):
        if __opts__['test']:
            ret['comment'] = 'Function {0} is set to be created.'.format(FunctionName)
            ret['result'] = None
            return ret
        r = __salt__['boto_lambda.create_function'](FunctionName=FunctionName, Runtime=Runtime,
                                                    Role=Role, Handler=Handler,
                                                    ZipFile=ZipFile, S3Bucket=S3Bucket,
                                                    S3Key=S3Key,
                                                    S3ObjectVersion=S3ObjectVersion,
                                                    Description=Description,
                                                    Timeout=Timeout, MemorySize=MemorySize,
                                                    WaitForRole=True,
                                                    RoleRetries=RoleRetries,
                                                    region=region, key=key,
                                                    keyid=keyid, profile=profile)
        if not r.get('created'):
            ret['result'] = False
            ret['comment'] = 'Failed to create function: {0}.'.format(r['error']['message'])
            return ret

        if Permissions:
            for sid, permission in Permissions.iteritems():
                r = __salt__['boto_lambda.add_permission'](FunctionName=FunctionName,
                                                       StatementId=sid,
                                                       **permission)
                if not r.get('updated'):
                    ret['result'] = False
                    ret['comment'] = 'Failed to create function: {0}.'.format(r['error']['message'])

        _describe = __salt__['boto_lambda.describe_function'](FunctionName,
                           region=region, key=key, keyid=keyid, profile=profile)
        _describe['function']['Permissions'] = __salt__['boto_lambda.get_permissions'](FunctionName,
                           region=region, key=key, keyid=keyid, profile=profile)['permissions']
        ret['changes']['old'] = {'function': None}
        ret['changes']['new'] = _describe
        ret['comment'] = 'Function {0} created.'.format(FunctionName)
        return ret

    ret['comment'] = os.linesep.join([ret['comment'], 'Function {0} is present.'.format(FunctionName)])
    ret['changes'] = {}
    # function exists, ensure config matches
    _ret = _function_config_present(FunctionName, Role, Handler, Description, Timeout,
                                  MemorySize, region, key, keyid, profile)
    if not _ret.get('result'):
        ret['result'] = False
        ret['comment'] = _ret['comment']
        ret['changes'] = {}
        return ret
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    _ret = _function_code_present(FunctionName, ZipFile, S3Bucket, S3Key, S3ObjectVersion,
                                 region, key, keyid, profile)
    if not _ret.get('result'):
        ret['result'] = False
        ret['comment'] = _ret['comment']
        ret['changes'] = {}
        return ret
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    _ret = _function_permissions_present(FunctionName, Permissions,
                                 region, key, keyid, profile)
    if not _ret.get('result'):
        ret['result'] = False
        ret['comment'] = _ret['comment']
        ret['changes'] = {}
        return ret
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    return ret


def _get_role_arn(name, region=None, key=None, keyid=None, profile=None):
    if name.startswith('arn:aws:iam:'):
        return name

    account_id = __salt__['boto_iam.get_account_id'](
        region=region, key=key, keyid=keyid, profile=profile
    )
    return 'arn:aws:iam::{0}:role/{1}'.format(account_id, name)


def _function_config_present(FunctionName, Role, Handler, Description, Timeout,
                           MemorySize, region, key, keyid, profile):
    ret = {'result': True, 'comment': '', 'changes': {}}
    func = __salt__['boto_lambda.describe_function'](FunctionName,
           region=region, key=key, keyid=keyid, profile=profile)['function']
    role_arn = _get_role_arn(Role, region, key, keyid, profile)
    need_update = False
    for val, var in {
        'Role': 'role_arn',
        'Handler': 'Handler',
        'Description': 'Description',
        'Timeout': 'Timeout',
        'MemorySize': 'MemorySize',
    }.iteritems():
        if func[val] != locals()[var]:
            need_update = True
            ret['changes'].setdefault('new', {})[var] = locals()[var]
            ret['changes'].setdefault('old', {})[var] = func[val]
    if need_update:
        ret['comment'] = os.linesep.join([ret['comment'], 'Function config to be modified'])
        if __opts__['test']:
            msg = 'Function {0} set to be modified.'.format(FunctionName)
            ret['comment'] = msg
            ret['result'] = None
            return ret
        _r = __salt__['boto_lambda.update_function_config'](FunctionName=FunctionName,
                                        Role=Role, Handler=Handler, Description=Description,
                                        Timeout=Timeout, MemorySize=MemorySize,
                                        region=region, key=key,
                                        keyid=keyid, profile=profile)
        if not _r.get('updated'):
            ret['result'] = False
            ret['comment'] = 'Failed to update function: {0}.'.format(_r['error']['message'])
            ret['changes'] = {}
    return ret


def _function_code_present(FunctionName, ZipFile, S3Bucket, S3Key, S3ObjectVersion,
                         region, key, keyid, profile):
    ret = {'result': True, 'comment': '', 'changes': {}}
    func = __salt__['boto_lambda.describe_function'](FunctionName,
           region=region, key=key, keyid=keyid, profile=profile)['function']
    update = False
    if ZipFile:
        size = os.path.getsize(ZipFile)
        if size == func['CodeSize']:
            sha = hashlib.sha256()
            with salt.utils.fopen(ZipFile, 'rb') as f:
                sha.update(f.read())
            hashed = sha.digest().encode('base64').strip()
            if hashed != func['CodeSha256']:
                update = True
        else:
            update = True
    else:
        # No way to judge whether the item in the s3 bucket is current without
        # downloading it. Cheaper to just request an update every time, and still
        # idempotent
        update = True
    if update:
        if __opts__['test']:
            msg = 'Function {0} set to be modified.'.format(FunctionName)
            ret['comment'] = msg
            ret['result'] = None
            return ret
        ret['changes']['old'] = {
            'CodeSha256': func['CodeSha256'],
            'CodeSize': func['CodeSize'],
        }
        func = __salt__['boto_lambda.update_function_code'](FunctionName, ZipFile, S3Bucket,
            S3Key, S3ObjectVersion,
            region=region, key=key, keyid=keyid, profile=profile)
        if not func.get('updated'):
            ret['result'] = False
            ret['comment'] = 'Failed to update function: {0}.'.format(func['error']['message'])
            ret['changes'] = {}
            return ret
        func = func['function']
        if func['CodeSha256'] != ret['changes']['old']['CodeSha256'] or \
                func['CodeSize'] != ret['changes']['old']['CodeSize']:
            ret['comment'] = os.linesep.join([ret['comment'], 'Function code to be modified'])
            ret['changes']['new'] = {
                'CodeSha256': func['CodeSha256'],
                'CodeSize': func['CodeSize'],
            }
        else:
            del ret['changes']['old']
    return ret


def _function_permissions_present(FunctionName, Permissions,
                           region, key, keyid, profile):
    ret = {'result': True, 'comment': '', 'changes': {}}
    curr_permissions = __salt__['boto_lambda.get_permissions'](FunctionName,
           region=region, key=key, keyid=keyid, profile=profile)['permissions']
    need_update = False
    diffs = salt.utils.compare_dicts(curr_permissions, Permissions)
    if bool(diffs):
        ret['comment'] = os.linesep.join([ret['comment'], 'Function permissions to be modified'])
        if __opts__['test']:
            msg = 'Function {0} set to be modified.'.format(FunctionName)
            ret['comment'] = msg
            ret['result'] = None
            return ret
        for sid, diff in diffs.iteritems():
            if diff.get('old', '') != '':
                # There's a permssion that needs to be removed
                _r = __salt__['boto_lambda.remove_permission'](FunctionName=FunctionName,
                                        StatementId=sid,
                                        region=region, key=key,
                                        keyid=keyid, profile=profile)
                ret['changes'].setdefault('new', {}).setdefault('Permissions',
                                 {})[sid] = {}
                ret['changes'].setdefault('old', {}).setdefault('Permissions',
                                 {})[sid] = diff['old']
            if diff.get('new', '') != '':
                # New permission information needs to be added
                _r = __salt__['boto_lambda.add_permission'](FunctionName=FunctionName,
                                        StatementId=sid,
                                        region=region, key=key,
                                        keyid=keyid, profile=profile,
                                        **diff['new'])
                ret['changes'].setdefault('new', {}).setdefault('Permissions',
                                 {})[sid] = diff['new']
                oldperms = ret['changes'].setdefault('old', {}).setdefault('Permissions',
                                 {})
                if sid not in oldperms:
                    oldperms[sid] = {}
            if not _r.get('updated'):
                ret['result'] = False
                ret['comment'] = 'Failed to update function: {0}.'.format(_r['error']['message'])
                ret['changes'] = {}
    return ret


def function_absent(name, FunctionName, region=None, key=None, keyid=None, profile=None):
    '''
    Ensure function with passed properties is absent.

    name
        The name of the state definition.

    FunctionName
        Name of the function.

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

    ret = {'name': FunctionName,
           'result': True,
           'comment': '',
           'changes': {}
           }

    r = __salt__['boto_lambda.function_exists'](FunctionName, region=region,
                                    key=key, keyid=keyid, profile=profile)
    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to delete function: {0}.'.format(r['error']['message'])
        return ret

    if r and not r['exists']:
        ret['comment'] = 'Function {0} does not exist.'.format(FunctionName)
        return ret

    if __opts__['test']:
        ret['comment'] = 'Function {0} is set to be removed.'.format(FunctionName)
        ret['result'] = None
        return ret
    r = __salt__['boto_lambda.delete_function'](FunctionName,
                                    region=region, key=key,
                                    keyid=keyid, profile=profile)
    if not r['deleted']:
        ret['result'] = False
        ret['comment'] = 'Failed to delete function: {0}.'.format(r['error']['message'])
        return ret
    ret['changes']['old'] = {'function': FunctionName}
    ret['changes']['new'] = {'function': None}
    ret['comment'] = 'Function {0} deleted.'.format(FunctionName)
    return ret


def alias_present(name, FunctionName, Name, FunctionVersion, Description='',
            region=None, key=None, keyid=None, profile=None):
    '''
    Ensure alias exists.

    name
        The name of the state definition.

    FunctionName
        Name of the function for which you want to create an alias.

    Name
        The name of the alias to be created.

    FunctionVersion
        Function version for which you are creating the alias.

    Description
        A short, user-defined function description. Lambda does not use this value. Assign a meaningful
        description as you see fit.

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
    ret = {'name': Name,
           'result': True,
           'comment': '',
           'changes': {}
           }

    r = __salt__['boto_lambda.alias_exists'](FunctionName=FunctionName, Name=Name, region=region,
                                    key=key, keyid=keyid, profile=profile)

    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to create alias: {0}.'.format(r['error']['message'])
        return ret

    if not r.get('exists'):
        if __opts__['test']:
            ret['comment'] = 'Alias {0} is set to be created.'.format(Name)
            ret['result'] = None
            return ret
        r = __salt__['boto_lambda.create_alias'](FunctionName, Name,
                FunctionVersion, Description,
                region, key, keyid, profile)
        if not r.get('created'):
            ret['result'] = False
            ret['comment'] = 'Failed to create alias: {0}.'.format(r['error']['message'])
            return ret
        _describe = __salt__['boto_lambda.describe_alias'](FunctionName, Name, region=region, key=key,
                                                  keyid=keyid, profile=profile)
        ret['changes']['old'] = {'alias': None}
        ret['changes']['new'] = _describe
        ret['comment'] = 'Alias {0} created.'.format(Name)
        return ret

    ret['comment'] = os.linesep.join([ret['comment'], 'Alias {0} is present.'.format(Name)])
    ret['changes'] = {}
    _describe = __salt__['boto_lambda.describe_alias'](FunctionName, Name,
                                                  region=region, key=key, keyid=keyid,
                                                  profile=profile)['alias']

    need_update = False
    for val, var in {
        'FunctionVersion': 'FunctionVersion',
        'Description': 'Description',
    }.iteritems():
        if _describe[val] != locals()[var]:
            need_update = True
            ret['changes'].setdefault('new', {})[var] = locals()[var]
            ret['changes'].setdefault('old', {})[var] = _describe[val]
    if need_update:
        ret['comment'] = os.linesep.join([ret['comment'], 'Alias config to be modified'])
        if __opts__['test']:
            msg = 'Alias {0} set to be modified.'.format(Name)
            ret['comment'] = msg
            ret['result'] = None
            return ret
        _r = __salt__['boto_lambda.update_alias'](FunctionName=FunctionName, Name=Name,
                                        FunctionVersion=FunctionVersion, Description=Description,
                                        region=region, key=key,
                                        keyid=keyid, profile=profile)
        if not _r.get('updated'):
            ret['result'] = False
            ret['comment'] = 'Failed to update alias: {0}.'.format(_r['error']['message'])
            ret['changes'] = {}
    return ret


def alias_absent(name, FunctionName, Name, region=None, key=None, keyid=None, profile=None):
    '''
    Ensure alias with passed properties is absent.

    name
        The name of the state definition.

    FunctionName
        Name of the function.

    Name
        Name of the alias.

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

    ret = {'name': Name,
           'result': True,
           'comment': '',
           'changes': {}
           }

    r = __salt__['boto_lambda.alias_exists'](FunctionName, Name, region=region,
                                    key=key, keyid=keyid, profile=profile)
    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to delete alias: {0}.'.format(r['error']['message'])
        return ret

    if r and not r['exists']:
        ret['comment'] = 'Alias {0} does not exist.'.format(Name)
        return ret

    if __opts__['test']:
        ret['comment'] = 'Alias {0} is set to be removed.'.format(Name)
        ret['result'] = None
        return ret
    r = __salt__['boto_lambda.delete_alias'](FunctionName, Name,
                                    region=region, key=key,
                                    keyid=keyid, profile=profile)
    if not r['deleted']:
        ret['result'] = False
        ret['comment'] = 'Failed to delete alias: {0}.'.format(r['error']['message'])
        return ret
    ret['changes']['old'] = {'alias': Name}
    ret['changes']['new'] = {'alias': None}
    ret['comment'] = 'Alias {0} deleted.'.format(Name)
    return ret


def _get_function_arn(name, region=None, key=None, keyid=None, profile=None):
    if name.startswith('arn:aws:lambda:'):
        return name

    account_id = __salt__['boto_iam.get_account_id'](
        region=region, key=key, keyid=keyid, profile=profile
    )
    if profile and 'region' in profile:
        region = profile['region']
    if region is None:
        region = 'us-east-1'
    return 'arn:aws:lambda:{0}:{1}:function:{2}'.format(region, account_id, name)


def event_source_mapping_present(name, EventSourceArn, FunctionName, StartingPosition,
            Enabled=True, BatchSize=100,
            region=None, key=None, keyid=None, profile=None):
    '''
    Ensure event source mapping exists.

    name
        The name of the state definition.

    EventSourceArn
        The Amazon Resource Name (ARN) of the Amazon Kinesis or the Amazon
        DynamoDB stream that is the event source.

    FunctionName
        The Lambda function to invoke when AWS Lambda detects an event on the
        stream.

        You can specify an unqualified function name (for example, "Thumbnail")
        or you can specify Amazon Resource Name (ARN) of the function (for
        example, "arn:aws:lambda:us-west-2:account-id:function:ThumbNail"). AWS
        Lambda also allows you to specify only the account ID qualifier (for
        example, "account-id:Thumbnail"). Note that the length constraint
        applies only to the ARN. If you specify only the function name, it is
        limited to 64 character in length.

    StartingPosition
        The position in the stream where AWS Lambda should start reading.
        (TRIM_HORIZON | LATEST)

    Enabled
        Indicates whether AWS Lambda should begin polling the event source. By
        default, Enabled is true.

    BatchSize
        The largest number of records that AWS Lambda will retrieve from your
        event source at the time of invoking your function. Your function
        receives an event with all the retrieved records. The default is 100
        records.

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
    ret = {'name': None,
           'result': True,
           'comment': '',
           'changes': {}
           }

    r = __salt__['boto_lambda.event_source_mapping_exists'](EventSourceArn=EventSourceArn,
                                    FunctionName=FunctionName,
                                    region=region, key=key, keyid=keyid, profile=profile)

    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to create event source mapping: {0}.'.format(r['error']['message'])
        return ret

    if not r.get('exists'):
        if __opts__['test']:
            ret['comment'] = 'Event source mapping {0} is set to be created.'.format(FunctionName)
            ret['result'] = None
            return ret
        r = __salt__['boto_lambda.create_event_source_mapping'](EventSourceArn=EventSourceArn,
                    FunctionName=FunctionName, StartingPosition=StartingPosition,
                    Enabled=Enabled, BatchSize=BatchSize,
                    region=region, key=key, keyid=keyid, profile=profile)
        if not r.get('created'):
            ret['result'] = False
            ret['comment'] = 'Failed to create event source mapping: {0}.'.format(r['error']['message'])
            return ret
        _describe = __salt__['boto_lambda.describe_event_source_mapping'](
                                 EventSourceArn=EventSourceArn,
                                 FunctionName=FunctionName,
                                 region=region, key=key, keyid=keyid, profile=profile)
        ret['name'] = _describe['event_source_mapping']['UUID']
        ret['changes']['old'] = {'event_source_mapping': None}
        ret['changes']['new'] = _describe
        ret['comment'] = 'Event source mapping {0} created.'.format(ret['name'])
        return ret

    ret['comment'] = os.linesep.join([ret['comment'], 'Event source mapping is present.'])
    ret['changes'] = {}
    _describe = __salt__['boto_lambda.describe_event_source_mapping'](
                                 EventSourceArn=EventSourceArn,
                                 FunctionName=FunctionName,
                                 region=region, key=key, keyid=keyid, profile=profile)['event_source_mapping']

    need_update = False
    for val, var in {
        'BatchSize': 'BatchSize',
    }.iteritems():
        if _describe[val] != locals()[var]:
            need_update = True
            ret['changes'].setdefault('new', {})[var] = locals()[var]
            ret['changes'].setdefault('old', {})[var] = _describe[val]
    # verify FunctionName against FunctionArn
    function_arn = _get_function_arn(FunctionName,
                    region=region, key=key, keyid=keyid, profile=profile)
    if _describe['FunctionArn'] != function_arn:
        need_update = True
        ret['changes'].setdefault('new', {})['FunctionArn'] = function_arn
        ret['changes'].setdefault('old', {})['FunctionArn'] = _describe['FunctionArn']
    # TODO check for 'Enabled', since it doesn't directly map to a specific state
    if need_update:
        ret['comment'] = os.linesep.join([ret['comment'], 'Event source mapping to be modified'])
        if __opts__['test']:
            msg = 'Event source mapping {0} set to be modified.'.format(_describe['UUID'])
            ret['comment'] = msg
            ret['result'] = None
            return ret
        _r = __salt__['boto_lambda.update_event_source_mapping'](UUID=_describe['UUID'],
                                        FunctionName=FunctionName,
                                        Enabled=Enabled,
                                        BatchSize=BatchSize,
                                        region=region, key=key,
                                        keyid=keyid, profile=profile)
        if not _r.get('updated'):
            ret['result'] = False
            ret['comment'] = 'Failed to update mapping: {0}.'.format(_r['error']['message'])
            ret['changes'] = {}
    return ret


def event_source_mapping_absent(name, EventSourceArn, FunctionName,
                           region=None, key=None, keyid=None, profile=None):
    '''
    Ensure event source mapping with passed properties is absent.

    name
        The name of the state definition.

    EventSourceArn
        ARN of the event source.

    FunctionName
        Name of the lambda function.

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

    ret = {'name': None,
           'result': True,
           'comment': '',
           'changes': {}
           }

    desc = __salt__['boto_lambda.describe_event_source_mapping'](EventSourceArn=EventSourceArn,
                                    FunctionName=FunctionName,
                                    region=region, key=key, keyid=keyid, profile=profile)
    if 'error' in desc:
        ret['result'] = False
        ret['comment'] = 'Failed to delete event source mapping: {0}.'.format(desc['error']['message'])
        return ret

    if not desc.get('event_source_mapping'):
        ret['comment'] = 'Event source mapping does not exist.'
        return ret

    ret['name'] = desc['event_source_mapping']['UUID']
    if __opts__['test']:
        ret['comment'] = 'Event source mapping is set to be removed.'
        ret['result'] = None
        return ret
    r = __salt__['boto_lambda.delete_event_source_mapping'](EventSourceArn=EventSourceArn,
                                        FunctionName=FunctionName,
                                        region=region, key=key,
                                        keyid=keyid, profile=profile)
    if not r['deleted']:
        ret['result'] = False
        ret['comment'] = 'Failed to delete event source mapping: {0}.'.format(r['error']['message'])
        return ret
    ret['changes']['old'] = desc
    ret['changes']['new'] = {'event_source_mapping': None}
    ret['comment'] = 'Event source mapping deleted.'
    return ret
