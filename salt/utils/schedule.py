# -*- coding: utf-8 -*-
'''
Scheduling routines are located here. To activate the scheduler make the
schedule option available to the master or minion configurations (master config
file or for the minion via config or pillar)

.. code-block:: yaml

    schedule:
      job1:
        function: state.sls
        seconds: 3600
        args:
          - httpd
        kwargs:
          test: True

This will schedule the command: ``state.sls httpd test=True`` every 3600 seconds
(every hour).

.. code-block:: yaml

    schedule:
      job1:
        function: state.sls
        seconds: 3600
        args:
          - httpd
        kwargs:
          test: True
        splay: 15

This will schedule the command: ``state.sls httpd test=True`` every 3600 seconds
(every hour) splaying the time between 0 and 15 seconds.

.. code-block:: yaml

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

This will schedule the command: ``state.sls httpd test=True`` every 3600 seconds
(every hour) splaying the time between 10 and 15 seconds.

.. versionadded:: 2014.7.0

Frequency of jobs can also be specified using date strings supported by
the Python ``dateutil`` library. This requires the Python ``dateutil`` library
to be installed.

.. code-block:: yaml

    schedule:
      job1:
        function: state.sls
        args:
          - httpd
        kwargs:
          test: True
        when: 5:00pm

This will schedule the command: ``state.sls httpd test=True`` at 5:00 PM minion
localtime.

.. code-block:: yaml

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

This will schedule the command: ``state.sls httpd test=True`` at 5:00 PM on
Monday, Wednesday and Friday, and 3:00 PM on Tuesday and Thursday.

.. code-block:: yaml

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

This will schedule the command: ``state.sls httpd test=True`` every 3600 seconds
(every hour) between the hours of 8:00 AM and 5:00 PM. The range parameter must
be a dictionary with the date strings using the ``dateutil`` format.

.. code-block:: yaml

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

Using the invert option for range, this will schedule the command
``state.sls httpd test=True`` every 3600 seconds (every hour) until the current
time is between the hours of 8:00 AM and 5:00 PM. The range parameter must be
a dictionary with the date strings using the ``dateutil`` format.

.. code-block:: yaml

    schedule:
      job1:
        function: pkg.install
        kwargs:
          pkgs: [{'bar': '>1.2.3'}]
          refresh: true
        once: '2016-01-07T14:30:00'

This will schedule the function ``pkg.install`` to be executed once at the
specified time. The schedule entry ``job1`` will not be removed after the job
completes, therefore use ``schedule.delete`` to manually remove it afterwards.

The default date format is ISO 8601 but can be overridden by also specifying the
``once_fmt`` option, like this:

.. code-block:: yaml

    schedule:
      job1:
        function: test.ping
        once: 2015-04-22T20:21:00
        once_fmt: '%Y-%m-%dT%H:%M:%S'

.. versionadded:: 2014.7.0

The scheduler also supports ensuring that there are no more than N copies of
a particular routine running.  Use this for jobs that may be long-running
and could step on each other or pile up in case of infrastructure outage.

The default for ``maxrunning`` is 1.

.. code-block:: yaml

    schedule:
      long_running_job:
        function: big_file_transfer
        jid_include: True
        maxrunning: 1

.. versionadded:: 2014.7.0

.. code-block:: yaml

    schedule:
      job1:
        function: state.sls
        cron: '*/15 * * * *'
        args:
          - httpd
        kwargs:
          test: True

The scheduler also supports scheduling jobs using a cron like format.
This requires the Python ``croniter`` library.

.. versionadded:: 2015.5.0

By default, data about jobs runs from the Salt scheduler is returned to the
master. Setting the ``return_job`` parameter to False will prevent the data
from being sent back to the Salt master.

.. code-block:: yaml

    schedule:
      job1:
        function: scheduled_job_function
        return_job: False

.. versionadded:: 2015.5.0

It can be useful to include specific data to differentiate a job from other
jobs. Using the metadata parameter special values can be associated with
a scheduled job. These values are not used in the execution of the job,
but can be used to search for specific jobs later if combined with the
``return_job`` parameter. The metadata parameter must be specified as a
dictionary, othewise it will be ignored.

.. code-block:: yaml

    schedule:
      job1:
        function: scheduled_job_function
        metadata:
          foo: bar

.. versionadded:: 2015.5.0

By default any job scheduled based on the startup time of the minion will run
the scheduled job when the minion starts up. Sometimes this is not the desired
situation. Using the ``run_on_start`` parameter set to ``False`` will cause the
scheduler to skip this first run and wait until the next scheduled run:

.. code-block:: yaml

    schedule:
      job1:
        function: state.sls
        seconds: 3600
        run_on_start: False
        args:
          - httpd
        kwargs:
          test: True

.. versionadded:: 2015.8.0

.. code-block:: yaml

    schedule:
      job1:
        function: state.sls
        seconds: 15
        until: '12/31/2015 11:59pm'
        args:
          - httpd
        kwargs:
          test: True

Using the until argument, the Salt scheduler allows you to specify
an end time for a scheduled job. If this argument is specified, jobs
will not run once the specified time has passed. Time should be specified
in a format supported by the ``dateutil`` library.
This requires the Python ``dateutil`` library to be installed.

.. versionadded:: 2015.8.0

.. code-block:: yaml

    schedule:
      job1:
        function: state.sls
        seconds: 15
        after: '12/31/2015 11:59pm'
        args:
          - httpd
        kwargs:
          test: True

Using the after argument, the Salt scheduler allows you to specify
an start time for a scheduled job.  If this argument is specified, jobs
will not run until the specified time has passed. Time should be specified
in a format supported by the ``dateutil`` library.
This requires the Python ``dateutil`` library to be installed.

The scheduler also supports ensuring that there are no more than N copies of
a particular routine running.  Use this for jobs that may be long-running
and could step on each other or pile up in case of infrastructure outage.

The default for maxrunning is 1.

.. code-block:: yaml

    schedule:
      long_running_job:
          function: big_file_transfer
          jid_include: True
          maxrunning: 1

By default, data about jobs runs from the Salt scheduler is returned to the
master.  Setting the ``return_job`` parameter to False will prevent the data
from being sent back to the Salt master.

.. versionadded:: 2015.5.0

    schedule:
      job1:
          function: scheduled_job_function
          return_job: False

Setting the ``return_job`` parameter to 'nocache' prevents the salt master
from storing the job in the master cache. Still, an event is fired on the
master event bus in the form 'salt/job/nocache/ret/myminion'.

It can be useful to include specific data to differentiate a job from other
jobs.  Using the metadata parameter special values can be associated with
a scheduled job.  These values are not used in the execution of the job,
but can be used to search for specific jobs later if combined with the
return_job parameter.  The metadata parameter must be specified as a
dictionary, othewise it will be ignored.

.. versionadded:: 2015.5.0

    schedule:
      job1:
          function: scheduled_job_function
          metadata:
            foo: bar

'''

