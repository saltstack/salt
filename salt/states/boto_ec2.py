# -*- coding: utf-8 -*-
'''
Manage EC2

.. versionadded:: 2015.8.0

This module provides an interface to the Elastic Compute Cloud (EC2) service
from AWS.

The below code creates a key pair:

.. code-block:: yaml

    create-key-pair:
      boto_ec2.key_present:
        - name: mykeypair
        - save_private: /root/
        - region: eu-west-1
        - keyid: GKTADJGHEIQSXMKKRBJ08H
        - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

.. code-block:: yaml

    import-key-pair:
       boto_ec2.key_present:
        - name: mykeypair
        - upload_public: 'ssh-rsa AAAA'
        - keyid: GKTADJGHEIQSXMKKRBJ08H
        - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

You can also use salt:// in order to define the public key.

.. code-block:: yaml

    import-key-pair:
       boto_ec2.key_present:
        - name: mykeypair
        - upload_public: salt://mybase/public_key.pub
        - keyid: GKTADJGHEIQSXMKKRBJ08H
        - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

The below code deletes a key pair:

.. code-block:: yaml

    delete-key-pair:
      boto_ec2.key_absent:
        - name: mykeypair
        - region: eu-west-1
        - keyid: GKTADJGHEIQSXMKKRBJ08H
        - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
'''

# Import Python Libs
from __future__ import absolute_import
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


def key_present(name, save_private=None, upload_public=None, region=None, key=None,
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
    if upload_public is not None and 'salt://' in upload_public:
        try:
            upload_public = __salt__['cp.get_file_str'](upload_public)
        except IOError as e:
            log.debug(e)
            ret['comment'] = 'File {0} not found.'.format(upload_public)
            ret['result'] = False
            return ret
    if not exists:
        if __opts__['test']:
            ret['comment'] = 'The key {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        if save_private and not upload_public:
            created = __salt__['boto_ec2.create_key'](name, save_private, region,
                                                      key, keyid, profile)
            if created:
                ret['result'] = True
                ret['comment'] = 'The key {0} is created.'.format(name)
                ret['changes']['new'] = created
            else:
                ret['result'] = False
                ret['comment'] = 'Could not create key {0} '.format(name)
        elif not save_private and upload_public:
            imported = __salt__['boto_ec2.import_key'](name, upload_public,
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


def key_absent(name, region=None, key=None, keyid=None, profile=None):
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
