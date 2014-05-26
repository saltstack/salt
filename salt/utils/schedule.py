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

    schedule:
      job1:
        function: state.sls
        seconds: 3600
        args:
          - httpd
        kwargs:
          test: True
        splay: 15

This will schedule the command: state.sls httpd test=True every 3600 seconds
(every hour) splaying the time between 0 and 15 seconds

    schedule:
      job1:
        function: state.sls
        seconds: 3600
        args:
          - httpd
        kwargs:
          test: True
        splay:
          start: 10
          end: 15

This will schedule the command: state.sls httpd test=True every 3600 seconds
(every hour) splaying the time between 10 and 15 seconds

    ... versionadded:: Helium

Frequency of jobs can also be specified using date strings supported by
the python dateutil library.

    schedule:
      job1:
        function: state.sls
        args:
          - httpd
        kwargs:
          test: True
        when: 5:00pm

This will schedule the command: state.sls httpd test=True at 5:00pm minion
localtime.

    schedule:
      job1:
        function: state.sls
        args:
          - httpd
        kwargs:
          test: True
        when:
            - Monday 5:00pm
            - Tuesday 3:00pm
            - Wednesday 5:00pm
            - Thursday 3:00pm
            - Friday 5:00pm

This will schedule the command: state.sls httpd test=True at 5pm on Monday, Wednesday
and Friday, and 3pm on Tuesday and Thursday.

    schedule:
      job1:
        function: state.sls
        seconds: 3600
        args:
          - httpd
        kwargs:
          test: True
        range:
            start: 8:00am
            end: 5:00pm

This will schedule the command: state.sls httpd test=True every 3600 seconds
(every hour) between the hours of 8am and 5pm.  The range parameter must be a
dictionary with the date strings using the dateutil format.

    ... versionadded:: Helium

    schedule:
      job1:
        function: state.sls
        seconds: 3600
        args:
          - httpd
        kwargs:
          test: True
        range:
            invert: True
            start: 8:00am
            end: 5:00pm

Using the invert option for range, this will schedule the command: state.sls httpd
test=True every 3600 seconds (every hour) until the current time is between the hours
of 8am and 5pm.  The range parameter must be a dictionary with the date strings using
the dateutil format.

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
import errno
import random

try:
    import dateutil.parser as dateutil_parser
    _WHEN_SUPPORTED = True
    _RANGE_SUPPORTED = True
except ImportError:
    _WHEN_SUPPORTED = False
    _RANGE_SUPPORTED = False

