'''
Pillar LDAP is a plugin module for the salt pillar system which allows external
data (in this case data stored in an LDAP directory) to be incorporated into 
salt state files.

This module was written by Kris Saxton <kris@automationlogic.com>

REQUIREMENTS:

The salt ldap module
An LDAP directory

INSTALLATION:

Drop this module into the 'pillar' directory under the root of the salt 
python pkg; Restart your master.

CONFIGURATION:

Add something like the following to your salt master's config file:

ext_pillar:
  - pillar_ldap: /etc/salt/pillar/plugins/pillar_ldap.yaml

Configure the 'pillar_ldap' config file with your LDAP sources 
and an order in which to search them:

ldap: &defaults
  server: localhost
  port: 389
  tls: False
  dn: o=acme,c=gb
  binddn: uid=admin,o=acme,c=gb
  bindpw: sssssh
  attrs: [saltKeyValue, saltState]
  scope: 1

hosts:
  <<: *defaults
  filter: ou=hosts
  dn: o=customer,o=acme,c=gb

{{ fqdn }}:
  <<: *defaults
  filter: cn={{ fqdn }}
  dn: ou=hosts,o=customer,o=acme,c=gb

search_order:
  - hosts
  - {{ fqdn }}

Essentially whatever is referenced in the 'search_order' list will be searched
from first to last.  The config file is templated allowing you to ref grains.

Where repeated instances of the same data are found during the searches, the
instance found latest in the search order will override any earlier instances.
The final result set is merged with the pillar data.
'''

# Import python libs
import os
import logging
import traceback

# Import salt libs
import salt.config
import salt.utils
from salt._compat import string_types

# Import third party libs
import yaml
from jinja2 import Environment, FileSystemLoader
try:
    import ldap
    import ldap.modlist
    has_ldap = True
except ImportError:
    has_ldap = False

# Set up logging
log = logging.getLogger(__name__)

def __virtual__():
    '''
    Only return if ldap module is installed
    '''
    if has_ldap:
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

def _result_to_dict(data, attrs=None):
    '''
    Formats LDAP search results as a pillar dictionary.
    Attributes tagged in the pillar config file ('attrs') are scannned for the
    'key=value' format.  Matches are written to the dictionary directly as:
    dict[key] = value
    For example, search result:

        saltKeyValue': ['ntpserver=ntp.acme.local', 'foo=myfoo']
    
    is written to the pillar data dictionary as:

        {'ntpserver': 'ntp.acme.local', 'foo': 'myfoo'}
    '''
    
    if not attrs:
        attrs = []
    result = {}
    for key in data:
        if key in attrs:
            for item in data.get(key):
                if '=' in item:
                    k, v = item.split('=')
                    result[k] = v
                else:
                    result[key] = data.get(key)
        else:
            result[key] = data.get(key)
    return result

def _do_search(conf):
    '''
    Builds connection and search arguments, performs the LDAP search and
    formats the results as a dictionary appropriate for pillar use.
    '''
    # Build LDAP connection args
    connargs = {}
    for name in ['server', 'port', 'tls', 'binddn', 'bindpw']:
        connargs[name] = _config(name, conf)
    # Build search args
    try:
        filter = conf['filter']
    except KeyError:
        raise SaltInvocationError('missing filter')
    dn = _config('dn', conf)
    scope = _config('scope', conf) 
    attrs = _config('attrs', conf) 
    # Perform the search
    try:
        raw_result = __salt__['ldap.search'](filter, dn, scope, attrs, **connargs)['results'][0][1]
    except IndexError: # we got no results for this search
        raw_result = {}
        log.debug('LDAP search returned no results for filter {0}'.format(filter))
    except Exception:
        msg = traceback.format_exc()
        log.critical('Failed to retrieve pillar data from LDAP: {0}'.format(msg))
        return {}
    result = _result_to_dict(raw_result, attrs)
    return result

def ext_pillar(config_file):
    '''
    Execute LDAP searches and return the aggregated data
    '''
    if os.path.isfile(config_file):
        try:
            with open(config_file, 'r') as raw_config:
                config = _render_template(config_file) or {}
                opts = yaml.safe_load(config) or {}
            opts['conf_file'] = config_file
        except Exception as e:
            import salt.log
            msg = 'Error parsing configuration file: {0} - {1}'
            if salt.log.is_console_configured():
                log.warn(msg.format(config_file, e))
            else:
                print(msg.format(config_file, e))
    else:
        log.debug('Missing configuration file: {0}'.format(config_file))

    data = {}
    for source in opts['search_order']:
        config = opts[source]
        result = _do_search(config)
        if result:
            data.update(result)
    return data
