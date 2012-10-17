'''
Module to provide LDAP commands via salt.

REQUIREMENT 1:

In order to connect to LDAP, certain configuration is required
in the minion config on the LDAP server.
The minimum configuration items that must be set are:

    ldap.basedn: dc=acme,dc=com (example values, adjust to suit)

If your LDAP server requires authentication then you must also set:

    ldap.binddn: admin
    ldap.bindpw: password

In addition, the following optional values may be set:

    ldap.server: localhost (default=localhost, see warning below)
    ldap.port: 389 (default=389, standard port)
    ldap.tls: False (default=False, no TLS)
    ldap.scope: 2 (default=2, ldap.SCOPE_SUBTREE)
    ldap.attrs: [saltAttr] (default=None, return all attributes)

WARNING:
At the moment this module only recommends connection to LDAP services
listening on 'localhost'.  This is deliberate to avoid the potentially
dangerous situation of multiple minions sending identical update commands to
the same LDAP server.  It's easy enough to override this behaviour,
but badness may ensue - you have been warned.

REQUIREMENT 2:

Required python modules: ldap
'''
# Import Python libs
import time
import logging

# Import salt libs
from salt.exceptions import CommandExecutionError, SaltInvocationError

# Import third party libs
try:
    import ldap
    import ldap.modlist
    has_ldap = True
except ImportError:
    has_ldap = False

log = logging.getLogger(__name__)

# Defaults in the event that these are not found in the minion or pillar config
__opts__ = {'ldap.server': 'localhost',
            'ldap.port': '389',
            'ldap.tls': False,
            'ldap.scope': 2,
            'ldap.attrs': None,
            'ldap.binddn': '',
            'ldap.bindpw': ''}


def __virtual__():
    '''
    Only load this module if the ldap config is set
    '''
    # These config items must be set in the minion config
    if has_ldap:
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
        try:
            value = __opts__['ldap.{0}'.format(key)]
        except KeyError:
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

    return _LDAPConnection(**connargs).LDAP


def search(filter, dn=None, scope=None, attrs=None, **kwargs):
    '''
    Run an arbitrary LDAP query and return the results.

    CLI Examples::
        salt 'ldaphost' ldap.search "filter=cn=myhost"
        returns:
    'myhost': { 'count': 1,
                'results': [['cn=myhost,ou=hosts,o=acme,c=gb',
                    {'saltKeyValue': ['ntpserver=ntp.acme.local', 'foo=myfoo'],
                     'saltState': ['foo', 'bar']}]],
                'time': {'human': '1.2ms', 'raw': '0.00123'}}}

    Search and connection options can be overridden by specifying the relevant
    option as key=value pairs, for example:
        salt 'ldaphost' ldap.search filter=cn=myhost dn=ou=hosts,o=acme,c=gb
        scope=1 attrs='' server='localhost' port='7393' tls=True bindpw='ssh'

    '''
    if not dn:
        dn = _config('dn', 'basedn')
    if not scope:
        scope = _config('scope')
    if attrs == '':  # Allow command line 'return all' attr override
        attrs = None
    elif attrs is None:
        attrs = _config('attrs')
    _ldap = _connect(**kwargs)
    start = time.time()
    msg = 'Running LDAP search with filter:%s, dn:%s, scope:%s, attrs:%s' %\
        (filter, dn, scope, attrs)
    log.debug(msg)
    results = _ldap.search_s(dn, int(scope), filter, attrs)
    elapsed = (time.time() - start)
    if elapsed < 0.200:
        elapsed_h = str(round(elapsed * 1000, 1)) + 'ms'
    else:
        elapsed_h = str(round(elapsed, 2)) + 's'
    ret = {}
    ret['time'] = {'human': elapsed_h, 'raw': str(round(elapsed, 5))}
    ret['count'] = len(results)
    ret['results'] = results
    return ret


class _LDAPConnection:

    """Setup an LDAP connection."""

    def __init__(self, server, port, tls, binddn, bindpw):
        '''
        Bind to an LDAP directory using passed credentials."""
        '''
        self.server = server
        self.port = port
        self.tls = tls
        self.binddn = binddn
        self.bindpw = bindpw
        try:
            self.LDAP = ldap.initialize('ldap://%s:%s' %
                                        (self.server, self.port))
            self.LDAP.protocol_version = 3  # ldap.VERSION3
            if self.tls:
                self.LDAP.start_tls_s()
            self.LDAP.simple_bind_s(self.binddn, self.bindpw)
        except Exception:
            msg = 'Failed to bind to LDAP server %s:%s as %s' % \
                (self.server, self.port, self.binddn)
            raise CommandExecutionError(msg)
