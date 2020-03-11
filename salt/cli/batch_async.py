# -*- coding: utf-8 -*-
'''
Execute a job on the targeted minions by using a moving window of fixed size `batch`.
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import tornado

# Import salt libs
import salt.client

# pylint: enable=import-error,no-name-in-module,redefined-builtin
import logging
import fnmatch

log = logging.getLogger(__name__)

from salt.cli.batch import get_bnum, batch_get_opts, batch_get_eauth


class BatchAsync(object):
    '''
    Run a job on the targeted minions by using a moving window of fixed size `batch`.

    ``BatchAsync`` is used to execute a job on the targeted minions by keeping
    the number of concurrent running minions to the size of `batch` parameter.

    The control parameters are:
        - batch: number/percentage of concurrent running minions
        - batch_delay: minimum wait time between batches
        - batch_presence_ping_timeout: time to wait for presence pings before starting the batch
        - gather_job_timeout: `find_job` timeout
        - timeout: time to wait before firing a `find_job`

    When the batch stars, a `start` event is fired:
         - tag: salt/batch/<batch-jid>/start
         - data: {
             "available_minions": self.minions,
             "down_minions": self.down_minions
           }

    When the batch ends, an `done` event is fired:
        - tag: salt/batch/<batch-jid>/done
        - data: {
             "available_minions": self.minions,
             "down_minions": self.down_minions,
             "done_minions": self.done_minions,
             "timedout_minions": self.timedout_minions
         }
    '''
    def __init__(self, parent_opts, jid_gen, clear_load):
        ioloop = tornado.ioloop.IOLoop.current()
        self.local = salt.client.get_local_client(parent_opts['conf_file'])
        if 'gather_job_timeout' in clear_load['kwargs']:
            clear_load['gather_job_timeout'] = clear_load['kwargs'].pop('gather_job_timeout')
        else:
            clear_load['gather_job_timeout'] = self.local.opts['gather_job_timeout']
        self.batch_presence_ping_timeout = clear_load['kwargs'].get('batch_presence_ping_timeout', None)
        self.batch_delay = clear_load['kwargs'].get('batch_delay', 1)
        self.opts = batch_get_opts(
            clear_load.pop('tgt'),
            clear_load.pop('fun'),
            clear_load['kwargs'].pop('batch'),
            self.local.opts,
            **clear_load)
        self.eauth = batch_get_eauth(clear_load['kwargs'])
        self.metadata = clear_load['kwargs'].get('metadata', {})
        self.minions = set()
        self.down_minions = set()
        self.timedout_minions = set()
        self.done_minions = set()
        self.active = set()
        self.initialized = False
        self.ping_jid = jid_gen()
        self.batch_jid = jid_gen()
        self.find_job_jid = jid_gen()
        self.find_job_returned = set()
        self.event = salt.utils.event.get_event(
            'master',
            self.opts['sock_dir'],
            self.opts['transport'],
            opts=self.opts,
            listen=True,
            io_loop=ioloop,
            keep_loop=True)

    def __set_event_handler(self):
        ping_return_pattern = 'salt/job/{0}/ret/*'.format(self.ping_jid)
        batch_return_pattern = 'salt/job/{0}/ret/*'.format(self.batch_jid)
        find_job_return_pattern = 'salt/job/{0}/ret/*'.format(self.find_job_jid)
        self.event.subscribe(ping_return_pattern, match_type='glob')
        self.event.subscribe(batch_return_pattern, match_type='glob')
        self.event.subscribe(find_job_return_pattern, match_type='glob')
        self.event.patterns = {
            (ping_return_pattern, 'ping_return'),
            (batch_return_pattern, 'batch_run'),
            (find_job_return_pattern, 'find_job_return')
        }
        self.event.set_event_handler(self.__event_handler)

    def __event_handler(self, raw):
        if not self.event:
            return
        mtag, data = self.event.unpack(raw, self.event.serial)
        for (pattern, op) in self.event.patterns:
            if fnmatch.fnmatch(mtag, pattern):
                minion = data['id']
                if op == 'ping_return':
                    self.minions.add(minion)
                    self.down_minions.remove(minion)
                    if not self.down_minions:
                        self.event.io_loop.spawn_callback(self.start_batch)
                elif op == 'find_job_return':
                    self.find_job_returned.add(minion)
                elif op == 'batch_run':
                    if minion in self.active:
                        self.active.remove(minion)
                        self.done_minions.add(minion)
                        # call later so that we maybe gather more returns
                        self.event.io_loop.call_later(self.batch_delay, self.schedule_next)

        if self.initialized and self.done_minions == self.minions.difference(self.timedout_minions):
            self.end_batch()

    def _get_next(self):
        to_run = self.minions.difference(
            self.done_minions).difference(
            self.active).difference(
            self.timedout_minions)
        next_batch_size = min(
            len(to_run),                   # partial batch (all left)
            self.batch_size - len(self.active)  # full batch or available slots
        )
        return set(list(to_run)[:next_batch_size])

    @tornado.gen.coroutine
    def check_find_job(self, minions):
        did_not_return = minions.difference(self.find_job_returned)
        if did_not_return:
            for minion in did_not_return:
                if minion in self.find_job_returned:
                    self.find_job_returned.remove(minion)
                if minion in self.active:
                    self.active.remove(minion)
                self.timedout_minions.add(minion)
        running = minions.difference(did_not_return).difference(self.done_minions).difference(self.timedout_minions)
        if running:
            self.event.io_loop.add_callback(self.find_job, running)

    @tornado.gen.coroutine
    def find_job(self, minions):
        not_done = minions.difference(self.done_minions)
        ping_return = yield self.local.run_job_async(
            not_done,
            'saltutil.find_job',
            [self.batch_jid],
            'list',
            gather_job_timeout=self.opts['gather_job_timeout'],
            jid=self.find_job_jid,
            **self.eauth)
        self.event.io_loop.call_later(
            self.opts['gather_job_timeout'],
            self.check_find_job,
            not_done)

    @tornado.gen.coroutine
    def start(self):
        self.__set_event_handler()
        #start batching even if not all minions respond to ping
        self.event.io_loop.call_later(
            self.batch_presence_ping_timeout or self.opts['gather_job_timeout'],
            self.start_batch)
        ping_return = yield self.local.run_job_async(
            self.opts['tgt'],
            'test.ping',
            [],
            self.opts.get(
                'selected_target_option',
                self.opts.get('tgt_type', 'glob')
            ),
            gather_job_timeout=self.opts['gather_job_timeout'],
            jid=self.ping_jid,
            metadata=self.metadata,
            **self.eauth)
        self.down_minions = set(ping_return['minions'])

    @tornado.gen.coroutine
    def start_batch(self):
        if not self.initialized:
            self.batch_size = get_bnum(self.opts, self.minions, True)
            self.initialized = True
            data = {
                "available_minions": self.minions,
                "down_minions": self.down_minions,
                "metadata": self.metadata
            }
            self.event.fire_event(data, "salt/batch/{0}/start".format(self.batch_jid))
            yield self.schedule_next()

    def end_batch(self):
        data = {
            "available_minions": self.minions,
            "down_minions": self.down_minions,
            "done_minions": self.done_minions,
            "timedout_minions": self.timedout_minions,
            "metadata": self.metadata
        }
        self.event.fire_event(data, "salt/batch/{0}/done".format(self.batch_jid))
        self.event.remove_event_handler(self.__event_handler)

    @tornado.gen.coroutine
    def schedule_next(self):
        next_batch = self._get_next()
        if next_batch:
            yield self.local.run_job_async(
                next_batch,
                self.opts['fun'],
                self.opts['arg'],
                'list',
                raw=self.opts.get('raw', False),
                ret=self.opts.get('return', ''),
                gather_job_timeout=self.opts['gather_job_timeout'],
                jid=self.batch_jid,
                metadata=self.metadata,
                **self.eauth)
            self.event.io_loop.call_later(self.opts['timeout'], self.find_job, set(next_batch))
            self.active = self.active.union(next_batch)
