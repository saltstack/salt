# -*- coding: utf-8 -*-
'''
Connection module for Amazon ec2

.. versionadded:: 

:depends: boto
'''

from __future__ import absolute_import

# Import Python libs
import logging
from salt.ext.six import string_types

log = logging.getLogger(__name__)

# Import third party libs
try:
    import boto
    import boto.ec2
    logging.getLogger('boto').setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False


def __virtual__():
    '''
    Only load if boto libraries exist.
    '''
    if not HAS_BOTO:
        return False
    return True


def get_key(key_name, region=None, key=None, keyid=None, profile=None):
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        key = conn.get_key_pair(key_name)
        log.debug("the key to return is : {0}".format(key))
        if key is None:
            return False
        return key.name, key.fingerprint
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return False


def create_key(key_name, save_path, region=None, key=None, keyid=None,
               profile=None):
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        key = conn.create_key_pair(key_name)
        log.debug("the key to return is : {0}".format(key))
        key.save(save_path)
        return key.material
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return False


def import_key(key_name, public_key_material, region=None, key=None,
               keyid=None, profile=None):
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        key = conn.import_key_pair(key_name, public_key_material)
        log.debug("the key to return is : {0}".format(key))
        return key.fingerprint
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return False


def delete_key(key_name, region=None, key=None, keyid=None, profile=None):
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        key = conn.delete_key_pair(key_name)
        log.debug("the key to return is : {0}".format(key))
        return key
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return False


def get_keys(keynames=None, filters=None, region=None, key=None,
             keyid=None, profile=None):
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        keys = conn.get_all_key_pairs(keynames, filters)
        log.debug("the key to return is : {0}".format(keys))
        key_values = []
        if keys:
            for key in keys:
                key_values.append(key.name)
        return key_values
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return False


def _get_conn(region, key, keyid, profile):
    '''
    Get a boto connection to EC2.
    '''
    if profile:
        if isinstance(profile, string_types):
            _profile = __salt__['config.option'](profile)
        elif isinstance(profile, dict):
            _profile = profile
        key = _profile.get('key', None)
        keyid = _profile.get('keyid', None)
        region = _profile.get('region', None)

    if not region and __salt__['config.option']('ec2.region'):
        region = __salt__['config.option']('ec2.region')

    if not region:
        region = 'us-east-1'

    if not key and __salt__['config.option']('ec2.key'):
        key = __salt__['config.option']('ec2.key')
    if not keyid and __salt__['config.option']('ec2.keyid'):
        keyid = __salt__['config.option']('ec2.keyid')

    try:
        conn = boto.ec2.connect_to_region(region, aws_access_key_id=keyid,
                                           aws_secret_access_key=key)
    except boto.exception.NoAuthHandlerFound:
        log.error('No authentication credentials found when attempting to'
                  ' make boto ec2 connection.')
        return None
    return conn
