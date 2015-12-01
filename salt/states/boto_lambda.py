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

    Ensure function exists:
        boto_lambda.function_present:
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
    return 'boto_lambda' if 'boto_lambda.function_exists' in __salt__ else False


def function_present(name, runtime, role, handler, zipfile=None, s3bucket=None,
            s3key=None, s3objectversion=None, 
            description='', timeout=3, memorysize=128,
            region=None, key=None, keyid=None, profile=None):
    '''
    Ensure function exists.

    name
        Name of the Function.

    role
        The name or ARN of the IAM role that the function assumes when it executes your
        function to access any other AWS resources.

    runtime
        The runtime environment for the function. One of 
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
        The function execution time at which Lambda should terminate this function. Because the execution 
        time has cost implications, we recommend you set this value based on your expected execution time.
        The default is 3 seconds.

    memorysize
        The amount of memory, in MB, your function is given. Lambda uses this memory size to infer 
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

    r = __salt__['boto_lambda.function_exists'](name=name, region=region,
                                    key=key, keyid=keyid, profile=profile)

    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to create function: {0}.'.format(r['error']['message'])
        return ret

    if not r.get('exists'):
        if __opts__['test']:
            ret['comment'] = 'Function {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        r = __salt__['boto_lambda.create_function'](name=name, runtime=runtime,
                                                    role=role, handler=handler, 
                                                    zipfile=zipfile, s3bucket=s3bucket, 
                                                    s3key=s3key,
                                                    s3objectversion=s3objectversion,
                                                    description=description, 
                                                    timeout=timeout, memorysize=memorysize, 
                                                    region=region, key=key,
                                                    keyid=keyid, profile=profile)
        if not r.get('created'):
            ret['result'] = False
            ret['comment'] = 'Failed to create function: {0}.'.format(r['error']['message'])
            return ret
        _describe = __salt__['boto_lambda.describe_function'](name, region=region, key=key,
                                                  keyid=keyid, profile=profile)
        ret['changes']['old'] = {'function': None}
        ret['changes']['new'] = _describe
        ret['comment'] = 'Function {0} created.'.format(name)
        return ret

    ret['comment'] = os.linesep.join([ret['comment'], 'Function {0} is present.'.format(name)])
    ret['changes'] = {}
    # function exists, ensure config matches
    _ret = _function_config_present(name, role, handler, description, timeout,
                                  memorysize, region, key, keyid, profile)
    if not _ret.get('result'):
        ret['result'] = False
        ret['comment'] = _ret['comment']
        ret['changes'] = {}
        return ret
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    _ret = _function_code_present(name, zipfile, s3bucket, s3key, s3objectversion,
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


def _function_config_present(name, role, handler, description, timeout,
                           memorysize, region, key, keyid, profile):
    ret = {'result': True, 'comment': '', 'changes': {}}
    func = __salt__['boto_lambda.describe_function'](name, 
           region=region, key=key, keyid=keyid, profile=profile)['function']
    role_arn = _get_role_arn(role, region, key, keyid, profile)
    need_update = False
    for val, var in {
        'Role': 'role_arn',
        'Handler': 'handler',
        'Description': 'description',
        'Timeout': 'timeout',
        'MemorySize': 'memorysize',
    }.iteritems():
        if func[val] != locals()[var]:
            need_update = True
            ret['changes'].setdefault('new',{})[var] = locals()[var]
            ret['changes'].setdefault('old',{})[var] = func[val]
    if need_update:
        ret['comment'] = os.linesep.join([ret['comment'], 'Function config to be modified'])
        if __opts__['test']:
            msg = 'Function {0} set to be modified.'.format(name)
            ret['comment'] = msg
            ret['result'] = None
            return ret
        _r = __salt__['boto_lambda.update_function_config'](name=name,
                                        role=role, handler=handler, description=description,
                                        timeout=timeout, memorysize=memorysize, 
                                        region=region, key=key,
                                        keyid=keyid, profile=profile)
        if not _r.get('updated'):
            ret['result'] = False
            ret['comment'] = 'Failed to update function: {0}.'.format(_r['error']['message'])
            ret['changes'] = {}
    return ret


def _function_code_present(name, zipfile, s3bucket, s3key, s3objectversion,
                         region, key, keyid, profile):
    ret = {'result': True, 'comment': '', 'changes': {}}
    func = __salt__['boto_lambda.describe_function'](name, 
           region=region, key=key, keyid=keyid, profile=profile)['function']
    update = False
    if zipfile:
        size = os.path.getsize(zipfile)
        if size == func['CodeSize']:
            sha = hashlib.sha256()
            with open(zipfile, 'rb') as f:
                sha.update(f.read())
            hashed = sha.digest().encode('base64').strip()
            if hashed != func['CodeSha256']:
                update = True
        else:
            update=True
    else:
       # No way to judge whether the item in the s3 bucket is current without
       # downloading it. Cheaper to just request an update every time, and still
       # idempotent
       update = True
    if update:
        if __opts__['test']:
            msg = 'Function {0} set to be modified.'.format(name)
            ret['comment'] = msg
            ret['result'] = None
            return ret
        ret['changes']['old'] = {
            'CodeSha256': func['CodeSha256'],
            'CodeSize': func['CodeSize'],
        }
        func = __salt__['boto_lambda.update_function_code'](name, zipfile, s3bucket,
            s3key, s3objectversion, 
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
			del(ret['changes']['old'])
    return ret



def function_absent(name, region=None, key=None, keyid=None, profile=None):
    '''
    Ensure function with passed properties is absent.

    name
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

    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }

    r = __salt__['boto_lambda.function_exists'](name, region=region,
                                    key=key, keyid=keyid, profile=profile)
    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to delete function: {0}.'.format(r['error']['message'])
        return ret

    if not r:
        ret['comment'] = 'Function {0} does not exist.'.format(name)
        return ret

    if __opts__['test']:
        ret['comment'] = 'Function {0} is set to be removed.'.format(name)
        ret['result'] = None
        return ret
    r = __salt__['boto_lambda.delete_function'](name,
                                    region=region, key=key,
                                    keyid=keyid, profile=profile)
    if not r['deleted']:
        ret['result'] = False
        ret['comment'] = 'Failed to delete function: {0}.'.format(r['error']['message'])
        return ret
    ret['changes']['old'] = {'function': name}
    ret['changes']['new'] = {'function': None}
    ret['comment'] = 'Function {0} deleted.'.format(name)
    return ret


