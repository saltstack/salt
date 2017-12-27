# -*- coding: utf-8 -*-

# See doc/topics/jobs/index.rst
'''
Scheduling routines are located here. To activate the scheduler make the
``schedule`` option available to the master or minion configurations (master
config file or for the minion via config or pillar).

Detailed tutorial about scheduling jobs can be found :ref:`here
<scheduling-jobs>`.
'''

# Import python libs
from __future__ import absolute_import, with_statement
import os
import sys
import time
import copy
import signal
import datetime
import itertools
import threading
import logging
import errno
import random
import weakref

# Import Salt libs
import salt.config
import salt.utils.args
import salt.utils.error
import salt.utils.event
import salt.utils.files
import salt.utils.jid
import salt.utils.minion
import salt.utils.platform
import salt.utils.process
import salt.utils.stringutils
import salt.utils.user
import salt.utils.yaml
import salt.loader
import salt.minion
import salt.payload
import salt.syspaths
import salt.exceptions
import salt.log.setup as log_setup
import salt.defaults.exitcodes
from salt.utils.odict import OrderedDict

# Import 3rd-party libs
from salt.ext import six

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

    def __new__(cls, opts, functions, returners=None, intervals=None, cleanup=None, proxy=None, standalone=False):
        '''
        Only create one instance of Schedule
        '''
        if cls.instance is None:
            log.debug('Initializing new Schedule')
            # we need to make a local variable for this, as we are going to store
            # it in a WeakValueDictionary-- which will remove the item if no one
            # references it-- this forces a reference while we return to the caller
            cls.instance = object.__new__(cls)
            cls.instance.__singleton_init__(opts, functions, returners, intervals, cleanup, proxy, standalone)
        else:
            log.debug('Re-using Schedule')
        return cls.instance

    # has to remain empty for singletons, since __init__ will *always* be called
    def __init__(self, opts, functions, returners=None, intervals=None, cleanup=None, proxy=None, standalone=False):
        pass

    # an init for the singleton instance to call
    def __singleton_init__(self, opts, functions, returners=None, intervals=None, cleanup=None, proxy=None, standalone=False):
        self.opts = opts
        self.proxy = proxy
        self.functions = functions
        self.standalone = standalone
        self.skip_function = None
        self.skip_during_range = None
        if isinstance(intervals, dict):
            self.intervals = intervals
        else:
            self.intervals = {}
        if not self.standalone:
            if hasattr(returners, '__getitem__'):
                self.returners = returners
            else:
                self.returners = returners.loader.gen_functions()
        self.time_offset = self.functions.get('timezone.get_offset', lambda: '0000')()
        self.schedule_returner = self.option('schedule_returner')
        # Keep track of the lowest loop interval needed in this variable
        self.loop_interval = six.MAXSIZE
        if not self.standalone:
            clean_proc_dir(opts)
        if cleanup:
            for prefix in cleanup:
                self.delete_job_prefix(prefix)

    def __getnewargs__(self):
        return self.opts, self.functions, self.returners, self.intervals, None

    def option(self, opt):
        '''
        Return options merged from config and pillar
        '''
        if 'config.merge' in self.functions:
            return self.functions['config.merge'](opt, {}, omit_master=True)
        return self.opts.get(opt, {})

    def _get_schedule(self,
                      include_opts=True,
                      include_pillar=True):
        '''
        Return the schedule data structure
        '''
        schedule = {}
        if include_pillar:
            pillar_schedule = self.opts.get('pillar', {}).get('schedule', {})
            if not isinstance(pillar_schedule, dict):
                raise ValueError('Schedule must be of type dict.')
            schedule.update(pillar_schedule)
        if include_opts:
            opts_schedule = self.opts.get('schedule', {})
            if not isinstance(opts_schedule, dict):
                raise ValueError('Schedule must be of type dict.')
            schedule.update(opts_schedule)
        return schedule

    def persist(self):
        '''
        Persist the modified schedule into <<configdir>>/<<default_include>>/_schedule.conf
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

        if not os.path.isdir(minion_d_dir):
            os.makedirs(minion_d_dir)

        schedule_conf = os.path.join(minion_d_dir, '_schedule.conf')
        log.debug('Persisting schedule')
        try:
            with salt.utils.files.fopen(schedule_conf, 'wb+') as fp_:
                fp_.write(
                    salt.utils.stringutils.to_bytes(
                        salt.utils.yaml.safe_dump(
                            {'schedule': self._get_schedule(include_pillar=False)}
                        )
                    )
                )
        except (IOError, OSError):
            log.error('Failed to persist the updated schedule',
                      exc_info_on_loglevel=logging.DEBUG)

    def delete_job(self, name, persist=True):
        '''
        Deletes a job from the scheduler. Ignore jobs from pillar
        '''
        # ensure job exists, then delete it
        if name in self.opts['schedule']:
            del self.opts['schedule'][name]
        elif name in self._get_schedule(include_opts=False):
            log.warning('Cannot delete job {0}, '
                        'it`s in the pillar!'.format(name))

        # Fire the complete event back along with updated list of schedule
        evt = salt.utils.event.get_event('minion', opts=self.opts, listen=False)
        evt.fire_event({'complete': True, 'schedule': self._get_schedule()},
                       tag='/salt/minion/minion_schedule_delete_complete')

        # remove from self.intervals
        if name in self.intervals:
            del self.intervals[name]

        if persist:
            self.persist()

    def delete_job_prefix(self, name, persist=True):
        '''
        Deletes a job from the scheduler. Ignores jobs from pillar
        '''
        # ensure job exists, then delete it
        for job in list(self.opts['schedule'].keys()):
            if job.startswith(name):
                del self.opts['schedule'][job]
        for job in self._get_schedule(include_opts=False):
            if job.startswith(name):
                log.warning('Cannot delete job {0}, '
                            'it`s in the pillar!'.format(job))

        # Fire the complete event back along with updated list of schedule
        evt = salt.utils.event.get_event('minion', opts=self.opts, listen=False)
        evt.fire_event({'complete': True, 'schedule': self._get_schedule()},
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
        for job in data:
            if 'enabled' not in data[job]:
                data[job]['enabled'] = True

        new_job = next(six.iterkeys(data))

        if new_job in self._get_schedule(include_opts=False):
            log.warning('Cannot update job {0}, '
                        'it`s in the pillar!'.format(new_job))

        elif new_job in self.opts['schedule']:
            log.info('Updating job settings for scheduled '
                     'job: {0}'.format(new_job))
            self.opts['schedule'].update(data)

        else:
            log.info('Added new job {0} to scheduler'.format(new_job))
            self.opts['schedule'].update(data)

        # Fire the complete event back along with updated list of schedule
        evt = salt.utils.event.get_event('minion', opts=self.opts, listen=False)
        evt.fire_event({'complete': True, 'schedule': self._get_schedule()},
                       tag='/salt/minion/minion_schedule_add_complete')

        if persist:
            self.persist()

    def enable_job(self, name, persist=True):
        '''
        Enable a job in the scheduler. Ignores jobs from pillar
        '''
        # ensure job exists, then enable it
        if name in self.opts['schedule']:
            self.opts['schedule'][name]['enabled'] = True
            log.info('Enabling job {0} in scheduler'.format(name))
        elif name in self._get_schedule(include_opts=False):
            log.warning('Cannot modify job {0}, '
                        'it`s in the pillar!'.format(name))

        # Fire the complete event back along with updated list of schedule
        evt = salt.utils.event.get_event('minion', opts=self.opts, listen=False)
        evt.fire_event({'complete': True, 'schedule': self._get_schedule()},
                       tag='/salt/minion/minion_schedule_enabled_job_complete')

        if persist:
            self.persist()

    def disable_job(self, name, persist=True):
        '''
        Disable a job in the scheduler. Ignores jobs from pillar
        '''
        # ensure job exists, then disable it
        if name in self.opts['schedule']:
            self.opts['schedule'][name]['enabled'] = False
            log.info('Disabling job {0} in scheduler'.format(name))
        elif name in self._get_schedule(include_opts=False):
            log.warning('Cannot modify job {0}, '
                        'it`s in the pillar!'.format(name))

        # Fire the complete event back along with updated list of schedule
        evt = salt.utils.event.get_event('minion', opts=self.opts, listen=False)
        evt.fire_event({'complete': True, 'schedule': self._get_schedule()},
                       tag='/salt/minion/minion_schedule_disabled_job_complete')

        if persist:
            self.persist()

    def modify_job(self, name, schedule, persist=True):
        '''
        Modify a job in the scheduler. Ignores jobs from pillar
        '''
        # ensure job exists, then replace it
        if name in self.opts['schedule']:
            self.delete_job(name, persist)
        elif name in self._get_schedule(include_opts=False):
            log.warning('Cannot modify job {0}, '
                        'it`s in the pillar!'.format(name))
            return

        self.opts['schedule'][name] = schedule

        if persist:
            self.persist()

    def run_job(self, name):
        '''
        Run a schedule job now
        '''
        data = self._get_schedule().get(name, {})

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
            thread_cls = salt.utils.process.SignalHandlingMultiprocessingProcess
        else:
            thread_cls = threading.Thread

        if multiprocessing_enabled:
            with salt.utils.process.default_signals(signal.SIGINT, signal.SIGTERM):
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
        self.opts['schedule']['enabled'] = True

        # Fire the complete event back along with updated list of schedule
        evt = salt.utils.event.get_event('minion', opts=self.opts, listen=False)
        evt.fire_event({'complete': True, 'schedule': self._get_schedule()},
                       tag='/salt/minion/minion_schedule_enabled_complete')

    def disable_schedule(self):
        '''
        Disable the scheduler.
        '''
        self.opts['schedule']['enabled'] = False

        # Fire the complete event back along with updated list of schedule
        evt = salt.utils.event.get_event('minion', opts=self.opts, listen=False)
        evt.fire_event({'complete': True, 'schedule': self._get_schedule()},
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
        if where == 'pillar':
            schedule = self._get_schedule(include_opts=False)
        elif where == 'opts':
            schedule = self._get_schedule(include_pillar=False)
        else:
            schedule = self._get_schedule()

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

    def postpone_job(self, name, data):
        '''
        Postpone a job in the scheduler.
        Ignores jobs from pillar
        '''
        time = data['time']
        new_time = data['new_time']

        # ensure job exists, then disable it
        if name in self.opts['schedule']:
            if 'skip_explicit' not in self.opts['schedule'][name]:
                self.opts['schedule'][name]['skip_explicit'] = []
            self.opts['schedule'][name]['skip_explicit'].append(time)

            if 'run_explicit' not in self.opts['schedule'][name]:
                self.opts['schedule'][name]['run_explicit'] = []
            self.opts['schedule'][name]['run_explicit'].append(new_time)

        elif name in self._get_schedule(include_opts=False):
            log.warning('Cannot modify job {0}, '
                        'it`s in the pillar!'.format(name))

        # Fire the complete event back along with updated list of schedule
        evt = salt.utils.event.get_event('minion', opts=self.opts, listen=False)
        evt.fire_event({'complete': True, 'schedule': self._get_schedule()},
                       tag='/salt/minion/minion_schedule_postpone_job_complete')

    def skip_job(self, name, data):
        '''
        Skip a job at a specific time in the scheduler.
        Ignores jobs from pillar
        '''
        time = data['time']

        # ensure job exists, then disable it
        if name in self.opts['schedule']:
            if 'skip_explicit' not in self.opts['schedule'][name]:
                self.opts['schedule'][name]['skip_explicit'] = []
            self.opts['schedule'][name]['skip_explicit'].append(time)

        elif name in self._get_schedule(include_opts=False):
            log.warning('Cannot modify job {0}, '
                        'it`s in the pillar!'.format(name))

        # Fire the complete event back along with updated list of schedule
        evt = salt.utils.event.get_event('minion', opts=self.opts, listen=False)
        evt.fire_event({'complete': True, 'schedule': self._get_schedule()},
                       tag='/salt/minion/minion_schedule_skip_job_complete')

    def get_next_fire_time(self, name):
        '''
        Return the  next fire time for the specified job
        '''

        schedule = self._get_schedule()
        _next_fire_time = None
        if schedule:
            _next_fire_time = schedule.get(name, {}).get('_next_fire_time', None)

        # Fire the complete event back along with updated list of schedule
        evt = salt.utils.event.get_event('minion', opts=self.opts, listen=False)
        evt.fire_event({'complete': True, 'next_fire_time': _next_fire_time},
                       tag='/salt/minion/minion_schedule_next_fire_time_complete')

    def job_status(self, name):
        '''
        Return the specified schedule item
        '''

        schedule = self._get_schedule()
        return schedule.get(name, {})

    def handle_func(self, multiprocessing_enabled, func, data):
        '''
        Execute this method in a multiprocess or thread
        '''
        if salt.utils.platform.is_windows() \
                or self.opts.get('transport') == 'zeromq':
            # Since function references can't be pickled and pickling
            # is required when spawning new processes on Windows, regenerate
            # the functions and returners.
            # This also needed for ZeroMQ transport to reset all functions
            # context data that could keep paretns connections. ZeroMQ will
            # hang on polling parents connections from the child process.
            if self.opts['__role'] == 'master':
                self.functions = salt.loader.runner(self.opts)
            else:
                self.functions = salt.loader.minion_mods(self.opts, proxy=self.proxy)
            self.returners = salt.loader.returners(self.opts, self.functions, proxy=self.proxy)
        ret = {'id': self.opts.get('id', 'master'),
               'fun': func,
               'fun_args': [],
               'schedule': data['name'],
               'jid': salt.utils.jid.gen_jid(self.opts)}

        if 'metadata' in data:
            if isinstance(data['metadata'], dict):
                ret['metadata'] = data['metadata']
                ret['metadata']['_TOS'] = self.time_offset
                ret['metadata']['_TS'] = time.ctime()
                ret['metadata']['_TT'] = time.strftime('%Y %B %d %a %H %m', time.gmtime())
            else:
                log.warning('schedule: The metadata parameter must be '
                            'specified as a dictionary.  Ignoring.')

        salt.utils.process.appendproctitle('{0} {1}'.format(self.__class__.__name__, ret['jid']))

        if not self.standalone:
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
                        if ret['schedule'] == job['schedule'] \
                                and salt.utils.process.os_is_running(job['pid']):
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

        if multiprocessing_enabled and not salt.utils.platform.is_windows():
            # Reconfigure multiprocessing logging after daemonizing
            log_setup.setup_multiprocessing_logging()

        # Don't *BEFORE* to go into try to don't let it triple execute the finally section.
        salt.utils.process.daemonize_if(self.opts)

        # TODO: Make it readable! Splt to funcs, remove nested try-except-finally sections.
        try:
            ret['pid'] = os.getpid()

            if not self.standalone:
                if 'jid_include' not in data or data['jid_include']:
                    log.debug('schedule.handle_func: adding this job to the jobcache '
                              'with data {0}'.format(ret))
                    # write this to /var/cache/salt/minion/proc
                    with salt.utils.files.fopen(proc_fn, 'w+b') as fp_:
                        fp_.write(salt.payload.Serial(self.opts).dumps(ret))

            args = tuple()
            if 'args' in data:
                args = data['args']
                ret['fun_args'].extend(data['args'])

            kwargs = {}
            if 'kwargs' in data:
                kwargs = data['kwargs']
                ret['fun_args'].append(copy.deepcopy(kwargs))

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
                    if key is not 'kwargs':
                        kwargs['__pub_{0}'.format(key)] = copy.deepcopy(val)

            # Only include these when running runner modules
            if self.opts['__role'] == 'master':
                jid = salt.utils.jid.gen_jid(self.opts)
                tag = salt.utils.event.tagify(jid, prefix='salt/scheduler/')

                event = salt.utils.event.get_event(
                        self.opts['__role'],
                        self.opts['sock_dir'],
                        self.opts['transport'],
                        opts=self.opts,
                        listen=False)

                namespaced_event = salt.utils.event.NamespacedEvent(
                    event,
                    tag,
                    print_func=None
                )

                func_globals = {
                    '__jid__': jid,
                    '__user__': salt.utils.user.get_user(),
                    '__tag__': tag,
                    '__jid_event__': weakref.proxy(namespaced_event),
                }
                self_functions = copy.copy(self.functions)
                salt.utils.lazy.verify_fun(self_functions, func)

                # Inject some useful globals to *all* the function's global
                # namespace only once per module-- not per func
                completed_funcs = []

                for mod_name in six.iterkeys(self_functions):
                    if '.' not in mod_name:
                        continue
                    mod, _ = mod_name.split('.', 1)
                    if mod in completed_funcs:
                        continue
                    completed_funcs.append(mod)
                    for global_key, value in six.iteritems(func_globals):
                        self.functions[mod_name].__globals__[global_key] = value

            ret['return'] = self.functions[func](*args, **kwargs)

            if not self.standalone:
                # runners do not provide retcode
                if 'retcode' in self.functions.pack['__context__']:
                    ret['retcode'] = self.functions.pack['__context__']['retcode']

                ret['success'] = True

                data_returner = data.get('returner', None)
                if data_returner or self.schedule_returner:
                    if 'return_config' in data:
                        ret['ret_config'] = data['return_config']
                    if 'return_kwargs' in data:
                        ret['ret_kwargs'] = data['return_kwargs']
                    rets = []
                    for returner in [data_returner, self.schedule_returner]:
                        if isinstance(returner, six.string_types):
                            rets.append(returner)
                        elif isinstance(returner, list):
                            rets.extend(returner)
                    # simple de-duplication with order retained
                    for returner in OrderedDict.fromkeys(rets):
                        ret_str = '{0}.returner'.format(returner)
                        if ret_str in self.returners:
                            self.returners[ret_str](ret)
                        else:
                            log.info(
                                'Job {0} using invalid returner: {1}. Ignoring.'.format(
                                    func, returner
                                )
                            )

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
            # Only attempt to return data to the master if the scheduled job is running
            # on a master itself or a minion.
            if '__role' in self.opts and self.opts['__role'] in ('master', 'minion'):
                # The 'return_job' option is enabled by default even if not set
                if 'return_job' in data and not data['return_job']:
                    pass
                else:
                    # Send back to master so the job is included in the job list
                    mret = ret.copy()
                    mret['jid'] = 'req'
                    if data.get('return_job') == 'nocache':
                        # overwrite 'req' to signal to master that
                        # this job shouldn't be stored
                        mret['jid'] = 'nocache'
                    load = {'cmd': '_return', 'id': self.opts['id']}
                    for key, value in six.iteritems(mret):
                        load[key] = value

                    if '__role' in self.opts and self.opts['__role'] == 'minion':
                        event = salt.utils.event.get_event('minion',
                                                           opts=self.opts,
                                                           listen=False)
                    elif '__role' in self.opts and self.opts['__role'] == 'master':
                        event = salt.utils.event.get_master_event(self.opts,
                                                                  self.opts['sock_dir'])
                    try:
                        event.fire_event(load, '__schedule_return')
                    except Exception as exc:
                        log.exception("Unhandled exception firing event: {0}".format(exc))

            if not self.standalone:
                log.debug('schedule.handle_func: Removing {0}'.format(proc_fn))

                try:
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

    def eval(self, now=None):
        '''
        Evaluate and execute the schedule

        :param int now: Override current time with a Unix timestamp``

        '''

        log.trace('==== evaluating schedule now {} ====='.format(now))

        def _splay(splaytime):
            '''
            Calculate splaytime
            '''
            splay_ = None
            if isinstance(splaytime, dict):
                if splaytime['end'] >= splaytime['start']:
                    splay_ = random.randint(splaytime['start'],
                                            splaytime['end'])
                else:
                    log.error('schedule.handle_func: Invalid Splay, '
                              'end must be larger than start. Ignoring splay.')
            else:
                splay_ = random.randint(1, splaytime)
            return splay_

        schedule = self._get_schedule()
        if not isinstance(schedule, dict):
            raise ValueError('Schedule must be of type dict.')
        if 'enabled' in schedule and not schedule['enabled']:
            return
        if 'skip_function' in schedule:
            self.skip_function = schedule['skip_function']
        if 'skip_during_range' in schedule:
            self.skip_during_range = schedule['skip_during_range']

        _hidden = ['enabled',
                   'skip_function',
                   'skip_during_range']
        for job, data in six.iteritems(schedule):
            run = False

            if job in _hidden and not data:
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

            if '_next_fire_time' not in data:
                data['_next_fire_time'] = None

            if '_splay' not in data:
                data['_splay'] = None

            if 'run_on_start' in data and \
                    data['run_on_start'] and \
                    '_run_on_start' not in data:
                data['_run_on_start'] = True

            if not now:
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

            if 'run_explicit' in data:
                _run_explicit = data['run_explicit']

                if isinstance(_run_explicit, six.integer_types):
                    _run_explicit = [_run_explicit]

                # Copy the list so we can loop through it
                for i in copy.deepcopy(_run_explicit):
                    if len(_run_explicit) > 1:
                        if int(i) < now - self.opts['loop_interval']:
                            _run_explicit.remove(i)

                if _run_explicit:
                    if int(_run_explicit[0]) <= now < int(_run_explicit[0] + self.opts['loop_interval']):
                        run = True
                        data['_next_fire_time'] = _run_explicit[0]

            if True in [True for item in time_elements if item in data]:
                if '_seconds' not in data:
                    interval = int(data.get('seconds', 0))
                    interval += int(data.get('minutes', 0)) * 60
                    interval += int(data.get('hours', 0)) * 3600
                    interval += int(data.get('days', 0)) * 86400

                    data['_seconds'] = interval

                    if not data['_next_fire_time']:
                        data['_next_fire_time'] = now + data['_seconds']

                    if interval < self.loop_interval:
                        self.loop_interval = interval

            elif 'once' in data:
                if data['_next_fire_time'] and \
                        data['_next_fire_time'] < now - self.opts['loop_interval'] and \
                        data['_next_fire_time'] > now and \
                        not data['_splay']:
                    continue

                if not data['_next_fire_time'] and \
                        not data['_splay']:
                    once_fmt = data.get('once_fmt', '%Y-%m-%dT%H:%M:%S')
                    try:
                        once = datetime.datetime.strptime(data['once'],
                                                          once_fmt)
                        data['_next_fire_time'] = int(
                            time.mktime(once.timetuple()))
                    except (TypeError, ValueError):
                        log.error('Date string could not be parsed: %s, %s',
                                  data['once'], once_fmt)
                        continue
                    # If _next_fire_time is less than now or greater
                    # than now, continue.
                    if data['_next_fire_time'] < now - self.opts['loop_interval'] and \
                            data['_next_fire_time'] > now:
                        continue

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
                        _when.append(int(time.mktime(when__.timetuple())))

                    if data['_splay']:
                        _when.append(data['_splay'])

                    # Sort the list of "whens" from earlier to later schedules
                    _when.sort()

                    # Copy the list so we can loop through it
                    for i in copy.deepcopy(_when):
                        if len(_when) > 1:
                            if i < now - self.opts['loop_interval']:
                                # Remove all missed schedules except the latest one.
                                # We need it to detect if it was triggered previously.
                                _when.remove(i)

                    if _when:
                        # Grab the first element, which is the next run time or
                        # last scheduled time in the past.
                        when = _when[0]

                        if '_run' not in data:
                            # Prevent run of jobs from the past
                            data['_run'] = bool(when >= now - self.opts['loop_interval'])

                        if not data['_next_fire_time']:
                            data['_next_fire_time'] = when

                        if data['_next_fire_time'] < when and \
                                not run and \
                                not data['_run']:
                            data['_next_fire_time'] = when
                            data['_run'] = True

                    elif not data.get('_run', False):
                        data['_next_fire_time'] = None
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

                    if when < now - self.opts['loop_interval'] and \
                            not data.get('_run', False) and \
                            not run and \
                            not data['_splay']:
                        data['_next_fire_time'] = None
                        continue

                    if '_run' not in data:
                        data['_run'] = True

                    if not data['_next_fire_time']:
                        data['_next_fire_time'] = when

                    if data['_next_fire_time'] < when and \
                            not data['_run']:
                        data['_next_fire_time'] = when
                        data['_run'] = True

            elif 'cron' in data:
                if not _CRON_SUPPORTED:
                    log.error('Missing python-croniter. Ignoring job {0}'.format(job))
                    continue

                if data['_next_fire_time'] is None:
                    # Get next time frame for a "cron" job if it has been never
                    # executed before or already executed in the past.
                    try:
                        data['_next_fire_time'] = int(
                            croniter.croniter(data['cron'], now).get_next())
                    except (ValueError, KeyError):
                        log.error('Invalid cron string. Ignoring')
                        continue

                    # If next job run is scheduled more than 1 minute ahead and
                    # configured loop interval is longer than that, we should
                    # shorten it to get our job executed closer to the beginning
                    # of desired time.
                    interval = now - data['_next_fire_time']
                    if interval >= 60 and interval < self.loop_interval:
                        self.loop_interval = interval

            else:
                continue

            seconds = data['_next_fire_time'] - now

            if 'splay' in data:
                # Got "splay" configured, make decision to run a job based on that
                if not data['_splay']:
                    # Try to add "splay" time only if next job fire time is
                    # still in the future. We should trigger job run
                    # immediately otherwise.
                    splay = _splay(data['splay'])
                    if now < data['_next_fire_time'] + splay:
                        log.debug('schedule.handle_func: Adding splay of '
                                  '{0} seconds to next run.'.format(splay))
                        data['_splay'] = data['_next_fire_time'] + splay
                        if 'when' in data:
                            data['_run'] = True
                    else:
                        run = True

                if data['_splay']:
                    # The "splay" configuration has been already processed, just use it
                    seconds = data['_splay'] - now

            if '_seconds' in data:
                if seconds <= 0:
                    run = True
            elif 'when' in data and data['_run']:
                if data['_next_fire_time'] <= now <= (data['_next_fire_time'] + self.opts['loop_interval']):
                    data['_run'] = False
                    run = True
            elif 'cron' in data:
                # Reset next scheduled time because it is in the past now,
                # and we should trigger the job run, then wait for the next one.
                if seconds <= 0:
                    data['_next_fire_time'] = None
                    run = True
            elif 'once' in data:
                if data['_next_fire_time'] <= now <= (data['_next_fire_time'] + self.opts['loop_interval']):
                    run = True
            elif seconds == 0:
                run = True

            if '_run_on_start' in data and data['_run_on_start']:
                run = True
                data['_run_on_start'] = False
            elif run:
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
                                    if start <= now <= end:
                                        run = True
                                    else:
                                        if self.skip_function:
                                            run = True
                                            func = self.skip_function
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

                # If there is no job specific skip_during_range available,
                # grab the global which defaults to None.
                if 'skip_during_range' not in data:
                    data['skip_during_range'] = self.skip_during_range

                if 'skip_during_range' in data and data['skip_during_range']:
                    if not _RANGE_SUPPORTED:
                        log.error('Missing python-dateutil. Ignoring job {0}'.format(job))
                        continue
                    else:
                        if isinstance(data['skip_during_range'], dict):
                            try:
                                start = int(time.mktime(dateutil_parser.parse(data['skip_during_range']['start']).timetuple()))
                            except ValueError:
                                log.error('Invalid date string for start in skip_during_range. Ignoring job {0}.'.format(job))
                                continue
                            try:
                                end = int(time.mktime(dateutil_parser.parse(data['skip_during_range']['end']).timetuple()))
                            except ValueError:
                                log.error('Invalid date string for end in skip_during_range. Ignoring job {0}.'.format(job))
                                log.error(data)
                                continue

                            # Check to see if we should run the job immediately
                            # after the skip_during_range is over
                            if 'run_after_skip_range' in data and \
                               data['run_after_skip_range']:
                                if 'run_explicit' not in data:
                                    data['run_explicit'] = []
                                # Add a run_explicit for immediately after the
                                # skip_during_range ends
                                _run_immediate = end + self.opts['loop_interval']
                                if _run_immediate not in data['run_explicit']:
                                    data['run_explicit'].append(_run_immediate)

                            if end > start:
                                if start <= now <= end:
                                    if self.skip_function:
                                        run = True
                                        func = self.skip_function
                                    else:
                                        run = False
                                else:
                                    run = True
                            else:
                                log.error('schedule.handle_func: Invalid range, end must be larger than start. \
                                         Ignoring job {0}.'.format(job))
                                continue
                        else:
                            log.error('schedule.handle_func: Invalid, range must be specified as a dictionary. \
                                     Ignoring job {0}.'.format(job))
                            continue

                if 'skip_explicit' in data:
                    _skip_explicit = data['skip_explicit']

                    if isinstance(_skip_explicit, six.string_types):
                        _skip_explicit = [_skip_explicit]

                    # Copy the list so we can loop through it
                    for i in copy.deepcopy(_skip_explicit):
                        if i < now - self.opts['loop_interval']:
                            _skip_explicit.remove(i)

                    if _skip_explicit:
                        if _skip_explicit[0] <= now <= (_skip_explicit[0] + self.opts['loop_interval']):
                            if self.skip_function:
                                run = True
                                func = self.skip_function
                            else:
                                run = False
                        else:
                            run = True

            if not run:
                continue

            miss_msg = ''
            if seconds < 0:
                miss_msg = ' (runtime missed ' \
                           'by {0} seconds)'.format(abs(seconds))

            log.info('Running scheduled job: {0}{1}'.format(job, miss_msg))

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

            if salt.utils.platform.is_windows():
                # Temporarily stash our function references.
                # You can't pickle function references, and pickling is
                # required when spawning new processes on Windows.
                functions = self.functions
                self.functions = {}
                returners = self.returners
                self.returners = {}
            try:
                if multiprocessing_enabled:
                    thread_cls = salt.utils.process.SignalHandlingMultiprocessingProcess
                else:
                    thread_cls = threading.Thread
                proc = thread_cls(target=self.handle_func, args=(multiprocessing_enabled, func, data))

                if multiprocessing_enabled:
                    with salt.utils.process.default_signals(signal.SIGINT, signal.SIGTERM):
                        # Reset current signals before starting the process in
                        # order not to inherit the current signal handlers
                        proc.start()
                else:
                    proc.start()

                if multiprocessing_enabled:
                    proc.join()
            finally:
                if '_seconds' in data:
                    data['_next_fire_time'] = now + data['_seconds']
                data['_last_run'] = now
                data['_splay'] = None
            if salt.utils.platform.is_windows():
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
        with salt.utils.files.fopen(fn_, 'rb') as fp_:
            job = None
            try:
                job = salt.payload.Serial(opts).load(fp_)
            except Exception:  # It's corrupted
                # Windows cannot delete an open file
                if salt.utils.platform.is_windows():
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
                    if salt.utils.platform.is_windows():
                        fp_.close()
                    # Maybe the file is already gone
                    try:
                        os.unlink(fn_)
                    except OSError:
                        pass
