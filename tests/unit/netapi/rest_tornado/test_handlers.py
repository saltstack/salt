# coding: utf-8

# Import Python libs
from __future__ import absolute_import
import json
import yaml
import os

# Import Salt Testing Libs
from salttesting.unit import skipIf
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../..')
import integration  # pylint: disable=import-error

# Import Salt libs
try:
    from salt.netapi.rest_tornado import saltnado
    HAS_TORNADO = True
except ImportError:
    HAS_TORNADO = False
import salt.auth


# Import 3rd-party libs
# pylint: disable=import-error
try:
    import tornado.testing
    import tornado.concurrent
    from tornado.testing import AsyncHTTPTestCase
    HAS_TORNADO = True
except ImportError:
    HAS_TORNADO = False

    # Let's create a fake AsyncHTTPTestCase so we can properly skip the test case
    class AsyncHTTPTestCase(object):
        pass

import salt.ext.six as six
from salt.ext.six.moves.urllib.parse import urlencode, urlparse  # pylint: disable=no-name-in-module
# pylint: enable=import-error

from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch


@skipIf(HAS_TORNADO is False, 'The tornado package needs to be installed')  # pylint: disable=W0223
class SaltnadoTestCase(integration.ModuleCase, AsyncHTTPTestCase):
    '''
    Mixin to hold some shared things
    '''
    content_type_map = {'json': 'application/json',
                        'yaml': 'application/x-yaml',
                        'text': 'text/plain',
                        'form': 'application/x-www-form-urlencoded'}
    auth_creds = (
        ('username', 'saltdev_api'),
        ('password', 'saltdev'),
        ('eauth', 'auto'))

    @property
    def auth_creds_dict(self):
        return dict(self.auth_creds)

    @property
    def opts(self):
        return self.get_config('client_config', from_scratch=True)

    @property
    def mod_opts(self):
        return self.get_config('minion', from_scratch=True)

    @property
    def auth(self):
        if not hasattr(self, '__auth'):
            self.__auth = salt.auth.LoadAuth(self.opts)
        return self.__auth

    @property
    def token(self):
        ''' Mint and return a valid token for auth_creds '''
        return self.auth.mk_token(self.auth_creds_dict)

    def setUp(self):
        super(SaltnadoTestCase, self).setUp()
        self.async_timeout_prev = os.environ.pop('ASYNC_TEST_TIMEOUT', None)
        os.environ['ASYNC_TEST_TIMEOUT'] = str(30)

    def tearDown(self):
        super(SaltnadoTestCase, self).tearDown()
        if self.async_timeout_prev is None:
            os.environ.pop('ASYNC_TEST_TIMEOUT', None)
        else:
            os.environ['ASYNC_TEST_TIMEOUT'] = self.async_timeout_prev

    def build_tornado_app(self, urls):
        application = tornado.web.Application(urls, debug=True)

        application.auth = self.auth
        application.opts = self.opts
        application.mod_opts = self.mod_opts

        return application


class TestBaseSaltAPIHandler(SaltnadoTestCase):
    def get_app(self):
        class StubHandler(saltnado.BaseSaltAPIHandler):  # pylint: disable=W0223
            def get(self):
                return self.echo_stuff()

            def post(self):
                return self.echo_stuff()

            def echo_stuff(self):
                ret_dict = {'foo': 'bar'}
                attrs = ('token',
                         'start',
                         'connected',
                         'lowstate',
                         )
                for attr in attrs:
                    ret_dict[attr] = getattr(self, attr)

                self.write(self.serialize(ret_dict))
        urls = [('/', StubHandler)]
        return self.build_tornado_app(urls)

    def test_content_type(self):
        '''
        Test the base handler's accept picking
        '''

        # send NO accept header, should come back with json
        response = self.fetch('/')
        self.assertEqual(response.headers['Content-Type'], self.content_type_map['json'])
        self.assertEqual(type(json.loads(response.body)), dict)

        # send application/json
        response = self.fetch('/', headers={'Accept': self.content_type_map['json']})
        self.assertEqual(response.headers['Content-Type'], self.content_type_map['json'])
        self.assertEqual(type(json.loads(response.body)), dict)

        # send application/x-yaml
        response = self.fetch('/', headers={'Accept': self.content_type_map['yaml']})
        self.assertEqual(response.headers['Content-Type'], self.content_type_map['yaml'])
        self.assertEqual(type(yaml.load(response.body)), dict)

    def test_token(self):
        '''
        Test that the token is returned correctly
        '''
        token = json.loads(self.fetch('/').body)['token']
        self.assertIs(token, None)

        # send a token as a header
        response = self.fetch('/', headers={saltnado.AUTH_TOKEN_HEADER: 'foo'})
        token = json.loads(response.body)['token']
        self.assertEqual(token, 'foo')

        # send a token as a cookie
        response = self.fetch('/', headers={'Cookie': '{0}=foo'.format(saltnado.AUTH_COOKIE_NAME)})
        token = json.loads(response.body)['token']
        self.assertEqual(token, 'foo')

        # send both, make sure its the header
        response = self.fetch('/', headers={saltnado.AUTH_TOKEN_HEADER: 'foo',
                                            'Cookie': '{0}=bar'.format(saltnado.AUTH_COOKIE_NAME)})
        token = json.loads(response.body)['token']
        self.assertEqual(token, 'foo')

    def test_deserialize(self):
        '''
        Send various encoded forms of lowstates (and bad ones) to make sure we
        handle deserialization correctly
        '''
        valid_lowstate = [{
                "client": "local",
                "tgt": "*",
                "fun": "test.fib",
                "arg": ["10"]
            },
            {
                "client": "runner",
                "fun": "jobs.lookup_jid",
                "jid": "20130603122505459265"
            }]

        # send as JSON
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(valid_lowstate),
                              headers={'Content-Type': self.content_type_map['json']})

        self.assertEqual(valid_lowstate, json.loads(response.body)['lowstate'])

        # send yaml as json (should break)
        response = self.fetch('/',
                              method='POST',
                              body=yaml.dump(valid_lowstate),
                              headers={'Content-Type': self.content_type_map['json']})
        self.assertEqual(response.code, 400)

        # send as yaml
        response = self.fetch('/',
                              method='POST',
                              body=yaml.dump(valid_lowstate),
                              headers={'Content-Type': self.content_type_map['yaml']})
        self.assertEqual(valid_lowstate, json.loads(response.body)['lowstate'])

        # send json as yaml (works since yaml is a superset of json)
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(valid_lowstate),
                              headers={'Content-Type': self.content_type_map['yaml']})
        self.assertEqual(valid_lowstate, json.loads(response.body)['lowstate'])

        # send json as text/plain
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(valid_lowstate),
                              headers={'Content-Type': self.content_type_map['text']})
        self.assertEqual(valid_lowstate, json.loads(response.body)['lowstate'])

        # send form-urlencoded
        form_lowstate = (
            ('client', 'local'),
            ('tgt', '*'),
            ('fun', 'test.fib'),
            ('arg', '10'),
            ('arg', 'foo'),
        )
        response = self.fetch('/',
                              method='POST',
                              body=urlencode(form_lowstate),
                              headers={'Content-Type': self.content_type_map['form']})
        returned_lowstate = json.loads(response.body)['lowstate']
        self.assertEqual(len(returned_lowstate), 1)
        returned_lowstate = returned_lowstate[0]

        self.assertEqual(returned_lowstate['client'], 'local')
        self.assertEqual(returned_lowstate['tgt'], '*')
        self.assertEqual(returned_lowstate['fun'], 'test.fib')
        self.assertEqual(returned_lowstate['arg'], ['10', 'foo'])


