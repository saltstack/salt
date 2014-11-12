# encoding: utf-8
'''
A REST API for Salt
===================

.. py:currentmodule:: salt.netapi.rest_tornado.saltnado

:depends:   - tornado Python module



In order to run rest_tornado with the salt-master
add the following to your salt master config file.

.. code-block:: yaml

    rest_tornado:
        # can be any port
        port: 8000
        ssl_crt: /etc/pki/api/certs/server.crt
        # no need to specify ssl_key if cert and key
        # are in one single file
        ssl_key: /etc/pki/api/certs/server.key
        debug: False
        disable_ssl: False


Notes
=====

.. code-block:: bash

    curl localhost:8888/login -d client=local -d username=username -d password=password -d eauth=pam

    # for testing
    curl -H 'X-Auth-Token: 89010c15bcbc8e4fc4ce4605b6699165' localhost:8888 -d client=local -d tgt='*' -d fun='test.ping'

    # not working.... but in siege 3.0.1 and posts..
    siege -c 1 -n 1 "http://127.0.0.1:8888 POST client=local&tgt=*&fun=test.ping"

    # this works
    ab - c 50 -n 100 -p body -T 'application/x-www-form-urlencoded' http://localhost:8888/

    {"return": [{"perms": ["*.*"], "start": 1396151398.373983, "token": "cb86b805e8915c84bceb0d466026caab", "expire": 1396194598.373983, "user": "jacksontj", "eauth": "pam"}]}[jacksontj@Thomas-PC netapi]$
'''
# pylint: disable=W0232

import logging
from copy import copy

import time
import os
import sys

import tornado.httpserver
import tornado.ioloop
import tornado.web
import tornado.gen

from tornado.concurrent import Future

from collections import defaultdict

import math
import functools
import yaml
import zmq
import fnmatch

# salt imports
import salt.netapi
import salt.utils
import salt.utils.event
from salt.utils.event import tagify
import salt.client
import salt.runner
import salt.auth
from salt import syspaths


json = salt.utils.import_json()
logger = logging.getLogger()

# The clients rest_cherrypi supports. We want to mimic the interface, but not
#     necessarily use the same API under the hood
# # all of these require coordinating minion stuff
#  - "local" (done)
#  - "local_async" (done)
#  - "local_batch" (done)

# # master side
#  - "runner" (done)
#  - "wheel" (need async api...)


class SaltClientsMixIn(object):
    '''
    MixIn class to container all of the salt clients that the API needs
    '''
    @property
    def saltclients(self):
        if not hasattr(self, '__saltclients'):
            # TODO: refreshing clients using cachedict
            self.__saltclients = {
                'local': salt.client.get_local_client(mopts=self.application.opts).run_job,
                # not the actual client we'll use.. but its what we'll use to get args
                'local_batch': salt.client.get_local_client(mopts=self.application.opts).cmd_batch,
                'local_async': salt.client.get_local_client(mopts=self.application.opts).run_job,
                'runner': salt.runner.RunnerClient(opts=self.application.opts).async,
                }
        return self.__saltclients


AUTH_TOKEN_HEADER = 'X-Auth-Token'
AUTH_COOKIE_NAME = 'session_id'


class TimeoutException(Exception):
    pass


class Any(Future):
    '''
    Future that wraps other futures to "block" until one is done
    '''
    def __init__(self, futures):  # pylint: disable=E1002
        super(Any, self).__init__()
        for future in futures:
            future.add_done_callback(self.done_callback)

    def done_callback(self, future):
        # Any is completed once one is done, we don't set for the rest
        if not self.done():
            self.set_result(future)


