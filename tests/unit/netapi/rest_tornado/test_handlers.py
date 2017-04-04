# coding: utf-8

# Import Python libs
from __future__ import absolute_import
import json
import os
import copy
import hashlib

# Import Salt Testing Libs
from tests.integration import AdaptedConfigurationTestCaseMixIn
from tests.support.unit import TestCase, skipIf

# Import Salt libs
import salt.auth
try:
    import salt.netapi.rest_tornado as rest_tornado
    from salt.netapi.rest_tornado import saltnado
    HAS_TORNADO = True
except ImportError:
    HAS_TORNADO = False

# Import 3rd-party libs
import yaml
# pylint: disable=import-error
try:
    import tornado.escape
    import tornado.testing
    import tornado.concurrent
    from tornado.testing import AsyncHTTPTestCase, gen_test
    from tornado.httpclient import HTTPRequest, HTTPError
    from tornado.websocket import websocket_connect
    HAS_TORNADO = True
except ImportError:
    HAS_TORNADO = False

    # Let's create a fake AsyncHTTPTestCase so we can properly skip the test case
    class AsyncHTTPTestCase(object):
        pass

import salt.ext.six as six
from salt.ext.six.moves.urllib.parse import urlencode, urlparse  # pylint: disable=no-name-in-module
# pylint: enable=import-error

from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch


@skipIf(HAS_TORNADO is False, 'The tornado package needs to be installed')  # pylint: disable=W0223
class SaltnadoTestCase(TestCase, AdaptedConfigurationTestCaseMixIn, AsyncHTTPTestCase):
    '''
    Mixin to hold some shared things
    '''
    content_type_map = {'json': 'application/json',
                        'json-utf8': 'application/json; charset=utf-8',
                        'yaml': 'application/x-yaml',
                        'text': 'text/plain',
                        'form': 'application/x-www-form-urlencoded',
                        'xml': 'application/xml',
                        'real-accept-header-json': 'application/json, text/javascript, */*; q=0.01',
                        'real-accept-header-yaml': 'application/x-yaml, text/yaml, */*; q=0.01'}
    auth_creds = (
        ('username', 'saltdev_api'),
        ('password', 'saltdev'),
        ('eauth', 'auto'))

    @property
    def auth_creds_dict(self):
        return dict(self.auth_creds)

    @property
    def opts(self):
        return self.get_temp_config('client_config')

    @property
    def mod_opts(self):
        return self.get_temp_config('minion')

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
        if hasattr(self, 'http_server'):
            del self.http_server
        if hasattr(self, 'io_loop'):
            del self.io_loop
        if hasattr(self, '_app'):
            del self._app
        if hasattr(self, 'http_client'):
            del self.http_client
        if hasattr(self, '__port'):
            del self.__port
        if hasattr(self, '_AsyncHTTPTestCase__port'):
            del self._AsyncHTTPTestCase__port
        if hasattr(self, '__auth'):
            del self.__auth
        if hasattr(self, '_SaltnadoTestCase__auth'):
            del self._SaltnadoTestCase__auth
        if hasattr(self, '_test_generator'):
            del self._test_generator
        if hasattr(self, 'application'):
            del self.application

    def build_tornado_app(self, urls):
        application = tornado.web.Application(urls, debug=True)

        application.auth = self.auth
        application.opts = self.opts
        application.mod_opts = self.mod_opts

        return application

    def decode_body(self, response):
        if six.PY2:
            return response
        if response.body:
            # Decode it
            if response.headers.get('Content-Type') == 'application/json':
                response._body = response.body.decode('utf-8')
            else:
                response._body = tornado.escape.native_str(response.body)
        return response

    def fetch(self, path, **kwargs):
        return self.decode_body(super(SaltnadoTestCase, self).fetch(path, **kwargs))


