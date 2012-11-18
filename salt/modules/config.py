'''
Return config information
'''

import logging
import re
from pprint import pformat
from types import StringTypes

log = logging.getLogger(__name__)

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
    Pass in a generic option and recieve the value that will be assigned
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
    Pass in a configuration value that should be preceeded by the module name
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


def pack_pkgs(sources):
    '''
    Accepts list (or a string representing a list) and returns back either the
    list passed, or the list represenation of the string passed.

    Example: '["foo","bar","baz"]' would become ["foo","bar","baz"]
    '''
    if type(sources) in StringTypes:
        try:
            # Safely eval the string data into a list
            sources = eval(sources,{'__builtins__': None},{})
        except Exception as e:
            log.error(e)
            return []
    if not isinstance(sources,list) \
    or [x for x in sources if type(x) not in StringTypes]:
        log.error('Invalid input: {0}'.format(pformat(source)))
        return []
    return sources


def pack_sources(sources):
    '''
    Accepts list of dicts (or a string representing a list of dicts) and packs
    the key/value pairs into a single dict.

    Example: '[{"foo": "salt://foo.rpm"}, {"bar": "salt://bar.rpm"}]' would
    become {"foo": "salt://foo.rpm", "bar": "salt://bar.rpm"}
    '''
    if type(sources) in StringTypes:
        try:
            # Safely eval the string data into a list of dicts
            sources = eval(sources,{'__builtins__': None},{})
        except Exception as e:
            log.error(e)
            return {}
    ret = {}
    for source in sources:
        if (not isinstance(source,dict)) or len(source) != 1:
            log.error('Invalid input: {0}'.format(pformat(sources)))
            return {}
        else:
            ret.update(source)
    return ret
