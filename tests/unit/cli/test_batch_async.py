# -*- coding: utf-8 -*-

from __future__ import absolute_import

# Import Salt Libs
from salt.cli.batch_async import BatchAsync

import tornado
from tornado.testing import AsyncTestCase
from tests.support.unit import skipIf, TestCase
from tests.support.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON


@skipIf(NO_MOCK, NO_MOCK_REASON)
class AsyncBatchTestCase(AsyncTestCase, TestCase):

    def setUp(self):
        self.io_loop = self.get_new_ioloop()
        opts = {'batch': '1',
                'conf_file': {},
                'tgt': '*',
                'timeout': 5,
                'gather_job_timeout': 5,
                'batch_presence_ping_timeout': 1,
                'transport': None,
                'sock_dir': ''}

        with patch('salt.client.get_local_client', MagicMock(return_value=MagicMock())):
            with patch('salt.cli.batch_async.batch_get_opts',
                MagicMock(return_value=opts)
            ):
                self.batch = BatchAsync(
                    opts,
                    MagicMock(side_effect=['1234', '1235', '1236']),
                    {
                        'tgt': '',
                        'fun': '',
                        'kwargs': {
                            'batch': '',
                            'batch_presence_ping_timeout': 1
                        }
                    })

    def test_ping_jid(self):
        self.assertEqual(self.batch.ping_jid, '1234')

    def test_batch_jid(self):
        self.assertEqual(self.batch.batch_jid, '1235')

    def test_find_job_jid(self):
        self.assertEqual(self.batch.find_job_jid, '1236')

    def test_batch_size(self):
        '''
        Tests passing batch value as a number
        '''
        self.batch.opts = {'batch': '2', 'timeout': 5}
        self.batch.minions = set(['foo', 'bar'])
        self.batch.start_batch()
        self.assertEqual(self.batch.batch_size, 2)

    @tornado.testing.gen_test
    def test_batch_start_on_batch_presence_ping_timeout(self):
        self.batch.event = MagicMock()
        future = tornado.gen.Future()
        future.set_result({'minions': ['foo', 'bar']})
        self.batch.local.run_job_async.return_value = future
        ret = self.batch.start()
        # assert start_batch is called later with batch_presence_ping_timeout as param
        self.assertEqual(
            self.batch.event.io_loop.call_later.call_args[0],
            (self.batch.batch_presence_ping_timeout, self.batch.start_batch))
        # assert test.ping called
        self.assertEqual(
            self.batch.local.run_job_async.call_args[0],
            ('*', 'test.ping', [], 'glob')
        )
        # assert down_minions == all minions matched by tgt
        self.assertEqual(self.batch.down_minions, set(['foo', 'bar']))

    @tornado.testing.gen_test
    def test_batch_start_on_gather_job_timeout(self):
        self.batch.event = MagicMock()
        future = tornado.gen.Future()
        future.set_result({'minions': ['foo', 'bar']})
        self.batch.local.run_job_async.return_value = future
        self.batch.batch_presence_ping_timeout = None
        ret = self.batch.start()
        # assert start_batch is called later with gather_job_timeout as param
        self.assertEqual(
            self.batch.event.io_loop.call_later.call_args[0],
            (self.batch.opts['gather_job_timeout'], self.batch.start_batch))

    def test_batch_fire_start_event(self):
        self.batch.minions = set(['foo', 'bar'])
        self.batch.opts = {'batch': '2', 'timeout': 5}
        self.batch.event = MagicMock()
        self.batch.metadata = {'mykey': 'myvalue'}
        self.batch.start_batch()
        self.assertEqual(
            self.batch.event.fire_event.call_args[0],
            (
                {
                    'available_minions': set(['foo', 'bar']),
                    'down_minions': set(),
                    'metadata': self.batch.metadata
                },
                "salt/batch/1235/start"
            )
        )

    @tornado.testing.gen_test
    def test_start_batch_calls_next(self):
        self.batch.schedule_next = MagicMock(return_value=MagicMock())
        self.batch.event = MagicMock()
        future = tornado.gen.Future()
        future.set_result(None)
        self.batch.schedule_next = MagicMock(return_value=future)
        self.batch.start_batch()
        self.assertEqual(self.batch.initialized, True)
        self.assertEqual(len(self.batch.schedule_next.mock_calls), 1)

    def test_batch_fire_done_event(self):
        self.batch.minions = set(['foo', 'bar'])
        self.batch.event = MagicMock()
        self.batch.metadata = {'mykey': 'myvalue'}
        self.batch.end_batch()
        self.assertEqual(
            self.batch.event.fire_event.call_args[0],
            (
                {
                    'available_minions': set(['foo', 'bar']),
                    'done_minions': set(),
                    'down_minions': set(),
                    'timedout_minions': set(),
                    'metadata': self.batch.metadata
                },
                "salt/batch/1235/done"
            )
        )
        self.assertEqual(
            len(self.batch.event.remove_event_handler.mock_calls), 1)

    @tornado.testing.gen_test
    def test_batch_next(self):
        self.batch.event = MagicMock()
        self.batch.opts['fun'] = 'my.fun'
        self.batch.opts['arg'] = []
        self.batch._get_next = MagicMock(return_value={'foo', 'bar'})
        self.batch.batch_size = 2
        future = tornado.gen.Future()
        future.set_result({'minions': ['foo', 'bar']})
        self.batch.local.run_job_async.return_value = future
        self.batch.eauth = {'username': 'user#1', 'password': 'pass'}
        self.batch.metadata = {'mykey': 'myvalue'}
        ret = self.batch.schedule_next().result()
        self.assertEqual(
            self.batch.local.run_job_async.call_args[0],
            ({'foo', 'bar'}, 'my.fun', [], 'list')
        )
        self.assertEqual(
            self.batch.event.io_loop.call_later.call_args[0],
            (self.batch.opts['timeout'], self.batch.find_job, {'foo', 'bar'})
        )
        self.assertEqual(
            self.batch.local.run_job_async.call_args[1],
            {
                'username': 'user#1',
                'password': 'pass',
                'jid': self.batch.batch_jid,
                'ret': u'',
                'gather_job_timeout': self.batch.opts['gather_job_timeout'],
                'raw': False,
                'metadata': {'mykey': 'myvalue'}
            }
        )
        self.assertEqual(self.batch.active, {'bar', 'foo'})

    def test_next_batch(self):
        self.batch.minions = {'foo', 'bar'}
        self.batch.batch_size = 2
        self.assertEqual(self.batch._get_next(), {'foo', 'bar'})

    def test_next_batch_one_done(self):
        self.batch.minions = {'foo', 'bar'}
        self.batch.done_minions = {'bar'}
        self.batch.batch_size = 2
        self.assertEqual(self.batch._get_next(), {'foo'})

    def test_next_batch_one_done_one_active(self):
        self.batch.minions = {'foo', 'bar', 'baz'}
        self.batch.done_minions = {'bar'}
        self.batch.active = {'baz'}
        self.batch.batch_size = 2
        self.assertEqual(self.batch._get_next(), {'foo'})

    def test_next_batch_one_done_one_active_one_timedout(self):
        self.batch.minions = {'foo', 'bar', 'baz', 'faz'}
        self.batch.done_minions = {'bar'}
        self.batch.active = {'baz'}
        self.batch.timedout_minions = {'faz'}
        self.batch.batch_size = 2
        self.assertEqual(self.batch._get_next(), {'foo'})

    def test_next_batch_bigger_size(self):
        self.batch.minions = {'foo', 'bar'}
        self.batch.batch_size = 3
        self.assertEqual(self.batch._get_next(), {'foo', 'bar'})

    def test_next_batch_all_done(self):
        self.batch.minions = {'foo', 'bar'}
        self.batch.done_minions = {'foo', 'bar'}
        self.batch.batch_size = 2
        self.assertEqual(self.batch._get_next(), set())

    def test_next_batch_all_active(self):
        self.batch.minions = {'foo', 'bar'}
        self.batch.active = {'foo', 'bar'}
        self.batch.batch_size = 2
        self.assertEqual(self.batch._get_next(), set())

    def test_next_batch_all_timedout(self):
        self.batch.minions = {'foo', 'bar'}
        self.batch.timedout_minions = {'foo', 'bar'}
        self.batch.batch_size = 2
        self.assertEqual(self.batch._get_next(), set())

    def test_batch__event_handler_ping_return(self):
        self.batch.down_minions = {'foo'}
        self.batch.event = MagicMock(
            unpack=MagicMock(return_value=('salt/job/1234/ret/foo', {'id': 'foo'})))
        self.batch.start()
        self.assertEqual(self.batch.minions, set())
        self.batch._BatchAsync__event_handler(MagicMock())
        self.assertEqual(self.batch.minions, {'foo'})
        self.assertEqual(self.batch.done_minions, set())

    def test_batch__event_handler_call_start_batch_when_all_pings_return(self):
        self.batch.down_minions = {'foo'}
        self.batch.event = MagicMock(
            unpack=MagicMock(return_value=('salt/job/1234/ret/foo', {'id': 'foo'})))
        self.batch.start()
        self.batch._BatchAsync__event_handler(MagicMock())
        self.assertEqual(
            self.batch.event.io_loop.spawn_callback.call_args[0],
            (self.batch.start_batch,))

    def test_batch__event_handler_not_call_start_batch_when_not_all_pings_return(self):
        self.batch.down_minions = {'foo', 'bar'}
        self.batch.event = MagicMock(
            unpack=MagicMock(return_value=('salt/job/1234/ret/foo', {'id': 'foo'})))
        self.batch.start()
        self.batch._BatchAsync__event_handler(MagicMock())
        self.assertEqual(
            len(self.batch.event.io_loop.spawn_callback.mock_calls), 0)

    def test_batch__event_handler_batch_run_return(self):
        self.batch.event = MagicMock(
            unpack=MagicMock(return_value=('salt/job/1235/ret/foo', {'id': 'foo'})))
        self.batch.start()
        self.batch.active = {'foo'}
        self.batch._BatchAsync__event_handler(MagicMock())
        self.assertEqual(self.batch.active, set())
        self.assertEqual(self.batch.done_minions, {'foo'})
        self.assertEqual(
            self.batch.event.io_loop.call_later.call_args[0],
            (self.batch.batch_delay, self.batch.schedule_next))

    def test_batch__event_handler_find_job_return(self):
        self.batch.event = MagicMock(
            unpack=MagicMock(return_value=('salt/job/1236/ret/foo', {'id': 'foo'})))
        self.batch.start()
        self.batch._BatchAsync__event_handler(MagicMock())
        self.assertEqual(self.batch.find_job_returned, {'foo'})

    @tornado.testing.gen_test
    def test_batch__event_handler_end_batch(self):
        self.batch.event = MagicMock(
            unpack=MagicMock(return_value=('salt/job/not-my-jid/ret/foo', {'id': 'foo'})))
        future = tornado.gen.Future()
        future.set_result({'minions': ['foo', 'bar', 'baz']})
        self.batch.local.run_job_async.return_value = future
        self.batch.start()
        self.batch.initialized = True
        self.assertEqual(self.batch.down_minions, {'foo', 'bar', 'baz'})
        self.batch.end_batch = MagicMock()
        self.batch.minions = {'foo', 'bar', 'baz'}
        self.batch.done_minions = {'foo', 'bar'}
        self.batch.timedout_minions = {'baz'}
        self.batch._BatchAsync__event_handler(MagicMock())
        self.assertEqual(len(self.batch.end_batch.mock_calls), 1)

    @tornado.testing.gen_test
    def test_batch_find_job(self):
        self.batch.event = MagicMock()
        future = tornado.gen.Future()
        future.set_result({})
        self.batch.local.run_job_async.return_value = future
        self.batch.find_job({'foo', 'bar'})
        self.assertEqual(
            self.batch.event.io_loop.call_later.call_args[0],
            (self.batch.opts['gather_job_timeout'], self.batch.check_find_job, {'foo', 'bar'})
        )

    @tornado.testing.gen_test
    def test_batch_find_job_with_done_minions(self):
        self.batch.done_minions = {'bar'}
        self.batch.event = MagicMock()
        future = tornado.gen.Future()
        future.set_result({})
        self.batch.local.run_job_async.return_value = future
        self.batch.find_job({'foo', 'bar'})
        self.assertEqual(
            self.batch.event.io_loop.call_later.call_args[0],
            (self.batch.opts['gather_job_timeout'], self.batch.check_find_job, {'foo'})
        )

    def test_batch_check_find_job_did_not_return(self):
        self.batch.event = MagicMock()
        self.batch.active = {'foo'}
        self.batch.find_job_returned = set()
        self.batch.check_find_job({'foo'})
        self.assertEqual(self.batch.find_job_returned, set())
        self.assertEqual(self.batch.active, set())
        self.assertEqual(len(self.batch.event.io_loop.add_callback.mock_calls), 0)

    def test_batch_check_find_job_did_return(self):
        self.batch.event = MagicMock()
        self.batch.find_job_returned = {'foo'}
        self.batch.check_find_job({'foo'})
        self.assertEqual(
            self.batch.event.io_loop.add_callback.call_args[0],
            (self.batch.find_job, {'foo'})
        )

    def test_batch_check_find_job_multiple_states(self):
        self.batch.event = MagicMock()
        # currently running minions
        self.batch.active = {'foo', 'bar'}

        # minion is running and find_job returns
        self.batch.find_job_returned = {'foo'}

        # minion started running but find_job did not return
        self.batch.timedout_minions = {'faz'}

        # minion finished
        self.batch.done_minions = {'baz'}

        # both not yet done but only 'foo' responded to find_job
        not_done = {'foo', 'bar'}

        self.batch.check_find_job(not_done)

        # assert 'bar' removed from active
        self.assertEqual(self.batch.active, {'foo'})

        # assert 'bar' added to timedout_minions
        self.assertEqual(self.batch.timedout_minions, {'bar', 'faz'})

        # assert 'find_job' schedueled again only for 'foo'
        self.assertEqual(
            self.batch.event.io_loop.add_callback.call_args[0],
            (self.batch.find_job, {'foo'})
        )
