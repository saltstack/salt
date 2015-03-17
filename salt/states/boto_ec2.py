# -*- coding: utf-8 -*-
'''
Manage EC2

.. versionadded:: TBD
This module provides an interface to the Elastic Compute Cloud (EC2) service
from AWS.

The below code creates a key pair:

.. code-block:: yaml

    Ensure-key-pair-exists:
      boto_ec2.create_key:
        - name: mykeypair
        - save_path: /home/jdoe/
        - region: us-east-1
        - keyid: GKTADJGHEIQSXMKKRBJ08H
        - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

'''
import logging
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto is available.
    '''
    if 'boto_ec2.get_key' in __salt__:
        return 'boto_ec2'
    else:
        return False


def create_key(name, save_path, region=None, key=None, keyid=None,
               profile=None):
    '''
    Ensure key pair is present.
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }
    exists = __salt__['boto_ec2.get_key'](name, region, key, keyid, profile)
    log.debug('exists is {0}'.format(exists))
    if not exists:
        if __opts__['test']:
            ret['comment'] = 'The key {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        created = __salt__['boto_ec2.create_key'](name, save_path, region, key,
                                                  keyid, profile)
        if created:
            ret['result'] = True
            ret['comment'] = 'The key {0} is created.'.format(name)
            ret['changes']['new'] = created
        else:
            ret['result'] = False
            ret['comment'] = 'Could not create key {0} '.format(name)
    else:
        ret['result'] = True
        ret['comment'] = 'The key name {0} already exists'.format(name)
    return ret


def import_key(name, public_key, region=None, key=None,
               keyid=None, profile=None):
    '''
    Create a key by importing the public key.
    .. code-block:: yaml
    import-my-key:
        name: mykey
        public_key: ssh-rsa AAANzaC1yc2EAADABAAABAQC name@domain.local
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }
    exists = __salt__['boto_ec2.get_key'](name, region, key, keyid, profile)
    if not exists:
        if __opts__['test']:
            ret['comment'] = 'The key {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        created = __salt__['boto_ec2.import_key'](name, public_key, region,
                                                  key, keyid, profile)
        if created:
            ret['result'] = True
            ret['comment'] = 'The key {0} is created.'.format(name)
            ret['changes']['old'] = None
            ret['changes']['new'] = created
        else:
            ret['result'] = False
            ret['comment'] = 'Could not create key {0} '.format(name)
    else:
        ret['result'] = True
        ret['comment'] = 'The key name {0} already exists'.format(name)
    return ret


def delete_key(name, region=None, key=None, keyid=None, profile=None):
    '''
    Deletes a key pair
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }
    exists = __salt__['boto_ec2.get_key'](name, region, key, keyid, profile)
    if exists:
        if __opts__['test']:
            ret['comment'] = 'The key {0} is set to be deleted.'.format(name)
            ret['result'] = None
            return ret
        deleted = __salt__['boto_ec2.delete_key'](name, region,
                                                  key, keyid,
                                                  profile)
        log.debug('exists is {0}'.format(deleted))
        if deleted:
            ret['result'] = True
            ret['comment'] = 'The key {0} is deleted.'.format(name)
            ret['changes']['old'] = name
        else:
            ret['result'] = False
            ret['comment'] = 'Could not delete key {0} '.format(name)
    else:
        ret['result'] = True
        ret['comment'] = 'The key name {0} does not exist'.format(name)
    return ret
