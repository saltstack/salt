# -*- coding: utf-8 -*-
'''
Provide authentication using Django Web Framework

Django authentication depends on the presence of the django
framework in the PYTHONPATH, the django project's settings.py file being in
the PYTHONPATH and accessible via the DJANGO_SETTINGS_MODULE environment
variable.  This can be hard to debug.

django auth can be defined like any other eauth module:

external_auth:
  django:
    fred:
      - .*
      - '@runner'

This will authenticate Fred via django and allow him to run any
execution module and all runners.

The details of the django auth can also be located inside the django database.  The
relevant entry in the models.py file would look like this:

class SaltExternalAuthModel(models.Model):

  user_fk = models.ForeignKey(auth.User)
  minion_matcher = models.CharField()
  minion_fn = models.CharField()

The contents of this table is loaded and merged with whatever external_auth
definition is in the master config file.  This enables fallback in case the
django database is in an inconsistent state.

This external auth module requires that a particular schema be loaded.
It also needs to


:depends:   - Django Web Framework
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
    import django
    import django.contrib.auth
    HAS_DJANGO = True
except ImportError:
    HAS_DJANGO = False

# Defaults, override in master config
__defopts__ = {'auth.ldap.uri': '',
               'auth.ldap.server': 'localhost',
               'auth.ldap.port': '389',
               'auth.ldap.tls': False,
               'auth.ldap.no_verify': False,
               'auth.ldap.anonymous': False,
               'auth.ldap.scope': 2,
               'auth.ldap.groupou': 'Groups'
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
                 anonymous):
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


def auth(username, password):
    '''
    Simple Django auth
    '''

    # Versions 1.7 and later of Django don't pull models until
    # they are needed.  When using framework facilities outside the
    # web application container we need to run django.setup() to
    # get the model definitions cached.
    if django.VERSION >= (1,7):
        django.setup()
    user = django.contrib.auth.authenticate(username=username, password=password)
    if user is not None:
        if user.is_active:
            log.debug('Django authentication successful')
            return True
        else:
            log.debug('Django authentication: the password is valid but the account is disabled.')

    return False


def groups(username, **kwargs):
    '''
    Authenticate against an LDAP group

    Uses groupou and basedn specified in group to filter
    group search
    '''
    group_list = []
    bind = _bind(username, kwargs['password'])
    if bind:
        search_results = bind.search_s('ou={0},{1}'.format(_config('groupou'), _config('basedn')),
                                       ldap.SCOPE_SUBTREE,
                                       '(&(memberUid={0})(objectClass=posixGroup))'.format(username),
                                       ['memberUid', 'cn'])
    else:
        return False
    for _, entry in search_results:
        if entry['memberUid'][0] == username:
            group_list.append(entry['cn'][0])
    log.debug('User {0} is a member of groups: {1}'.format(username, group_list))
    return group_list
