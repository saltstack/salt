# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import

# Import Salt Libs
import salt.auth.ldap

# Import Salt Testing Libs
from tests.support.mock import patch, NO_MOCK, NO_MOCK_REASON
from tests.support.unit import skipIf, TestCase

salt.auth.ldap.__opts__ = {}


class Bind(object):
    '''
    fake search_s return
    '''

    @staticmethod
    def search_s(*args, **kwargs):
        return [
            (
                'cn=saltusers,cn=groups,cn=compat,dc=saltstack,dc=com',
                {'memberUid': [b'saltuser'], 'cn': [b'saltusers']},
            ),
        ]


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not salt.auth.ldap.HAS_LDAP, 'Install python-ldap for this test')
class LDAPAuthTestCase(TestCase):
    '''
    Unit tests for salt.auth.ldap
    '''

    def setUp(self):
        self.opts = {
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
        self.opts['auth.ldap.freeipa'] = False
        self.opts['auth.ldap.activedirectory'] = False

    def test_config(self):
        '''
        Test that the _config function works correctly
        '''
        with patch.dict(salt.auth.ldap.__opts__, self.opts):
            self.assertEqual(salt.auth.ldap._config('basedn'), 'dc=saltstack,dc=com')
            self.assertEqual(salt.auth.ldap._config('group_filter'), '(&(memberUid={{ username }})(objectClass=posixgroup))')
            self.assertEqual(salt.auth.ldap._config('accountattributename'), 'memberUid')
            self.assertEqual(salt.auth.ldap._config('groupattribute'), 'memberOf')

    def test_groups_freeipa(self):
        '''
        test groups in freeipa
        '''
        self.opts['auth.ldap.freeipa'] = True
        with patch.dict(salt.auth.ldap.__opts__, self.opts):
            with patch('salt.auth.ldap.auth', return_value=Bind):
                self.assertIn('saltusers', salt.auth.ldap.groups('saltuser', password='password'))

    def test_groups(self):
        '''
        test groups in ldap
        '''
        with patch.dict(salt.auth.ldap.__opts__, self.opts):
            with patch('salt.auth.ldap.auth', return_value=Bind):
                self.assertIn('saltusers', salt.auth.ldap.groups('saltuser', password='password'))

    def test_groups_activedirectory(self):
        '''
        test groups in activedirectory
        '''
        self.opts['auth.ldap.activedirectory'] = True
        with patch.dict(salt.auth.ldap.__opts__, self.opts):
            with patch('salt.auth.ldap.auth', return_value=Bind):
                self.assertIn('saltusers', salt.auth.ldap.groups('saltuser', password='password'))
