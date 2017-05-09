# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import fnmatch
import glob
import logging

# Import salt libs
import salt.runner
import salt.state
import salt.utils
import salt.utils.cache
import salt.utils.event
import salt.utils.process
import salt.defaults.exitcodes

# Import 3rd-party libs
import yaml
import salt.ext.six as six

log = logging.getLogger(__name__)


class Reactor(salt.utils.process.SignalHandlingMultiprocessingProcess, salt.state.Compiler):
    '''
    Read in the reactor configuration variable and compare it to events
    processed on the master.
    The reactor has the capability to execute pre-programmed executions
    as reactions to events
    '''
    def __init__(self, opts, log_queue=None):
        super(Reactor, self).__init__(log_queue=log_queue)
        local_minion_opts = opts.copy()
        local_minion_opts['file_client'] = 'local'
        self.minion = salt.minion.MasterMinion(local_minion_opts)
        salt.state.Compiler.__init__(self, opts, self.minion.rend)

    # We need __setstate__ and __getstate__ to avoid pickling errors since
    # 'self.rend' (from salt.state.Compiler) contains a function reference
    # which is not picklable.
    # These methods are only used when pickling so will not be used on
    # non-Windows platforms.
    def __setstate__(self, state):
        self._is_child = True
        Reactor.__init__(
            self, state['opts'],
            log_queue=state['log_queue'])

    def __getstate__(self):
        return {'opts': self.opts,
                'log_queue': self.log_queue}

    def render_reaction(self, glob_ref, tag, data):
        '''
        Execute the render system against a single reaction file and return
        the data structure
        '''
        react = {}

        if glob_ref.startswith('salt://'):
            glob_ref = self.minion.functions['cp.cache_file'](glob_ref) or ''
        globbed_ref = glob.glob(glob_ref)
        if not globbed_ref:
            log.error('Can not render SLS {0} for tag {1}. File missing or not found.'.format(glob_ref, tag))
        for fn_ in globbed_ref:
            try:
                res = self.render_template(
                    fn_,
                    tag=tag,
                    data=data)

                # for #20841, inject the sls name here since verify_high()
                # assumes it exists in case there are any errors
                for name in res:
                    res[name]['__sls__'] = fn_

                react.update(res)
            except Exception:
                log.error('Failed to render "{0}": '.format(fn_), exc_info=True)
        return react

    def list_reactors(self, tag):
        '''
        Take in the tag from an event and return a list of the reactors to
        process
        '''
        log.debug('Gathering reactors for tag {0}'.format(tag))
        reactors = []
        if isinstance(self.opts['reactor'], six.string_types):
            try:
                with salt.utils.fopen(self.opts['reactor']) as fp_:
                    react_map = yaml.safe_load(fp_.read())
            except (OSError, IOError):
                log.error(
                    'Failed to read reactor map: "{0}"'.format(
                        self.opts['reactor']
                        )
                    )
            except Exception:
                log.error(
                    'Failed to parse YAML in reactor map: "{0}"'.format(
                        self.opts['reactor']
                        )
                    )
        else:
            react_map = self.opts['reactor']
        for ropt in react_map:
            if not isinstance(ropt, dict):
                continue
            if len(ropt) != 1:
                continue
            key = next(six.iterkeys(ropt))
            val = ropt[key]
            if fnmatch.fnmatch(tag, key):
                if isinstance(val, six.string_types):
                    reactors.append(val)
                elif isinstance(val, list):
                    reactors.extend(val)
        return reactors

    def list_all(self):
        '''
        Return a list of the reactors
        '''
        if isinstance(self.minion.opts['reactor'], six.string_types):
            log.debug('Reading reactors from yaml {0}'.format(self.opts['reactor']))
            try:
                with salt.utils.fopen(self.opts['reactor']) as fp_:
                    react_map = yaml.safe_load(fp_.read())
            except (OSError, IOError):
                log.error(
                    'Failed to read reactor map: "{0}"'.format(
                        self.opts['reactor']
                        )
                    )
            except Exception:
                log.error(
                    'Failed to parse YAML in reactor map: "{0}"'.format(
                        self.opts['reactor']
                        )
                    )
        else:
            log.debug('Not reading reactors from yaml')
            react_map = self.minion.opts['reactor']
        return react_map

    def add_reactor(self, tag, reaction):
        '''
        Add a reactor
        '''
        reactors = self.list_all()
        for reactor in reactors:
            _tag = next(six.iterkeys(reactor))
            if _tag == tag:
                return {'status': False, 'comment': 'Reactor already exists.'}

        self.minion.opts['reactor'].append({tag: reaction})
        return {'status': True, 'comment': 'Reactor added.'}

    def delete_reactor(self, tag):
        '''
        Delete a reactor
        '''
        reactors = self.list_all()
        for reactor in reactors:
            _tag = next(six.iterkeys(reactor))
            if _tag == tag:
                self.minion.opts['reactor'].remove(reactor)
                return {'status': True, 'comment': 'Reactor deleted.'}

        return {'status': False, 'comment': 'Reactor does not exists.'}

    def reactions(self, tag, data, reactors):
        '''
        Render a list of reactor files and returns a reaction struct
        '''
        log.debug('Compiling reactions for tag {0}'.format(tag))
        high = {}
        chunks = []
        try:
            for fn_ in reactors:
                high.update(self.render_reaction(fn_, tag, data))
            if high:
                errors = self.verify_high(high)
                if errors:
                    log.error(('Unable to render reactions for event {0} due to '
                               'errors ({1}) in one or more of the sls files ({2})').format(tag, errors, reactors))
                    return []  # We'll return nothing since there was an error
                chunks = self.order_chunks(self.compile_high_data(high))
        except Exception as exc:
            log.error('Exception trying to compile reactions: {0}'.format(exc), exc_info=True)

        return chunks

    def call_reactions(self, chunks):
        '''
        Execute the reaction state
        '''
        for chunk in chunks:
            self.wrap.run(chunk)

    def run(self):
        '''
        Enter into the server loop
        '''
        salt.utils.appendproctitle(self.__class__.__name__)

        # instantiate some classes inside our new process
        self.event = salt.utils.event.get_event(
                self.opts['__role'],
                self.opts['sock_dir'],
                self.opts['transport'],
                opts=self.opts,
                listen=True)
        self.wrap = ReactWrap(self.opts)

        for data in self.event.iter_events(full=True):
            # skip all events fired by ourselves
            if data['data'].get('user') == self.wrap.event_user:
                continue
            if data['tag'].endswith('salt/reactors/manage/add'):
                _data = data['data']
                res = self.add_reactor(_data['event'], _data['reactors'])
                self.event.fire_event({'reactors': self.list_all(),
                                       'result': res},
                                      'salt/reactors/manage/add-complete')
            elif data['tag'].endswith('salt/reactors/manage/delete'):
                _data = data['data']
                res = self.delete_reactor(_data['event'])
                self.event.fire_event({'reactors': self.list_all(),
                                       'result': res},
                                      'salt/reactors/manage/delete-complete')
            elif data['tag'].endswith('salt/reactors/manage/list'):
                self.event.fire_event({'reactors': self.list_all()},
                                      'salt/reactors/manage/list-results')
            else:
                reactors = self.list_reactors(data['tag'])
                if not reactors:
                    continue
                chunks = self.reactions(data['tag'], data['data'], reactors)
                if chunks:
                    try:
                        self.call_reactions(chunks)
                    except SystemExit:
                        log.warning('Exit ignored by reactor')


