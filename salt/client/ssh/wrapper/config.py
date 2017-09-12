# -*- coding: utf-8 -*-
'''
Return config information
'''

# Import python libs
from __future__ import absolute_import
import re
import os

# Import salt libs
import salt.utils
import salt.syspaths as syspaths

# Import 3rd-party libs
from salt.ext import six

# Set up the default values for all systems
DEFAULTS = {u'mongo.db': u'salt',
            u'mongo.host': u'salt',
            u'mongo.password': u'',
            u'mongo.port': 27017,
            u'mongo.user': u'',
            u'redis.db': u'0',
            u'redis.host': u'salt',
            u'redis.port': 6379,
            u'test.foo': u'unconfigured',
            u'ca.cert_base_path': u'/etc/pki',
            u'solr.cores': [],
            u'solr.host': u'localhost',
            u'solr.port': u'8983',
            u'solr.baseurl': u'/solr',
            u'solr.type': u'master',
            u'solr.request_timeout': None,
            u'solr.init_script': u'/etc/rc.d/solr',
            u'solr.dih.import_options': {u'clean': False, u'optimize': True,
                                         u'commit': True, u'verbose': False},
            u'solr.backup_path': None,
            u'solr.num_backups': 1,
            u'poudriere.config': u'/usr/local/etc/poudriere.conf',
            u'poudriere.config_dir': u'/usr/local/etc/poudriere.d',
            u'ldap.server': u'localhost',
            u'ldap.port': u'389',
            u'ldap.tls': False,
            u'ldap.scope': 2,
            u'ldap.attrs': None,
            u'ldap.binddn': u'',
            u'ldap.bindpw': u'',
            u'hosts.file': u'/etc/hosts',
            u'aliases.file': u'/etc/aliases',
            u'virt.images': os.path.join(syspaths.SRV_ROOT_DIR, u'salt-images'),
            u'virt.tunnel': False,
            }


def backup_mode(backup=u''):
    '''
    Return the backup mode

    CLI Example:

    .. code-block:: bash

        salt '*' config.backup_mode
    '''
    if backup:
        return backup
    return option(u'backup_mode')


def manage_mode(mode):
    '''
    Return a mode value, normalized to a string

    CLI Example:

    .. code-block:: bash

        salt '*' config.manage_mode
    '''
    # config.manage_mode should no longer be invoked from the __salt__ dunder
    # in Salt code, this function is only being left here for backwards
    # compatibility.
    return salt.utils.normalize_mode(mode)


def valid_fileproto(uri):
    '''
    Returns a boolean value based on whether or not the URI passed has a valid
    remote file protocol designation

    CLI Example:

    .. code-block:: bash

        salt '*' config.valid_fileproto salt://path/to/file
    '''
    try:
        return bool(re.match(u'^(?:salt|https?|ftp)://', uri))
    except Exception:
        return False


def option(
        value,
        default=u'',
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
        if value in __pillar__.get(u'master', {}):
            return __pillar__[u'master'][value]
    if not omit_pillar:
        if value in __pillar__:
            return __pillar__[value]
    if value in DEFAULTS:
        return DEFAULTS[value]
    return default


def merge(value,
          default=u'',
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
            if isinstance(ret, six.string_types):
                return ret
    if not omit_master:
        if value in __pillar__.get(u'master', {}):
            tmp = __pillar__[u'master'][value]
            if ret is None:
                ret = tmp
                if isinstance(ret, six.string_types):
                    return ret
            elif isinstance(ret, dict) and isinstance(tmp, dict):
                tmp.update(ret)
                ret = tmp
            elif (isinstance(ret, (list, tuple)) and
                    isinstance(tmp, (list, tuple))):
                ret = list(ret) + list(tmp)
    if not omit_pillar:
        if value in __pillar__:
            tmp = __pillar__[value]
            if ret is None:
                ret = tmp
                if isinstance(ret, six.string_types):
                    return ret
            elif isinstance(ret, dict) and isinstance(tmp, dict):
                tmp.update(ret)
                ret = tmp
            elif (isinstance(ret, (list, tuple)) and
                    isinstance(tmp, (list, tuple))):
                ret = list(ret) + list(tmp)
    if ret is None and value in DEFAULTS:
        return DEFAULTS[value]
    return ret or default


def get(key, default=u''):
    '''
    .. versionadded: 0.14.0

    Attempt to retrieve the named value from opts, pillar, grains of the master
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
    ret = salt.utils.traverse_dict_and_list(__opts__, key, u'_|-')
    if ret != u'_|-':
        return ret
    ret = salt.utils.traverse_dict_and_list(__grains__, key, u'_|-')
    if ret != u'_|-':
        return ret
    ret = salt.utils.traverse_dict_and_list(__pillar__, key, u'_|-')
    if ret != u'_|-':
        return ret
    ret = salt.utils.traverse_dict_and_list(__pillar__.get(u'master', {}), key, u'_|-')
    if ret != u'_|-':
        return ret
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
    for key, val in six.iteritems(__pillar__.get(u'master', {})):
        if key.startswith(u'{0}.'.format(value)):
            ret[key] = val
    for key, val in six.iteritems(__opts__):
        if key.startswith(u'{0}.'.format(value)):
            ret[key] = val
    return ret
