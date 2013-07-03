'''
Module to provide LDAP commands via salt.

:depends:   - ldap Python module
:configuration: In order to connect to LDAP, certain configuration is required
    in the minion config on the LDAP server. The minimum configuration items
    that must be set are::

        ldap.basedn: dc=acme,dc=com (example values, adjust to suit)

    If your LDAP server requires authentication then you must also set::

        ldap.binddn: admin
        ldap.bindpw: password

    In addition, the following optional values may be set::

        ldap.server: localhost (default=localhost, see warning below)
        ldap.port: 389 (default=389, standard port)
        ldap.tls: False (default=False, no TLS)
        ldap.scope: 2 (default=2, ldap.SCOPE_SUBTREE)
        ldap.attrs: [saltAttr] (default=None, return all attributes)

.. warning::

    At the moment this module only recommends connection to LDAP services
    listening on 'localhost'.  This is deliberate to avoid the potentially
    dangerous situation of multiple minions sending identical update commands
    to the same LDAP server.  It's easy enough to override this behaviour, but
    badness may ensue - you have been warned.
'''

# Import python libs
import time
import logging

# Import salt libs
from salt.exceptions import CommandExecutionError, SaltInvocationError

# Import third party libs
try:
    import ldap
    import ldap.modlist
    HAS_LDAP = True
except ImportError:
    HAS_LDAP = False

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load this module if the ldap config is set
    '''
    # These config items must be set in the minion config
    if HAS_LDAP:
        return 'ldap'
    return False


def _config(name, key=None, **kwargs):
    '''
    Return a value for 'name' from command line args then config file options.
    Specify 'key' if the config file option is not the same as 'name'.
    '''
    if key is None:
        key = name
    if name in kwargs:
        value = kwargs[name]
    else:
        value = __salt__['config.option']('ldap.{0}'.format(key))
        if not value:
            msg = 'missing ldap.{0} in config or {1} in args'.format(key, name)
            raise SaltInvocationError(msg)
    return value


def _connect(**kwargs):
    '''
    Instantiate LDAP Connection class and return an LDAP connection object
    '''
    connargs = {}
    for name in ['server', 'port', 'tls', 'binddn', 'bindpw']:
        connargs[name] = _config(name, **kwargs)

    return _LDAPConnection(**connargs).ldap


def search(filter,      # pylint: disable=C0103
           dn=None,     # pylint: disable=C0103
           scope=None,
           attrs=None,
           **kwargs):
    '''
    Run an arbitrary LDAP query and return the results.

    CLI Examples::

        salt 'ldaphost' ldap.search "filter=cn=myhost"

    returns::

        'myhost': { 'count': 1,
                'results': [['cn=myhost,ou=hosts,o=acme,c=gb',
                    {'saltKeyValue': ['ntpserver=ntp.acme.local', 'foo=myfoo'],
                     'saltState': ['foo', 'bar']}]],
                'time': {'human': '1.2ms', 'raw': '0.00123'}}}

    Search and connection options can be overridden by specifying the relevant
    option as key=value pairs, for example::

        salt 'ldaphost' ldap.search filter=cn=myhost dn=ou=hosts,o=acme,c=gb
        scope=1 attrs='' server='localhost' port='7393' tls=True bindpw='ssh'

    '''
    if not dn:
        dn = _config('dn', 'basedn')  # pylint: disable=C0103
    if not scope:
        scope = _config('scope')
    if attrs == '':  # Allow command line 'return all' attr override
        attrs = None
    elif attrs is None:
        attrs = _config('attrs')
    _ldap = _connect(**kwargs)
    start = time.time()
    log.debug(
        'Running LDAP search with filter:{0}, dn:{1}, scope:{2}, '
        'attrs:{3}'.format(
            filter, dn, scope, attrs
        )
    )
    results = _ldap.search_s(dn, int(scope), filter, attrs)
    elapsed = (time.time() - start)
    if elapsed < 0.200:
        elapsed_h = str(round(elapsed * 1000, 1)) + 'ms'
    else:
        elapsed_h = str(round(elapsed, 2)) + 's'

    ret = {
        'results': results,
        'count': len(results),
        'time': {'human': elapsed_h, 'raw': str(round(elapsed, 5))},
    }
    return ret


class _LDAPConnection:
    '''
    Setup a LDAP connection.
    '''
    def __init__(self, server, port, tls, binddn, bindpw):
        '''
        Bind to a LDAP directory using passed credentials."""
        '''
        self.server = server
        self.port = port
        self.tls = tls
        self.binddn = binddn
        self.bindpw = bindpw
        try:
            # TODO: Support ldaps:// and possibly ldapi://
            self.ldap = ldap.initialize('ldap://{0}:{1}'.format(
                self.server, self.port
            ))
            self.ldap.protocol_version = 3  # ldap.VERSION3
            if self.tls:
                self.ldap.start_tls_s()
            self.ldap.simple_bind_s(self.binddn, self.bindpw)
        except Exception:
            raise CommandExecutionError(
                'Failed to bind to LDAP server {0}:{1} as {2}'.format(
                    self.server, self.port, self.binddn
                )
            )
