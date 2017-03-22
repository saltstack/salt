# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import
from __future__ import print_function
import json
import time
import threading

# Import Salt Libs
from salt.netapi.rest_tornado import saltnado
from salt.utils.versions import StrictVersion

# Import Salt Testing Libs
from tests.unit.netapi.rest_tornado.test_handlers import SaltnadoTestCase
from tests.support.helpers import flaky
from tests.support.unit import skipIf

# Import 3rd-party libs
import salt.ext.six as six
try:
    import zmq
    from zmq.eventloop.ioloop import ZMQIOLoop
    HAS_ZMQ_IOLOOP = True
except ImportError:
    HAS_ZMQ_IOLOOP = False


def json_loads(data):
    if six.PY3:
        data = data.decode('utf-8')
    return json.loads(data)


@skipIf(HAS_ZMQ_IOLOOP is False, 'PyZMQ version must be >= 14.0.1 to run these tests.')
@skipIf(StrictVersion(zmq.__version__) < StrictVersion('14.0.1'), 'PyZMQ must be >= 14.0.1 to run these tests.')
class TestSaltAPIHandler(SaltnadoTestCase):
    def get_app(self):
        urls = [('/', saltnado.SaltAPIHandler)]

        application = self.build_tornado_app(urls)

        application.event_listener = saltnado.EventListener({}, self.opts)
        return application

    def test_root(self):
        '''
        Test the root path which returns the list of clients we support
        '''
        response = self.fetch('/',
                              connect_timeout=30,
                              request_timeout=30,
                )
        self.assertEqual(response.code, 200)
        response_obj = json_loads(response.body)
        self.assertEqual(sorted(response_obj['clients']),
                         ['local', 'local_async', 'runner', 'runner_async'])
        self.assertEqual(response_obj['return'], 'Welcome')

    def test_post_no_auth(self):
        '''
        Test post with no auth token, should 401
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
                              follow_redirects=False,
                              connect_timeout=30,
                              request_timeout=30,
                              )
        self.assertEqual(response.code, 302)
        self.assertEqual(response.headers['Location'], '/login')

    # Local client tests
    @skipIf(True, 'to be reenabled when #23623 is merged')
    def test_simple_local_post(self):
        '''
        Test a basic API of /
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
                              connect_timeout=30,
                              request_timeout=30,
                              )
        response_obj = json_loads(response.body)
        self.assertEqual(response_obj['return'], [{'minion': True, 'sub_minion': True}])

    def test_simple_local_post_no_tgt(self):
        '''
        POST job with invalid tgt
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
                              connect_timeout=30,
                              request_timeout=30,
                              )
        response_obj = json_loads(response.body)
        self.assertEqual(response_obj['return'], ["No minions matched the target. No command was sent, no jid was assigned."])

    # local client request body test
    @skipIf(True, 'Undetermined race condition in test. Temporarily disabled.')
    def test_simple_local_post_only_dictionary_request(self):
        '''
        Test a basic API of /
        '''
        low = {'client': 'local',
                'tgt': '*',
                'fun': 'test.ping',
              }
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              connect_timeout=30,
                              request_timeout=30,
                              )
        response_obj = json_loads(response.body)
        self.assertEqual(response_obj['return'], [{'minion': True, 'sub_minion': True}])

    def test_simple_local_post_invalid_request(self):
        '''
        Test a basic API of /
        '''
        low = ["invalid request"]
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              connect_timeout=30,
                              request_timeout=30,
                              )
        self.assertEqual(response.code, 400)

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

        response_obj = json_loads(response.body)
        ret = response_obj['return']
        ret[0]['minions'] = sorted(ret[0]['minions'])

        # TODO: verify pub function? Maybe look at how we test the publisher
        self.assertEqual(len(ret), 1)
        self.assertIn('jid', ret[0])
        self.assertEqual(ret[0]['minions'], sorted(['minion', 'sub_minion']))

    def test_multi_local_async_post(self):
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

        response_obj = json_loads(response.body)
        ret = response_obj['return']
        ret[0]['minions'] = sorted(ret[0]['minions'])
        ret[1]['minions'] = sorted(ret[1]['minions'])

        self.assertEqual(len(ret), 2)
        self.assertIn('jid', ret[0])
        self.assertIn('jid', ret[1])
        self.assertEqual(ret[0]['minions'], sorted(['minion', 'sub_minion']))
        self.assertEqual(ret[1]['minions'], sorted(['minion', 'sub_minion']))

    def test_multi_local_async_post_multitoken(self):
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

        response_obj = json_loads(response.body)
        ret = response_obj['return']
        ret[0]['minions'] = sorted(ret[0]['minions'])
        ret[1]['minions'] = sorted(ret[1]['minions'])

        self.assertEqual(len(ret), 3)  # make sure we got 3 responses
        self.assertIn('jid', ret[0])  # the first 2 are regular returns
        self.assertIn('jid', ret[1])
        self.assertIn('Failed to authenticate', ret[2])  # bad auth
        self.assertEqual(ret[0]['minions'], sorted(['minion', 'sub_minion']))
        self.assertEqual(ret[1]['minions'], sorted(['minion', 'sub_minion']))

    def test_simple_local_async_post_no_tgt(self):
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
        response_obj = json_loads(response.body)
        self.assertEqual(response_obj['return'], [{}])

    # runner tests
    def test_simple_local_runner_post(self):
        low = [{'client': 'runner',
                'fun': 'manage.up',
                }]
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              connect_timeout=30,
                              request_timeout=30,
                              )
        response_obj = json_loads(response.body)
        self.assertEqual(len(response_obj['return']), 1)
        self.assertEqual(set(response_obj['return'][0]), set(['minion', 'sub_minion']))

    # runner_async tests
    def test_simple_local_runner_async_post(self):
        low = [{'client': 'runner_async',
                'fun': 'manage.up',
                }]
        response = self.fetch('/',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              connect_timeout=10,
                              request_timeout=10,
                              )
        response_obj = json_loads(response.body)
        self.assertIn('return', response_obj)
        self.assertEqual(1, len(response_obj['return']))
        self.assertIn('jid', response_obj['return'][0])
        self.assertIn('tag', response_obj['return'][0])


@flaky
@skipIf(HAS_ZMQ_IOLOOP is False, 'PyZMQ version must be >= 14.0.1 to run these tests.')
class TestMinionSaltAPIHandler(SaltnadoTestCase):
    def get_app(self):
        urls = [(r"/minions/(.*)", saltnado.MinionSaltAPIHandler),
                (r"/minions", saltnado.MinionSaltAPIHandler),
                ]
        application = self.build_tornado_app(urls)
        application.event_listener = saltnado.EventListener({}, self.opts)
        return application

    @skipIf(True, 'issue #34753')
    def test_get_no_mid(self):
        response = self.fetch('/minions',
                              method='GET',
                              headers={saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              follow_redirects=False,
                              )
        response_obj = json_loads(response.body)
        self.assertEqual(len(response_obj['return']), 1)
        # one per minion
        self.assertEqual(len(response_obj['return'][0]), 2)
        # check a single grain
        for minion_id, grains in six.iteritems(response_obj['return'][0]):
            self.assertEqual(minion_id, grains['id'])

    @skipIf(True, 'to be reenabled when #23623 is merged')
    def test_get(self):
        response = self.fetch('/minions/minion',
                              method='GET',
                              headers={saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              follow_redirects=False,
                              )
        response_obj = json_loads(response.body)
        self.assertEqual(len(response_obj['return']), 1)
        self.assertEqual(len(response_obj['return'][0]), 1)
        # check a single grain
        self.assertEqual(response_obj['return'][0]['minion']['id'], 'minion')

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

        response_obj = json_loads(response.body)
        ret = response_obj['return']
        ret[0]['minions'] = sorted(ret[0]['minions'])

        # TODO: verify pub function? Maybe look at how we test the publisher
        self.assertEqual(len(ret), 1)
        self.assertIn('jid', ret[0])
        self.assertEqual(ret[0]['minions'], sorted(['minion', 'sub_minion']))

    def test_post_with_client(self):
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

        response_obj = json_loads(response.body)
        ret = response_obj['return']
        ret[0]['minions'] = sorted(ret[0]['minions'])

        # TODO: verify pub function? Maybe look at how we test the publisher
        self.assertEqual(len(ret), 1)
        self.assertIn('jid', ret[0])
        self.assertEqual(ret[0]['minions'], sorted(['minion', 'sub_minion']))

    def test_post_with_incorrect_client(self):
        '''
        The /minions endpoint is async only, so if you try something else
        make sure you get an error
        '''
        # get a token for this test
        low = [{'client': 'local',
                'tgt': '*',
                'fun': 'test.ping',
                }]
        response = self.fetch('/minions',
                              method='POST',
                              body=json.dumps(low),
                              headers={'Content-Type': self.content_type_map['json'],
                                       saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              )
        self.assertEqual(response.code, 400)


@skipIf(HAS_ZMQ_IOLOOP is False, 'PyZMQ version must be >= 14.0.1 to run these tests.')
class TestJobsSaltAPIHandler(SaltnadoTestCase):
    def get_app(self):
        urls = [(r"/jobs/(.*)", saltnado.JobsSaltAPIHandler),
                (r"/jobs", saltnado.JobsSaltAPIHandler),
                ]
        application = self.build_tornado_app(urls)
        application.event_listener = saltnado.EventListener({}, self.opts)
        return application

    @skipIf(True, 'to be reenabled when #23623 is merged')
    def test_get(self):
        # test with no JID
        self.http_client.fetch(self.get_url('/jobs'),
                               self.stop,
                               method='GET',
                               headers={saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                               follow_redirects=False,
                               )
        response = self.wait(timeout=30)
        response_obj = json_loads(response.body)['return'][0]
        try:
            for jid, ret in six.iteritems(response_obj):
                self.assertIn('Function', ret)
                self.assertIn('Target', ret)
                self.assertIn('Target-type', ret)
                self.assertIn('User', ret)
                self.assertIn('StartTime', ret)
                self.assertIn('Arguments', ret)
        except AttributeError as attribute_error:
            print(json_loads(response.body))
            raise

        # test with a specific JID passed in
        jid = next(six.iterkeys(response_obj))
        self.http_client.fetch(self.get_url('/jobs/{0}'.format(jid)),
                               self.stop,
                               method='GET',
                               headers={saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                               follow_redirects=False,
                               )
        response = self.wait(timeout=30)
        response_obj = json_loads(response.body)['return'][0]
        self.assertIn('Function', response_obj)
        self.assertIn('Target', response_obj)
        self.assertIn('Target-type', response_obj)
        self.assertIn('User', response_obj)
        self.assertIn('StartTime', response_obj)
        self.assertIn('Arguments', response_obj)
        self.assertIn('Result', response_obj)


# TODO: run all the same tests from the root handler, but for now since they are
# the same code, we'll just sanity check
@skipIf(HAS_ZMQ_IOLOOP is False, 'PyZMQ version must be >= 14.0.1 to run these tests.')
class TestRunSaltAPIHandler(SaltnadoTestCase):
    def get_app(self):
        urls = [("/run", saltnado.RunSaltAPIHandler),
                ]
        application = self.build_tornado_app(urls)
        application.event_listener = saltnado.EventListener({}, self.opts)
        return application

    @skipIf(True, 'to be reenabled when #23623 is merged')
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
        response_obj = json_loads(response.body)
        self.assertEqual(response_obj['return'], [{'minion': True, 'sub_minion': True}])


@skipIf(HAS_ZMQ_IOLOOP is False, 'PyZMQ version must be >= 14.0.1 to run these tests.')
class TestEventsSaltAPIHandler(SaltnadoTestCase):
    def get_app(self):
        urls = [(r"/events", saltnado.EventsSaltAPIHandler),
                ]
        application = self.build_tornado_app(urls)
        application.event_listener = saltnado.EventListener({}, self.opts)

        # store a reference, for magic later!
        self.application = application
        self.events_to_fire = 0
        return application

    def test_get(self):
        self.events_to_fire = 5
        response = self.fetch('/events',
                              headers={saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                              streaming_callback=self.on_event,
                              )

    def _stop(self):
        self.stop()

    def on_event(self, event):
        if six.PY3:
            event = event.decode('utf-8')
        if self.events_to_fire > 0:
            self.application.event_listener.event.fire_event({
                'foo': 'bar',
                'baz': 'qux',
            }, 'salt/netapi/test')
            self.events_to_fire -= 1
        # once we've fired all the events, lets call it a day
        else:
            # wait so that we can ensure that the next future is ready to go
            # to make sure we don't explode if the next one is ready
            ZMQIOLoop.current().add_timeout(time.time() + 0.5, self._stop)

        event = event.strip()
        # if we got a retry, just continue
        if event != 'retry: 400':
            tag, data = event.splitlines()
            self.assertTrue(tag.startswith('tag: '))
            self.assertTrue(data.startswith('data: '))


@skipIf(HAS_ZMQ_IOLOOP is False, 'PyZMQ version must be >= 14.0.1 to run these tests.')
class TestWebhookSaltAPIHandler(SaltnadoTestCase):

    def get_app(self):

        urls = [(r"/hook(/.*)?", saltnado.WebhookSaltAPIHandler),
                ]

        application = self.build_tornado_app(urls)

        self.application = application

        application.event_listener = saltnado.EventListener({}, self.opts)
        return application

    @skipIf(True, 'Skipping until we can devote more resources to debugging this test.')
    def test_post(self):
        self._future_resolved = threading.Event()
        try:
            def verify_event(future):
                '''
                Notify the threading event that the future is resolved
                '''
                self._future_resolved.set()

            self._finished = False  # TODO: remove after some cleanup of the event listener

            # get an event future
            future = self.application.event_listener.get_event(self,
                                                               tag='salt/netapi/hook',
                                                               callback=verify_event)
            # fire the event
            response = self.fetch('/hook',
                                  method='POST',
                                  body='foo=bar',
                                  headers={saltnado.AUTH_TOKEN_HEADER: self.token['token']},
                                  )
            response_obj = json_loads(response.body)
            self.assertTrue(response_obj['success'])
            self._future_resolved.wait(30)
            event = future.result()
            self.assertEqual(event['tag'], 'salt/netapi/hook')
            self.assertIn('headers', event['data'])
            self.assertEqual(event['data']['post'], {'foo': 'bar'})
        finally:
            self._future_resolved.clear()
            del self._future_resolved
