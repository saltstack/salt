# -*- coding: utf-8 -*-
'''
Manage Lambda Functions
=================

.. versionadded:: 

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

    Ensure Lambda function exists:
        boto_lmabda.present:
            - name: myfunction
            - runtime: python2.7
            - role: iam_role_name
            - handler: entry_function
            - zipfile: code.zip
            - s3bucket: bucketname
            - s3key: keyname
            - s3objectversion: version
            - description: "My Lambda Function"
            - timeout: 3
            - memorysize: 128
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

# Import Salt Libs
import salt.utils.dictupdate as dictupdate

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto_lambda' if 'boto_lambda.exists' in __salt__ else False


def present(name, runtime, role, handler, zipfile=None, s3bucket=None,
            s3key=None, s3objectversion=None, 
            description='', timeout=3, memorysize=128,
            region=None, key=None, keyid=None, profile=None):
    '''
    Ensure Lambda Function exists.

    name
        Name of the Lambda Function.

    role
        The name or ARN of the IAM role that Lambda assumes when it executes your
        function to access any other AWS resources.

    runtime
        The runtime environment for the Lambda function. One of 
        'nodejs', 'java8', or 'python2.7'

    handler
        The function within your code that Lambda calls to begin execution. For Node.js it is the
        module-name.*export* value in your function. For Java, it can be package.classname::handler or
        package.class-name.

    zipfile
        A path to a .zip file containing your deployment package. If this is
        specified, s3bucket and s3key must not be specified.

    s3bucket
        Amazon S3 bucket name where the .zip file containing your package is
        stored. If this is specified, s3key must be specified and zipfile must
        NOT be specified.

    s3key
        The Amazon S3 object (the deployment package) key name you want to
        upload. If this is specified, s3key must be specified and zipfile must
        NOT be specified.

    s3objectversion
        The version of S3 object to use. Optional, should only be specified if
        s3bucket and s3key are specified.

    description
        A short, user-defined function description. Lambda does not use this value. Assign a meaningful
        description as you see fit.

    timeout
        The function execution time at which Lamda should terminate this function. Because the execution 
        time has cost implications, we recommend you set this value based on your expected execution time.
        The default is 3 seconds.

    memorysize
        The amount of memory, in MB, your Lambda function is given. Lamda uses this memory size to infer 
        the amount of CPU and memory allocated to your function. Your function use-case determines your
        CPU and memory requirements. For example, a database operation might need less memory compared
        to an image processing function. The default value is 128 MB. The value must be a multiple of
        64 MB.

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
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }

    r = __salt__['boto_lambda.exists'](name=name, region=region,
                                    key=key, keyid=keyid, profile=profile)

    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to create Lambda function: {0}.'.format(r['error']['message'])
        return ret

    if not r.get('exists'):
        if __opts__['test']:
            ret['comment'] = 'Lambda function {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        r = __salt__['boto_lambda.create'](name, runtime, role, handler, 
            zipfile, s3bucket, s3key, s3objectversion,
            description, timeout, memorysize, 
            region, key, keyid, profile)
        if not r.get('created'):
            ret['result'] = False
            ret['comment'] = 'Failed to create Lamda function: {0}.'.format(r['error']['message'])
            return ret
        _describe = __salt__['boto_lambda.describe'](name, region=region, key=key,
                                                  keyid=keyid, profile=profile)
        ret['changes']['old'] = {'lambda': None}
        ret['changes']['new'] = _describe
        ret['comment'] = 'Lambda function {0} created.'.format(name)
        return ret

    ret['comment'] = os.linesep.join([ret['comment'], 'Lambda function {0} is present.'.format(name)])
    ret['changes'] = {}
    # Lambda function exists, ensure config matches
    _ret = _lambda_config_present(name, role, handler, description, timeout,
                                  memorysize, region, key, keyid, profile)
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    _ret = _lambda_code_present(name, zipfile, s3bucket, s3key, s3objectversion,
                                 region, key, keyid, profile)
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


