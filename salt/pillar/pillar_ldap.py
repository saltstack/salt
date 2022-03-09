"""
Use LDAP data as a Pillar source

This pillar module executes a series of LDAP searches.
Data returned by these searches are aggregated, whereby data returned by later
searches override data by previous searches with the same key.

The final result is merged with existing pillar data.

The configuration of this external pillar module is done via an external
file which provides the actual configuration for the LDAP searches.

===============================
Configuring the LDAP ext_pillar
===============================

The basic configuration is part of the `master configuration
<master-configuration-ext-pillar>`_.

.. code-block:: yaml

    ext_pillar:
      - pillar_ldap: /etc/salt/master.d/pillar_ldap.yaml

.. note::

    When placing the file in the ``master.d`` directory, make sure its name
    doesn't end in ``.conf``, otherwise the salt-master process will attempt
    to parse its content.

.. warning::

    Make sure this file has very restrictive permissions, as it will contain
    possibly sensitive LDAP credentials!

The only required key in the master configuration is ``pillar_ldap`` pointing
to a file containing the actual configuration.

Configuring the LDAP searches
=============================

The file is processed using `Salt's Renderers <renderers>` which makes it
possible to reference grains within the configuration.

.. warning::

    When using Jinja in this file, make sure to do it in a way which prevents
    leaking sensitive information. A rogue minion could send arbitrary grains
    to trick the master into returning secret data.
    Use only the 'id' grain which is verified through the minion's key/cert.


Map Mode
--------

The ``it-admins`` configuration below returns the Pillar ``it-admins`` by:

- filtering for:
  - members of the group ``it-admins``
  - objects with ``objectclass=user``
- returning the data of users, where each user is a dictionary containing the
  configured string or list attributes.


Configuration
*************

.. code-block:: yaml

    salt-users:
      server:    ldap.company.tld
      port:      389
      tls:       true
      dn:        'dc=company,dc=tld'
      binddn:    'cn=salt-pillars,ou=users,dc=company,dc=tld'
      bindpw:    bi7ieBai5Ano
      referrals: false
      anonymous: false
      mode:      map
      dn:        'ou=users,dc=company,dc=tld'
      filter:    '(&(memberof=cn=it-admins,ou=groups,dc=company,dc=tld)(objectclass=user))'
      attrs:
        - cn
        - displayName
        - givenName
        - sn
      lists:
        - memberOf

    search_order:
      - salt-users

Result
******

.. code-block:: python

    {
        'salt-users': [
            {
                'cn': 'cn=johndoe,ou=users,dc=company,dc=tld',
                'displayName': 'John Doe'
                'givenName': 'John'
                'sn': 'Doe'
                'memberOf': [
                  'cn=it-admins,ou=groups,dc=company,dc=tld',
                  'cn=team01,ou=groups,dc=company'
                ]
            },
            {
                'cn': 'cn=janedoe,ou=users,dc=company,dc=tld',
                'displayName': 'Jane Doe',
                'givenName': 'Jane',
                'sn': 'Doe',
                'memberOf': [
                  'cn=it-admins,ou=groups,dc=company,dc=tld',
                  'cn=team02,ou=groups,dc=company'
                ]
            }
        ]
    }
"""
import logging
import os

import jinja2
import salt.utils.data
from salt.exceptions import SaltInvocationError

try:
    import ldap  # pylint: disable=W0611

    HAS_LDAP = True
except ImportError:
    HAS_LDAP = False

# Set up logging
log = logging.getLogger(__name__)


def __virtual__():
    """
    Only return if ldap module is installed
    """
    if HAS_LDAP:
        return "pillar_ldap"
    else:
        return False


def _render_template(config_file):
    """
    Render config template, substituting grains where found.
    """
    dirname, filename = os.path.split(config_file)
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(dirname))
    template = env.get_template(filename)
    return template.render(__grains__)


def _config(name, conf, default=None):
    """
    Return a value for 'name' from the config file options. If the 'name' is
    not in the config, the 'default' value is returned. This method converts
    unicode values to str type under python 2.
    """
    try:
        value = conf[name]
    except KeyError:
        value = default
    return salt.utils.data.decode(value, to_str=True)


