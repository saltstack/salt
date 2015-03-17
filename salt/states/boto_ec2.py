# -*- coding: utf-8 -*-
'''
Manage EC2

.. versionadded:: TBD
This module provides an interface to the Elastic Compute Cloud (EC2) service
from AWS.

The below code creates a key pair:

.. code-block:: yaml

    create-key-pair:
      boto_ec2.present:
        - name: mykeypair
        - save_priv: /root/
        - region: eu-west-1
        - keyid: GKTADJGHEIQSXMKKRBJ08H
        - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

.. code-block:: yaml

    import-key-pair:
       boto_ec2.present:
        - name: mykeypair
        - upload_pub: 'ssh-rsa AAAA'
        - keyid: GKTADJGHEIQSXMKKRBJ08H
        - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
The below code deleted a key pair:

.. code-block:: yaml
    delete-key-pair:
      boto_ec2.absent:
        - name: mykeypair9
        - region: eu-west-1
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


def present(name, save_priv=None, upload_pub=None, region=None, key=None,
            keyid=None, profile=None):
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
        if save_priv and not upload_pub:
            created = __salt__['boto_ec2.create_key'](name, save_priv, region,
                                                      key, keyid, profile)
            if created:
                ret['result'] = True
                ret['comment'] = 'The key {0} is created.'.format(name)
                ret['changes']['new'] = created
            else:
                ret['result'] = False
                ret['comment'] = 'Could not create key {0} '.format(name)
        elif not save_priv and upload_pub:
            imported = __salt__['boto_ec2.import_key'](name, upload_pub,
                                                       region, key, keyid,
                                                       profile)
            if imported:
                ret['result'] = True
                ret['comment'] = 'The key {0} is created.'.format(name)
                ret['changes']['old'] = None
                ret['changes']['new'] = imported
            else:
                ret['result'] = False
                ret['comment'] = 'Could not create key {0} '.format(name)
        else:
            ret['result'] = False
            ret['comment'] = 'You can either upload or download a private key '
    else:
        ret['result'] = True
        ret['comment'] = 'The key name {0} already exists'.format(name)
    return ret


def absent(name, region=None, key=None, keyid=None, profile=None):
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
