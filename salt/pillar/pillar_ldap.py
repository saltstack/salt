# -*- coding: utf-8 -*-
'''
Use LDAP data as a Pillar source

This pillar module parses a config file (specified in the salt master config),
and executes a series of LDAP searches based on that config.  Data returned by
these searches is aggregated, with data items found later in the LDAP search
order overriding data found earlier on.

The final result set is merged with the pillar data.
'''

# Import python libs
from __future__ import print_function
from __future__ import absolute_import
import os
import logging

# Import salt libs
from salt.exceptions import SaltInvocationError

# Import third party libs
import yaml
from jinja2 import Environment, FileSystemLoader
try:
    import ldap  # pylint: disable=W0611
    HAS_LDAP = True
except ImportError:
    HAS_LDAP = False

# Set up logging
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only return if ldap module is installed
    '''
    if HAS_LDAP:
        return 'pillar_ldap'
    else:
        return False


def _render_template(config_file):
    '''
    Render config template, substituting grains where found.
    '''
    dirname, filename = os.path.split(config_file)
    env = Environment(loader=FileSystemLoader(dirname))
    template = env.get_template(filename)
    config = template.render(__grains__)
    return config


def _config(name, conf):
    '''
    Return a value for 'name' from  the config file options.
    '''
    try:
        value = conf[name]
    except KeyError:
        value = None
    return value


def _result_to_dict(data, result, conf):
    '''
    Aggregates LDAP search result based on rules, returns a dictionary.

    Rules:
    Attributes tagged in the pillar config as 'attrs' or 'lists' are
    scanned for a 'key=value' format (non matching entries are ignored.

    Entries matching the 'attrs' tag overwrite previous values where
    the key matches a previous result.

    Entries matching the 'lists' tag are appended to list of values where
    the key matches a previous result.

    All Matching entries are then written directly to the pillar data
    dictionary as data[key] = value.

    For example, search result:

        { saltKeyValue': ['ntpserver=ntp.acme.local', 'foo=myfoo'],
          'saltList': ['vhost=www.acme.net', 'vhost=www.acme.local' }

    is written to the pillar data dictionary as:

        { 'ntpserver': 'ntp.acme.local', 'foo': 'myfoo',
           'vhost': ['www.acme.net', 'www.acme.local' }
    '''
    attrs = _config('attrs', conf) or []
    lists = _config('lists', conf) or []
    for key in result:
        if key in attrs:
            for item in result.get(key):
                if '=' in item:
                    skey, sval = item.split('=', 1)
                    data[skey] = sval
        elif key in lists:
            for item in result.get(key):
                if '=' in item:
                    skey, sval = item.split('=', 1)
                    if skey not in data:
                        data[skey] = [sval]
                    else:
                        data[skey].append(sval)
    print('Returning data {0}'.format(data))
    return data


def _do_search(conf):
    '''
    Builds connection and search arguments, performs the LDAP search and
    formats the results as a dictionary appropriate for pillar use.
    '''
    # Build LDAP connection args
    connargs = {}
    for name in ['server', 'port', 'tls', 'binddn', 'bindpw', 'anonymous']:
        connargs[name] = _config(name, conf)
    if connargs['binddn'] and connargs['bindpw']:
        connargs['anonymous'] = False
    # Build search args
    try:
        _filter = conf['filter']
    except KeyError:
        raise SaltInvocationError('missing filter')
    _dn = _config('dn', conf)
    scope = _config('scope', conf)
    _lists = _config('lists', conf) or []
    _attrs = _config('attrs', conf) or []
    attrs = _lists + _attrs
    if not attrs:
        attrs = None
    # Perform the search
    try:
        result = __salt__['ldap.search'](_filter, _dn, scope, attrs,
                                         **connargs)['results'][0][1]
    except IndexError:  # we got no results for this search
        log.debug(
            'LDAP search returned no results for filter {0}'.format(
                _filter
            )
        )
        result = {}
    except Exception:
        log.critical(
            'Failed to retrieve pillar data from LDAP:\n', exc_info=True
        )
        return {}
    return result


def ext_pillar(minion_id,  # pylint: disable=W0613
               pillar,  # pylint: disable=W0613
               config_file):
    '''
    Execute LDAP searches and return the aggregated data
    '''
    if os.path.isfile(config_file):
        try:
            #open(config_file, 'r') as raw_config:
            config = _render_template(config_file) or {}
            opts = yaml.safe_load(config) or {}
            opts['conf_file'] = config_file
        except Exception as err:
            import salt.log
            msg = 'Error parsing configuration file: {0} - {1}'
            if salt.log.is_console_configured():
                log.warn(msg.format(config_file, err))
            else:
                print(msg.format(config_file, err))
    else:
        log.debug('Missing configuration file: {0}'.format(config_file))

    data = {}
    for source in opts['search_order']:
        config = opts[source]
        result = _do_search(config)
        print('source {0} got result {1}'.format(source, result))
        if result:
            data = _result_to_dict(data, result, config)
    return data