class EventListener(object):
    '''
    Class responsible for listening to the salt master event bus and updating
    futures. This is the core of what makes this async, this allows us to do
    non-blocking work in the main processes and "wait" for an event to happen
    '''

    def __init__(self, mod_opts, opts):
        self.mod_opts = mod_opts
        self.opts = opts
        self.event = salt.utils.event.get_event(
            'master',
            opts['sock_dir'],
            opts['transport'],
            opts=opts)

        self.event.subscribe()  # start listening for events immediately

        # tag -> list of futures
        self.tag_map = defaultdict(list)

        # request_obj -> list of (tag, future)
        self.request_map = defaultdict(list)

        # start listening for events
        tornado.ioloop.IOLoop.current().add_callback(self.iter_events)

    def clean_timeout_futures(self, request):
        '''
        Remove all futures that were waiting for request `request` since it is done waiting
        '''
        if request not in self.request_map:
            return
        for tag, future in self.request_map[request]:
            # TODO: log, this shouldn't happen...
            if tag not in self.tag_map:
                continue
            # mark the future done
            future.set_exception(TimeoutException())
            self.tag_map[tag].remove(future)

            # if that was the last of them, remove the key all together
            if len(self.tag_map[tag]) == 0:
                del self.tag_map[tag]

    def get_event(self,
                  request,
                  tag='',
                  callback=None,
                  ):
        '''
        Get an event (async of course) return a future that will get it later
        '''
        future = Future()
        if callback is not None:
            def handle_future(future):
                response = future.result()
                tornado.ioloop.IOLoop.current().add_callback(callback, response)
            future.add_done_callback(handle_future)
        # add this tag and future to the callbacks
        self.tag_map[tag].append(future)
        self.request_map[request].append((tag, future))

        return future

    # TODO: change to use ZMQStreams (http://zeromq.github.io/pyzmq/api/generated/zmq.eventloop.zmqstream.html)
    def iter_events(self):
        '''
        Iterate over all events that could happen
        '''
        try:
            data = self.event.get_event_noblock()
            # see if we have any futures that need this info:
            for tag_prefix, futures in self.tag_map.items():
                if data['tag'].startswith(tag_prefix):
                    for future in futures:
                        if future.done():
                            continue
                        future.set_result(data)
                        self.tag_map[tag_prefix].remove(future)

            # call yourself back!
            tornado.ioloop.IOLoop.current().add_callback(self.iter_events)

        except zmq.ZMQError as e:
            # TODO: not sure what other errors we can get...
            if e.errno != zmq.EAGAIN:
                raise Exception()
            # add callback in the future (to avoid spinning)
            # TODO: configurable timeout
            tornado.ioloop.IOLoop.current().add_timeout(time.time() + 0.1, self.iter_events)
        except:
            logging.critical('Uncaught exception in the event_listener: {0}'.format(sys.exc_info()))
            # TODO: configurable timeout
            tornado.ioloop.IOLoop.current().add_timeout(time.time() + 0.1, self.iter_events)


# TODO: move to a utils function within salt-- the batching stuff is a bit tied together
def get_batch_size(batch, num_minions):
    '''
    Return the batch size that you should have
        batch: string
        num_minions: int

    '''
    # figure out how many we can keep in flight
    partition = lambda x: float(x) / 100.0 * num_minions
    try:
        if '%' in batch:
            res = partition(float(batch.strip('%')))
            if res < 1:
                return int(math.ceil(res))
            else:
                return int(res)
        else:
            return int(batch)
    except ValueError:
        print(('Invalid batch data sent: {0}\nData must be in the form'
               'of %10, 10% or 3').format(batch))