def alias_present(functionname, name, functionversion, description='', 
            region=None, key=None, keyid=None, profile=None):
    '''
    Ensure alias exists.

    functionname
        Name of the function for which you want to create an alias.

    name
        The name of the alias to be created.

    functionversion
        Function version for which you are creating the alias.

    description
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
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }

    r = __salt__['boto_lambda.alias_exists'](functionname=functionname, name=name, region=region,
                                    key=key, keyid=keyid, profile=profile)

    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to create alias: {0}.'.format(r['error']['message'])
        return ret

    if not r.get('exists'):
        if __opts__['test']:
            ret['comment'] = 'Alias {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        r = __salt__['boto_lambda.create_alias'](functionname, name,
                functionversion, description,
                region, key, keyid, profile)
        if not r.get('created'):
            ret['result'] = False
            ret['comment'] = 'Failed to create alias: {0}.'.format(r['error']['message'])
            return ret
        _describe = __salt__['boto_lambda.describe_alias'](functionname, name, region=region, key=key,
                                                  keyid=keyid, profile=profile)
        ret['changes']['old'] = {'alias': None}
        ret['changes']['new'] = _describe
        ret['comment'] = 'Alias {0} created.'.format(name)
        return ret

    ret['comment'] = os.linesep.join([ret['comment'], 'Alias {0} is present.'.format(name)])
    ret['changes'] = {}
    _describe = __salt__['boto_lambda.describe_alias'](functionname, name, 
                                                  region=region, key=key, keyid=keyid,
                                                  profile=profile)['alias']

    need_update = False
    for val, var in {
        'FunctionVersion': 'functionversion',
        'Description': 'description',
    }.iteritems():
        if _describe[val] != locals()[var]:
            need_update = True
            ret['changes'].setdefault('new',{})[var] = locals()[var]
            ret['changes'].setdefault('old',{})[var] = func[val]
    if need_update:
        ret['comment'] = os.linesep.join([ret['comment'], 'Alias config to be modified'])
        if __opts__['test']:
            msg = 'Alias {0} set to be modified.'.format(name)
            ret['comment'] = msg
            ret['result'] = None
            return ret
        _r = __salt__['boto_lambda.update_alias'](functionname=functionname, name=name,
                                        functionversion=functionversion, description=description, 
                                        region=region, key=key,
                                        keyid=keyid, profile=profile)
        ret['changes'] = dictupdate.update(ret['changes'], _r['changes'])
        ret['comment'] = ' '.join([ret['comment'], _r['comment']])
    return ret


def alias_absent(functionname, name, region=None, key=None, keyid=None, profile=None):
    '''
    Ensure alias with passed properties is absent.

    functionname
        Name of the function.

    name
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

    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }

    r = __salt__['boto_lambda.alias_exists'](functionname, name, region=region,
                                    key=key, keyid=keyid, profile=profile)
    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to delete alias: {0}.'.format(r['error']['message'])
        return ret

    if not r:
        ret['comment'] = 'Alias {0} does not exist.'.format(name)
        return ret

    if __opts__['test']:
        ret['comment'] = 'Alias {0} is set to be removed.'.format(name)
        ret['result'] = None
        return ret
    r = __salt__['boto_lambda.delete_alias'](functionname, name,
                                    region=region, key=key,
                                    keyid=keyid, profile=profile)
    if not r['deleted']:
        ret['result'] = False
        ret['comment'] = 'Failed to delete alias: {0}.'.format(r['error']['message'])
        return ret
    ret['changes']['old'] = {'function': name}
    ret['changes']['new'] = {'function': None}
    ret['comment'] = 'Function {0} deleted.'.format(name)
    return ret