def _result_to_dict(data, result, conf, source):
    """
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
          'saltList': ['vhost=www.acme.net', 'vhost=www.acme.local'] }

    is written to the pillar data dictionary as:

        { 'ntpserver': 'ntp.acme.local', 'foo': 'myfoo',
           'vhost': ['www.acme.net', 'www.acme.local'] }
    """
    attrs = _config("attrs", conf) or []
    lists = _config("lists", conf) or []
    dict_key_attr = _config("dict_key_attr", conf) or "dn"
    # TODO:
    # deprecate the default 'mode: split' and make the more
    # straightforward 'mode: map' the new default
    mode = _config("mode", conf) or "split"
    if mode == "map":
        data[source] = []
        for record in result:
            ret = {}
            if "dn" in attrs or "distinguishedName" in attrs:
                log.debug("dn: %s", record[0])
                ret["dn"] = record[0]
            record = record[1]
            log.debug("record: %s", record)
            for key in record:
                if key in attrs:
                    for item in record.get(key):
                        ret[key] = item
                if key in lists:
                    ret[key] = record.get(key)
            data[source].append(ret)
    elif mode == "dict":
        data[source] = {}
        for record in result:
            ret = {}
            distinguished_name = record[0]
            log.debug("dn: %s", distinguished_name)
            if "dn" in attrs or "distinguishedName" in attrs:
                ret["dn"] = distinguished_name
            record = record[1]
            log.debug("record: %s", record)
            for key in record:
                if key in attrs:
                    for item in record.get(key):
                        ret[key] = item
                if key in lists:
                    ret[key] = record.get(key)
            if dict_key_attr in ["dn", "distinguishedName"]:
                dict_key = distinguished_name
            else:
                dict_key = ",".join(sorted(record.get(dict_key_attr, [])))
            try:
                data[source][dict_key].append(ret)
            except KeyError:
                data[source][dict_key] = [ret]
    elif mode == "split":
        for key in result[0][1]:
            if key in attrs:
                for item in result.get(key):
                    skey, sval = item.split("=", 1)
                    data[skey] = sval
            elif key in lists:
                for item in result.get(key):
                    if "=" in item:
                        skey, sval = item.split("=", 1)
                        if skey not in data:
                            data[skey] = [sval]
                        else:
                            data[skey].append(sval)
    return data


def _do_search(conf):
    """
    Builds connection and search arguments, performs the LDAP search and
    formats the results as a dictionary appropriate for pillar use.
    """
    # Build LDAP connection args
    connargs = {}
    for name in ["server", "port", "tls", "binddn", "bindpw", "anonymous"]:
        connargs[name] = _config(name, conf)
    if connargs["binddn"] and connargs["bindpw"]:
        connargs["anonymous"] = False
    # Build search args
    try:
        _filter = conf["filter"]
    except KeyError:
        raise SaltInvocationError("missing filter")
    _dn = _config("dn", conf)
    scope = _config("scope", conf)
    _lists = _config("lists", conf) or []
    _attrs = _config("attrs", conf) or []
    _dict_key_attr = _config("dict_key_attr", conf, "dn")
    attrs = _lists + _attrs + [_dict_key_attr]
    if not attrs:
        attrs = None
    # Perform the search
    try:
        result = __salt__["ldap.search"](_filter, _dn, scope, attrs, **connargs)[
            "results"
        ]
    except IndexError:  # we got no results for this search
        log.debug("LDAP search returned no results for filter %s", _filter)
        result = {}
    except Exception:  # pylint: disable=broad-except
        log.critical("Failed to retrieve pillar data from LDAP:\n", exc_info=True)
        return {}
    return result


def ext_pillar(
    minion_id, pillar, config_file  # pylint: disable=W0613  # pylint: disable=W0613
):
    """
    Execute LDAP searches and return the aggregated data
    """
    config_template = None
    try:
        config_template = _render_template(config_file)
    except jinja2.exceptions.TemplateNotFound:
        log.debug("pillar_ldap: missing configuration file %s", config_file)
    except Exception:  # pylint: disable=broad-except
        log.debug(
            "pillar_ldap: failed to render template for %s", config_file, exc_info=True
        )

    if not config_template:
        # We don't have a config file
        return {}

    import salt.utils.yaml

    try:
        opts = salt.utils.yaml.safe_load(config_template) or {}
        opts["conf_file"] = config_file
    except Exception as err:  # pylint: disable=broad-except
        import salt.log

        msg = "pillar_ldap: error parsing configuration file: {} - {}".format(
            config_file, err
        )
        if salt.log.is_console_configured():
            log.warning(msg)
        else:
            print(msg)
        return {}
    else:
        if not isinstance(opts, dict):
            log.warning(
                "pillar_ldap: %s is invalidly formatted, must be a YAML "
                "dictionary. See the documentation for more information.",
                config_file,
            )
            return {}

    if "search_order" not in opts:
        log.warning(
            "pillar_ldap: search_order missing from configuration. See the "
            "documentation for more information."
        )
        return {}

    data = {}
    for source in opts["search_order"]:
        config = opts[source]
        result = _do_search(config)
        log.debug("source %s got result %s", source, result)
        if result:
            data = _result_to_dict(data, result, config, source)
    return data
