# -*- coding: utf-8 -*-
'''
Scheduling routines are located here. To activate the scheduler make the
schedule option available to the master or minion configurations (master config
file or for the minion via config or pillar)

code-block:: yaml

    schedule:
      job1:
        function: state.sls
        seconds: 3600
        args:
          - httpd
        kwargs:
          test: True

This will schedule the command: state.sls httpd test=True every 3600 seconds
(every hour)

The scheduler also supports ensuring that there are no more than N copies of
a particular routine running.  Use this for jobs that may be long-running
and could step on each other or pile up in case of infrastructure outage.

The default for maxrunning is 1.

code-block:: yaml

    schedule:
      long_running_job:
          function: big_file_transfer
          jid_include: True
          maxrunning: 1

'''

# Import python libs
import os
import time
import datetime
import multiprocessing
import threading
import sys
import logging

# Import Salt libs
import salt.utils
import salt.utils.process
import salt.payload

log = logging.getLogger(__name__)


class Schedule(object):
    '''
    Create a Schedule object, pass in the opts and the functions dict to use
    '''
    def __init__(self, opts, functions, returners=None, intervals=None):
        self.opts = opts
        self.functions = functions
        if isinstance(intervals, dict):
            self.intervals = intervals
        else:
            self.intervals = {}
        if isinstance(returners, dict):
            self.returners = returners
        else:
            self.returners = {}
        self.schedule_returner = self.option('schedule_returner')
        # Keep track of the lowest loop interval needed in this variable
        self.loop_interval = sys.maxint
        clean_proc_dir(opts)

    def option(self, opt):
        '''
        Return the schedule data structure
        '''
        if 'config.merge' in self.functions:
            return self.functions['config.merge'](opt, {}, omit_master=True)
        return self.opts.get(opt, {})

    def handle_func(self, func, data):
        '''
        Execute this method in a multiprocess or thread
        '''
        if salt.utils.is_windows():
            self.functions = salt.loader.minion_mods(self.opts)
            self.returners = salt.loader.returners(self.opts, self.functions)
        ret = {'id': self.opts.get('id', 'master'),
               'fun': func,
               'jid': '{0:%Y%m%d%H%M%S%f}'.format(datetime.datetime.now())}

        proc_fn = os.path.join(
            salt.minion.get_proc_dir(self.opts['cachedir']),
            ret['jid']
        )

        # Check to see if there are other jobs with this
        # signature running.  If there are more than maxrunning
        # jobs present then don't start another.
        # If jid_include is False for this job we can ignore all this
        # NOTE--jid_include defaults to True, thus if it is missing from the data
        # dict we treat it like it was there and is True
        if 'jid_include' not in data or data['jid_include']:
            jobcount = 0
            for basefilename in os.listdir(salt.minion.get_proc_dir(self.opts['cachedir'])):
                fn = os.path.join(salt.minion.get_proc_dir(self.opts['cachedir']), basefilename)
                with salt.utils.fopen(fn, 'r') as fp_:
                    job = salt.payload.Serial(self.opts).load(fp_)
                    log.debug('schedule.handle_func: Checking job against '
                              'fun {0}: {1}'.format(ret['fun'], job))
                    if ret['fun'] == job['fun']:
                        jobcount += 1
                        log.debug(
                            'schedule.handle_func: Incrementing jobcount, now '
                            '{0}, maxrunning is {1}'.format(
                                      jobcount, data['maxrunning']))
                        if jobcount >= data['maxrunning']:
                            log.debug(
                                'schedule.handle_func: The scheduled job {0} '
                                'was not started, {1} already running'.format(
                                    func, data['maxrunning']))
                            return False

        salt.utils.daemonize_if(self.opts)

        ret['pid'] = os.getpid()

        if 'jid_include' not in data or data['jid_include']:
            log.debug('schedule.handle_func: adding this job to the jobcache '
                      'with data {0}'.format(ret))
            # write this to /var/cache/salt/minion/proc
            with salt.utils.fopen(proc_fn, 'w+') as fp_:
                fp_.write(salt.payload.Serial(self.opts).dumps(ret))

        args = None
        if 'args' in data:
            args = data['args']

        kwargs = None
        if 'kwargs' in data:
            kwargs = data['kwargs']

        if args and kwargs:
            ret['return'] = self.functions[func](*args, **kwargs)

        if args and not kwargs:
            ret['return'] = self.functions[func](*args)

        if kwargs and not args:
            ret['return'] = self.functions[func](**kwargs)

        if not kwargs and not args:
            ret['return'] = self.functions[func]()

        if 'returner' in data or self.schedule_returner:
            rets = []
            if isinstance(data['returner'], str):
                rets.append(data['returner'])
            elif isinstance(data['returner'], list):
                for returner in data['returner']:
                    if returner not in rets:
                        rets.append(returner)
            if isinstance(self.schedule_returner, list):
                for returner in self.schedule_returner:
                    if returner not in rets:
                        rets.append(returner)
            if isinstance(self.schedule_returner, str):
                if self.schedule_returner not in rets:
                    rets.append(self.schedule_returner)
            for returner in rets:
                ret_str = '{0}.returner'.format(returner)
                if ret_str in self.returners:
                    ret['success'] = True
                    self.returners[ret_str](ret)
                else:
                    log.info(
                        'Job {0} using invalid returner: {1} Ignoring.'.format(
                        func, returner
                        )
                    )
        try:
            os.unlink(proc_fn)
        except OSError:
            pass

    def eval(self):
        '''
        Evaluate and execute the schedule
        '''
        schedule = self.option('schedule')
        if not isinstance(schedule, dict):
            return
        for job, data in schedule.items():
            if 'function' in data:
                func = data['function']
            elif 'func' in data:
                func = data['func']
            elif 'fun' in data:
                func = data['fun']
            else:
                func = None
            if func not in self.functions:
                log.info(
                    'Invalid function: {0} in job {1}. Ignoring.'.format(
                        job, func
                    )
                )
                continue
            # Add up how many seconds between now and then
            seconds = 0
            seconds += int(data.get('seconds', 0))
            seconds += int(data.get('minutes', 0)) * 60
            seconds += int(data.get('hours', 0)) * 3600
            seconds += int(data.get('days', 0)) * 86400
            # Check if the seconds variable is lower than current lowest
            # loop interval needed. If it is lower then overwrite variable
            # external loops using can then check this variable for how often
            # they need to reschedule themselves
            if seconds < self.loop_interval:
                self.loop_interval = seconds
            now = int(time.time())
            run = False
            if job in self.intervals:
                if now - self.intervals[job] >= seconds:
                    run = True
            else:
                run = True
            if not run:
                continue
            else:
                log.debug('Running scheduled job: {0}'.format(job))

            if 'jid_include' not in data or data['jid_include']:
                data['jid_include'] = True
                log.debug('schedule: This job was scheduled with jid_include, '
                          'adding to cache (jid_include defaults to True)')
                if 'maxrunning' in data:
                    log.debug('schedule: This job was scheduled with a max '
                              'number of {0}'.format(data['maxrunning']))
                else:
                    log.info('schedule: maxrunning parameter was not specified for '
                              'job {0}, defaulting to 1.'.format(job))
                    data['maxrunning'] = 1

            try:
                if self.opts.get('multiprocessing', True):
                    thread_cls = multiprocessing.Process
                else:
                    thread_cls = threading.Thread
                proc = thread_cls(target=self.handle_func, args=(func, data))
                proc.start()
                if self.opts.get('multiprocessing', True):
                    proc.join()
            finally:
                self.intervals[job] = int(time.time())


def clean_proc_dir(opts):

    '''
    Loop through jid files in the minion proc directory (default /var/cache/salt/minion/proc)
    and remove any that refer to processes that no longer exist
    '''

    for basefilename in os.listdir(salt.minion.get_proc_dir(opts['cachedir'])):
        fn = os.path.join(salt.minion.get_proc_dir(opts['cachedir']), basefilename)
        with salt.utils.fopen(fn, 'r') as fp_:
            job = salt.payload.Serial(opts).load(fp_)
            log.debug('schedule.clean_proc_dir: checking job {0} for process '
                      'existence'.format(job))
            if job is not None and 'pid' in job:
                if salt.utils.process.os_is_running(job['pid']):
                    log.debug('schedule.clean_proc_dir: Cleaning proc dir, '
                              'pid {0} still exists.'.format(job['pid']))
                else:
                    # Windows cannot delete an open file
                    if salt.utils.is_windows():
                        fp_.close()
                    # Maybe the file is already gone
                    try:
                        os.unlink(fn)
                    except OSError:
                        pass