class TestBaseSaltAPIHandler(SaltnadoTestCase):
    def get_app(self):
        class StubHandler(saltnado.BaseSaltAPIHandler):  # pylint: disable=W0223
            def get(self, *args, **kwargs):
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
        urls = [('/', StubHandler),
                ('/(.*)', StubHandler)]
        return self.build_tornado_app(urls)

    def test_accept_content_type(self):
        '''
        Test the base handler's accept picking
        '''

        # send NO accept header, should come back with json
        response = self.fetch('/')
        self.assertEqual(response.headers['Content-Type'], self.content_type_map['json'])
        self.assertEqual(type(json.loads(response.body)), dict)

        # Request application/json
        response = self.fetch('/', headers={'Accept': self.content_type_map['json']})
        self.assertEqual(response.headers['Content-Type'], self.content_type_map['json'])
        self.assertEqual(type(json.loads(response.body)), dict)

        # Request application/x-yaml
        response = self.fetch('/', headers={'Accept': self.content_type_map['yaml']})
        self.assertEqual(response.headers['Content-Type'], self.content_type_map['yaml'])
        self.assertEqual(type(yaml.load(response.body)), dict)

        # Request not supported content-type
        response = self.fetch('/', headers={'Accept': self.content_type_map['xml']})
        self.assertEqual(response.code, 406)

        # Request some JSON with a browser like Accept
        accept_header = self.content_type_map['real-accept-header-json']
        response = self.fetch('/', headers={'Accept': accept_header})
        self.assertEqual(response.headers['Content-Type'], self.content_type_map['json'])
        self.assertEqual(type(json.loads(response.body)), dict)

        # Request some YAML with a browser like Accept
        accept_header = self.content_type_map['real-accept-header-yaml']
        response = self.fetch('/', headers={'Accept': accept_header})
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

        # Send json with utf8 charset
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(valid_lowstate),
                              headers={'Content-Type': self.content_type_map['json-utf8']})
        self.assertEqual(valid_lowstate, json.loads(response.body)['lowstate'])

    def test_get_lowstate(self):
        '''
        Test transformations low data of the function _get_lowstate
        '''
        valid_lowstate = [{
                u"client": u"local",
                u"tgt": u"*",
                u"fun": u"test.fib",
                u"arg": [u"10"]
            }]

        # Case 1. dictionary type of lowstate
        request_lowstate = {
                "client": "local",
                "tgt": "*",
                "fun": "test.fib",
                "arg": ["10"]
            }

        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(request_lowstate),
                              headers={'Content-Type': self.content_type_map['json']})

        self.assertEqual(valid_lowstate, json.loads(response.body)['lowstate'])

        # Case 2. string type of arg
        request_lowstate = {
                "client": "local",
                "tgt": "*",
                "fun": "test.fib",
                "arg": "10"
            }

        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(request_lowstate),
                              headers={'Content-Type': self.content_type_map['json']})

        self.assertEqual(valid_lowstate, json.loads(response.body)['lowstate'])

        # Case 3. Combine Case 1 and Case 2.
        request_lowstate = {
                "client": "local",
                "tgt": "*",
                "fun": "test.fib",
                "arg": "10"
            }

        # send as json
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(request_lowstate),
                              headers={'Content-Type': self.content_type_map['json']})

        self.assertEqual(valid_lowstate, json.loads(response.body)['lowstate'])

        # send as yaml
        response = self.fetch('/',
                              method='POST',
                              body=yaml.dump(request_lowstate),
                              headers={'Content-Type': self.content_type_map['yaml']})
        self.assertEqual(valid_lowstate, json.loads(response.body)['lowstate'])

        # send as plain text
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(request_lowstate),
                              headers={'Content-Type': self.content_type_map['text']})
        self.assertEqual(valid_lowstate, json.loads(response.body)['lowstate'])

        # send as form-urlencoded
        request_form_lowstate = (
            ('client', 'local'),
            ('tgt', '*'),
            ('fun', 'test.fib'),
            ('arg', '10'),
        )

        response = self.fetch('/',
                              method='POST',
                              body=urlencode(request_form_lowstate),
                              headers={'Content-Type': self.content_type_map['form']})
        self.assertEqual(valid_lowstate, json.loads(response.body)['lowstate'])

    def test_cors_origin_wildcard(self):
        '''
        Check that endpoints returns Access-Control-Allow-Origin
        '''
        self._app.mod_opts['cors_origin'] = '*'

        headers = self.fetch('/').headers
        self.assertEqual(headers["Access-Control-Allow-Origin"], "*")

    def test_cors_origin_single(self):
        '''
        Check that endpoints returns the Access-Control-Allow-Origin when
        only one origins is set
        '''
        self._app.mod_opts['cors_origin'] = 'http://example.foo'

        # Example.foo is an authorized origin
        headers = self.fetch('/', headers={'Origin': 'http://example.foo'}).headers
        self.assertEqual(headers["Access-Control-Allow-Origin"], "http://example.foo")

        # Example2.foo is not an authorized origin
        headers = self.fetch('/', headers={'Origin': 'http://example2.foo'}).headers
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), None)

    def test_cors_origin_multiple(self):
        '''
        Check that endpoints returns the Access-Control-Allow-Origin when
        multiple origins are set
        '''
        self._app.mod_opts['cors_origin'] = ['http://example.foo', 'http://foo.example']

        # Example.foo is an authorized origin
        headers = self.fetch('/', headers={'Origin': 'http://example.foo'}).headers
        self.assertEqual(headers["Access-Control-Allow-Origin"], "http://example.foo")

        # Example2.foo is not an authorized origin
        headers = self.fetch('/', headers={'Origin': 'http://example2.foo'}).headers
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), None)

    def test_cors_preflight_request(self):
        '''
        Check that preflight request contains right headers
        '''
        self._app.mod_opts['cors_origin'] = '*'

        request_headers = 'X-Auth-Token, accept, content-type'
        preflight_headers = {'Access-Control-Request-Headers': request_headers,
                             'Access-Control-Request-Method': 'GET'}

        response = self.fetch('/', method='OPTIONS', headers=preflight_headers)
        headers = response.headers

        self.assertEqual(response.code, 204)
        self.assertEqual(headers['Access-Control-Allow-Headers'], request_headers)
        self.assertEqual(headers['Access-Control-Expose-Headers'], 'X-Auth-Token')
        self.assertEqual(headers['Access-Control-Allow-Methods'], 'OPTIONS, GET, POST')

        self.assertEqual(response.code, 204)

    def test_cors_origin_url_with_arguments(self):
        '''
        Check that preflight requests works with url with components
        like jobs or minions endpoints.
        '''
        self._app.mod_opts['cors_origin'] = '*'

        request_headers = 'X-Auth-Token, accept, content-type'
        preflight_headers = {'Access-Control-Request-Headers': request_headers,
                             'Access-Control-Request-Method': 'GET'}
        response = self.fetch('/1234567890', method='OPTIONS',
                              headers=preflight_headers)
        headers = response.headers

        self.assertEqual(response.code, 204)
        self.assertEqual(headers["Access-Control-Allow-Origin"], "*")


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

        # Test in form encoded
        response = self.fetch('/login',
                               method='POST',
                               body=urlencode(self.auth_creds),
                               headers={'Content-Type': self.content_type_map['form']})

        self.assertEqual(response.code, 200)
        response_obj = json.loads(response.body)['return'][0]
        self.assertEqual(response_obj['perms'], self.opts['external_auth']['auto'][self.auth_creds_dict['username']])
        self.assertIn('token', response_obj)  # TODO: verify that its valid?
        self.assertEqual(response_obj['user'], self.auth_creds_dict['username'])
        self.assertEqual(response_obj['eauth'], self.auth_creds_dict['eauth'])

        # Test in JSON
        response = self.fetch('/login',
                               method='POST',
                               body=json.dumps(self.auth_creds_dict),
                               headers={'Content-Type': self.content_type_map['json']})

        self.assertEqual(response.code, 200)
        response_obj = json.loads(response.body)['return'][0]
        self.assertEqual(response_obj['perms'], self.opts['external_auth']['auto'][self.auth_creds_dict['username']])
        self.assertIn('token', response_obj)  # TODO: verify that its valid?
        self.assertEqual(response_obj['user'], self.auth_creds_dict['username'])
        self.assertEqual(response_obj['eauth'], self.auth_creds_dict['eauth'])

        # Test in YAML
        response = self.fetch('/login',
                               method='POST',
                               body=yaml.dump(self.auth_creds_dict),
                               headers={'Content-Type': self.content_type_map['yaml']})

        self.assertEqual(response.code, 200)
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

    def test_login_invalid_data_structure(self):
        '''
        Test logins with either list or string JSON payload
        '''
        response = self.fetch('/login',
                               method='POST',
                               body=json.dumps(self.auth_creds),
                               headers={'Content-Type': self.content_type_map['form']})

        self.assertEqual(response.code, 400)

        response = self.fetch('/login',
                               method='POST',
                               body=json.dumps(42),
                               headers={'Content-Type': self.content_type_map['form']})

        self.assertEqual(response.code, 400)

        response = self.fetch('/login',
                               method='POST',
                               body=json.dumps('mystring42'),
                               headers={'Content-Type': self.content_type_map['form']})

        self.assertEqual(response.code, 400)


