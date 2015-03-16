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
    '''
    Check to see if a key exists. Returns fingerprint and name if
    it does and False if it doesn't
    CLI example::

        salt myminion boto_ec2.get_key mykey
    '''
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
    '''
    Creates a key and saves it to a given path.
    Returns the private key.
    CLI example::

        salt myminion boto_ec2.create mykey /root/
    '''
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
    '''
    Imports the public key from an RSA key pair that you created with a third-party tool.
    Supported formats:
    - OpenSSH public key format (e.g., the format in ~/.ssh/authorized_keys)
    - Base64 encoded DER format
    - SSH public key file format as specified in RFC4716
    - DSA keys are not supported. Make sure your key generator is set up to create RSA keys.
    Supported lengths: 1024, 2048, and 4096.
    CLI example::

        salt myminion boto_ec2.import mykey publickey
    '''
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
    '''
    Deletes a key. Always returns True
    CLI example::

        salt myminion boto_ec2.delete_key mykey
    '''
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
    '''
    Gets all keys or filters them by name and returns a list.
    keynames (list):: A list of the names of keypairs to retrieve.
    If not provided, all key pairs will be returned.
    filters (dict) :: Optional filters that can be used to limit the
    results returned. Filters are provided in the form of a dictionary
    consisting of filter names as the key and filter values as the
    value. The set of allowable filter names/values is dependent on
    the request being performed. Check the EC2 API guide for details.
    CLI example::

        salt myminion boto_ec2.get_keys
    '''
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