class BaseSaltAPIHandler(tornado.web.RequestHandler, SaltClientsMixIn):
    ct_out_map = (
        ('application/json', json.dumps),
        ('application/x-yaml', yaml.safe_dump),
    )

    def min_syndic_wait_done(self):
        '''
        Ensure that the request has been open for a minimum of syndic_wait time
        '''
        if not self.application.opts['order_masters']:
            return True
        elif time.time() > self.start + self.application.opts['syndic_wait']:
            return True
        return False

    def _verify_client(self, client):
        '''
        Verify that the client is in fact one we have
        '''
        if client not in self.saltclients:
            self.set_status(400)
            self.write("We don't serve your kind here")
            self.finish()

    @property
    def token(self):
        '''
        The token used for the request
        '''
        # find the token (cookie or headers)
        if AUTH_TOKEN_HEADER in self.request.headers:
            return self.request.headers[AUTH_TOKEN_HEADER]
        else:
            return self.get_cookie(AUTH_COOKIE_NAME)

    def _verify_auth(self):
        '''
        Boolean whether the request is auth'd
        '''

        return self.token and bool(self.application.auth.get_tok(self.token))

    def prepare(self):
        '''
        Run before get/posts etc. Pre-flight checks:
            - verify that we can speak back to them (compatible accept header)
        '''
        # verify the content type
        found = False
        for content_type, dumper in self.ct_out_map:
            if fnmatch.fnmatch(content_type, self.request.headers.get('Accept', '*/*')):
                found = True
                break

        # better return message?
        if not found:
            self.send_error(406)

        self.content_type = content_type
        self.dumper = dumper

        # do the common parts
        self.start = time.time()
        self.connected = True

        self.lowstate = self._get_lowstate()

    def timeout_futures(self):
        '''
        timeout a session
        '''
        # TODO: set a header or something??? so we know it was a timeout
        self.application.event_listener.clean_timeout_futures(self)

    def on_finish(self):
        '''
        When the job has been done, lets cleanup
        '''
        # timeout all the futures
        self.timeout_futures()

    def on_connection_close(self):
        '''
        If the client disconnects, lets close out
        '''
        self.finish()

    def serialize(self, data):
        '''
        Serlialize the output based on the Accept header
        '''
        self.set_header('Content-Type', self.content_type)

        return self.dumper(data)

    def _form_loader(self, _):
        '''
        function to get the data from the urlencoded forms
        ignore the data passed in and just get the args from wherever they are
        '''
        data = {}
        for key, val in self.request.arguments.iteritems():
            if len(val) == 1:
                data[key] = val[0]
            else:
                data[key] = val
        return data

    def deserialize(self, data):
        '''
        Deserialize the data based on request content type headers
        '''
        ct_in_map = {
            'application/x-www-form-urlencoded': self._form_loader,
            'application/json': json.loads,
            'application/x-yaml': yaml.safe_load,
            'text/yaml': yaml.safe_load,
            # because people are terrible and dont mean what they say
            'text/plain': json.loads
        }

        try:
            return ct_in_map[self.request.headers['Content-Type']](data)
        except KeyError:
            self.send_error(406)
        except ValueError:
            self.send_error(400)

    def _get_lowstate(self):
        '''
        Format the incoming data into a lowstate object
        '''
        if not self.request.body:
            return
        data = self.deserialize(self.request.body)
        self.raw_data = copy(data)

        if self.request.headers.get('Content-Type') == 'application/x-www-form-urlencoded':
            if 'arg' in data and not isinstance(data['arg'], list):
                data['arg'] = [data['arg']]
            lowstate = [data]
        else:
            lowstate = data
        return lowstate


class SaltAuthHandler(BaseSaltAPIHandler):
    '''
    Handler for login resquests
    '''
    def get(self):
        '''
        We don't allow gets on the login path, so lets send back a nice message
        '''
        self.set_status(401)
        self.set_header('WWW-Authenticate', 'Session')

        ret = {'status': '401 Unauthorized',
               'return': 'Please log in'}

        self.write(self.serialize(ret))
        self.finish()

    # TODO: make async? Underlying library isn't... and we ARE making disk calls :(
    def post(self):
        '''
        Authenticate against Salt's eauth system
        {"return": [{"perms": ["*.*"], "start": 1395507675.396021, "token": "dea8274dc359fee86357d9d0263ec93c0498888e", "expire": 1395550875.396021, "user": "jacksontj", "eauth": "pam"}]}
        '''
        try:
            creds = {'username': self.get_arguments('username')[0],
                     'password': self.get_arguments('password')[0],
                     'eauth': self.get_arguments('eauth')[0],
                     }
        # if any of the args are missing, its a bad request
        except IndexError:
            self.send_error(400)
            return


        token = self.application.auth.mk_token(creds)
        if 'token' not in token:
            # TODO: nicer error message
            # 'Could not authenticate using provided credentials')
            self.send_error(401)
            # return since we don't want to execute any more
            return

        # Grab eauth config for the current backend for the current user
        try:
            perms = self.application.opts['external_auth'][token['eauth']][token['name']]

        # If we can't find the creds, then they aren't authorized
        except KeyError:
            self.send_error(401)
            return

        except (AttributeError, IndexError):
            logging.debug("Configuration for external_auth malformed for "
                          "eauth '{0}', and user '{1}'."
                          .format(token.get('eauth'), token.get('name')), exc_info=True)
            # TODO better error -- 'Configuration for external_auth could not be read.'
            self.send_error(500)
            return

        ret = {'return': [{
            'token': token['token'],
            'expire': token['expire'],
            'start': token['start'],
            'user': token['name'],
            'eauth': token['eauth'],
            'perms': perms,
            }]}

        self.write(self.serialize(ret))
        self.finish()


