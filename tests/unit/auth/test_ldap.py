# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import yaml

# Import Salt Libs
import salt.auth.ldap

# Import Salt Testing Libs
from tests.support.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON
from tests.support.unit import skipIf, TestCase


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not salt.auth.ldap.HAS_LDAP, 'Install python-ldap for this test')
class LDAPAuthTestCase(TestCase):
    '''
    Unit tests for salt.auth.ldap
    '''
    def setUp(self):
        salt.auth.ldap.__opts__ = {
            'auth.ldap.binddn': 'uid={{username}},cn=users,cn=compat,dc=saltstack,dc=com',
            'auth.ldap.port': 389,
            'auth.ldap.tls': False,
            'auth.ldap.server': '172.18.0.2',
            'auth.ldap.accountattributename': 'memberUid',
            'auth.ldap.groupattribute': 'memberOf',
            'auth.ldap.group_basedn': 'cn=groups,cn=compat,dc=saltstack,dc=com',
            'auth.ldap.basedn': 'dc=saltstack,dc=com',
            'auth.ldap.group_filter': '(&(memberUid={{ username }})(objectClass=posixgroup))'}
    
    def tearDown(self):
        salt.auth.ldap.__opts__['auth.ldap.freeipa'] = False
        salt.auth.ldap.__opts__['auth.ldap.activedirectory'] = False
    
    def test_config(self):
        self.assertEqual(salt.auth.ldap._config('basedn'), 'dc=saltstack,dc=com')
        self.assertEqual(salt.auth.ldap._config('group_filter'), '(&(memberUid={{ username }})(objectClass=posixgroup))')
        self.assertEqual(salt.auth.ldap._config('accountattributename'), 'memberUid')
        self.assertEqual(salt.auth.ldap._config('groupattribute'), 'memberOf')

    def test_groups_freeipa(self):
        salt.auth.ldap.__opts__['auth.ldap.freeipa'] = True
        class Bind(object):
            @classmethod
            def search_s(*args, **kwargs):
                return [
                    (
                        'cn=saltusers,cn=groups,cn=compat,dc=saltstack,dc=com',
                        {'memberUid': [b'saltuser'], 'cn': [b'saltusers']},
                    ),
                ]
        with patch('salt.auth.ldap.auth', return_value=Bind):
            self.assertIn('saltusers', salt.auth.ldap.groups('saltuser', password='password'))

    def test_groups(self):
        class Bind(object):
            @classmethod
            def search_s(*args, **kwargs):
                return [
                    (
                        'cn=saltusers,cn=users,cn=compat,dc=saltstack,dc=com',
                        {'memberUid': [b'saltuser'], 'cn': [b'saltusers']},
                    ),
                ]
        with patch('salt.auth.ldap.auth', return_value=Bind):
            self.assertIn('saltusers', salt.auth.ldap.groups('saltuser', password='password'))

    def test_groups_activedirectory(self):
        salt.auth.ldap.__opts__['auth.ldap.activedirectory'] = True
        class Bind(object):
            @classmethod
            def search_s(*args, **kwargs):
                return [
                    (
                        'cn=saltusers,cn=users,cn=compat,dc=saltstack,dc=com',
                        {'memberUid': [b'saltuser'], 'cn': [b'saltusers']},
                    ),
                ]
        with patch('salt.auth.ldap.auth', return_value=Bind):
            self.assertIn('saltusers', salt.auth.ldap.groups('saltuser', password='password'))
