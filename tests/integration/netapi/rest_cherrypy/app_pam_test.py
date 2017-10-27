# coding: utf-8
'''
Integration Tests for restcherry salt-api with pam eauth
'''

# Import python libs
from __future__ import absolute_import
import os

# Import salttesting libs
from salttesting.unit import skipIf
from salttesting.helpers import (
    ensure_in_syspath,
    destructiveTest)
ensure_in_syspath('../../../')

from tests.utils import BaseRestCherryPyTest

# Import Salt Libs
import salt.utils
from tests import integration

# Import 3rd-party libs
# pylint: disable=import-error,unused-import
from salt.ext.six.moves.urllib.parse import urlencode  # pylint: disable=no-name-in-module
try:
    import cherrypy
    HAS_CHERRYPY = True
except ImportError:
    HAS_CHERRYPY = False
# pylint: enable=import-error,unused-import

USERA = 'saltdev'
USERA_PWD = 'saltdev'
HASHED_USERA_PWD = '$6$SALTsalt$ZZFD90fKFWq8AGmmX0L3uBtS9fXL62SrTk5zcnQ6EkD6zoiM3kB88G1Zvs0xm/gZ7WXJRs5nsTBybUvGSqZkT.'

AUTH_CREDS = {
    'username': USERA,
    'password': USERA_PWD,
    'eauth': 'pam'}


@skipIf(HAS_CHERRYPY is False, 'CherryPy not installed')
class TestAuthPAM(BaseRestCherryPyTest, integration.ModuleCase):
    '''
    Test auth with pam using salt-api
    '''

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
    def setUp(self):
        super(TestAuthPAM, self).setUp()
        try:
            add_user = self.run_function('user.add', [USERA], createhome=False)
            add_pwd = self.run_function('shadow.set_password',
                                        [USERA, USERA_PWD if salt.utils.is_darwin() else HASHED_USERA_PWD])
            self.assertTrue(add_user)
            self.assertTrue(add_pwd)
            user_list = self.run_function('user.list_users')
            self.assertIn(USERA, str(user_list))
        except AssertionError:
            self.run_function('user.delete', [USERA], remove=True)
            self.skipTest(
                'Could not add user or password, skipping test'
                )

    def test_bad_pwd_pam_chsh_service(self):
        '''
        Test login while specifying chsh service with bad passwd
        This test ensures this PR is working correctly:
        https://github.com/saltstack/salt/pull/31826
        '''
        copyauth_creds = AUTH_CREDS.copy()
        copyauth_creds['service'] = 'chsh'
        copyauth_creds['password'] = 'wrong_password'
        body = urlencode(copyauth_creds)
        request, response = self.request('/login', method='POST', body=body,
                                         headers={
                                             'content-type': 'application/x-www-form-urlencoded'
                                             })
        self.assertEqual(response.status, '401 Unauthorized')

    def test_bad_pwd_pam_login_service(self):
        '''
        Test login while specifying login service with bad passwd
        This test ensures this PR is working correctly:
        https://github.com/saltstack/salt/pull/31826
       '''
        copyauth_creds = AUTH_CREDS.copy()
        copyauth_creds['service'] = 'login'
        copyauth_creds['password'] = 'wrong_password'
        body = urlencode(copyauth_creds)
        request, response = self.request('/login', method='POST', body=body,
                                         headers={
                                             'content-type': 'application/x-www-form-urlencoded'
                                             })
        self.assertEqual(response.status, '401 Unauthorized')

    def test_good_pwd_pam_chsh_service(self):
        '''
        Test login while specifying chsh service with good passwd
        This test ensures this PR is working correctly:
        https://github.com/saltstack/salt/pull/31826
        '''
        copyauth_creds = AUTH_CREDS.copy()
        copyauth_creds['service'] = 'chsh'
        body = urlencode(copyauth_creds)
        request, response = self.request('/login', method='POST', body=body,
                                         headers={
                                             'content-type': 'application/x-www-form-urlencoded'
                                             })
        self.assertEqual(response.status, '200 OK')

    def test_good_pwd_pam_login_service(self):
        '''
        Test login while specifying login service with good passwd
        This test ensures this PR is working correctly:
        https://github.com/saltstack/salt/pull/31826
        '''
        copyauth_creds = AUTH_CREDS.copy()
        copyauth_creds['service'] = 'login'
        body = urlencode(copyauth_creds)
        request, response = self.request('/login', method='POST', body=body,
                                         headers={
                                             'content-type': 'application/x-www-form-urlencoded'
                                             })
        self.assertEqual(response.status, '200 OK')

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
    def tearDown(self):
        '''
        Clean up after tests. Delete user
        '''
        super(TestAuthPAM, self).tearDown()
        user_list = self.run_function('user.list_users')
        # Remove saltdev user
        if USERA in user_list:
            self.run_function('user.delete', [USERA], remove=True)
        #need to exit cherypy engine
        cherrypy.engine.exit()
