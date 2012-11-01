'''
Return config information
'''

import re

# Set up the default values for all systems
defaults = {'mongo.db': 'salt',
            'mongo.host': 'salt',
            'mongo.password': '',
            'mongo.port': 27017,
            'mongo.user': '',
            'redis.db': '0',
            'redis.host': 'salt',
            'redis.port': 6379,
            'test.foo': 'unconfigured',
            'ca.cert_base_path': '/etc/pki'}


def backup_mode(backup=''):
    '''
    Return the backup mode
    '''
    if backup:
        return backup
    if 'backup_mode' in __opts__:
        return __opts__['backup_mode']
    if 'master.backup_mode' in __pillar__:
        return __pillar__['master.backup_mode']
    id_conf = 'master.{0}.backup_mode'.format(__grains__['id'])
    if id_conf in __pillar__:
        return __pillar__[id_conf]


def manage_mode(mode):
    '''
    Return a mode value, normalized to a string
    '''
    if mode:
        mode = str(mode).lstrip('0')
        if not mode:
            return '0'
        else:
            return mode
    return mode


def valid_fileproto(uri):
    '''
    Returns a boolean value based on whether or not the URI passed has a valid
    remote file protocol designation
    '''
    try:
        return bool(re.match('^(?:salt|https?|ftp)://',uri))
    except:
        return False


def option(value):
    '''
    Pass in a generic option and recieve the value that will be assigned
    '''
    if value in __opts__:
        return __opts__[value]
    elif value in __pillar__.get('master', {}):
        return __pillar__['master'][value]
    elif value in defaults:
        return defaults[value]
    return ''
