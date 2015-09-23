# -*- coding: utf-8 -*-
'''
Provide authentication using simple LDAP binds

:depends:   - ldap Python module
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import salt libs
from salt.exceptions import CommandExecutionError, SaltInvocationError

log = logging.getLogger(__name__)
# Import third party libs
from jinja2 import Environment
try:
    import ldap
    import ldap.modlist
    import ldap.filter
    HAS_LDAP = True
except ImportError:
    HAS_LDAP = False

# Defaults, override in master config
__defopts__ = {'auth.ldap.uri': '',
               'auth.ldap.server': 'localhost',
               'auth.ldap.port': '389',
               'auth.ldap.tls': False,
               'auth.ldap.no_verify': False,
               'auth.ldap.anonymous': False,
               'auth.ldap.scope': 2,
               'auth.ldap.groupou': 'Groups',
               'auth.ldap.accountattributename': 'memberUid',
               'auth.ldap.persontype': 'person',
               'auth.ldap.groupclass': 'posixGroup',
               'auth.ldap.activedirectory': False,
               }


def _config(key, mandatory=True):
    '''
    Return a value for 'name' from master config file options or defaults.
    '''
    try:
        value = __opts__['auth.ldap.{0}'.format(key)]
    except KeyError:
        try:
            value = __defopts__['auth.ldap.{0}'.format(key)]
        except KeyError:
            if mandatory:
                msg = 'missing auth.ldap.{0} in master config'.format(key)
                raise SaltInvocationError(msg)
            return False
    return value


def _render_template(param, username):
    '''
    Render config template, substituting username where found.
    '''
    env = Environment()
    template = env.from_string(param)
    variables = {'username': username}
    return template.render(variables)


class _LDAPConnection(object):
    '''
    Setup an LDAP connection.
    '''

    def __init__(self, uri, server, port, tls, no_verify, binddn, bindpw,
                 anonymous, accountattributename, activedirectory=False):
        '''
        Bind to an LDAP directory using passed credentials.
        '''
        self.uri = uri
        self.server = server
        self.port = port
        self.tls = tls
        schema = 'ldaps' if tls else 'ldap'
        self.binddn = binddn
        self.bindpw = bindpw
        if not HAS_LDAP:
            raise CommandExecutionError('Failed to connect to LDAP, module '
                                        'not loaded')
        if self.uri == '':
            self.uri = '{0}://{1}:{2}'.format(schema, self.server, self.port)

        try:
            if no_verify:
                ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT,
                                ldap.OPT_X_TLS_NEVER)

            self.ldap = ldap.initialize(
                '{0}'.format(self.uri)
            )
            self.ldap.protocol_version = 3  # ldap.VERSION3
            self.ldap.set_option(ldap.OPT_REFERRALS, 0)  # Needed for AD

            if not anonymous:
                self.ldap.simple_bind_s(self.binddn, self.bindpw)
        except Exception as ldap_error:
            raise CommandExecutionError(
                'Failed to bind to LDAP server {0} as {1}: {2}'.format(
                    self.uri, self.binddn, ldap_error
                )
            )


def _bind(username, password, anonymous=False):
    '''
    Authenticate via an LDAP bind
    '''
    # Get config params; create connection dictionary
    basedn = _config('basedn')
    scope = _config('scope')
    connargs = {}
    # config params (auth.ldap.*)
    params = {
        'mandatory': ['uri', 'server', 'port', 'tls', 'no_verify', 'anonymous',
                      'accountattributename', 'activedirectory'],
        'additional': ['binddn', 'bindpw', 'filter', 'groupclass',
                       'auth_by_group_membership_only'],
    }

    paramvalues = {}

    for param in params['mandatory']:
        paramvalues[param] = _config(param)

    for param in params['additional']:
        paramvalues[param] = _config(param, mandatory=False)
        #try:
        #    paramvalues[param] = _config(param)
        #except SaltInvocationError:
        #    pass

    paramvalues['anonymous'] = anonymous
    if paramvalues['binddn']:
        # the binddn can also be composited, e.g.
        #   - {{ username }}@domain.com
        #   - cn={{ username }},ou=users,dc=company,dc=tld
        # so make sure to render it first before using it
        paramvalues['binddn'] = _render_template(paramvalues['binddn'], username)
        paramvalues['binddn'] = ldap.filter.escape_filter_chars(paramvalues['binddn'])

    if paramvalues['filter']:
        escaped_username = ldap.filter.escape_filter_chars(username)
        paramvalues['filter'] = _render_template(paramvalues['filter'], escaped_username)

    # Only add binddn/bindpw to the connargs when they're set, as they're not
    # mandatory for initializing the LDAP object, but if they're provided
    # initially, a bind attempt will be done during the initialization to
    # validate them
    if paramvalues['binddn']:
        connargs['binddn'] = paramvalues['binddn']
        if paramvalues['bindpw']:
            params['mandatory'].append('bindpw')

    for name in params['mandatory']:
        connargs[name] = paramvalues[name]

    if not paramvalues['anonymous']:
        if paramvalues['binddn'] and paramvalues['bindpw']:
            # search for the user's DN to be used for the actual authentication
            _ldap = _LDAPConnection(**connargs).ldap
            log.debug(
                'Running LDAP user dn search with filter:{0}, dn:{1}, '
                'scope:{2}'.format(
                    paramvalues['filter'], basedn, scope
                )
            )
            result = _ldap.search_s(basedn, int(scope), paramvalues['filter'])
            if len(result) < 1:
                log.warn('Unable to find user {0}'.format(username))
                return False
            elif len(result) > 1:
                # Active Directory returns something odd.  Though we do not
                # chase referrals (ldap.set_option(ldap.OPT_REFERRALS, 0) above)
                # it still appears to return several entries for other potential
                # sources for a match.  All these sources have None for the
                # CN (ldap array return items are tuples: (cn, ldap entry))
                # But the actual CNs are at the front of the list.
                # So with some list comprehension magic, extract the first tuple
                # entry from all the results, create a list from those,
                # and count the ones that are not None.  If that total is more than one
                # we need to error out because the ldap filter isn't narrow enough.
                cns = [tup[0] for tup in result]
                total_not_none = sum(1 for c in cns if c is not None)
                if total_not_none > 1:
                    log.error('LDAP lookup found multiple results for user {0}'.format(username))
                    return False
                elif total_not_none == 0:
                    log.error('LDAP lookup--unable to find CN matching user {0}'.format(username))
                    return False

            connargs['binddn'] = result[0][0]
        if paramvalues['binddn'] and not paramvalues['bindpw']:
            connargs['binddn'] = paramvalues['binddn']
    elif paramvalues['binddn'] and not paramvalues['bindpw']:
        connargs['binddn'] = paramvalues['binddn']

    # Update connection dictionary with the user's password
    connargs['bindpw'] = password
    # Attempt bind with user dn and password
    if paramvalues['anonymous']:
        log.debug('Attempting anonymous LDAP bind')
    else:
        log.debug('Attempting LDAP bind with user dn: {0}'.format(connargs['binddn']))
    try:
        ldap_conn = _LDAPConnection(**connargs).ldap
    except Exception:
        connargs.pop('bindpw', None)  # Don't log the password
        log.error('Failed to authenticate user dn via LDAP: {0}'.format(connargs))
        log.debug('Error authenticating user dn via LDAP:', exc_info=True)
        return False
    log.debug(
        'Successfully authenticated user dn via LDAP: {0}'.format(
            connargs['binddn']
        )
    )
    return ldap_conn


def auth(username, password):
    '''
    Simple LDAP auth
    '''
    if _bind(username, password, anonymous=_config('auth_by_group_membership_only', mandatory=False) and
                                           _config('anonymous', mandatory=False)):
        log.debug('LDAP authentication successful')
        return True
    else:
        log.error('LDAP _bind authentication FAILED')
        return False


def groups(username, **kwargs):
    '''
    Authenticate against an LDAP group

    Behavior is highly dependent on if Active Directory is in use.

    AD handles group membership very differently than OpenLDAP.
    See the :ref:`External Authentication <acl-eauth>` documentation for a thorough
    discussion of available parameters for customizing the search.

    OpenLDAP allows you to search for all groups in the directory
    and returns members of those groups.  Then we check against
    the username entered.

    '''
    group_list = []

    bind = _bind(username, kwargs['password'],
                 anonymous=_config('anonymous', mandatory=False))
    if bind:
        log.debug('ldap bind to determine group membership succeeded!')

        if _config('activedirectory'):
            try:
                get_user_dn_search = '(&({0}={1})(objectClass={2}))'.format(_config('accountattributename'),
                                                                            username,
                                                                            _config('persontype'))
                user_dn_results = bind.search_s(_config('basedn'),
                                                ldap.SCOPE_SUBTREE,
                                                get_user_dn_search, ['distinguishedName'])
            except Exception as e:
                log.error('Exception thrown while looking up user DN in AD: {0}'.format(e))
                return group_list
            if not user_dn_results:
                log.error('Could not get distinguished name for user {0}'.format(username))
                return group_list
            # LDAP results are always tuples.  First entry in the tuple is the DN
            dn = ldap.filter.escape_filter_chars(user_dn_results[0][0])
            ldap_search_string = '(&(member={0})(objectClass={1}))'.format(dn, _config('groupclass'))
            log.debug('Running LDAP group membership search: {0}'.format(ldap_search_string))
            try:
                search_results = bind.search_s(_config('basedn'),
                                               ldap.SCOPE_SUBTREE,
                                               ldap_search_string,
                                               [_config('accountattributename'), 'cn'])
            except Exception as e:
                log.error('Exception thrown while retrieving group membership in AD: {0}'.format(e))
                return group_list
            for _, entry in search_results:
                if 'cn' in entry:
                    group_list.append(entry['cn'][0])
            log.debug('User {0} is a member of groups: {1}'.format(username, group_list))
        else:
            if _config('groupou'):
                search_base = 'ou={0},{1}'.format(_config('groupou'), _config('basedn'))
            else:
                search_base = '{0}'.format(_config('basedn'))
            search_string = '(&({0}={1})(objectClass={2}))'.format(_config('accountattributename'),
                                                                   username, _config('groupclass'))
            search_results = bind.search_s(search_base,
                                           ldap.SCOPE_SUBTREE,
                                           search_string,
                                           [_config('accountattributename'), 'cn'])
            for _, entry in search_results:
                if username in entry[_config('accountattributename')]:
                    group_list.append(entry['cn'][0])
            log.debug('User {0} is a member of groups: {1}'.format(username, group_list))

            if not auth(username, kwargs['password']):
                log.error('LDAP username and password do not match')
                return []
    else:
        log.error('ldap bind to determine group membership FAILED!')
        return group_list

    return group_list