class SaltAPIHandler(BaseSaltAPIHandler, SaltClientsMixIn):
    '''
    Main API handler for base "/"
    '''
    def get(self):
        '''
        return data about what clients you have
        '''
        ret = {"clients": self.saltclients.keys(),
               "return": "Welcome"}
        self.write(self.serialize(ret))
        self.finish()

    @tornado.web.asynchronous
    def post(self):
        '''
        This function takes in all the args for dispatching requests
            **Example request**::

            % curl -si https://localhost:8000 \\
                    -H "Accept: application/x-yaml" \\
                    -H "X-Auth-Token: d40d1e1e" \\
                    -d client=local \\
                    -d tgt='*' \\
                    -d fun='test.sleep' \\
                    -d arg=1
        '''
        # if you aren't authenticated, redirect to login
        if not self._verify_auth():
            self.redirect('/login')
            return

        self.disbatch()

    @tornado.gen.coroutine
    def disbatch(self):
        '''
        Disbatch a lowstate job to the appropriate client

        Auth must have been verified before this point
        '''
        ret = []

        # check clients before going, we want to throw 400 if one is bad
        for low in self.lowstate:
            client = low.get('client')
            self._verify_client(client)

        for low in self.lowstate:
            # disbatch to the correct handler
            try:
                chunk_ret = yield getattr(self, '_disbatch_{0}'.format(low['client']))(low)
                ret.append(chunk_ret)
            except Exception as ex:
                # TODO: log?
                print ex
                import traceback
                traceback.print_exc()
                ret.append('Unexpected exception while handling request: {0}'.format(ex))

        self.write(self.serialize({'return': ret}))
        self.finish()

    @tornado.gen.coroutine
    def _disbatch_local_batch(self, chunk):
        '''
        Disbatch local client batched commands
        '''
        f_call = salt.utils.format_call(self.saltclients['local_batch'], chunk)
        # override the expr_form
        f_call['kwargs']['expr_form'] = 'list'

        # ping all the minions (to see who we have to talk to)
        # Don't catch any exception, since we won't know what to do, we'll
        # let the upper level deal with this one
        ping_ret = yield self._disbatch_local({'tgt': chunk['tgt'],
                                               'fun': 'test.ping',
                                               'expr_form': f_call['kwargs']['expr_form']})

        chunk_ret = {}

        if not isinstance(ping_ret, dict):
            raise tornado.gen.Return(chunk_ret)
        minions = ping_ret.keys()

        maxflight = get_batch_size(f_call['kwargs']['batch'], len(minions))
        inflight_futures = []
        # do this batch
        while len(minions) > 0 or len(inflight_futures) > 0:
            # if you have more to go, lets disbatch jobs
            while len(inflight_futures) < maxflight and len(minions) > 0:
                minion_id = minions.pop(0)
                f_call['args'][0] = [minion_id]  # set the tgt to the minion
                pub_data = self.saltclients['local'](*f_call.get('args', ()),
                                                     **f_call.get('kwargs', {}))
                # if the job didn't publish, lets not wait around for nothing
                # we'll just skip
                # TODO: set header??, some special return?, Or just ignore it (like we do in CLI)
                if 'jid' not in pub_data:
                    continue
                tag = tagify([pub_data['jid'], 'ret', minion_id], 'job')
                future = self.application.event_listener.get_event(self, tag=tag)
                inflight_futures.append(future)

            # if we have nothing to wait for, don't wait
            if len(inflight_futures) == 0:
                continue

            # wait until someone is done
            finished_future = yield Any(inflight_futures)
            try:
                event = finished_future.result()
            except TimeoutException:
                break
            chunk_ret[event['data']['id']] = event['data']['return']
            inflight_futures.remove(finished_future)

        raise tornado.gen.Return(chunk_ret)


    @tornado.gen.coroutine
    def _disbatch_local(self, chunk):
        '''
        Disbatch local client commands
        '''
        # TODO: not sure why.... we already verify auth, probably for ACLs
        # require token or eauth
        chunk['token'] = self.token

        chunk_ret = {}

        f_call = salt.utils.format_call(self.saltclients['local'], chunk)
        # fire a job off
        try:
            ping_pub_data = self.saltclients['local'](chunk['tgt'],
                                                      'test.ping',
                                                      [],
                                                      expr_form=f_call['kwargs']['expr_form'])
            pub_data = self.saltclients['local'](*f_call.get('args', ()), **f_call.get('kwargs', {}))
        except EauthAuthenticationError:
            raise tornado.gen.Return('Not authorized to run this job')

        # if the job didn't publish, lets not wait around for nothing
        # TODO: set header??
        if 'jid' not in pub_data:
            raise tornado.gen.Return('No minions matched the target. No command was sent, no jid was assigned.')

        # get the tag that we are looking for
        ping_tag = tagify([ping_pub_data['jid'], 'ret'], 'job')
        ret_tag = tagify([pub_data['jid'], 'ret'], 'job')

        # seed minions_remaining with the pub_data
        minions_remaining = pub_data['minions']

        ret_event = self.application.event_listener.get_event(self, tag=ret_tag)
        ping_event = self.application.event_listener.get_event(self, tag=ping_tag)

        # while we are waiting on all the mininons
        while len(minions_remaining) > 0 or not self.min_syndic_wait_done():
            event_future = yield Any([ret_event, ping_event])
            try:
                event = event_future.result()
            # if you hit a timeout, just stop waiting ;)
            except TimeoutException:
                break
            # If someone returned from the ping, and they are new-- add to minions_remaining
            if event_future == ping_event:
                ping_id = event['data']['id']
                if ping_id not in chunk_ret and ping_id not in minions_remaining:
                    minions_remaining.append(ping_id)
                ping_event = self.application.event_listener.get_event(self, tag=ping_tag)
            # if it is a ret future, its just a regular return
            else:
                chunk_ret[event['data']['id']] = event['data']['return']
                # its possible to get a return that wasn't in the minion_remaining list
                try:
                    minions_remaining.remove(event['data']['id'])
                except ValueError:
                    pass
                ret_event = self.application.event_listener.get_event(self, tag=ret_tag)

        raise tornado.gen.Return(chunk_ret)


    @tornado.gen.coroutine
    def _disbatch_local_async(self, chunk):
        '''
        Disbatch local client_async commands
        '''
        f_call = salt.utils.format_call(self.saltclients['local_async'], chunk)
        # fire a job off
        pub_data = self.saltclients['local_async'](*f_call.get('args', ()), **f_call.get('kwargs', {}))

        raise tornado.gen.Return(pub_data)


    @tornado.gen.coroutine
    def _disbatch_runner(self, chunk):
        '''
        Disbatch runner client commands
        '''
        timeout = float(chunk.get('timeout', self.application.opts['timeout']))
        # set the timeout
        timeout_obj = tornado.ioloop.IOLoop.current().add_timeout(time.time() + timeout, self.timeout_futures)

        f_call = {'args': [chunk['fun'], chunk]}
        pub_data = self.saltclients['runner'](chunk['fun'], chunk)
        tag = pub_data['tag'] + '/ret'
        try:
            event = yield self.application.event_listener.get_event(self, tag=tag)

            # if we finish in time, cancel the timeout
            tornado.ioloop.IOLoop.current().remove_timeout(timeout_obj)

            # only return the return data
            raise tornado.gen.Return(event['data']['return'])
        except TimeoutException:
            raise tornado.gen.Return('Timeout waiting for runner to execute')


