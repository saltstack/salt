'''
Return config information
'''

# Import python libs
import re
import os
import urllib

# Import salt libs
import salt.utils

# Set up the default values for all systems
DEFAULTS = {'mongo.db': 'salt',
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
            'virt.images': '/srv/salt-images',
            'virt.tunnel': False,
            }


def backup_mode(backup=''):
    '''
    Return the backup mode

    CLI Example::

        salt '*' config.backup_mode
    '''
    if backup:
        return backup
    return option('backup_mode')


def manage_mode(mode):
    '''
    Return a mode value, normalized to a string

    CLI Example::

        salt '*' config.manage_mode
    '''
    if mode is None:
        return None
    return str(mode).lstrip('0').zfill(3)


def valid_fileproto(uri):
    '''
    Returns a boolean value based on whether or not the URI passed has a valid
    remote file protocol designation

    CLI Example::

        salt '*' config.valid_fileproto salt://path/to/file
    '''
    try:
        return bool(re.match('^(?:salt|https?|ftp)://', uri))
    except Exception:
        return False


def option(
        value,
        default='',
        omit_opts=False,
        omit_master=False,
        omit_pillar=False):
    '''
    Pass in a generic option and receive the value that will be assigned

    CLI Example::

        salt '*' config.option redis.host
    '''
    if not omit_opts:
        if value in __opts__:
            return __opts__[value]
    if not omit_master:
        if value in __pillar__.get('master', {}):
            return __pillar__['master'][value]
    if not omit_pillar:
        if value in __pillar__:
            return __pillar__[value]
    if value in DEFAULTS:
        return DEFAULTS[value]
    return default


def merge(value,
          default='',
          omit_opts=False,
          omit_master=False,
          omit_pillar=False):
    '''
    Retrieves an option based on key, merging all matches.

    Same as ``option()`` except that it merges all matches, rather than taking
    the first match.

    CLI Example::

        salt '*' config.merge schedule
    '''
    ret = None
    if not omit_opts:
        if value in __opts__:
            ret = __opts__[value]
            if isinstance(ret, str):
                return ret
    if not omit_master:
        if value in __pillar__.get('master', {}):
            tmp = __pillar__['master'][value]
            if ret is None:
                ret = tmp
                if isinstance(ret, str):
                    return ret
            elif isinstance(ret, dict) and isinstance(tmp, dict):
                tmp.update(ret)
                ret = tmp
            elif isinstance(ret, (list, tuple)) and isinstance(tmp,
                                                               (list, tuple)):
                ret = list(ret) + list(tmp)
    if not omit_pillar:
        if value in __pillar__:
            tmp = __pillar__[value]
            if ret is None:
                ret = tmp
                if isinstance(ret, str):
                    return ret
            elif isinstance(ret, dict) and isinstance(tmp, dict):
                tmp.update(ret)
                ret = tmp
            elif isinstance(ret, (list, tuple)) and isinstance(tmp,
                                                               (list, tuple)):
                ret = list(ret) + list(tmp)
    if ret is None and value in DEFAULTS:
        return DEFAULTS[value]
    return ret or default


def get(key, default=''):
    '''
    .. versionadded: 0.14

    Attempt to retrieve the named value from opts, pillar, grains of the master
    config, if the named value is not available return the passed default.
    The default return is an empty string.

    The value can also represent a value in a nested dict using a ":" delimiter
    for the dict. This means that if a dict looks like this:

    {'pkg': {'apache': 'httpd'}}

    To retrieve the value associated with the apache key in the pkg dict this
    key can be passed:

    pkg:apache

    This routine traverses these data stores in this order:

        Local minion config (opts)
        Minion's grains
        Minion's pillar
        Master config

    CLI Example::

        salt '*' config.get pkg:apache
    '''
    ret = salt.utils.traverse_dict(__opts__, key, '_|-')
    if ret != '_|-':
        return ret
    ret = salt.utils.traverse_dict(__grains__, key, '_|-')
    if ret != '_|-':
        return ret
    ret = salt.utils.traverse_dict(__pillar__, key, '_|-')
    if ret != '_|-':
        return ret
    ret = salt.utils.traverse_dict(__pillar__.get('master', {}), key, '_|-')
    if ret != '_|-':
        return ret
    return default


def dot_vals(value):
    '''
    Pass in a configuration value that should be preceded by the module name
    and a dot, this will return a list of all read key/value pairs

    CLI Example::

        salt '*' config.dot_vals host
    '''
    ret = {}
    for key, val in __pillar__.get('master', {}).items():
        if key.startswith('{0}.'.format(value)):
            ret[key] = val
    for key, val in __opts__.items():
        if key.startswith('{0}.'.format(value)):
            ret[key] = val
    return ret


def gather_bootstrap_script(replace=False):
    '''
    Download the salt-bootstrap script, set replace to True to refresh the
    script if it has already been downloaded

    CLI Example::

        salt '*' qemu.gather_bootstrap_script True
    '''
    fn_ = os.path.join(__opts__['cachedir'], 'bootstrap.sh')
    if not replace and os.path.isfile(fn_):
        return fn_
    with open(fn_, 'w+') as fp_:
        fp_.write(urllib.urlopen('http://bootstrap.saltstack.org').read())
    return fn_
