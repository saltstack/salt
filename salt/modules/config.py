# -*- coding: utf-8 -*-
'''
Return config information
'''

# Import python libs
import re
import os

# Import salt libs
import salt.utils
try:
    # Gated for salt-ssh (salt.utils.cloud imports msgpack)
    import salt.utils.cloud
    HAS_CLOUD = True
except ImportError:
    HAS_CLOUD = False

import salt._compat
import salt.syspaths as syspaths
import salt.utils.sdb as sdb

__proxyenabled__ = ['*']

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
            'ldap.uri': '',
            'ldap.server': 'localhost',
            'ldap.port': '389',
            'ldap.tls': False,
            'ldap.no_verify': False,
            'ldap.anonymous': True,
            'ldap.scope': 2,
            'ldap.attrs': None,
            'ldap.binddn': '',
            'ldap.bindpw': '',
            'hosts.file': '/etc/hosts',
            'aliases.file': '/etc/aliases',
            'virt.images': os.path.join(syspaths.SRV_ROOT_DIR, 'salt-images'),
            'virt.tunnel': False,
            }


def backup_mode(backup=''):
    '''
    Return the backup mode

    CLI Example:

    .. code-block:: bash

        salt '*' config.backup_mode
    '''
    if backup:
        return backup
    return option('backup_mode')


def manage_mode(mode):
    '''
    Return a mode value, normalized to a string

    CLI Example:

    .. code-block:: bash

        salt '*' config.manage_mode
    '''
    if mode is None:
        return None
    if not isinstance(mode, salt._compat.string_types):
        # Make it a string in case it's not
        mode = str(mode)
    # Strip any quotes and initial 0, though zero-pad it up to 4
    ret = mode.strip('"').strip('\'').lstrip('0').zfill(4)
    if ret[0] != '0':
        # Always include a leading zero
        return '0{0}'.format(ret)
    return ret


def valid_fileproto(uri):
    '''
    Returns a boolean value based on whether or not the URI passed has a valid
    remote file protocol designation

    CLI Example:

    .. code-block:: bash

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

    CLI Example:

    .. code-block:: bash

        salt '*' config.option redis.host
    '''
    if not omit_opts:
        if value in __opts__:
            return __opts__[value]
    if not omit_master:
        if value in __pillar__.get('master', {}):
            salt.utils.warn_until(
                'Lithium',
                'pillar_opts will default to False in the Lithium release'
            )
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

    CLI Example:

    .. code-block:: bash

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
            salt.utils.warn_until(
                'Lithium',
                'pillar_opts will default to False in the Lithium release'
            )
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
    .. versionadded: 0.14.0

    Attempt to retrieve the named value from opts, pillar, grains or the master
    config, if the named value is not available return the passed default.
    The default return is an empty string.

    The value can also represent a value in a nested dict using a ":" delimiter
    for the dict. This means that if a dict looks like this::

        {'pkg': {'apache': 'httpd'}}

    To retrieve the value associated with the apache key in the pkg dict this
    key can be passed::

        pkg:apache

    This routine traverses these data stores in this order:

    - Local minion config (opts)
    - Minion's grains
    - Minion's pillar
    - Master config

    CLI Example:

    .. code-block:: bash

        salt '*' config.get pkg:apache
    '''
    ret = salt.utils.traverse_dict_and_list(__opts__, key, '_|-')
    if ret != '_|-':
        return sdb.sdb_get(ret, __opts__)

    ret = salt.utils.traverse_dict_and_list(__grains__, key, '_|-')
    if ret != '_|-':
        return sdb.sdb_get(ret, __opts__)

    ret = salt.utils.traverse_dict_and_list(__pillar__, key, '_|-')
    if ret != '_|-':
        return sdb.sdb_get(ret, __opts__)

    ret = salt.utils.traverse_dict_and_list(__pillar__.get('master', {}), key, '_|-')
    salt.utils.warn_until(
        'Lithium',
        'pillar_opts will default to False in the Lithium release'
    )
    if ret != '_|-':
        return sdb.sdb_get(ret, __opts__)

    return default


def dot_vals(value):
    '''
    Pass in a configuration value that should be preceded by the module name
    and a dot, this will return a list of all read key/value pairs

    CLI Example:

    .. code-block:: bash

        salt '*' config.dot_vals host
    '''
    ret = {}
    for key, val in __pillar__.get('master', {}).items():
        salt.utils.warn_until(
            'Lithium',
            'pillar_opts will default to False in the Lithium release'
        )
        if key.startswith('{0}.'.format(value)):
            ret[key] = val
    for key, val in __opts__.items():
        if key.startswith('{0}.'.format(value)):
            ret[key] = val
    return ret


def gather_bootstrap_script(bootstrap=None):
    '''
    Download the salt-bootstrap script, and return its location

    bootstrap
        URL of alternate bootstrap script

    CLI Example:

    .. code-block:: bash

        salt '*' config.gather_bootstrap_script
    '''
    if not HAS_CLOUD:
        return False, 'config.gather_bootstrap_script is unavailable'
    ret = salt.utils.cloud.update_bootstrap(__opts__, url=bootstrap)
    if 'Success' in ret and len(ret['Success']['Files updated']) > 0:
        return ret['Success']['Files updated'][0]
