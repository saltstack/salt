# coding: utf-8
import os

import json
import yaml
import urllib

from salt.netapi.rest_tornado import saltnado

import tornado.testing
import tornado.concurrent
from salttesting import skipIf, TestCase

from unit.utils.event_test import eventpublisher_process, event, SOCK_DIR


class TestUtils(TestCase):
    def test_batching(self):
        assert 1 == saltnado.get_batch_size('1', 10)
        assert 2 == saltnado.get_batch_size('2', 10)

        assert 1 == saltnado.get_batch_size('10%', 10)
        # TODO: exception in this case? The core doesn't so we shouldn't
        assert 11 == saltnado.get_batch_size('110%', 10)


class TestSaltnadoUtils(tornado.testing.AsyncTestCase):
    def test_any_future(self):
        '''
        Test that the Any Future does what we think it does
        '''
        # create a few futures
        futures = []
        for x in xrange(0, 3):
            future = tornado.concurrent.Future()
            future.add_done_callback(self.stop)
            futures.append(future)

        # create an any future, make sure it isn't immediately done
        any_ = saltnado.Any(futures)
        assert any_.done() is False

        # finish one, lets see who finishes
        futures[0].set_result('foo')
        self.wait()

        assert any_.done() is True
        assert futures[0].done() is True
        assert futures[1].done() is False
        assert futures[2].done() is False

        # make sure it returned the one that finished
        assert any_.result() == futures[0]


class TestEventListener(tornado.testing.AsyncTestCase):
    def setUp(self):
        if not os.path.exists(SOCK_DIR):
            os.makedirs(SOCK_DIR)
        super(TestEventListener, self).setUp()

    def test_simple(self):
        '''
        Test getting a few events
        '''
        with eventpublisher_process():
            me = event.MasterEvent(SOCK_DIR)
            event_listener = saltnado.EventListener({},  # we don't use mod_opts, don't save?
                                                    {'sock_dir': SOCK_DIR,
                                                     'transport': 'zeromq'})
            event_future = event_listener.get_event(1, 'evt1', self.stop)  # get an event future
            me.fire_event({'data': 'foo2'}, 'evt2')  # fire an event we don't want
            me.fire_event({'data': 'foo1'}, 'evt1')  # fire an event we do want
            self.wait()  # wait for the future

            # check that we got the event we wanted
            assert event_future.done()
            assert event_future.result()['tag'] ==  'evt1'
            assert event_future.result()['data']['data'] ==  'foo1'

class TestBaseSaltAPIHandler(tornado.testing.AsyncHTTPTestCase):
    content_type_map = {'json': 'application/json',
                        'yaml': 'application/x-yaml',
                        'text': 'text/plain',
                        'form': 'application/x-www-form-urlencoded'}
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

    # TODO: break into separate functions per type?
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
        assert returned_lowstate['arg'] == ['10']



if __name__ == '__main__':
    from integration import run_tests
    run_tests(TestUtils, needs_daemon=False)