@skipIf(HAS_TORNADO is False, 'The tornado package needs to be installed')  # pylint: disable=W0223
class TestWebsocketSaltAPIHandler(SaltnadoTestCase):

    def get_app(self):
        opts = copy.deepcopy(self.opts)
        opts.setdefault('rest_tornado', {})['websockets'] = True
        return rest_tornado.get_application(opts)

    @gen_test
    def test_websocket_handler_upgrade_to_websocket(self):
        response = yield self.http_client.fetch(self.get_url('/login'),
                                                method='POST',
                                                body=urlencode(self.auth_creds),
                                                headers={'Content-Type': self.content_type_map['form']})
        token = json.loads(self.decode_body(response).body)['return'][0]['token']

        url = 'ws://127.0.0.1:{0}/all_events/{1}'.format(self.get_http_port(), token)
        request = HTTPRequest(url, headers={'Origin': 'http://example.com',
                                            'Host': 'example.com'})
        ws = yield websocket_connect(request)
        ws.write_message('websocket client ready')
        ws.close()

    @gen_test
    def test_websocket_handler_bad_token(self):
        """
        A bad token should returns a 401 during a websocket connect
        """
        token = 'A'*len(getattr(hashlib, self.opts.get('hash_type', 'md5'))().hexdigest())

        url = 'ws://127.0.0.1:{0}/all_events/{1}'.format(self.get_http_port(), token)
        request = HTTPRequest(url, headers={'Origin': 'http://example.com',
                                            'Host': 'example.com'})
        try:
            ws = yield websocket_connect(request)
        except HTTPError as error:
            self.assertEqual(error.code, 401)

    @gen_test
    def test_websocket_handler_cors_origin_wildcard(self):
        self._app.mod_opts['cors_origin'] = '*'

        response = yield self.http_client.fetch(self.get_url('/login'),
                                                method='POST',
                                                body=urlencode(self.auth_creds),
                                                headers={'Content-Type': self.content_type_map['form']})
        token = json.loads(self.decode_body(response).body)['return'][0]['token']

        url = 'ws://127.0.0.1:{0}/all_events/{1}'.format(self.get_http_port(), token)
        request = HTTPRequest(url, headers={'Origin': 'http://foo.bar',
                                            'Host': 'example.com'})
        ws = yield websocket_connect(request)
        ws.write_message('websocket client ready')
        ws.close()

    @gen_test
    def test_cors_origin_single(self):
        self._app.mod_opts['cors_origin'] = 'http://example.com'

        response = yield self.http_client.fetch(self.get_url('/login'),
                                                method='POST',
                                                body=urlencode(self.auth_creds),
                                                headers={'Content-Type': self.content_type_map['form']})
        token = json.loads(self.decode_body(response).body)['return'][0]['token']
        url = 'ws://127.0.0.1:{0}/all_events/{1}'.format(self.get_http_port(), token)

        # Example.com should works
        request = HTTPRequest(url, headers={'Origin': 'http://example.com',
                                            'Host': 'example.com'})
        ws = yield websocket_connect(request)
        ws.write_message('websocket client ready')
        ws.close()

        # But foo.bar not
        request = HTTPRequest(url, headers={'Origin': 'http://foo.bar',
                                            'Host': 'example.com'})
        try:
            ws = yield websocket_connect(request)
        except HTTPError as error:
            self.assertEqual(error.code, 403)

    @gen_test
    def test_cors_origin_multiple(self):
        self._app.mod_opts['cors_origin'] = ['http://example.com', 'http://foo.bar']

        response = yield self.http_client.fetch(self.get_url('/login'),
                                                method='POST',
                                                body=urlencode(self.auth_creds),
                                                headers={'Content-Type': self.content_type_map['form']})
        token = json.loads(self.decode_body(response).body)['return'][0]['token']
        url = 'ws://127.0.0.1:{0}/all_events/{1}'.format(self.get_http_port(), token)

        # Example.com should works
        request = HTTPRequest(url, headers={'Origin': 'http://example.com',
                                            'Host': 'example.com'})
        ws = yield websocket_connect(request)
        ws.write_message('websocket client ready')
        ws.close()

        # Foo.bar too
        request = HTTPRequest(url, headers={'Origin': 'http://foo.bar',
                                            'Host': 'example.com'})
        ws = yield websocket_connect(request)
        ws.write_message('websocket client ready')
        ws.close()