# Import python libs
from __future__ import absolute_import, with_statement
import os
import sys
import time
import signal
import datetime
import itertools
import threading
import logging
import errno
import random
import yaml

# Import Salt libs
import salt.config
import salt.utils
import salt.utils.jid
import salt.utils.process
import salt.utils.args
import salt.utils.minion
import salt.loader
import salt.minion
import salt.payload
import salt.syspaths
import salt.exceptions
import salt.log.setup as log_setup
import salt.defaults.exitcodes
from salt.utils.odict import OrderedDict
from salt.utils.process import os_is_running, default_signals, SignalHandlingMultiprocessingProcess

# Import 3rd-party libs
import salt.ext.six as six

# pylint: disable=import-error
try:
    import dateutil.parser as dateutil_parser
    _WHEN_SUPPORTED = True
    _RANGE_SUPPORTED = True
except ImportError:
    _WHEN_SUPPORTED = False
    _RANGE_SUPPORTED = False

try:
    import croniter
    _CRON_SUPPORTED = True
except ImportError:
    _CRON_SUPPORTED = False
# pylint: enable=import-error

log = logging.getLogger(__name__)


class Schedule(object):
    '''
    Create a Schedule object, pass in the opts and the functions dict to use
    '''
    instance = None

    def __new__(cls, opts, functions, returners=None, intervals=None, cleanup=None):
        '''
        Only create one instance of Schedule
        '''
        if cls.instance is None:
            log.debug('Initializing new Schedule')
            # we need to make a local variable for this, as we are going to store
            # it in a WeakValueDictionary-- which will remove the item if no one
            # references it-- this forces a reference while we return to the caller
            cls.instance = object.__new__(cls)
            cls.instance.__singleton_init__(opts, functions, returners, intervals, cleanup)
        else:
            log.debug('Re-using Schedule')
        return cls.instance

    # has to remain empty for singletons, since __init__ will *always* be called
    def __init__(self, opts, functions, returners=None, intervals=None, cleanup=None):
        pass

    # an init for the singleton instance to call
    def __singleton_init__(self, opts, functions, returners=None, intervals=None, cleanup=None):
        self.opts = opts
        self.functions = functions
        if isinstance(intervals, dict):
            self.intervals = intervals
        else:
            self.intervals = {}
        if hasattr(returners, '__getitem__'):
            self.returners = returners
        else:
            self.returners = returners.loader.gen_functions()
        self.time_offset = self.functions.get('timezone.get_offset', lambda: '0000')()
        self.schedule_returner = self.option('schedule_returner')
        # Keep track of the lowest loop interval needed in this variable
        self.loop_interval = six.MAXSIZE
        clean_proc_dir(opts)
        if cleanup:
            for prefix in cleanup:
                self.delete_job_prefix(prefix)

    def __getnewargs__(self):
        return self.opts, self.functions, self.returners, self.intervals, None

    def option(self, opt):
        '''
        Return the schedule data structure
        '''
        if 'config.merge' in self.functions:
            return self.functions['config.merge'](opt, {}, omit_master=True)
        return self.opts.get(opt, {})

    def persist(self):
        '''
        Persist the modified schedule into <<configdir>>/minion.d/_schedule.conf
        '''
        config_dir = self.opts.get('conf_dir', None)
        if config_dir is None and 'conf_file' in self.opts:
            config_dir = os.path.dirname(self.opts['conf_file'])
        if config_dir is None:
            config_dir = salt.syspaths.CONFIG_DIR

        minion_d_dir = os.path.join(
            config_dir,
            os.path.dirname(self.opts.get('default_include',
                                          salt.config.DEFAULT_MINION_OPTS['default_include'])))
        if salt.utils.is_proxy():
            # each proxy will have a separate _schedule.conf file
            minion_d_dir = os.path.join(minion_d_dir, self.opts['proxyid'])

        if not os.path.isdir(minion_d_dir):
            os.makedirs(minion_d_dir)

        schedule_conf = os.path.join(minion_d_dir, '_schedule.conf')
        log.debug('Persisting schedule')
        try:
            with salt.utils.fopen(schedule_conf, 'wb+') as fp_:
                fp_.write(
                    salt.utils.to_bytes(
                        yaml.dump({'schedule': self.option('schedule')})
                    )
                )
        except (IOError, OSError):
            log.error('Failed to persist the updated schedule',
                      exc_info_on_loglevel=logging.DEBUG)

    def delete_job(self, name, persist=True, where=None):
        '''
        Deletes a job from the scheduler.
        '''
        if where is None or where != 'pillar':
            # ensure job exists, then delete it
            schedule = self.option('schedule')
            if name in schedule:
                del schedule[name]
        else:
            # If job is in pillar, delete it there too
            if 'schedule' in self.opts['pillar']:
                if name in self.opts['pillar']['schedule']:
                    del self.opts['pillar']['schedule'][name]
            schedule = self.opts['pillar']['schedule']
            log.warning('Pillar schedule deleted. Pillar refresh recommended. Run saltutil.refresh_pillar.')

        # Fire the complete event back along with updated list of schedule
        evt = salt.utils.event.get_event('minion', opts=self.opts, listen=False)
        evt.fire_event({'complete': True, 'schedule': schedule},
                       tag='/salt/minion/minion_schedule_delete_complete')

        # remove from self.intervals
        if name in self.intervals:
            del self.intervals[name]

        if persist:
            self.persist()

    def delete_job_prefix(self, name, persist=True, where=None):
        '''
        Deletes a job from the scheduler.
        '''
        if where is None or where != 'pillar':
            # ensure job exists, then delete it
            schedule = self.option('schedule')
            for job in list(schedule.keys()):
                if job.startswith(name):
                    del schedule[job]
        else:
            # If job is in pillar, delete it there too
            if 'schedule' in self.opts['pillar']:
                for job in list(self.opts['pillar']['schedule'].keys()):
                    if job.startswith(name):
                        del self.opts['pillar']['schedule'][job]
            schedule = self.opts['pillar']['schedule']
            log.warning('Pillar schedule deleted. Pillar refresh recommended. Run saltutil.refresh_pillar.')

        # Fire the complete event back along with updated list of schedule
        evt = salt.utils.event.get_event('minion', opts=self.opts, listen=False)
        evt.fire_event({'complete': True, 'schedule': schedule},
                       tag='/salt/minion/minion_schedule_delete_complete')

        # remove from self.intervals
        for job in list(self.intervals.keys()):
            if job.startswith(name):
                del self.intervals[job]

        if persist:
            self.persist()

    def add_job(self, data, persist=True):
        '''
        Adds a new job to the scheduler. The format is the same as required in
        the configuration file. See the docs on how YAML is interpreted into
        python data-structures to make sure, you pass correct dictionaries.
        '''

        # we don't do any checking here besides making sure its a dict.
        # eval() already does for us and raises errors accordingly
        if not isinstance(data, dict):
            raise ValueError('Scheduled jobs have to be of type dict.')
        if not len(data) == 1:
            raise ValueError('You can only schedule one new job at a time.')

        # if enabled is not included in the job,
        # assume job is enabled.
        for job in data.keys():
            if 'enabled' not in data[job]:
                data[job]['enabled'] = True

        new_job = next(six.iterkeys(data))

        schedule = self.option('schedule')
        if new_job in schedule:
            log.info('Updating job settings for scheduled '
                     'job: {0}'.format(new_job))
        else:
            log.info('Added new job {0} to scheduler'.format(new_job))

        schedule.update(data)

        # Fire the complete event back along with updated list of schedule
        evt = salt.utils.event.get_event('minion', opts=self.opts, listen=False)
        evt.fire_event({'complete': True, 'schedule': schedule},
                       tag='/salt/minion/minion_schedule_add_complete')

        if persist:
            self.persist()

    def enable_job(self, name, persist=True, where=None):
        '''
        Enable a job in the scheduler.
        '''
        if where == 'pillar':
            self.opts['pillar']['schedule'][name]['enabled'] = True
            schedule = self.opts['pillar']['schedule']
        else:
            schedule = self.option('schedule')
            schedule[name]['enabled'] = True

        # Fire the complete event back along with updated list of schedule
        evt = salt.utils.event.get_event('minion', opts=self.opts, listen=False)
        evt.fire_event({'complete': True, 'schedule': schedule},
                       tag='/salt/minion/minion_schedule_enabled_job_complete')

        log.info('Enabling job {0} in scheduler'.format(name))

        if persist:
            self.persist()

    def disable_job(self, name, persist=True, where=None):
        '''
        Disable a job in the scheduler.
        '''
        if where == 'pillar':
            self.opts['pillar']['schedule'][name]['enabled'] = False
            schedule = self.opts['pillar']['schedule']
        else:
            schedule = self.option('schedule')
            schedule[name]['enabled'] = False

        # Fire the complete event back along with updated list of schedule
        evt = salt.utils.event.get_event('minion', opts=self.opts, listen=False)
        evt.fire_event({'complete': True, 'schedule': schedule},
                       tag='/salt/minion/minion_schedule_disabled_job_complete')

        log.info('Disabling job {0} in scheduler'.format(name))

        if persist:
            self.persist()

    def modify_job(self, name, schedule, persist=True, where=None):
        '''
        Modify a job in the scheduler.
        '''
        if where == 'pillar':
            if name in self.opts['pillar']['schedule']:
                self.delete_job(name, persist, where=where)
            self.opts['pillar']['schedule'][name] = schedule
        else:
            if name in self.option('schedule'):
                self.delete_job(name, persist, where=where)
            self.option('schedule')[name] = schedule

        if persist:
            self.persist()

    def run_job(self, name):
        '''
        Run a schedule job now
        '''
        schedule = self.option('schedule')
        if 'schedule' in self.opts['pillar']:
            schedule.update(self.opts['pillar']['schedule'])
        data = schedule[name]

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
                'Invalid function: {0} in scheduled job {1}.'.format(
                    func, name
                )
            )

        if 'name' not in data:
            data['name'] = name
        log.info(
            'Running Job: {0}.'.format(name)
        )

        multiprocessing_enabled = self.opts.get('multiprocessing', True)
        if multiprocessing_enabled:
            thread_cls = SignalHandlingMultiprocessingProcess
        else:
            thread_cls = threading.Thread

        if multiprocessing_enabled:
            with default_signals(signal.SIGINT, signal.SIGTERM):
                proc = thread_cls(target=self.handle_func, args=(multiprocessing_enabled, func, data))
                # Reset current signals before starting the process in
                # order not to inherit the current signal handlers
                proc.start()
            proc.join()
        else:
            proc = thread_cls(target=self.handle_func, args=(multiprocessing_enabled, func, data))
            proc.start()

    def enable_schedule(self):
        '''
        Enable the scheduler.
        '''
        schedule = self.option('schedule')
        schedule['enabled'] = True

        # Fire the complete event back along with updated list of schedule
        evt = salt.utils.event.get_event('minion', opts=self.opts, listen=False)
        evt.fire_event({'complete': True, 'schedule': schedule},
                       tag='/salt/minion/minion_schedule_enabled_complete')

    def disable_schedule(self):
        '''
        Disable the scheduler.
        '''
        schedule = self.option('schedule')
        schedule['enabled'] = False

        # Fire the complete event back along with updated list of schedule
        evt = salt.utils.event.get_event('minion', opts=self.opts, listen=False)
        evt.fire_event({'complete': True, 'schedule': schedule},
                       tag='/salt/minion/minion_schedule_disabled_complete')

    def reload(self, schedule):
        '''
        Reload the schedule from saved schedule file.
        '''
        # Remove all jobs from self.intervals
        self.intervals = {}

        if 'schedule' in schedule:
            schedule = schedule['schedule']
        self.opts.setdefault('schedule', {}).update(schedule)

    def list(self, where):
        '''
        List the current schedule items
        '''
        schedule = {}
        if where == 'pillar':
            if 'schedule' in self.opts['pillar']:
                schedule.update(self.opts['pillar']['schedule'])
        elif where == 'opts':
            schedule.update(self.option('schedule'))
        else:
            schedule.update(self.option('schedule'))
            if 'schedule' in self.opts['pillar']:
                schedule.update(self.opts['pillar']['schedule'])

        # Fire the complete event back along with the list of schedule
        evt = salt.utils.event.get_event('minion', opts=self.opts, listen=False)
        evt.fire_event({'complete': True, 'schedule': schedule},
                       tag='/salt/minion/minion_schedule_list_complete')

    def save_schedule(self):
        '''
        Save the current schedule
        '''
        self.persist()

        # Fire the complete event back along with the list of schedule
        evt = salt.utils.event.get_event('minion', opts=self.opts, listen=False)
        evt.fire_event({'complete': True},
                       tag='/salt/minion/minion_schedule_saved')

    def handle_func(self, multiprocessing_enabled, func, data):
        '''
        Execute this method in a multiprocess or thread
        '''
        if salt.utils.is_windows() or self.opts.get('transport') == 'zeromq':
            # Since function references can't be pickled and pickling
            # is required when spawning new processes on Windows, regenerate
            # the functions and returners.
            # This also needed for ZeroMQ transport to reset all functions
            # context data that could keep paretns connections. ZeroMQ will
            # hang on polling parents connections from the child process.
            self.functions = salt.loader.minion_mods(self.opts)
            self.returners = salt.loader.returners(self.opts, self.functions)
        ret = {'id': self.opts.get('id', 'master'),
               'fun': func,
               'fun_args': [],
               'schedule': data['name'],
               'jid': salt.utils.jid.gen_jid()}

        if 'metadata' in data:
            if isinstance(data['metadata'], dict):
                ret['metadata'] = data['metadata']
                ret['metadata']['_TOS'] = self.time_offset
                ret['metadata']['_TS'] = time.ctime()
                ret['metadata']['_TT'] = time.strftime('%Y %B %d %a %H %m', time.gmtime())
            else:
                log.warning('schedule: The metadata parameter must be '
                            'specified as a dictionary.  Ignoring.')

        salt.utils.appendproctitle('{0} {1}'.format(self.__class__.__name__, ret['jid']))

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
            for job in salt.utils.minion.running(self.opts):
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

        if multiprocessing_enabled and not salt.utils.is_windows():
            # Reconfigure multiprocessing logging after daemonizing
            log_setup.setup_multiprocessing_logging()

        # Don't *BEFORE* to go into try to don't let it triple execute the finally section.
        salt.utils.daemonize_if(self.opts)

        # TODO: Make it readable! Splt to funcs, remove nested try-except-finally sections.
        try:
            ret['pid'] = os.getpid()

            if 'jid_include' not in data or data['jid_include']:
                log.debug('schedule.handle_func: adding this job to the jobcache '
                          'with data {0}'.format(ret))
                # write this to /var/cache/salt/minion/proc
                with salt.utils.fopen(proc_fn, 'w+b') as fp_:
                    fp_.write(salt.payload.Serial(self.opts).dumps(ret))

            args = tuple()
            if 'args' in data:
                args = data['args']
                ret['fun_args'].extend(data['args'])

            kwargs = {}
            if 'kwargs' in data:
                kwargs = data['kwargs']
                ret['fun_args'].append(data['kwargs'])

            if func not in self.functions:
                ret['return'] = self.functions.missing_fun_string(func)
                salt.utils.error.raise_error(
                    message=self.functions.missing_fun_string(func))

            # if the func support **kwargs, lets pack in the pub data we have
            # TODO: pack the *same* pub data as a minion?
            argspec = salt.utils.args.get_function_argspec(self.functions[func])
            if argspec.keywords:
                # this function accepts **kwargs, pack in the publish data
                for key, val in six.iteritems(ret):
                    kwargs['__pub_{0}'.format(key)] = val

            ret['return'] = self.functions[func](*args, **kwargs)

            data_returner = data.get('returner', None)
            if data_returner or self.schedule_returner:
                if 'return_config' in data:
                    ret['ret_config'] = data['return_config']
                if 'return_kwargs' in data:
                    ret['ret_kwargs'] = data['return_kwargs']
                rets = []
                for returner in [data_returner, self.schedule_returner]:
                    if isinstance(returner, str):
                        rets.append(returner)
                    elif isinstance(returner, list):
                        rets.extend(returner)
                # simple de-duplication with order retained
                for returner in OrderedDict.fromkeys(rets):
                    ret_str = '{0}.returner'.format(returner)
                    if ret_str in self.returners:
                        ret['success'] = True
                        self.returners[ret_str](ret)
                    else:
                        log.info(
                            'Job {0} using invalid returner: {1}. Ignoring.'.format(
                                func, returner
                            )
                        )

            # runners do not provide retcode
            if 'retcode' in self.functions.pack['__context__']:
                ret['retcode'] = self.functions.pack['__context__']['retcode']

            ret['success'] = True
        except Exception:
            log.exception("Unhandled exception running {0}".format(ret['fun']))
            # Although catch-all exception handlers are bad, the exception here
            # is to let the exception bubble up to the top of the thread context,
            # where the thread will die silently, which is worse.
            if 'return' not in ret:
                ret['return'] = "Unhandled exception running {0}".format(ret['fun'])
            ret['success'] = False
            ret['retcode'] = 254
        finally:
            try:
                # Only attempt to return data to the master
                # if the scheduled job is running on a minion.
                if '__role' in self.opts and self.opts['__role'] == 'minion':
                    if 'return_job' in data and not data['return_job']:
                        pass
                    else:
                        # Send back to master so the job is included in the job list
                        mret = ret.copy()
                        mret['jid'] = 'req'
                        if data.get('return_job') == 'nocache':
                            # overwrite 'req' to signal to master that this job shouldn't be stored
                            mret['jid'] = 'nocache'
                        event = salt.utils.event.get_event('minion', opts=self.opts, listen=False)
                        load = {'cmd': '_return', 'id': self.opts['id']}
                        for key, value in six.iteritems(mret):
                            load[key] = value
                        event.fire_event(load, '__schedule_return')

                log.debug('schedule.handle_func: Removing {0}'.format(proc_fn))
                os.unlink(proc_fn)
            except OSError as exc:
                if exc.errno == errno.EEXIST or exc.errno == errno.ENOENT:
                    # EEXIST and ENOENT are OK because the file is gone and that's what
                    # we wanted
                    pass
                else:
                    log.error("Failed to delete '{0}': {1}".format(proc_fn, exc.errno))
                    # Otherwise, failing to delete this file is not something
                    # we can cleanly handle.
                    raise
            finally:
                if multiprocessing_enabled:
                    # Let's make sure we exit the process!
                    sys.exit(salt.defaults.exitcodes.EX_GENERIC)

    def eval(self):
        '''
        Evaluate and execute the schedule
        '''
        schedule = self.option('schedule')
        if not isinstance(schedule, dict):
            raise ValueError('Schedule must be of type dict.')
        if 'enabled' in schedule and not schedule['enabled']:
            return
        for job, data in six.iteritems(schedule):
            if job == 'enabled' or not data:
                continue
            if not isinstance(data, dict):
                log.error('Scheduled job "{0}" should have a dict value, not {1}'.format(job, type(data)))
                continue
            # Job is disabled, continue
            if 'enabled' in data and not data['enabled']:
                continue
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
                    'Invalid function: {0} in scheduled job {1}.'.format(
                        func, job
                    )
                )
            if 'name' not in data:
                data['name'] = job
            # Add up how many seconds between now and then
            when = 0
            seconds = 0
            cron = 0
            now = int(time.time())

            if 'until' in data:
                if not _WHEN_SUPPORTED:
                    log.error('Missing python-dateutil. '
                              'Ignoring until.')
                else:
                    until__ = dateutil_parser.parse(data['until'])
                    until = int(time.mktime(until__.timetuple()))

                    if until <= now:
                        log.debug('Until time has passed '
                                  'skipping job: {0}.'.format(data['name']))
                        continue

            if 'after' in data:
                if not _WHEN_SUPPORTED:
                    log.error('Missing python-dateutil. '
                              'Ignoring after.')
                else:
                    after__ = dateutil_parser.parse(data['after'])
                    after = int(time.mktime(after__.timetuple()))

                    if after >= now:
                        log.debug('After time has not passed '
                                  'skipping job: {0}.'.format(data['name']))
                        continue

            # Used for quick lookups when detecting invalid option combinations.
            schedule_keys = set(data.keys())

            time_elements = ('seconds', 'minutes', 'hours', 'days')
            scheduling_elements = ('when', 'cron', 'once')

            invalid_sched_combos = [set(i)
                    for i in itertools.combinations(scheduling_elements, 2)]

            if any(i <= schedule_keys for i in invalid_sched_combos):
                log.error('Unable to use "{0}" options together. Ignoring.'
                          .format('", "'.join(scheduling_elements)))
                continue

            invalid_time_combos = []
            for item in scheduling_elements:
                all_items = itertools.chain([item], time_elements)
                invalid_time_combos.append(
                    set(itertools.combinations(all_items, 2)))

            if any(set(x) <= schedule_keys for x in invalid_time_combos):
                log.error('Unable to use "{0}" with "{1}" options. Ignoring'
                          .format('", "'.join(time_elements),
                                  '", "'.join(scheduling_elements)))
                continue

            if True in [True for item in time_elements if item in data]:
                # Add up how many seconds between now and then
                seconds += int(data.get('seconds', 0))
                seconds += int(data.get('minutes', 0)) * 60
                seconds += int(data.get('hours', 0)) * 3600
                seconds += int(data.get('days', 0)) * 86400
            elif 'once' in data:
                once_fmt = data.get('once_fmt', '%Y-%m-%dT%H:%M:%S')

                try:
                    once = datetime.datetime.strptime(data['once'], once_fmt)
                    once = int(time.mktime(once.timetuple()))
                except (TypeError, ValueError):
                    log.error('Date string could not be parsed: %s, %s',
                            data['once'], once_fmt)
                    continue

                if now != once:
                    continue
                else:
                    seconds = 1

            elif 'when' in data:
                if not _WHEN_SUPPORTED:
                    log.error('Missing python-dateutil. '
                              'Ignoring job {0}.'.format(job))
                    continue

                if isinstance(data['when'], list):
                    _when = []
                    for i in data['when']:
                        if ('pillar' in self.opts and 'whens' in self.opts['pillar'] and
                                i in self.opts['pillar']['whens']):
                            if not isinstance(self.opts['pillar']['whens'],
                                              dict):
                                log.error('Pillar item "whens" must be dict. '
                                          'Ignoring')
                                continue
                            __when = self.opts['pillar']['whens'][i]
                            try:
                                when__ = dateutil_parser.parse(__when)
                            except ValueError:
                                log.error('Invalid date string. Ignoring')
                                continue
                        elif ('whens' in self.opts['grains'] and
                              i in self.opts['grains']['whens']):
                            if not isinstance(self.opts['grains']['whens'],
                                              dict):
                                log.error('Grain "whens" must be dict.'
                                          'Ignoring')
                                continue
                            __when = self.opts['grains']['whens'][i]
                            try:
                                when__ = dateutil_parser.parse(__when)
                            except ValueError:
                                log.error('Invalid date string. Ignoring')
                                continue
                        else:
                            try:
                                when__ = dateutil_parser.parse(i)
                            except ValueError:
                                log.error('Invalid date string {0}. '
                                          'Ignoring job {1}.'.format(i, job))
                                continue
                        when = int(time.mktime(when__.timetuple()))
                        if when >= now:
                            _when.append(when)
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
                        seconds = when - now

                        # scheduled time is in the past and the run was not triggered before
                        if seconds < 0 and not data.get('_when_run', False):
                            continue

                        if '_when_run' not in data:
                            data['_when_run'] = True

                        # Backup the run time
                        if '_when' not in data:
                            data['_when'] = when

                        # A new 'when' ensure _when_run is True
                        if when > data['_when']:
                            data['_when'] = when
                            data['_when_run'] = True

                    else:
                        continue

                else:
                    if ('pillar' in self.opts and 'whens' in self.opts['pillar'] and
                            data['when'] in self.opts['pillar']['whens']):
                        if not isinstance(self.opts['pillar']['whens'], dict):
                            log.error('Pillar item "whens" must be dict.'
                                      'Ignoring')
                            continue
                        _when = self.opts['pillar']['whens'][data['when']]
                        try:
                            when__ = dateutil_parser.parse(_when)
                        except ValueError:
                            log.error('Invalid date string. Ignoring')
                            continue
                    elif ('whens' in self.opts['grains'] and
                          data['when'] in self.opts['grains']['whens']):
                        if not isinstance(self.opts['grains']['whens'], dict):
                            log.error('Grain "whens" must be dict. Ignoring')
                            continue
                        _when = self.opts['grains']['whens'][data['when']]
                        try:
                            when__ = dateutil_parser.parse(_when)
                        except ValueError:
                            log.error('Invalid date string. Ignoring')
                            continue
                    else:
                        try:
                            when__ = dateutil_parser.parse(data['when'])
                        except ValueError:
                            log.error('Invalid date string. Ignoring')
                            continue
                    when = int(time.mktime(when__.timetuple()))
                    now = int(time.time())
                    seconds = when - now

                    # scheduled time is in the past and the run was not triggered before
                    if seconds < 0 and not data.get('_when_run', False):
                        continue

                    if '_when_run' not in data:
                        data['_when_run'] = True

                    # Backup the run time
                    if '_when' not in data:
                        data['_when'] = when

                    # A new 'when' ensure _when_run is True
                    if when > data['_when']:
                        data['_when'] = when
                        data['_when_run'] = True

            elif 'cron' in data:
                if not _CRON_SUPPORTED:
                    log.error('Missing python-croniter. Ignoring job {0}'.format(job))
                    continue

                now = int(time.mktime(datetime.datetime.now().timetuple()))
                try:
                    cron = int(croniter.croniter(data['cron'], now).get_next())
                except (ValueError, KeyError):
                    log.error('Invalid cron string. Ignoring')
                    continue
                seconds = cron - now
            else:
                continue

            # Check if the seconds variable is lower than current lowest
            # loop interval needed. If it is lower than overwrite variable
            # external loops using can then check this variable for how often
            # they need to reschedule themselves
            # Not used with 'when' parameter, causes run away jobs and CPU
            # spikes.
            if 'when' not in data:
                if seconds < self.loop_interval:
                    self.loop_interval = seconds
            run = False

            if 'splay' in data:
                if 'when' in data:
                    log.error('Unable to use "splay" with "when" option at this time. Ignoring.')
                elif 'cron' in data:
                    log.error('Unable to use "splay" with "cron" option at this time. Ignoring.')
                else:
                    if '_seconds' not in data:
                        log.debug('The _seconds parameter is missing, '
                                  'most likely the first run or the schedule '
                                  'has been refreshed refresh.')
                        if 'seconds' in data:
                            data['_seconds'] = data['seconds']
                        else:
                            data['_seconds'] = 0

            if 'when' in data:
                # scheduled time is now or in the past, and the run was triggered before
                if seconds <= 0 and data['_when_run']:
                    data['_when_run'] = False
                    run = True
            elif 'cron' in data:
                if seconds == 1:
                    run = True
            else:
                if job in self.intervals:
                    if now - self.intervals[job] >= seconds:
                        run = True
                else:
                    # If run_on_start is True, the job will run when the Salt
                    # minion start.  If the value is False will run at the next
                    # scheduled run.  Default is True.
                    if 'run_on_start' in data:
                        if data['run_on_start']:
                            run = True
                        else:
                            self.intervals[job] = int(time.time())
                    else:
                        run = True

            if run:
                if 'range' in data:
                    if not _RANGE_SUPPORTED:
                        log.error('Missing python-dateutil. Ignoring job {0}'.format(job))
                        continue
                    else:
                        if isinstance(data['range'], dict):
                            try:
                                start = int(time.mktime(dateutil_parser.parse(data['range']['start']).timetuple()))
                            except ValueError:
                                log.error('Invalid date string for start. Ignoring job {0}.'.format(job))
                                continue
                            try:
                                end = int(time.mktime(dateutil_parser.parse(data['range']['end']).timetuple()))
                            except ValueError:
                                log.error('Invalid date string for end. Ignoring job {0}.'.format(job))
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
                                log.error('schedule.handle_func: Invalid range, end must be larger than start. \
                                         Ignoring job {0}.'.format(job))
                                continue
                        else:
                            log.error('schedule.handle_func: Invalid, range must be specified as a dictionary. \
                                     Ignoring job {0}.'.format(job))
                            continue

            if not run:
                continue
            else:
                if 'splay' in data:
                    if 'when' in data:
                        log.error('Unable to use "splay" with "when" option at this time. Ignoring.')
                    else:
                        if isinstance(data['splay'], dict):
                            if data['splay']['end'] >= data['splay']['start']:
                                splay = random.randint(data['splay']['start'], data['splay']['end'])
                            else:
                                log.error('schedule.handle_func: Invalid Splay, end must be larger than start. \
                                         Ignoring splay.')
                                splay = None
                        else:
                            splay = random.randint(0, data['splay'])

                        if splay:
                            log.debug('schedule.handle_func: Adding splay of '
                                      '{0} seconds to next run.'.format(splay))
                            if 'seconds' in data:
                                data['seconds'] = data['_seconds'] + splay
                            else:
                                data['seconds'] = 0 + splay

                log.info('Running scheduled job: {0}'.format(job))

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

            multiprocessing_enabled = self.opts.get('multiprocessing', True)

            if salt.utils.is_windows():
                # Temporarily stash our function references.
                # You can't pickle function references, and pickling is
                # required when spawning new processes on Windows.
                functions = self.functions
                self.functions = {}
                returners = self.returners
                self.returners = {}
            try:
                if multiprocessing_enabled:
                    thread_cls = SignalHandlingMultiprocessingProcess
                else:
                    thread_cls = threading.Thread
                proc = thread_cls(target=self.handle_func, args=(multiprocessing_enabled, func, data))

                if multiprocessing_enabled:
                    with default_signals(signal.SIGINT, signal.SIGTERM):
                        # Reset current signals before starting the process in
                        # order not to inherit the current signal handlers
                        proc.start()
                else:
                    proc.start()

                if multiprocessing_enabled:
                    proc.join()
            finally:
                self.intervals[job] = now
            if salt.utils.is_windows():
                # Restore our function references.
                self.functions = functions
                self.returners = returners


def clean_proc_dir(opts):

    '''
    Loop through jid files in the minion proc directory (default /var/cache/salt/minion/proc)
    and remove any that refer to processes that no longer exist
    '''

    for basefilename in os.listdir(salt.minion.get_proc_dir(opts['cachedir'])):
        fn_ = os.path.join(salt.minion.get_proc_dir(opts['cachedir']), basefilename)
        with salt.utils.fopen(fn_, 'rb') as fp_:
            job = None
            try:
                job = salt.payload.Serial(opts).load(fp_)
            except Exception:  # It's corrupted
                # Windows cannot delete an open file
                if salt.utils.is_windows():
                    fp_.close()
                try:
                    os.unlink(fn_)
                    continue
                except OSError:
                    continue
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
                        os.unlink(fn_)
                    except OSError:
                        pass