# Import Salt libs
import salt.utils
import salt.utils.process
from salt.utils.odict import OrderedDict
from salt.utils.process import os_is_running
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
            self.returners = returners.loader.gen_functions()
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
               'schedule': data['name'],
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
                    if 'schedule' in job:
                        log.debug('schedule.handle_func: Checking job against '
                                  'fun {0}: {1}'.format(ret['fun'], job))
                        if ret['schedule'] == job['schedule'] and os_is_running(job['pid']):
                            jobcount += 1
                            log.debug(
                                'schedule.handle_func: Incrementing jobcount, now '
                                '{0}, maxrunning is {1}'.format(
                                          jobcount, data['maxrunning']))
                            if jobcount >= data['maxrunning']:
                                log.debug(
                                    'schedule.handle_func: The scheduled job {0} '
                                    'was not started, {1} already running'.format(
                                        ret['schedule'], data['maxrunning']))
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

        try:
            if args and kwargs:
                ret['return'] = self.functions[func](*args, **kwargs)

            if args and not kwargs:
                ret['return'] = self.functions[func](*args)

            if kwargs and not args:
                ret['return'] = self.functions[func](**kwargs)

            if not kwargs and not args:
                ret['return'] = self.functions[func]()

            data_returner = data.get('returner', None)
            if data_returner or self.schedule_returner:
                rets = []
                for returner in [data_returner, self.schedule_returner]:
                    if isinstance(returner, str):
                        rets.append(returner)
                    elif isinstance(returner, list):
                        rets.extend(returner)
                # simple de-duplication with order retained
                rets = OrderedDict.fromkeys(rets).keys()
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
        except Exception:
            log.exception("Unhandled exception running {0}".format(ret['fun']))
            # Although catch-all exception handlers are bad, the exception here
            # is to let the exception bubble up to the top of the thread context,
            # where the thread will die silently, which is worse.
        finally:
            try:
                os.unlink(proc_fn)
            except OSError as e:
                if e.errno == errno.EEXIST:
                    # EEXIST is OK because the file is gone and that's what
                    # we wanted
                    pass
                else:
                    log.error("Failed to delete '{0}': {1}".format(proc_fn, e.errno))
                    # Otherwise, failing to delete this file is not something
                    # we can cleanly handle.
                    raise

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
                        func, job
                    )
                )
                continue
            if 'name' not in data:
                data['name'] = job
            # Add up how many seconds between now and then
            when = 0
            seconds = 0

            # clean this up
            if ('seconds' in data or 'hours' in data or 'minutes' in data or 'days' in data) and 'when' in data:
                log.info('Unable to use "seconds", "minutes", "hours", or "days" with "when" option.  Ignoring.')
                continue

            # clean this up
            if 'seconds' in data or 'minutes' in data or 'hours' in data or 'days' in data:
                # Add up how many seconds between now and then
                seconds += int(data.get('seconds', 0))
                seconds += int(data.get('minutes', 0)) * 60
                seconds += int(data.get('hours', 0)) * 3600
                seconds += int(data.get('days', 0)) * 86400
            elif 'when' in data:
                if not _WHEN_SUPPORTED:
                    log.info('Missing python-dateutil.  Ignoring job {0}'.format(job))
                    continue

                if isinstance(data['when'], list):
                    _when = []
                    now = int(time.time())
                    for i in data['when']:
                        try:
                            tmp = int(dateutil_parser.parse(i).strftime('%s'))
                        except ValueError:
                            log.info('Invalid date string {0}.  Ignoring job {1}.'.format(i, job))
                            continue
                        if tmp >= now:
                            _when.append(tmp)
                    _when.sort()
                    if _when:
                        # Grab the first element
                        # which is the next run time
                        when = _when[0]

                        # If we're switching to the next run in a list
                        # ensure the job can run
                        if '_when' in data and data['_when'] != when:
                            data['_when_run'] = True
                            data['_when'] = when
                        seconds = when - int(time.time())

                        # scheduled time is in the past
                        if seconds < 0:
                            continue

                        if not '_when_run' in data:
                            data['_when_run'] = True

                        # Backup the run time
                        if not '_when' in data:
                            data['_when'] = when

                        # A new 'when' ensure _when_run is True
                        if when > data['_when']:
                            data['_when'] = when
                            data['_when_run'] = True

                    else:
                        continue

                else:
                    try:
                        when = int(dateutil_parser.parse(data['when']).strftime('%s'))
                    except ValueError:
                        log.info('Invalid date string.  Ignoring')
                        continue

                    now = int(time.time())
                    seconds = when - now

                    # scheduled time is in the past
                    if seconds < 0:
                        continue

                    if not '_when_run' in data:
                        data['_when_run'] = True

                    # Backup the run time
                    if not '_when' in data:
                        data['_when'] = when

                    # A new 'when' ensure _when_run is True
                    if when > data['_when']:
                        data['_when'] = when
                        data['_when_run'] = True

            else:
                continue
            # Check if the seconds variable is lower than current lowest
            # loop interval needed. If it is lower then overwrite variable
            # external loops using can then check this variable for how often
            # they need to reschedule themselves
            if seconds < self.loop_interval:
                self.loop_interval = seconds
            now = int(time.time())
            run = False
            if job in self.intervals:
                if 'when' in data:
                    if now - when >= seconds:
                        if data['_when_run']:
                            data['_when_run'] = False
                            run = True
                else:
                    if now - self.intervals[job] >= seconds:
                        run = True
            else:
                if 'splay' in data:
                    if 'when' in data:
                        log.debug('Unable to use "splay" with "when" option at this time.  Ignoring.')
                    else:
                        data['_seconds'] = data['seconds']

                if 'when' in data:
                    if now - when >= seconds:
                        if data['_when_run']:
                            data['_when_run'] = False
                            run = True
                else:
                    run = True

            if run:
                if 'range' in data:
                    if not _RANGE_SUPPORTED:
                        log.info('Missing python-dateutil.  Ignoring job {0}'.format(job))
                        continue
                    else:
                        if isinstance(data['range'], dict):
                            try:
                                start = int(dateutil_parser.parse(data['range']['start']).strftime('%s'))
                            except ValueError:
                                log.info('Invalid date string for start.  Ignoring job {0}.'.format(job))
                                continue
                            try:
                                end = int(dateutil_parser.parse(data['range']['end']).strftime('%s'))
                            except ValueError:
                                log.info('Invalid date string for end.  Ignoring job {0}.'.format(job))
                                continue
                            if end > start:
                                if 'invert' in data['range'] and data['range']['invert']:
                                    if now <= start or now >= end:
                                        run = True
                                    else:
                                        run = False
                                else:
                                    if now >= start and now <= end:
                                        run = True
                                    else:
                                        run = False
                            else:
                                log.info('schedule.handle_func: Invalid range, end must be larger than start. Ignoring job {0}.'.format(job))
                                continue
                        else:
                            log.info('schedule.handle_func: Invalid, range must be specified as a dictionary. Ignoring job {0}.'.format(job))
                            continue

            if not run:
                continue
            else:
                if 'splay' in data:
                    if 'when' in data:
                        log.debug('Unable to use "splay" with "when" option at this time.  Ignoring.')
                    else:
                        if isinstance(data['splay'], dict):
                            if data['splay']['end'] > data['splay']['start']:
                                splay = random.randint(data['splay']['start'], data['splay']['end'])
                            else:
                                log.info('schedule.handle_func: Invalid Splay, end must be larger than start. Ignoring splay.')
                                splay = None
                        else:
                            splay = random.randint(0, data['splay'])

                        if splay:
                            log.debug('schedule.handle_func: Adding splay of '
                                      '{0} seconds to next run.'.format(splay))
                            data['seconds'] = data['_seconds'] + splay

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
