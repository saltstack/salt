# coding: utf-8

import json
import yaml
import urllib

from salt.netapi.rest_tornado import saltnado
import salt.auth
import integration

import tornado.testing
import tornado.concurrent


class SaltnadoTestCase(integration.ModuleCase, tornado.testing.AsyncHTTPTestCase):
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
        return self.get_config('master', from_scratch=True)

    @property
    def auth(self):
        if not hasattr(self, '__auth'):
            self.__auth = salt.auth.LoadAuth(self.opts)
        return self.__auth

    @property
    def token(self):
        ''' Mint and return a valid token for auth_creds '''
        return self.auth.mk_token(self.auth_creds_dict)


class TestBaseSaltAPIHandler(SaltnadoTestCase):
    def get_app(self):
        class StubHandler(saltnado.BaseSaltAPIHandler):
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

        return tornado.web.Application([('/', StubHandler)], debug=True)

    def test_content_type(self):
        '''
        Test the base handler's accept picking
        '''

        # send NO accept header, should come back with json
        response = self.fetch('/')
        assert response.headers['Content-Type'] == self.content_type_map['json']
        assert type(json.loads(response.body)) == dict

        # send application/json
        response = self.fetch('/', headers={'Accept': self.content_type_map['json']})
        assert response.headers['Content-Type'] == self.content_type_map['json']
        assert type(json.loads(response.body)) == dict

        # send application/x-yaml
        response = self.fetch('/', headers={'Accept': self.content_type_map['yaml']})
        assert response.headers['Content-Type'] == self.content_type_map['yaml']
        assert type(yaml.load(response.body)) == dict

    def test_token(self):
        '''
        Test that the token is returned correctly
        '''
        token = json.loads(self.fetch('/').body)['token']
        assert token is None

        # send a token as a header
        response = self.fetch('/', headers={saltnado.AUTH_TOKEN_HEADER: 'foo'})
        token = json.loads(response.body)['token']
        assert token == 'foo'

        # send a token as a cookie
        response = self.fetch('/', headers={'Cookie': '{0}=foo'.format(saltnado.AUTH_COOKIE_NAME)})
        token = json.loads(response.body)['token']
        assert token == 'foo'

        # send both, make sure its the header
        response = self.fetch('/', headers={saltnado.AUTH_TOKEN_HEADER: 'foo',
                                            'Cookie': '{0}=bar'.format(saltnado.AUTH_COOKIE_NAME)})
        token = json.loads(response.body)['token']
        assert token == 'foo'

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

        assert valid_lowstate == json.loads(response.body)['lowstate']

        # send yaml as json (should break)
        response = self.fetch('/',
                              method='POST',
                              body=yaml.dump(valid_lowstate),
                              headers={'Content-Type': self.content_type_map['json']})
        assert response.code == 400

        # send as yaml
        response = self.fetch('/',
                              method='POST',
                              body=yaml.dump(valid_lowstate),
                              headers={'Content-Type': self.content_type_map['yaml']})
        assert valid_lowstate == json.loads(response.body)['lowstate']

        # send json as yaml (works since yaml is a superset of json)
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(valid_lowstate),
                              headers={'Content-Type': self.content_type_map['yaml']})
        assert valid_lowstate == json.loads(response.body)['lowstate']

        # send json as text/plain
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(valid_lowstate),
                              headers={'Content-Type': self.content_type_map['text']})
        assert valid_lowstate == json.loads(response.body)['lowstate']

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
                              body=urllib.urlencode(form_lowstate),
                              headers={'Content-Type': self.content_type_map['form']})
        returned_lowstate = json.loads(response.body)['lowstate']
        assert len(returned_lowstate) == 1
        returned_lowstate = returned_lowstate[0]

        assert returned_lowstate['client'] == 'local'
        assert returned_lowstate['tgt'] == '*'
        assert returned_lowstate['fun'] == 'test.fib'
        assert returned_lowstate['arg'] == ['10', 'foo']


class TestSaltAuthHandler(SaltnadoTestCase):
    def get_app(self):

        # TODO: make a "GET APPPLICATION" func
        application = tornado.web.Application([('/login', saltnado.SaltAuthHandler)], debug=True)

        application.auth = self.auth
        application.opts = self.opts
        return application

    def test_get(self):
        '''
        We don't allow gets, so assert we get 401s
        '''
        response = self.fetch('/login')
        assert response.code == 401

    def test_login(self):
        '''
        Test valid logins
        '''
        response = self.fetch('/login',
                               method='POST',
                               body=urllib.urlencode(self.auth_creds),
                               headers={'Content-Type': self.content_type_map['form']})

        response_obj = json.loads(response.body)['return'][0]
        assert response_obj['perms'] == self.opts['external_auth']['auto'][self.auth_creds_dict['username']]
        assert 'token' in response_obj  # TODO: verify that its valid?
        assert response_obj['user'] == self.auth_creds_dict['username']
        assert response_obj['eauth'] == self.auth_creds_dict['eauth']

    def test_login_missing_password(self):
        '''
        Test logins with bad/missing passwords
        '''
        bad_creds = []
        for key, val in self.auth_creds_dict.iteritems():
            if key == 'password':
                continue
            bad_creds.append((key, val))
        response = self.fetch('/login',
                               method='POST',
                               body=urllib.urlencode(bad_creds),
                               headers={'Content-Type': self.content_type_map['form']})

        assert response.code == 400

    def test_login_bad_creds(self):
        '''
        Test logins with bad/missing passwords
        '''
        bad_creds = []
        for key, val in self.auth_creds_dict.iteritems():
            if key == 'username':
                val = val + 'foo'
            bad_creds.append((key, val))
        response = self.fetch('/login',
                               method='POST',
                               body=urllib.urlencode(bad_creds),
                               headers={'Content-Type': self.content_type_map['form']})

        assert response.code == 401