class MinionSaltAPIHandler(SaltAPIHandler):
    '''
    Handler for /minion requests
    '''
    @tornado.web.asynchronous
    def get(self, mid=None):  # pylint: disable=W0221
        # if you aren't authenticated, redirect to login
        if not self._verify_auth():
            self.redirect('/login')
            return

        self.lowstate = [{
            'client': 'local',
            'tgt': mid or '*',
            'fun': 'grains.items',
        }]
        self.disbatch()

    @tornado.web.asynchronous
    def post(self):
        '''
        local_async post endpoint
        '''
        # if you aren't authenticated, redirect to login
        if not self._verify_auth():
            self.redirect('/login')
            return

        # verify that all lowstates are the correct client type
        for low in self.lowstate:
            # if you didn't specify, its fine
            if 'client' not in low:
                low['client'] = 'local_async'
                continue
            # if you specified something else, we don't do that
            if low.get('client') != 'local_async':
                self.set_status(400)
                self.write('We don\'t serve your kind here')
                self.finish()
                return

        self.disbatch()


class JobsSaltAPIHandler(SaltAPIHandler):
    '''
    Handler for /minion requests
    '''
    @tornado.web.asynchronous
    def get(self, jid=None):  # pylint: disable=W0221
        # if you aren't authenticated, redirect to login
        if not self._verify_auth():
            self.redirect('/login')
            return

        if jid:
            self.lowstate = [{
                'fun': 'jobs.list_job',
                'jid': jid,
                'client': 'runner',
            }]
        else:
            self.lowstate = [{
                'fun': 'jobs.list_jobs',
                'client': 'runner',
            }]

        self.disbatch()