def _lambda_config_present(name, role, handler, description, timeout,
                           memorysize, region, key, keyid, profile):
    ret = {'result': True, 'comment': '', 'changes': {}}
    lmbda = __salt__['boto_lambda.describe'](name, 
           region=region, key=key, keyid=keyid, profile=profile)['lambda']
    role_arn = _get_role_arn(role, region, key, keyid, profile)
    need_update = False
    for val, var in {
        'Role': 'role_arn',
        'Handler': 'handler',
        'Description': 'description',
        'Timeout': 'timeout',
        'MemorySize': 'memorysize',
    }.iteritems():
        if lmbda[val] != locals()[var]:
            need_update = True
            ret['changes'].setdefault('new',{})[var] = locals()[var]
            ret['changes'].setdefault('old',{})[var] = lmbda[val]
    if need_update:
        ret['comment'] = os.linesep.join([ret['comment'], 'Lambda function config to be modified'])
        _r = __salt__['boto_lambda.update_config'](name, role, handler, description,
                                        timeout, memorysize, region=region, key=key,
                                        keyid=keyid, profile=profile)
    return ret


def _lambda_code_present(name, zipfile, s3bucket, s3key, s3objectversion,
                         region, key, keyid, profile):
    ret = {'result': True, 'comment': '', 'changes': {}}
    lmbda = __salt__['boto_lambda.describe'](name, 
           region=region, key=key, keyid=keyid, profile=profile)['lambda']
    update = False
    if zipfile:
        size = os.path.getsize(zipfile)
        if size == lmbda['CodeSize']:
            sha = hashlib.sha256()
            with open(zipfile, 'rb') as f:
                sha.update(f.read())
            hashed = sha.digest().encode('base64').strip()
            if hashed != lmbda['CodeSha256']:
                update = True
        else:
            update=True
    else:
       # No way to judge whether the item in the s3 bucket is current without
       # downloading it. Cheaper to just request an update every time, and still
       # idempotent
       update = True
    if update:
        ret['changes']['old'] = {
            'CodeSha256': lmbda['CodeSha256'],
            'CodeSize': lmbda['CodeSize'],
        }
        lmbda = __salt__['boto_lambda.update_code'](name, zipfile, s3bucket,
            s3key, s3objectversion, 
            region=region, key=key, keyid=keyid, profile=profile)['lambda']
        if lmbda['CodeSha256'] != ret['changes']['old']['CodeSha256'] or \
                lmbda['CodeSize'] != ret['changes']['old']['CodeSize']:
            ret['comment'] = os.linesep.join([ret['comment'], 'Lambda function code to be modified'])
            ret['changes']['new'] = {
                'CodeSha256': lmbda['CodeSha256'],
                'CodeSize': lmbda['CodeSize'],
            }
        else:
			del(ret['changes']['old'])
    return ret



def absent(name, region=None, key=None, keyid=None, profile=None):
    '''
    Ensure Lamda function with passed properties is absent.

    name
        Name of the Lambda function.

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

    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }

    r = __salt__['boto_lambda.exists'](name, region=region,
                                    key=key, keyid=keyid, profile=profile)
    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to delete Lambda function: {0}.'.format(r['error']['message'])
        return ret

    if not r:
        ret['comment'] = 'Lambda function {0} does not exist.'.format(name)
        return ret

    if __opts__['test']:
        ret['comment'] = 'Lambda function {0} is set to be removed.'.format(name)
        ret['result'] = None
        return ret
    r = __salt__['boto_lambda.delete'](name,
                                    region=region, key=key,
                                    keyid=keyid, profile=profile)
    if not r['deleted']:
        ret['result'] = False
        ret['comment'] = 'Failed to delete Lambda function: {0}.'.format(r['error']['message'])
        return ret
    ret['changes']['old'] = {'lambda': name}
    ret['changes']['new'] = {'lambda': None}
    ret['comment'] = 'Lambda function {0} deleted.'.format(name)
    return ret
