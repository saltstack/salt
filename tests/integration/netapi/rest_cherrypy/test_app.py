# coding: utf-8
import mock
import urllib

from salt.exceptions import EauthAuthenticationError
from tests.utils import BaseRestCherryPyTest

# Import 3rd-party libs
try:
    import cherrypy  # pylint: disable=W0611
    HAS_CHERRYPY = True
except ImportError:
    HAS_CHERRYPY = False


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

        body = urllib.urlencode(self.auth_creds)
        request, response = self.request('/login', method='POST', body=body,
            headers={
                'content-type': 'application/x-www-form-urlencoded'
        })
        self.assertEqual(response.status, '200 OK')

    def test_bad_login(self):
        '''
        Test logging in
        '''
        # Mock mk_token for a negative return
        self.Resolver.return_value.mk_token.return_value = {}

        body = urllib.urlencode({'totally': 'invalid_creds'})
        request, response = self.request('/login', method='POST', body=body,
            headers={
                'content-type': 'application/x-www-form-urlencoded'
        })
        self.assertEqual(response.status, '401 Unauthorized')


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
        body = urllib.urlencode(cmd)

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
        body = urllib.urlencode(cmd)

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

        body = urllib.urlencode({'foo': 'Foo!'})
        request, response = self.request('/hook', method='POST', body=body,
            headers={
                'content-type': 'application/x-www-form-urlencoded'
        })
        self.assertEqual(response.status, '200 OK')