class RunSaltAPIHandler(SaltAPIHandler):
    '''
    Handler for /run requests
    '''
    @tornado.web.asynchronous
    def post(self):
        self.disbatch()


class EventsSaltAPIHandler(SaltAPIHandler):
    '''
    Handler for /events requests
    '''
    @tornado.gen.coroutine
    def get(self):
        # if you aren't authenticated, redirect to login
        if not self._verify_auth():
            self.redirect('/login')
            return
        # set the streaming headers
        self.set_header('Content-Type', 'text/event-stream')
        self.set_header('Cache-Control', 'no-cache')
        self.set_header('Connection', 'keep-alive')

        self.write(u'retry: {0}\n'.format(400))
        self.flush()

        while True:
            try:
                event = yield self.application.event_listener.get_event(self)
                self.write(u'tag: {0}\n'.format(event.get('tag', '')))
                self.write(u'data: {0}\n\n'.format(json.dumps(event)))
                self.flush()
            except TimeoutException:
                break

        self.finish()


class WebhookSaltAPIHandler(SaltAPIHandler):
    '''
    Handler for /hook requests
    '''
    def post(self, tag_suffix=None):  # pylint: disable=W0221
        if not self._verify_auth():
            self.redirect('/login')
            return

        # if you have the tag, prefix
        tag = 'salt/netapi/hook'
        if tag_suffix:
            tag += tag_suffix

        # TODO: consolidate??
        self.event = salt.utils.event.get_event(
            'master',
            self.application.opts['sock_dir'],
            self.application.opts['transport'],
            opts=self.application.opts)

        ret = self.event.fire_event({
            'post': self.raw_data,
            'headers': self.request.headers,
        }, tag)

        self.write(self.serialize({'success': ret}))
