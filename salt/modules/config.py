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
            'ca.cert_base_path': '/etc/pki',
            'solr.cores': [],
            'solr.host': 'localhost',
            'solr.port': '8983',
            'solr.baseurl': '/solr',
            'solr.type': 'master',
            'solr.request_timeout': None,
            'solr.init_script': '/etc/rc.d/solr',
            'solr.dih.import_options': {'clean': False, 'optimize': True,
                                        'commit': True, 'verbose': False},
            'solr.backup_path': None,
            'solr.num_backups': 1,
            'poudriere.config': '/usr/local/etc/poudriere.conf',
            'poudriere.config_dir': '/usr/local/etc/poudriere.d',
            'ldap.server': 'localhost',
            'ldap.port': '389',
            'ldap.tls': False,
            'ldap.scope': 2,
            'ldap.attrs': None,
            'ldap.binddn': '',
            'ldap.bindpw': '',
            'hosts.file': '/etc/hosts',
            'aliases.file': '/etc/aliases',
            }



def backup_mode(backup=''):
    '''
    Return the backup mode
    '''
    if backup:
        return backup
    return option('backup_mode')


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


def option(value, default=''):
    '''
    Pass in a generic option and receive the value that will be assigned
    '''
    if value in __opts__:
        return __opts__[value]
    elif value in __pillar__.get('master', {}):
        return __pillar__['master'][value]
    elif value in __pillar__:
        return __pillar__[value]
    elif value in defaults:
        return defaults[value]
    return default


def dot_vals(value):
    '''
    Pass in a configuration value that should be preceded by the module name
    and a dot, this will return a list of all read key/value pairs
    '''
    ret = {}
    for key, val in __pillar__.get('master', {}).items():
        if key.startswith('{0}.'.format(value)):
            ret[key] = val
    for key, val in __opts__.items():
        if key.startswith('{0}.'.format(value)):
            ret[key] = val
    return ret
