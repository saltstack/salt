# coding: utf-8

# Import python libs
from __future__ import absolute_import

# Import salt libs
import salt.utils.json
import salt.utils.stringutils

# Import test support libs
import tests.support.cherrypy_testclasses as cptc

# Import 3rd-party libs
from salt.ext.six.moves.urllib.parse import urlencode  # pylint: disable=no-name-in-module,import-error


class TestAuth(cptc.BaseRestCherryPyTest):
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


class TestLogin(cptc.BaseRestCherryPyTest):
    auth_creds = (
            ('username', 'saltdev'),
            ('password', 'saltdev'),
            ('eauth', 'auto'))

    def test_good_login(self):
        '''
        Test logging in
        '''
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


class TestRun(cptc.BaseRestCherryPyTest):
    auth_creds = (
        ('username', 'saltdev_auto'),
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

        request, response = self.request('/run', method='POST', body=body,
            headers={
                'content-type': 'application/x-www-form-urlencoded'
        })
        self.assertEqual(response.status, '401 Unauthorized')


class TestWebhookDisableAuth(cptc.BaseRestCherryPyTest):

    def __get_opts__(self):
        return {
            'rest_cherrypy': {
                'port': 8000,
                'debug': True,
                'webhook_disable_auth': True,
            },
        }

    def test_webhook_noauth(self):
        '''
        Auth can be disabled for requests to the webhook URL
        '''
        body = urlencode({'foo': 'Foo!'})
        request, response = self.request('/hook', method='POST', body=body,
            headers={
                'content-type': 'application/x-www-form-urlencoded'
        })
        self.assertEqual(response.status, '200 OK')


class TestArgKwarg(cptc.BaseRestCherryPyTest):
    auth_creds = (
        ('username', 'saltdev'),
        ('password', 'saltdev'),
        ('eauth', 'auto'))

    low = (
        ('client', 'runner'),
        ('fun', 'test.arg'),
        # use singular form for arg and kwarg
        ('arg', [1234]),
        ('kwarg', {'ext_source': 'redis'}),
    )

    def _token(self):
        '''
        Return the token
        '''
        body = urlencode(self.auth_creds)
        request, response = self.request(
            '/login',
            method='POST',
            body=body,
            headers={
                'content-type': 'application/x-www-form-urlencoded'
            }
        )
        return response.headers['X-Auth-Token']

    def test_accepts_arg_kwarg_keys(self):
        '''
        Ensure that (singular) arg and kwarg keys (for passing parameters)
        are supported by runners.
        '''
        cmd = dict(self.low)
        body = salt.utils.json.dumps(cmd)

        request, response = self.request(
            '/',
            method='POST',
            body=body,
            headers={
                'content-type': 'application/json',
                'X-Auth-Token': self._token(),
                'Accept': 'application/json',
            }
        )
        resp = salt.utils.json.loads(salt.utils.stringutils.to_str(response.body[0]))
        self.assertEqual(resp['return'][0]['args'], [1234])
        self.assertEqual(resp['return'][0]['kwargs'],
                         {'ext_source': 'redis'})


class TestJobs(cptc.BaseRestCherryPyTest):
    auth_creds = (
        ('username', 'saltdev_auto'),
        ('password', 'saltdev'),
        ('eauth', 'auto'))

    low = (
        ('client', 'local'),
        ('tgt', '*'),
        ('fun', 'test.ping'),
    )

    def _token(self):
        '''
        Return the token
        '''
        body = urlencode(self.auth_creds)
        request, response = self.request(
            '/login',
            method='POST',
            body=body,
            headers={
                'content-type': 'application/x-www-form-urlencoded'
            }
        )
        return response.headers['X-Auth-Token']

    def _add_job(self):
        '''
        Helper function to add a job to the job cache
        '''
        cmd = dict(self.low, **dict(self.auth_creds))
        body = urlencode(cmd)

        request, response = self.request('/run', method='POST', body=body,
            headers={
                'content-type': 'application/x-www-form-urlencoded'
        })
        self.assertEqual(response.status, '200 OK')

    def test_all_jobs(self):
        '''
        test query to /jobs returns job data
        '''
        self._add_job()

        request, response = self.request('/jobs', method='GET',
            headers={
                'Accept': 'application/json',
                'X-Auth-Token': self._token(),
        })

        resp = salt.utils.json.loads(salt.utils.stringutils.to_str(response.body[0]))
        self.assertIn('test.ping', str(resp['return']))
        self.assertEqual(response.status, '200 OK')
