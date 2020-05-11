# -*- coding: utf-8 -*-
'''
Functions which implement running reactor jobs
'''


# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import collections
import fnmatch
import glob
import logging
import time

# Import salt libs
import salt.client
import salt.runner
import salt.state
import salt.utils.args
import salt.utils.cache
import salt.utils.data
import salt.utils.event
import salt.utils.files
import salt.utils.master
import salt.utils.process
import salt.utils.yaml
import salt.wheel
import salt.defaults.exitcodes
from salt.utils.event import tagify

# Import 3rd-party libs
from salt.ext import six

log = logging.getLogger(__name__)

REACTOR_INTERNAL_KEYWORDS = frozenset([
    '__id__',
    '__sls__',
    'name',
    'order',
    'fun',
    'key',
    'state',
])


class Reactor(salt.utils.process.SignalHandlingMultiprocessingProcess, salt.state.Compiler):
    '''
    Read in the reactor configuration variable and compare it to events
    processed on the master.
    The reactor has the capability to execute pre-programmed executions
    as reactions to events
    '''
    aliases = {
        'cmd': 'local',
    }

    def __init__(self, opts, **kwargs):
        super(Reactor, self).__init__(**kwargs)
        local_minion_opts = opts.copy()
        local_minion_opts['file_client'] = 'local'
        self.minion = salt.minion.MasterMinion(local_minion_opts)
        salt.state.Compiler.__init__(self, opts, self.minion.rend)
        self.event = salt.utils.event.get_master_event(opts, opts['sock_dir'], listen=False)
        self.stats = collections.defaultdict(lambda: {'mean': 0, 'latency': 0, 'runs': 0})
        self.stat_clock = time.time()
        self.is_leader = True

    # We need __setstate__ and __getstate__ to avoid pickling errors since
    # 'self.rend' (from salt.state.Compiler) contains a function reference
    # which is not picklable.
    # These methods are only used when pickling so will not be used on
    # non-Windows platforms.
    def __setstate__(self, state):
        self._is_child = True
        Reactor.__init__(
            self, state['opts'],
            log_queue=state['log_queue'],
            log_queue_level=state['log_queue_level']
        )

    def __getstate__(self):
        return {
            'opts': self.opts,
            'log_queue': self.log_queue,
            'log_queue_level': self.log_queue_level
        }

    def _post_stats(self, stats):
        '''
        Fire events with stat info if it's time
        '''
        end_time = time.time()
        if end_time - self.stat_clock > self.opts['master_stats_event_iter']:
            # Fire the event with the stats and wipe the tracker
            self.event.fire_event({'time': end_time - self.stat_clock, 'worker': self.name, 'stats': stats}, tagify(self.name, 'stats'))
            self.stats = collections.defaultdict(lambda: {'mean': 0, 'latency': 0, 'runs': 0})
            self.stat_clock = end_time

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
            log.error('Can not render SLS %s for tag %s. File missing or not found.', glob_ref, tag)
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
                log.exception('Failed to render "%s": ', fn_)
        return react

    def list_reactors(self, tag):
        '''
        Take in the tag from an event and return a list of the reactors to
        process
        '''
        log.debug('Gathering reactors for tag %s', tag)
        reactors = []
        if isinstance(self.opts['reactor'], six.string_types):
            try:
                with salt.utils.files.fopen(self.opts['reactor']) as fp_:
                    react_map = salt.utils.yaml.safe_load(fp_)
            except (OSError, IOError):
                log.error('Failed to read reactor map: "%s"', self.opts['reactor'])
            except Exception:
                log.error('Failed to parse YAML in reactor map: "%s"', self.opts['reactor'])
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
            log.debug('Reading reactors from yaml %s', self.opts['reactor'])
            try:
                with salt.utils.files.fopen(self.opts['reactor']) as fp_:
                    react_map = salt.utils.yaml.safe_load(fp_)
            except (OSError, IOError):
                log.error('Failed to read reactor map: "%s"', self.opts['reactor'])
            except Exception:
                log.error(
                    'Failed to parse YAML in reactor map: "%s"',
                    self.opts['reactor']
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

    def resolve_aliases(self, chunks):
        '''
        Preserve backward compatibility by rewriting the 'state' key in the low
        chunks if it is using a legacy type.
        '''
        for idx, _ in enumerate(chunks):
            new_state = self.aliases.get(chunks[idx]['state'])
            if new_state is not None:
                chunks[idx]['state'] = new_state

    def reactions(self, tag, data, reactors):
        '''
        Render a list of reactor files and returns a reaction struct
        '''
        log.debug('Compiling reactions for tag %s', tag)
        high = {}
        chunks = []
        try:
            for fn_ in reactors:
                high.update(self.render_reaction(fn_, tag, data))
            if high:
                errors = self.verify_high(high)
                if errors:
                    log.error(
                        'Unable to render reactions for event %s due to '
                        'errors (%s) in one or more of the sls files (%s)',
                        tag, errors, reactors
                    )
                    return []  # We'll return nothing since there was an error
                chunks = self.order_chunks(self.compile_high_data(high))
        except Exception as exc:
            log.exception('Exception encountered while compiling reactions')

        self.resolve_aliases(chunks)
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
        salt.utils.process.appendproctitle(self.__class__.__name__)

        # instantiate some classes inside our new process
        with salt.utils.event.get_event(
                self.opts['__role'],
                self.opts['sock_dir'],
                self.opts['transport'],
                opts=self.opts,
                listen=True) as event:
            self.wrap = ReactWrap(self.opts)

            for data in event.iter_events(full=True):
                # skip all events fired by ourselves
                if data['data'].get('user') == self.wrap.event_user:
                    continue
                # NOTE: these events must contain the masters key in order to be accepted
                # see salt.runners.reactor for the requesting interface
                if 'salt/reactors/manage' in data['tag']:
                    master_key = salt.utils.master.get_master_key('root', self.opts)
                    if data['data'].get('key') != master_key:
                        log.error('received salt/reactors/manage event without matching master_key. discarding')
                        continue
                if data['tag'].endswith('salt/reactors/manage/is_leader'):
                    event.fire_event({'result': self.is_leader,
                                           'user': self.wrap.event_user},
                                          'salt/reactors/manage/leader/value')
                if data['tag'].endswith('salt/reactors/manage/set_leader'):
                    # we only want to register events from the local master
                    if data['data'].get('id') == self.opts['id']:
                        self.is_leader = data['data']['value']
                    event.fire_event({'result': self.is_leader,
                                           'user': self.wrap.event_user},
                                          'salt/reactors/manage/leader/value')
                if data['tag'].endswith('salt/reactors/manage/add'):
                    _data = data['data']
                    res = self.add_reactor(_data['event'], _data['reactors'])
                    event.fire_event({'reactors': self.list_all(),
                                           'result': res,
                                           'user': self.wrap.event_user},
                                          'salt/reactors/manage/add-complete')
                elif data['tag'].endswith('salt/reactors/manage/delete'):
                    _data = data['data']
                    res = self.delete_reactor(_data['event'])
                    event.fire_event({'reactors': self.list_all(),
                                           'result': res,
                                           'user': self.wrap.event_user},
                                          'salt/reactors/manage/delete-complete')
                elif data['tag'].endswith('salt/reactors/manage/list'):
                    event.fire_event({'reactors': self.list_all(),
                                           'user': self.wrap.event_user},
                                          'salt/reactors/manage/list-results')

                # do not handle any reactions if not leader in cluster
                if not self.is_leader:
                    continue
                else:
                    reactors = self.list_reactors(data['tag'])
                    if not reactors:
                        continue
                    chunks = self.reactions(data['tag'], data['data'], reactors)
                    if chunks:
                        if self.opts['master_stats']:
                            _data = data['data']
                            start = time.time()
                        try:
                            self.call_reactions(chunks)
                        except SystemExit:
                            log.warning('Exit ignored by reactor')

                        if self.opts['master_stats']:
                            stats = salt.utils.event.update_stats(self.stats, start, _data)
                            self._post_stats(stats)


class ReactWrap(object):
    '''
    Wrapper that executes low data for the Reactor System
    '''
    # class-wide cache of clients
    client_cache = None
    event_user = 'Reactor'

    reaction_class = {
        'local': salt.client.LocalClient,
        'runner': salt.runner.RunnerClient,
        'wheel': salt.wheel.Wheel,
        'caller': salt.client.Caller,
    }

    def __init__(self, opts):
        self.opts = opts
        if ReactWrap.client_cache is None:
            ReactWrap.client_cache = salt.utils.cache.CacheDict(opts['reactor_refresh_interval'])

        self.pool = salt.utils.process.ThreadPool(
            self.opts['reactor_worker_threads'],  # number of workers for runner/wheel
            queue_size=self.opts['reactor_worker_hwm']  # queue size for those workers
        )

    def populate_client_cache(self, low):
        '''
        Populate the client cache with an instance of the specified type
        '''
        reaction_type = low['state']
        if reaction_type not in self.client_cache:
            log.debug('Reactor is populating %s client cache', reaction_type)
            if reaction_type in ('runner', 'wheel'):
                # Reaction types that run locally on the master want the full
                # opts passed.
                self.client_cache[reaction_type] = \
                    self.reaction_class[reaction_type](self.opts)
                # The len() function will cause the module functions to load if
                # they aren't already loaded. We want to load them so that the
                # spawned threads don't need to load them. Loading in the
                # spawned threads creates race conditions such as sometimes not
                # finding the required function because another thread is in
                # the middle of loading the functions.
                len(self.client_cache[reaction_type].functions)
            else:
                # Reactions which use remote pubs only need the conf file when
                # instantiating a client instance.
                self.client_cache[reaction_type] = \
                    self.reaction_class[reaction_type](self.opts['conf_file'])

    def run(self, low):
        '''
        Execute a reaction by invoking the proper wrapper func
        '''
        self.populate_client_cache(low)
        try:
            l_fun = getattr(self, low['state'])
        except AttributeError:
            log.error(
                'ReactWrap is missing a wrapper function for \'%s\'',
                low['state']
            )

        try:
            wrap_call = salt.utils.args.format_call(l_fun, low)
            args = wrap_call.get('args', ())
            kwargs = wrap_call.get('kwargs', {})
            # TODO: Setting user doesn't seem to work for actual remote pubs
            if low['state'] in ('runner', 'wheel'):
                # Update called function's low data with event user to
                # segregate events fired by reactor and avoid reaction loops
                kwargs['__user__'] = self.event_user
                # Replace ``state`` kwarg which comes from high data compiler.
                # It breaks some runner functions and seems unnecessary.
                kwargs['__state__'] = kwargs.pop('state')
                # NOTE: if any additional keys are added here, they will also
                # need to be added to filter_kwargs()

            if 'args' in kwargs:
                # New configuration
                reactor_args = kwargs.pop('args')
                for item in ('arg', 'kwarg'):
                    if item in low:
                        log.warning(
                            'Reactor \'%s\' is ignoring \'%s\' param %s due to '
                            'presence of \'args\' param. Check the Reactor System '
                            'documentation for the correct argument format.',
                            low['__id__'], item, low[item]
                        )
                if low['state'] == 'caller' \
                        and isinstance(reactor_args, list) \
                        and not salt.utils.data.is_dictlist(reactor_args):
                    # Legacy 'caller' reactors were already using the 'args'
                    # param, but only supported a list of positional arguments.
                    # If low['args'] is a list but is *not* a dictlist, then
                    # this is actually using the legacy configuration. So, put
                    # the reactor args into kwarg['arg'] so that the wrapper
                    # interprets them as positional args.
                    kwargs['arg'] = reactor_args
                    kwargs['kwarg'] = {}
                else:
                    kwargs['arg'] = ()
                    kwargs['kwarg'] = reactor_args
                if not isinstance(kwargs['kwarg'], dict):
                    kwargs['kwarg'] = salt.utils.data.repack_dictlist(kwargs['kwarg'])
                    if not kwargs['kwarg']:
                        log.error(
                            'Reactor \'%s\' failed to execute %s \'%s\': '
                            'Incorrect argument format, check the Reactor System '
                            'documentation for the correct format.',
                            low['__id__'], low['state'], low['fun']
                        )
                        return
            else:
                # Legacy configuration
                react_call = {}
                if low['state'] in ('runner', 'wheel'):
                    if 'arg' not in kwargs or 'kwarg' not in kwargs:
                        # Runner/wheel execute on the master, so we can use
                        # format_call to get the functions args/kwargs
                        react_fun = self.client_cache[low['state']].functions.get(low['fun'])
                        if react_fun is None:
                            log.error(
                                'Reactor \'%s\' failed to execute %s \'%s\': '
                                'function not available',
                                low['__id__'], low['state'], low['fun']
                            )
                            return

                        react_call = salt.utils.args.format_call(
                            react_fun,
                            low,
                            expected_extra_kws=REACTOR_INTERNAL_KEYWORDS
                        )

                if 'arg' not in kwargs:
                    kwargs['arg'] = react_call.get('args', ())
                if 'kwarg' not in kwargs:
                    kwargs['kwarg'] = react_call.get('kwargs', {})

            # Execute the wrapper with the proper args/kwargs. kwargs['arg']
            # and kwargs['kwarg'] contain the positional and keyword arguments
            # that will be passed to the client interface to execute the
            # desired runner/wheel/remote-exec/etc. function.
            ret = l_fun(*args, **kwargs)

            if ret is False:
                log.error('Reactor \'%s\' failed  to execute %s \'%s\': '
                            'TaskPool queue is full!'
                            ' Consider tuning reactor_worker_threads and/or'
                            ' reactor_worker_hwm',
                            low['__id__'], low['state'], low['fun']
                )

        except SystemExit:
            log.warning(
                'Reactor \'%s\' attempted to exit. Ignored.', low['__id__']
            )
        except Exception:
            log.error(
                'Reactor \'%s\' failed to execute %s \'%s\'',
                low['__id__'], low['state'], low['fun'], exc_info=True
            )

    def runner(self, fun, **kwargs):
        '''
        Wrap RunnerClient for executing :ref:`runner modules <all-salt.runners>`
        '''
        return self.pool.fire_async(self.client_cache['runner'].low, args=(fun, kwargs))

    def wheel(self, fun, **kwargs):
        '''
        Wrap Wheel to enable executing :ref:`wheel modules <all-salt.wheel>`
        '''
        return self.pool.fire_async(self.client_cache['wheel'].low, args=(fun, kwargs))

    def local(self, fun, tgt, **kwargs):
        '''
        Wrap LocalClient for running :ref:`execution modules <all-salt.modules>`
        '''
        self.client_cache['local'].cmd_async(tgt, fun, **kwargs)

    def caller(self, fun, **kwargs):
        '''
        Wrap LocalCaller to execute remote exec functions locally on the Minion
        '''
        self.client_cache['caller'].cmd(fun, *kwargs['arg'], **kwargs['kwarg'])
