'''
Return config information
'''

import re

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
