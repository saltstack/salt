# coding: utf-8
import os

import json

from salt.netapi.rest_tornado import saltnado

import tornado.testing
import tornado.concurrent
import tornado.web

from unit.netapi.rest_tornado.test_handlers import SaltnadoTestCase

from salttesting import skipIf, TestCase

import json

# TODO:
'''
    - Add support for different client in each chunk
    - fix timeouts (or document how its different)
    - fix "ping" of minions
'''
class TestSaltAPIHandler(SaltnadoTestCase):
    def get_app(self):
        application = tornado.web.Application([('/', saltnado.SaltAPIHandler)], debug=True)

        application.auth = self.auth
        application.opts = self.opts

        application.event_listener = saltnado.EventListener({}, self.opts)
        return application

    def test_root(self):
        '''
        Test the root path which returns the list of clients we support
        '''
        response = self.fetch('/')
        assert response.code == 200
        response_obj = json.loads(response.body)
        assert response_obj['clients'] == ['runner',
                                           'local_async',
                                           'local',
                                           'local_batch']
        assert response_obj['return'] == 'Welcome'

    def test_post_no_auth(self):
        '''
        '''
        # get a token for this test
        low = [{'client': 'local',
                'tgt': '*',
                'fun': 'test.ping',
                }]
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json']},
                              follow_redirects=False
                              )
        assert response.code == 302
        assert response.headers['Location'] == '/login'

    # Local client tests
    def test_simple_local_post(self):
        '''
        '''
        low = [{'client': 'local',
                'tgt': '*',
                'fun': 'test.ping',
                }]
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              )
        response_obj = json.loads(response.body)
        assert response_obj['return'] == [{'minion': True, 'sub_minion': True}]

    def test_simple_local_post_no_tgt(self):
        '''
        '''
        low = [{'client': 'local',
                'tgt': 'minion_we_dont_have',
                'fun': 'test.ping',
                }]
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              )
        response_obj = json.loads(response.body)
        assert response_obj['return'] == []

    # TODO: fix tracebacks from the minion, it returns after the master process dies
    # if you run just one test. Disabled until then
    def tsest_simple_local_timeout(self):
        '''
        Send a request that should timeout and make sure it does
        '''
        low = [{'client': 'local',
                'tgt': '*',
                'fun': 'test.sleep',
                'arg': [5],
                'timeout': 1,
                }]
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              )
        # TODO: some exceptional case for timeouts? Maybe some mechanism to
        # return pub_data?
        response_obj = json.loads(response.body)
        assert response_obj['return'] == [{}]

    # local_batch tests
    def test_simple_local_batch_post(self):
        '''
        '''
        low = [{'client': 'local_batch',
                'tgt': '*',
                'fun': 'test.ping',
                }]
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              )
        response_obj = json.loads(response.body)
        assert response_obj['return'] == [{'minion': True, 'sub_minion': True}]

    def test_simple_local_batch_post_no_tgt(self):
        '''
        '''
        low = [{'client': 'local_batch',
                'tgt': 'minion_we_dont_have',
                'fun': 'test.ping',
                }]
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              )
        response_obj = json.loads(response.body)
        assert response_obj['return'] == [{}]

    # TODO: fix tracebacks from the minion, it returns after the master process dies
    # if you run just one test. Disabled until then
    def tsest_simple_local_batch_timeout(self):
        '''
        Send a request that should timeout and make sure it does
        '''
        low = [{'client': 'local_batch',
                'tgt': '*',
                'fun': 'test.sleep',
                'arg': [5],
                'timeout': 1,
                }]
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              )
        # TODO: some exceptional case for timeouts? Maybe some mechanism to
        # return pub_data?
        response_obj = json.loads(response.body)
        assert response_obj['return'] == [{}]

    # local_async tests
    def test_simple_local_async_post(self):
        low = [{'client': 'local_async',
                'tgt': '*',
                'fun': 'test.ping',
                }]
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              )
        response_obj = json.loads(response.body)
        # TODO: verify pub function? Maybe look at how we test the publisher
        assert len(response_obj['return']) == 1
        assert 'jid' in response_obj['return'][0]
        assert response_obj['return'][0]['minions'] == ['minion', 'sub_minion']

    def test_simple_local_async_post_no_tgt(self):
        '''
        '''
        low = [{'client': 'local_async',
                'tgt': 'minion_we_dont_have',
                'fun': 'test.ping',
                }]
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              )
        response_obj = json.loads(response.body)
        assert response_obj['return'] == [{}]

    # runner tests
    def test_simple_local_runner_post(self):
        '''
        '''
        low = [{'client': 'runner',
                'fun': 'manage.up',
                }]
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              )
        response_obj = json.loads(response.body)
        assert response_obj['return'] == [['minion', 'sub_minion']]


class TestMinionSaltAPIHandler(SaltnadoTestCase):
    def get_app(self):
        application = tornado.web.Application([(r"/minions/(.*)", saltnado.MinionSaltAPIHandler),
                                               (r"/minions", saltnado.MinionSaltAPIHandler),
                                               ], debug=True)

        application.auth = self.auth
        application.opts = self.opts

        application.event_listener = saltnado.EventListener({}, self.opts)
        return application

    def test_get_no_mid(self):
        response = self.fetch('/minions',
                              method='GET',
                              headers={saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              follow_redirects=False,
                              )
        response_obj = json.loads(response.body)
        assert len(response_obj['return']) == 1
        # one per minion
        assert len(response_obj['return'][0]) == 2
        # check a single grain
        for minion_id, grains in response_obj['return'][0].iteritems():
            assert minion_id == grains['id']

    def test_get(self):
        response = self.fetch('/minions/minion',
                              method='GET',
                              headers={saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              follow_redirects=False,
                              )
        response_obj = json.loads(response.body)
        assert len(response_obj['return']) == 1
        assert len(response_obj['return'][0]) == 1
        # check a single grain
        assert response_obj['return'][0]['minion']['id'] == 'minion'

    def test_post(self):
        low = [{'tgt': '*',
                'fun': 'test.ping',
                }]
        response = self.fetch('/minions',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              )
        response_obj = json.loads(response.body)
        # TODO: verify pub function? Maybe look at how we test the publisher
        assert len(response_obj['return']) == 1
        assert 'jid' in response_obj['return'][0]
        assert response_obj['return'][0]['minions'] == ['minion', 'sub_minion']

    def test_post_with_client(self):
        '''
        '''
        # get a token for this test
        low = [{'client': 'local_batch',
                'tgt': '*',
                'fun': 'test.ping',
                }]
        response = self.fetch('/minions',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              )
        response_obj = json.loads(response.body)
        # TODO: verify pub function? Maybe look at how we test the publisher
        assert len(response_obj['return']) == 1
        assert 'jid' in response_obj['return'][0]
        assert response_obj['return'][0]['minions'] == ['minion', 'sub_minion']

#
