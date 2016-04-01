# -*- coding: utf-8 -*-
'''
Return config information
'''

# Import python libs
from __future__ import absolute_import
import copy
import re
import os
import logging

# Import salt libs
import salt.config
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

# Import 3rd-party libs
import salt.ext.six as six

log = logging.getLogger(__name__)

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
    if not isinstance(mode, six.string_types):
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


def get(key, default='', delimiter=':', merge=None):
    '''
    .. versionadded: 0.14.0

    Attempt to retrieve the named value from the minion config file, pillar,
    grains or the master config. If the named value is not available, return the
    value specified by ``default``. If not specified, the default is an empty
    string.

    Values can also be retrieved from nested dictionaries. Assume the below
    data structure:

    .. code-block:: python

        {'pkg': {'apache': 'httpd'}}

    To retrieve the value associated with the ``apache`` key, in the
    sub-dictionary corresponding to the ``pkg`` key, the following command can
    be used:

    .. code-block:: bash

        salt myminion config.get pkg:apache

    The ``:`` (colon) is used to represent a nested dictionary level.

    .. versionchanged:: 2015.5.0
        The ``delimiter`` argument was added, to allow delimiters other than
        ``:`` to be used.

    This function traverses these data stores in this order, returning the
    first match found:

    - Minion config file
    - Minion's grains
    - Minion's pillar data
    - Master config file

    This means that if there is a value that is going to be the same for the
    majority of minions, it can be configured in the Master config file, and
    then overridden using the grains, pillar, or Minion config file.

    **Arguments**

    delimiter
        .. versionadded:: 2015.5.0

        Override the delimiter used to separate nested levels of a data
        structure.

    merge
        .. versionadded:: 2015.5.0

        If passed, this parameter will change the behavior of the function so
        that, instead of traversing each data store above in order and
        returning the first match, the data stores are first merged together
        and then searched. The pillar data is merged into the master config
        data, then the grains are merged, followed by the Minion config data.
        The resulting data structure is then searched for a match. This allows
        for configurations to be more flexible.

        .. note::

            The merging described above does not mean that grain data will end
            up in the Minion's pillar data, or pillar data will end up in the
            master config data, etc. The data is just combined for the purposes
            of searching an amalgam of the different data stores.

        The supported merge strategies are as follows:

        - **recurse** - If a key exists in both dictionaries, and the new value
          is not a dictionary, it is replaced. Otherwise, the sub-dictionaries
          are merged together into a single dictionary, recursively on down,
          following the same criteria. For example:

          .. code-block:: python

              >>> dict1 = {'foo': {'bar': 1, 'qux': True},
                           'hosts': ['a', 'b', 'c'],
                           'only_x': None}
              >>> dict2 = {'foo': {'baz': 2, 'qux': False},
                           'hosts': ['d', 'e', 'f'],
                           'only_y': None}
              >>> merged
              {'foo': {'bar': 1, 'baz': 2, 'qux': False},
               'hosts': ['d', 'e', 'f'],
               'only_dict1': None,
               'only_dict2': None}

        - **overwrite** - If a key exists in the top level of both
          dictionaries, the new value completely overwrites the old. For
          example:

          .. code-block:: python

              >>> dict1 = {'foo': {'bar': 1, 'qux': True},
                           'hosts': ['a', 'b', 'c'],
                           'only_x': None}
              >>> dict2 = {'foo': {'baz': 2, 'qux': False},
                           'hosts': ['d', 'e', 'f'],
                           'only_y': None}
              >>> merged
              {'foo': {'baz': 2, 'qux': False},
               'hosts': ['d', 'e', 'f'],
               'only_dict1': None,
               'only_dict2': None}

    CLI Example:

    .. code-block:: bash

        salt '*' config.get pkg:apache
        salt '*' config.get lxc.container_profile:centos merge=recurse
    '''
    if merge is None:
        ret = salt.utils.traverse_dict_and_list(__opts__,
                                                key,
                                                '_|-',
                                                delimiter=delimiter)
        if ret != '_|-':
            return sdb.sdb_get(ret, __opts__)

        ret = salt.utils.traverse_dict_and_list(__grains__,
                                                key,
                                                '_|-',
                                                delimiter)
        if ret != '_|-':
            return sdb.sdb_get(ret, __opts__)

        ret = salt.utils.traverse_dict_and_list(__pillar__,
                                                key,
                                                '_|-',
                                                delimiter=delimiter)
        if ret != '_|-':
            return sdb.sdb_get(ret, __opts__)

        ret = salt.utils.traverse_dict_and_list(__pillar__.get('master', {}),
                                                key,
                                                '_|-',
                                                delimiter=delimiter)
        if ret != '_|-':
            return sdb.sdb_get(ret, __opts__)
    else:
        if merge not in ('recurse', 'overwrite'):
            log.warning('Unsupported merge strategy \'{0}\'. Falling back '
                        'to \'recurse\'.'.format(merge))
            merge = 'recurse'

        merge_lists = salt.config.master_config('/etc/salt/master').get('pillar_merge_lists')

        data = copy.copy(__pillar__.get('master', {}))
        data = salt.utils.dictupdate.merge(data, __pillar__, strategy=merge, merge_lists=merge_lists)
        data = salt.utils.dictupdate.merge(data, __grains__, strategy=merge, merge_lists=merge_lists)
        data = salt.utils.dictupdate.merge(data, __opts__, strategy=merge, merge_lists=merge_lists)
        ret = salt.utils.traverse_dict_and_list(data,
                                                key,
                                                '_|-',
                                                delimiter=delimiter)
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
    for key, val in six.iteritems(__pillar__.get('master', {})):
        if key.startswith('{0}.'.format(value)):
            ret[key] = val
    for key, val in six.iteritems(__opts__):
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
