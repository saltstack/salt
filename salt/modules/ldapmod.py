# -*- coding: utf-8 -*-
"""
Salt interface to LDAP commands

:depends:   - ldap Python module
:configuration: In order to connect to LDAP, certain configuration is required
    in the minion config on the LDAP server. The minimum configuration items
    that must be set are:

    .. code-block:: yaml

        ldap.basedn: dc=acme,dc=com (example values, adjust to suit)

    If your LDAP server requires authentication then you must also set:

    .. code-block:: yaml

        ldap.anonymous: False
        ldap.binddn: admin
        ldap.bindpw: password

    In addition, the following optional values may be set:

    .. code-block:: yaml

        ldap.server: localhost (default=localhost, see warning below)
        ldap.port: 389 (default=389, standard port)
        ldap.tls: False (default=False, no TLS)
        ldap.no_verify: False (default=False, verify TLS)
        ldap.anonymous: True (default=True, bind anonymous)
        ldap.scope: 2 (default=2, ldap.SCOPE_SUBTREE)
        ldap.attrs: [saltAttr] (default=None, return all attributes)

.. warning::

    At the moment this module only recommends connection to LDAP services
    listening on ``localhost``. This is deliberate to avoid the potentially
    dangerous situation of multiple minions sending identical update commands
    to the same LDAP server. It's easy enough to override this behavior, but
    badness may ensue - you have been warned.
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import time

# Import Salt libs
import salt.utils.data
from salt.exceptions import CommandExecutionError
from salt.ext import six

# Import third party libs
try:
    import ldap
    import ldap.modlist  # pylint: disable=no-name-in-module

    HAS_LDAP = True
except ImportError:
    HAS_LDAP = False

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "ldap"


def __virtual__():
    """
    Only load this module if the ldap config is set
    """
    # These config items must be set in the minion config
    if HAS_LDAP:
        return __virtualname__
    return (
        False,
        "The ldapmod execution module cannot be loaded: ldap config not present.",
    )


def _config(name, key=None, **kwargs):
    """
    Return a value for 'name' from command line args then config file options.
    Specify 'key' if the config file option is not the same as 'name'.
    """
    if key is None:
        key = name
    if name in kwargs:
        value = kwargs[name]
    else:
        value = __salt__["config.option"]("ldap.{0}".format(key))
    return salt.utils.data.decode(value, to_str=True)


def _connect(**kwargs):
    """
    Instantiate LDAP Connection class and return an LDAP connection object
    """
    connargs = {}
    for name in [
        "uri",
        "server",
        "port",
        "tls",
        "no_verify",
        "binddn",
        "bindpw",
        "anonymous",
    ]:
        connargs[name] = _config(name, **kwargs)

    return _LDAPConnection(**connargs).ldap


def search(
    filter,  # pylint: disable=C0103
    dn=None,  # pylint: disable=C0103
    scope=None,
    attrs=None,
    **kwargs
):
    """
    Run an arbitrary LDAP query and return the results.

    CLI Example:

    .. code-block:: bash

        salt 'ldaphost' ldap.search "filter=cn=myhost"

    Return data:

    .. code-block:: python

        {'myhost': {'count': 1,
                    'results': [['cn=myhost,ou=hosts,o=acme,c=gb',
                                 {'saltKeyValue': ['ntpserver=ntp.acme.local',
                                                   'foo=myfoo'],
                                  'saltState': ['foo', 'bar']}]],
                    'time': {'human': '1.2ms', 'raw': '0.00123'}}}

    Search and connection options can be overridden by specifying the relevant
    option as key=value pairs, for example:

    .. code-block:: bash

        salt 'ldaphost' ldap.search filter=cn=myhost dn=ou=hosts,o=acme,c=gb
        scope=1 attrs='' server='localhost' port='7393' tls=True bindpw='ssh'
    """
    if not dn:
        dn = _config("dn", "basedn")  # pylint: disable=C0103
    if not scope:
        scope = _config("scope")
    if attrs == "":  # Allow command line 'return all' attr override
        attrs = None
    elif attrs is None:
        attrs = _config("attrs")
    _ldap = _connect(**kwargs)
    start = time.time()
    log.debug(
        "Running LDAP search with filter:%s, dn:%s, scope:%s, " "attrs:%s",
        filter,
        dn,
        scope,
        attrs,
    )
    results = _ldap.search_s(dn, int(scope), filter, attrs)
    elapsed = time.time() - start
    if elapsed < 0.200:
        elapsed_h = six.text_type(round(elapsed * 1000, 1)) + "ms"
    else:
        elapsed_h = six.text_type(round(elapsed, 2)) + "s"

    ret = {
        "results": results,
        "count": len(results),
        "time": {"human": elapsed_h, "raw": six.text_type(round(elapsed, 5))},
    }
    return ret


class _LDAPConnection(object):
    """
    Setup an LDAP connection.
    """

    def __init__(self, uri, server, port, tls, no_verify, binddn, bindpw, anonymous):
        """
        Bind to an LDAP directory using passed credentials.
        """
        self.uri = uri
        self.server = server
        self.port = port
        self.tls = tls
        self.binddn = binddn
        self.bindpw = bindpw

        if self.uri == "":
            self.uri = "ldap://{0}:{1}".format(self.server, self.port)

        try:
            if no_verify:
                ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)

            self.ldap = ldap.initialize("{0}".format(self.uri))
            self.ldap.protocol_version = 3  # ldap.VERSION3
            self.ldap.set_option(ldap.OPT_REFERRALS, 0)  # Needed for AD

            if self.tls:
                self.ldap.start_tls_s()

            if not anonymous:
                self.ldap.simple_bind_s(self.binddn, self.bindpw)
        except Exception as ldap_error:  # pylint: disable=broad-except
            raise CommandExecutionError(
                "Failed to bind to LDAP server {0} as {1}: {2}".format(
                    self.uri, self.binddn, ldap_error
                )
            )