@skipIf(NO_MOCK, NO_MOCK_REASON)
class TestWebhookSaltHandler(SaltnadoTestCase):

    def get_app(self):
        urls = [
            (r'/hook(/.*)?', saltnado.WebhookSaltAPIHandler),
        ]
        return self.build_tornado_app(urls)

    @patch('salt.utils.event.get_event')
    def test_hook_can_handle_get_parameters(self, get_event):
        self._app.mod_opts['webhook_disable_auth'] = True
        event = MagicMock()
        event.fire_event.return_value = True
        get_event.return_value = event
        response = self.fetch('/hook/my_service/?param=1&param=2',
                              body=json.dumps({}),
                              method='POST',
                              headers={'Content-Type': self.content_type_map['json']})
        self.assertEqual(response.code, 200, response.body)
        host = urlparse(response.effective_url).netloc
        event.fire_event.assert_called_once_with(
            {'headers': {'Content-Length': '2',
                         'Connection': 'close',
                         'Content-Type': 'application/json',
                         'Host': host,
                         'Accept-Encoding': 'gzip'},
             'post': {},
             'get': {'param': ['1', '2']}
             },
            'salt/netapi/hook/my_service/',
        )


class TestSaltAuthHandler(SaltnadoTestCase):

    def get_app(self):
        urls = [('/login', saltnado.SaltAuthHandler)]
        return self.build_tornado_app(urls)

    def test_get(self):
        '''
        We don't allow gets, so assert we get 401s
        '''
        response = self.fetch('/login')
        self.assertEqual(response.code, 401)

    def test_login(self):
        '''
        Test valid logins
        '''
        response = self.fetch('/login',
                               method='POST',
                               body=urlencode(self.auth_creds),
                               headers={'Content-Type': self.content_type_map['form']})

        response_obj = json.loads(response.body)['return'][0]
        self.assertEqual(response_obj['perms'], self.opts['external_auth']['auto'][self.auth_creds_dict['username']])
        self.assertIn('token', response_obj)  # TODO: verify that its valid?
        self.assertEqual(response_obj['user'], self.auth_creds_dict['username'])
        self.assertEqual(response_obj['eauth'], self.auth_creds_dict['eauth'])

    def test_login_missing_password(self):
        '''
        Test logins with bad/missing passwords
        '''
        bad_creds = []
        for key, val in six.iteritems(self.auth_creds_dict):
            if key == 'password':
                continue
            bad_creds.append((key, val))
        response = self.fetch('/login',
                               method='POST',
                               body=urlencode(bad_creds),
                               headers={'Content-Type': self.content_type_map['form']})

        self.assertEqual(response.code, 400)

    def test_login_bad_creds(self):
        '''
        Test logins with bad/missing passwords
        '''
        bad_creds = []
        for key, val in six.iteritems(self.auth_creds_dict):
            if key == 'username':
                val = val + 'foo'
            bad_creds.append((key, val))
        response = self.fetch('/login',
                               method='POST',
                               body=urlencode(bad_creds),
                               headers={'Content-Type': self.content_type_map['form']})

        self.assertEqual(response.code, 401)


if __name__ == '__main__':
    from integration import run_tests  # pylint: disable=import-error
    run_tests(TestBaseSaltAPIHandler, TestSaltAuthHandler, needs_daemon=False)
