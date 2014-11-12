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
    - fix timeouts (or document how its different)
    - fix "ping" of minions
'''

# TODO: TODOC
'''
/ endpoint
    - failed job runs should return an error string (instead of dict)
    - run the jobs in serial-- if you wanted parallel use async
    - do *not* require success of previous runs-- since you can use compound commands/overstate
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
        assert response_obj['return'] == ["No minions matched the target. No command was sent, no jid was assigned."]

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

    # local_batch tests
    def test_full_local_batch_post(self):
        '''
        '''
        low = [{'client': 'local_batch',
                'tgt': '*',
                'fun': 'test.ping',
                'batch': '100%',
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

    def test_multi_local_async_post(self):
        '''
        '''
        low = [{'client': 'local_async',
                'tgt': '*',
                'fun': 'test.ping',
                },
                {'client': 'local_async',
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
        assert len(response_obj['return']) == 2
        assert 'jid' in response_obj['return'][0]
        assert 'jid' in response_obj['return'][1]
        assert response_obj['return'][0]['minions'] == ['minion', 'sub_minion']
        assert response_obj['return'][1]['minions'] == ['minion', 'sub_minion']

    def test_multi_local_async_post_multitoken(self):
        '''
        '''
        low = [{'client': 'local_async',
                'tgt': '*',
                'fun': 'test.ping',
                },
                {'client': 'local_async',
                'tgt': '*',
                'fun': 'test.ping',
                'token': self.token['token'],  # send a different (but still valid token)
                },
                {'client': 'local_async',
                'tgt': '*',
                'fun': 'test.ping',
                'token': 'BAD_TOKEN',  # send a bad token
                },
                ]
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              )
        response_obj = json.loads(response.body)
        assert len(response_obj['return']) == 3  # make sure we got 3 responses
        assert 'jid' in response_obj['return'][0]  # the first 2 are regular returns
        assert 'jid' in response_obj['return'][1]
        assert 'Failed to authenticate' in response_obj['return'][2]  # bad auth
        assert response_obj['return'][0]['minions'] == ['minion', 'sub_minion']
        assert response_obj['return'][1]['minions'] == ['minion', 'sub_minion']

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
        low = [{'client': 'local_async',
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

    def test_post_with_incorrect_client(self):
        '''
        The /minions endpoint is async only, so if you try something else
        make sure you get an error
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
        assert response.code == 400


class TestJobsSaltAPIHandler(SaltnadoTestCase):
    def get_app(self):
        application = tornado.web.Application([(r"/jobs/(.*)", saltnado.JobsSaltAPIHandler),
                                               (r"/jobs", saltnado.JobsSaltAPIHandler),
                                               ], debug=True)

        application.auth = self.auth
        application.opts = self.opts

        application.event_listener = saltnado.EventListener({}, self.opts)
        return application

    def test_get(self):
        # test with no JID
        response = self.fetch('/jobs',
                              method='GET',
                              headers={saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              follow_redirects=False,
                              )
        response_obj = json.loads(response.body)['return'][0]
        for jid, ret in response_obj.iteritems():
            assert 'Function' in ret
            assert 'Target' in ret
            assert 'Target-type' in ret
            assert 'User' in ret
            assert 'StartTime' in ret
            assert 'Arguments' in ret

        # test with a specific JID passed in
        jid = response_obj.iterkeys().next()
        response = self.fetch('/jobs/{0}'.format(jid),
                              method='GET',
                              headers={saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              follow_redirects=False,
                              )
        response_obj = json.loads(response.body)['return'][0]
        assert 'Function' in response_obj
        assert 'Target' in response_obj
        assert 'Target-type' in response_obj
        assert 'User' in response_obj
        assert 'StartTime' in response_obj
        assert 'Arguments' in response_obj
        assert 'Result' in response_obj


# TODO: run all the same tests from the root handler, but for now since they are
# the same code, we'll just sanity check
class TestRunSaltAPIHandler(SaltnadoTestCase):
    def get_app(self):
        application = tornado.web.Application([("/run", saltnado.RunSaltAPIHandler),
                                               ], debug=True)

        application.auth = self.auth
        application.opts = self.opts

        application.event_listener = saltnado.EventListener({}, self.opts)
        return application

    def test_get(self):
        low = [{'client': 'local',
                'tgt': '*',
                'fun': 'test.ping',
                }]
        response = self.fetch('/run',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              )
        response_obj = json.loads(response.body)
        assert response_obj['return'] == [{'minion': True, 'sub_minion': True}]


class TestEventsSaltAPIHandler(SaltnadoTestCase):
    def get_app(self):
        application = tornado.web.Application([(r"/events", saltnado.EventsSaltAPIHandler),
                                               ], debug=True)

        application.auth = self.auth
        application.opts = self.opts

        application.event_listener = saltnado.EventListener({}, self.opts)
        # store a reference, for magic later!
        self.application = application
        self.events_to_fire = 0
        return application

    def test_get(self):
        self.events_to_fire = 5
        response = self.fetch('/events',
                              headers={saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              streaming_callback=self.on_event
                              )

    def on_event(self, event):
        if self.events_to_fire > 0:
            self.application.event_listener.event.fire_event({
                'foo': 'bar',
                'baz': 'qux',
            }, 'salt/netapi/test')
            self.events_to_fire -= 1
        # once we've fired all the events, lets call it a day
        else:
            self.stop()

        event = event.strip()
        # if we got a retry, just continue
        if event != 'retry: 400':
            tag, data = event.splitlines()
            assert tag.startswith('tag: ')
            assert data.startswith('data: ')


class TestWebhookSaltAPIHandler(SaltnadoTestCase):
    def get_app(self):
        application = tornado.web.Application([(r"/hook(/.*)?", saltnado.WebhookSaltAPIHandler),
                                               ], debug=True)

        application.auth = self.auth
        application.opts = self.opts

        self.application = application

        application.event_listener = saltnado.EventListener({}, self.opts)
        return application

    def test_post(self):
        # get an event future
        event = self.application.event_listener.get_event(self,
                                                          tag='salt/netapi/hook',
                                                          callback=self.stop,
                                                          )
        # fire the event
        response = self.fetch('/hook',
                              method='POST',
                              body='foo=bar',
                              headers={saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              )
        response_obj = json.loads(response.body)
        assert response_obj['success'] is True
        self.wait()
        assert event.done()
        assert event.result()['tag'] == 'salt/netapi/hook'
        assert 'headers' in event.result()['data']
        assert event.result()['data']['post'] == {'foo': 'bar'}


#
