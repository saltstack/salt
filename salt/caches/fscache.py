# -*- coding: utf-8 -*-
'''
Classes for salts filesystem cache for larger installations.
'''
import salt.utils
import salt.config
import multiprocessing
import zmq
import time
import os
from salt.caches.fsworker import FSWorker
from threading import Thread, Event
import signal
import logging
import salt.log

log = logging.getLogger(__name__)


class FSTimer(Thread):
    '''
    A basic timer class the fires timer-events every second.
    '''
    def __init__(self, opts, event):
        Thread.__init__(self)
        self.opts = opts
        self.stopped = event
        self.daemon = True
        self.serial = salt.payload.Serial(opts.get('serial', ''))
        self.timer_sock = os.path.join(self.opts['sock_dir'], 'fsc_timer.ipc')

    def run(self):
        '''
        main loop that fires the event every second
        '''
        context = zmq.Context()
        # the socket for outgoing timer events
        socket = context.socket(zmq.PUSH)
        socket.setsockopt(zmq.LINGER, 100)
        socket.bind('ipc:///' + self.timer_sock)

        count = 0
        log.debug('FSCache-Timer started')
        while not self.stopped.wait(1):
            socket.send(self.serial.dumps(count))

            count += 1
            if count >= 60:
                count = 0


class FSCache(multiprocessing.Process):
    '''
    Provides access to the cache-system and manages the subprocesses
    that do the cache updates in the background.

    Access to the cache is available to any module that connects
    to the FSCaches IPC-socket.
    '''

    def __init__(self, opts):
        '''
        starts the timer and inits the cache itself
        '''
        super(FSCache, self).__init__()
        log.debug('FSCache initializing...')

        # the possible settings for the cache
        self.opts = opts

        # all jobs the FSCache should run in intervals
        self.jobs = {}

        # the actual cached data
        self.path_data = {}

        # the timer provides 1-second intervals to the loop in run()
        # to make the cache system most responsive, we do not use a loop-
        # delay which makes it hard to get 1-second intervals without a timer
        self.timer_stop = Event()
        self.timer = FSTimer(self.opts, self.timer_stop)
        self.timer.start()
        self.running = True
        self.cache_sock = os.path.join(self.opts['sock_dir'], 'fsc_cache.ipc')
        self.update_sock = os.path.join(self.opts['sock_dir'], 'fsc_upd.ipc')
        self.upd_t_sock = os.path.join(self.opts['sock_dir'], 'fsc_timer.ipc')
        self.cleanup()

    def signal_handler(self, sig, frame):
        '''
        handle signals and shutdown
        '''
        self.stop()

    def cleanup(self):
        log.debug('cleaning up')
        if os.path.exists(self.cache_sock):
            os.remove(self.cache_sock)
        if os.path.exists(self.update_sock):
            os.remove(self.update_sock)
        if os.path.exists(self.upd_t_sock):
            os.remove(self.upd_t_sock)

    def secure(self):
        if os.path.exists(self.cache_sock):
            os.chmod(self.cache_sock, 0600)
        if os.path.exists(self.update_sock):
            os.chmod(self.update_sock, 0600)
        if os.path.exists(self.upd_t_sock):
            os.chmod(self.upd_t_sock, 0600)

    def add_job(self, **kwargs):
        '''
        adds a new job to the FSCache
        '''
        req_vars = ['name', 'path', 'ival', 'patt']

        # make sure new jobs have all variables set
        for var in req_vars:
            if var not in kwargs:
                raise AttributeError('missing variable {0}'.format(var))
        job_name = kwargs['name']
        del kwargs['name']
        self.jobs[job_name] = {}
        self.jobs[job_name].update(kwargs)

    def run_job(self, name):
        '''
        Creates a new subprocess to execute the given job in
        '''
        log.debug('Starting worker \'{0}\''.format(name))
        sub_p = FSWorker(self.opts, name, **self.jobs[name])
        sub_p.start()

    def stop(self):
        '''
        shutdown cache process
        '''
        # avoid getting called twice
        self.cleanup()
        if self.running:
            self.running = False
            self.timer_stop.set()
            self.timer.join()

    def run(self):
        '''
        Main loop of the FSCache, checks schedule, retrieves result-data
        from the workers and answer requests with data from the cache
        '''
        context = zmq.Context()
        # the socket for incoming cache requests
        creq_in = context.socket(zmq.REP)
        creq_in.setsockopt(zmq.LINGER, 100)
        creq_in.bind('ipc:///' + self.cache_sock)

        # the socket for incoming cache-updates from workers
        cupd_in = context.socket(zmq.REP)
        cupd_in.setsockopt(zmq.LINGER, 100)
        cupd_in.bind('ipc:///' + self.update_sock)

        # wait for the timer to bind to its socket
        log.debug('wait 2 secs for the timer')
        time.sleep(2)

        # the socket for the timer-event
        timer_in = context.socket(zmq.PULL)
        timer_in.setsockopt(zmq.LINGER, 100)
        timer_in.connect('ipc:///' + self.upd_t_sock)

        poller = zmq.Poller()
        poller.register(creq_in, zmq.POLLIN)
        poller.register(cupd_in, zmq.POLLIN)
        poller.register(timer_in, zmq.POLLIN)

        # our serializer
        serial = salt.payload.Serial(self.opts.get('serial', ''))

        # register a signal handler
        signal.signal(signal.SIGINT, self.signal_handler)

        # secure the sockets from the world
        self.secure()

        log.info('FSCache started')
        log.debug('FSCache started')

        while self.running:

            # we check for new events with the poller
            try:
                socks = dict(poller.poll())
            except KeyboardInterrupt:
                self.stop()
            except zmq.ZMQError as t:
                self.stop()

            # check for next cache-request
            if socks.get(creq_in) == zmq.POLLIN:
                msg = serial.loads(creq_in.recv())
                log.debug('Received request: {0}'.format(msg))

                # we only accept requests as lists [req_id, <path>]
                if isinstance(msg, list):
                    # for now only one item is assumed to be requested
                    msgid, file_n = msg[:]
                    log.debug('Looking for {0}:{1}'.format(msgid, file_n))

                    fdata = self.path_data.get(file_n, None)

                    if fdata is not None:
                        log.debug('Cache HIT')
                    else:
                        log.debug('Cache MISS')

                    # simulate slow caches
                    #randsleep = random.randint(0,3)
                    #time.sleep(randsleep)

                    # Send reply back to client
                    reply = serial.dumps([msgid, fdata])
                    creq_in.send(reply)

                # wrong format, item not cached
                else:
                    reply = serial.dumps([msgid, None])
                    creq_in.send(reply)

            # check for next cache-update from workers
            elif socks.get(cupd_in) == zmq.POLLIN:
                new_c_data = serial.loads(cupd_in.recv())
                # tell the worker to exit
                cupd_in.send(serial.dumps('OK'))

                # check if the returned data is usable
                if not isinstance(new_c_data, dict):
                    log.error('Worker returned unusable result')
                    del new_c_data
                    continue

                # the workers will return differing data:
                # 1. '{'file1': <data1>, 'file2': <data2>,...}' - a cache update
                # 2. '{search-path: None}' -  job was not run, pre-checks failed
                # 3. '{}' - no files found, check the pattern if defined?
                # 4. anything else is considered malformed

                if len(new_c_data) == 0:
                    log.debug('Got empty update from worker')
                elif new_c_data.values()[0] is not None:
                    log.debug('Got cache update with {0} item(s)'.format(len(new_c_data)))
                    self.path_data.update(new_c_data)
                else:
                    log.debug('Got malformed result dict from worker')

                log.info('{0} entries in cache'.format(len(self.path_data)))

            # check for next timer-event to start new jobs
            elif socks.get(timer_in) == zmq.POLLIN:
                sec_event = serial.loads(timer_in.recv())

                log.debug('Timer event: #{0}'.format(sec_event))

                # loop through the jobs and start if a jobs ival matches
                for item in self.jobs:
                    if sec_event in self.jobs[item]['ival']:
                        self.run_job(item)
        self.stop()
        creq_in.close()
        cupd_in.close()
        timer_in.close()
        context.term()
        log.debug('Shutting down')\

if __name__ == '__main__':
    def run_test():
        opts = salt.config.master_config('./master')

        wlk = FSCache(opts)
        # add two jobs for jobs and cache-files
        wlk.add_job(**{
                        'name': 'grains',
                        'path': '/var/cache/salt/master/minions',
                        'ival': [2, 12, 22],
                        'patt': '^.*$'
                      })

        wlk.add_job(**{
                        'name': 'mine',
                        'path': '/var/cache/salt/master/jobs/',
                        'ival': [4, 14, 24, 34, 44, 54],
                        'patt': '^.*$'
                    })
        wlk.start()

    run_test()