class ReactWrap(object):
    '''
    Create a wrapper that executes low data for the reaction system
    '''
    # class-wide cache of clients
    client_cache = None
    event_user = 'Reactor'

    def __init__(self, opts):
        self.opts = opts
        if ReactWrap.client_cache is None:
            ReactWrap.client_cache = salt.utils.cache.CacheDict(opts['reactor_refresh_interval'])

        self.pool = salt.utils.process.ThreadPool(
            self.opts['reactor_worker_threads'],  # number of workers for runner/wheel
            queue_size=self.opts['reactor_worker_hwm']  # queue size for those workers
        )

    def run(self, low):
        '''
        Execute the specified function in the specified state by passing the
        low data
        '''
        l_fun = getattr(self, low['state'])
        try:
            f_call = salt.utils.format_call(l_fun, low)
            kwargs = f_call.get('kwargs', {})

            # TODO: Setting the user doesn't seem to work for actual remote publishes
            if low['state'] in ('runner', 'wheel'):
                # Update called function's low data with event user to
                # segregate events fired by reactor and avoid reaction loops
                kwargs['__user__'] = self.event_user

            l_fun(*f_call.get('args', ()), **kwargs)
        except Exception:
            log.error(
                    'Failed to execute {0}: {1}\n'.format(low['state'], l_fun),
                    exc_info=True
                    )

    def local(self, *args, **kwargs):
        '''
        Wrap LocalClient for running :ref:`execution modules <all-salt.modules>`
        '''
        if 'local' not in self.client_cache:
            self.client_cache['local'] = salt.client.LocalClient(self.opts['conf_file'])
        try:
            self.client_cache['local'].cmd_async(*args, **kwargs)
        except SystemExit:
            log.warning('Attempt to exit reactor. Ignored.')
        except Exception as exc:
            log.warning('Exception caught by reactor: {0}'.format(exc))

    cmd = local

    def runner(self, fun, **kwargs):
        '''
        Wrap RunnerClient for executing :ref:`runner modules <all-salt.runners>`
        '''
        if 'runner' not in self.client_cache:
            self.client_cache['runner'] = salt.runner.RunnerClient(self.opts)
            # The len() function will cause the module functions to load if
            # they aren't already loaded. We want to load them so that the
            # spawned threads don't need to load them. Loading in the spawned
            # threads creates race conditions such as sometimes not finding
            # the required function because another thread is in the middle
            # of loading the functions.
            len(self.client_cache['runner'].functions)
        try:
            self.pool.fire_async(self.client_cache['runner'].low, args=(fun, kwargs))
        except SystemExit:
            log.warning('Attempt to exit in reactor by runner. Ignored')
        except Exception as exc:
            log.warning('Exception caught by reactor: {0}'.format(exc))

    def wheel(self, fun, **kwargs):
        '''
        Wrap Wheel to enable executing :ref:`wheel modules <all-salt.wheel>`
        '''
        if 'wheel' not in self.client_cache:
            self.client_cache['wheel'] = salt.wheel.Wheel(self.opts)
            # The len() function will cause the module functions to load if
            # they aren't already loaded. We want to load them so that the
            # spawned threads don't need to load them. Loading in the spawned
            # threads creates race conditions such as sometimes not finding
            # the required function because another thread is in the middle
            # of loading the functions.
            len(self.client_cache['wheel'].functions)
        try:
            self.pool.fire_async(self.client_cache['wheel'].low, args=(fun, kwargs))
        except SystemExit:
            log.warning('Attempt to in reactor by whell. Ignored.')
        except Exception as exc:
            log.warning('Exception caught by reactor: {0}'.format(exc))

    def caller(self, fun, *args, **kwargs):
        '''
        Wrap Caller to enable executing :ref:`caller modules <all-salt.caller>`
        '''
        log.debug("in caller with fun {0} args {1} kwargs {2}".format(fun, args, kwargs))
        args = kwargs.get('args', [])
        kwargs = kwargs.get('kwargs', {})
        if 'caller' not in self.client_cache:
            self.client_cache['caller'] = salt.client.Caller(self.opts['conf_file'])
        try:
            self.client_cache['caller'].cmd(fun, *args, **kwargs)
        except SystemExit:
            log.warning('Attempt to exit reactor. Ignored.')
        except Exception as exc:
            log.warning('Exception caught by reactor: {0}'.format(exc))
