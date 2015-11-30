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
            - role_name: iam_role_name
            - handler: entry_function
            - code:
              zipfile: code.zip
              s3bucket: bucketname
              s3key: keyname
              s3objectversion: version
            - description: "My Lambda Function"
            - timeout: 3
            - memorysize: 128
            - publish: false
            - region: us-east-1
            - keyid: GKTADJGHEIQSXMKKRBJ08H
            - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

'''

# Import Python Libs
from __future__ import absolute_import
import logging

# Import Salt Libs
import salt.utils.dictupdate as dictupdate

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto_lambda' if 'boto_lambda.exists' in __salt__ else False


def present(name, runtime, handler, code, role_name=None, role_id=None, 
            description=None, timeout=None, memorysize=None, publish=False,
            region=None, key=None, keyid=None, profile=None):
    '''
    Ensure Lambda Function exists.

    name
        Name of the Lambda Function.

    runtime
        The runtime environment for the Lambda function. One of 
        'nodejs', 'java8', or 'python2.7'

    handler
        The function within your code that Lambda calls to begin execution. For Node.js it is the
        module-name.*export* value in your function. For Java, it can be package.classname::handler or
        package.class-name.

    code
        The code for the lambda function.
        * zipfile - A .zip file containing your deployment package.
        * s3bucket - Amazon S3 bucket name where the .zip file containing your package is stored.
        * s3key - The Amazon S3 object (the deployment package) key name you want to upload.
        * s3objectversion - The Amazon S3 object (the deployment package) version you want to upload.

    role_name
        The name of the IAM role that Lambda assumes when it executes your
        function to access any other AWS resources. One of role_name or role_id must be specified.

    role_id
        The Amazon Resource Name (ARN) of the IAM role that Lambda assumes when it executes your
        function to access any other AWS resources. One of role_name or role_id must be specified.

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

    publish
        This boolean parameter can be used to request AWS Lambda to create the Lambda function and publish
        a version as an atomic operation.

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
        r = __salt__['boto_lambda.create'](name, runtime, handler, code, role_name=None, role_id=None, 
            description=None, timeout=None, memorysize=None, publish=False,
            region=None, key=None, keyid=None, profile=Nonecidr_block, instance_tenancy,
                                        name, dns_support, dns_hostnames,
                                        tags, region, key, keyid, profile)
        if not r.get('created'):
            ret['result'] = False
            ret['comment'] = 'Failed to create Lamda function: {0}.'.format(r['error']['message'])
            return ret
        _describe = __salt__['boto_lambda.describe'](r['id'], region=region, key=key,
                                                  keyid=keyid, profile=profile)
        ret['changes']['old'] = {'lambda': None}
        ret['changes']['new'] = _describe
        ret['comment'] = 'Lambda function {0} created.'.format(name)
        return ret
    ret['comment'] = 'Lamda function present.'
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

    r = __salt__['boto_lambda.get_id'](name=name, region=region,
                                    key=key, keyid=keyid, profile=profile)
    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to delete Lambda function: {0}.'.format(r['error']['message'])
        return ret

    _id = r.get('id')
    if not _id:
        ret['comment'] = 'Lambda function {0} does not exist.'.format(name)
        return ret

    if __opts__['test']:
        ret['comment'] = 'Lambda function {0} is set to be removed.'.format(name)
        ret['result'] = None
        return ret
    r = __salt__['boto_lambda.delete'](name=name, 
                                    region=region, key=key,
                                    keyid=keyid, profile=profile)
    if not r['deleted']:
        ret['result'] = False
        ret['comment'] = 'Failed to delete Lambda function: {0}.'.format(r['error']['message'])
        return ret
    ret['changes']['old'] = {'lambda': _id}
    ret['changes']['new'] = {'lambda': None}
    ret['comment'] = 'Lambda function {0} deleted.'.format(name)
    return ret
