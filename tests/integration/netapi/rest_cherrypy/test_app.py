# coding: utf-8

# Import python libs
from __future__ import absolute_import

# Import salttesting libs
from salttesting import mock
from salttesting.unit import skipIf
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../../')

from salt.exceptions import EauthAuthenticationError
from tests.utils import BaseRestCherryPyTest

# Import 3rd-party libs
# pylint: disable=import-error,unused-import
from salt.ext.six.moves.urllib.parse import urlencode  # pylint: disable=no-name-in-module
try:
    import cherrypy
    HAS_CHERRYPY = True
except ImportError:
    HAS_CHERRYPY = False
# pylint: enable=import-error,unused-import


@skipIf(HAS_CHERRYPY is False, 'CherryPy not installed')
class TestAuth(BaseRestCherryPyTest):
    def test_get_root_noauth(self):
        '''
        GET requests to the root URL should not require auth
        '''
        request, response = self.request('/')
        self.assertEqual(response.status, '200 OK')

    def test_post_root_auth(self):
        '''
        POST requests to the root URL redirect to login
        '''
        request, response = self.request('/', method='POST', data={})
        self.assertEqual(response.status, '401 Unauthorized')

    def test_login_noauth(self):
        '''
        GET requests to the login URL should not require auth
        '''
        request, response = self.request('/login')
        self.assertEqual(response.status, '200 OK')

    def test_webhook_auth(self):
        '''
        Requests to the webhook URL require auth by default
        '''
        request, response = self.request('/hook', method='POST', data={})
        self.assertEqual(response.status, '401 Unauthorized')


class TestLogin(BaseRestCherryPyTest):
    auth_creds = (
            ('username', 'saltdev'),
            ('password', 'saltdev'),
            ('eauth', 'auto'))

    @mock.patch('salt.auth.Resolver', autospec=True)
    def setUp(self, Resolver, *args, **kwargs):
        super(TestLogin, self).setUp(*args, **kwargs)

        self.app.salt.auth.Resolver = Resolver
        self.Resolver = Resolver

    def test_good_login(self):
        '''
        Test logging in
        '''
        # Mock mk_token for a positive return
        self.Resolver.return_value.mk_token.return_value = {
            'token': '6d1b722e',
            'start': 1363805943.776223,
            'expire': 1363849143.776224,
            'name': 'saltdev',
            'eauth': 'auto',
        }

        body = urlencode(self.auth_creds)
        request, response = self.request('/login', method='POST', body=body,
            headers={
                'content-type': 'application/x-www-form-urlencoded'
        })
        self.assertEqual(response.status, '200 OK')
        return response

    def test_bad_login(self):
        '''
        Test logging in
        '''
        # Mock mk_token for a negative return
        self.Resolver.return_value.mk_token.return_value = {}

        body = urlencode({'totally': 'invalid_creds'})
        request, response = self.request('/login', method='POST', body=body,
            headers={
                'content-type': 'application/x-www-form-urlencoded'
        })
        self.assertEqual(response.status, '401 Unauthorized')

    def test_logout(self):
        ret = self.test_good_login()
        token = ret.headers['X-Auth-Token']

        body = urlencode({})
        request, response = self.request('/logout', method='POST', body=body,
            headers={
                'content-type': 'application/x-www-form-urlencoded',
                'X-Auth-Token': token,
        })
        self.assertEqual(response.status, '200 OK')


class TestRun(BaseRestCherryPyTest):
    auth_creds = (
        ('username', 'saltdev'),
        ('password', 'saltdev'),
        ('eauth', 'auto'))

    low = (
        ('client', 'local'),
        ('tgt', '*'),
        ('fun', 'test.ping'),
    )

    def test_run_good_login(self):
        '''
        Test the run URL with good auth credentials
        '''
        cmd = dict(self.low, **dict(self.auth_creds))
        body = urlencode(cmd)

        # Mock the interaction with Salt so we can focus on the API.
        with mock.patch.object(self.app.salt.netapi.NetapiClient, 'run',
                return_value=True):
            request, response = self.request('/run', method='POST', body=body,
                headers={
                    'content-type': 'application/x-www-form-urlencoded'
            })

        self.assertEqual(response.status, '200 OK')

    def test_run_bad_login(self):
        '''
        Test the run URL with bad auth credentials
        '''
        cmd = dict(self.low, **{'totally': 'invalid_creds'})
        body = urlencode(cmd)

        # Mock the interaction with Salt so we can focus on the API.
        with mock.patch.object(self.app.salt.netapi.NetapiClient, 'run',
                side_effect=EauthAuthenticationError('Oh noes!')):
            request, response = self.request('/run', method='POST', body=body,
                headers={
                    'content-type': 'application/x-www-form-urlencoded'
            })

        self.assertEqual(response.status, '401 Unauthorized')


class TestWebhookDisableAuth(BaseRestCherryPyTest):
    __opts__ = {
        'rest_cherrypy': {
            'port': 8000,
            'debug': True,
            'webhook_disable_auth': True,
        },
    }

    @mock.patch('salt.utils.event.get_event', autospec=True)
    def setUp(self, get_event, *args, **kwargs):
        super(TestWebhookDisableAuth, self).setUp(*args, **kwargs)

        self.app.salt.utils.event.get_event = get_event
        self.get_event = get_event

    def test_webhook_noauth(self):
        '''
        Auth can be disabled for requests to the webhook URL
        '''
        # Mock fire_event() since we're only testing auth here.
        self.get_event.return_value.fire_event.return_value = True

        body = urlencode({'foo': 'Foo!'})
        request, response = self.request('/hook', method='POST', body=body,
            headers={
                'content-type': 'application/x-www-form-urlencoded'
        })
        self.assertEqual(response.status, '200 OK')
