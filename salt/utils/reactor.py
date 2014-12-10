# -*- coding: utf-8 -*-
from __future__ import absolute_import

# Import python libs
import fnmatch
import glob
import logging
import multiprocessing

import yaml

# Import salt libs
import salt.state
import salt.utils
import salt.utils.cache
from salt.ext.six import string_types
import salt.utils.process
from salt._compat import string_types
log = logging.getLogger(__name__)


class Reactor(multiprocessing.Process, salt.state.Compiler):
    '''
    Read in the reactor configuration variable and compare it to events
    processed on the master.
    The reactor has the capability to execute pre-programmed executions
    as reactions to events
    '''
    def __init__(self, opts):
        multiprocessing.Process.__init__(self)
        salt.state.Compiler.__init__(self, opts)
        self.wrap = ReactWrap(self.opts)

        local_minion_opts = self.opts.copy()
        local_minion_opts['file_client'] = 'local'
        self.minion = salt.minion.MasterMinion(local_minion_opts)

    def render_reaction(self, glob_ref, tag, data):
        '''
        Execute the render system against a single reaction file and return
        the data structure
        '''
        react = {}

        if glob_ref.startswith('salt://'):
            glob_ref = self.minion.functions['cp.cache_file'](glob_ref)

        for fn_ in glob.glob(glob_ref):
            try:
                react.update(self.render_template(
                    fn_,
                    tag=tag,
                    data=data))
            except Exception:
                log.error('Failed to render "{0}"'.format(fn_))
        return react

    def list_reactors(self, tag):
        '''
        Take in the tag from an event and return a list of the reactors to
        process
        '''
        log.debug('Gathering reactors for tag {0}'.format(tag))
        reactors = []
        if isinstance(self.opts['reactor'], string_types):
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
            key = next(iter(ropt.keys()))
            val = ropt[key]
            if fnmatch.fnmatch(tag, key):
                if isinstance(val, string_types):
                    reactors.append(val)
                elif isinstance(val, list):
                    reactors.extend(val)
        return reactors

    def reactions(self, tag, data, reactors):
        '''
        Render a list of reactor files and returns a reaction struct
        '''
        log.debug('Compiling reactions for tag {0}'.format(tag))
        high = {}
        chunks = []
        for fn_ in reactors:
            high.update(self.render_reaction(fn_, tag, data))
        if high:
            errors = self.verify_high(high)
            if errors:
                return errors
            chunks = self.order_chunks(self.compile_high_data(high))
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
        self.event = salt.utils.event.SaltEvent('master', self.opts['sock_dir'])
        events = self.event.iter_events(full=True)
        self.event.fire_event({}, 'salt/reactor/start')
        for data in events:
            reactors = self.list_reactors(data['tag'])
            if not reactors:
                continue
            chunks = self.reactions(data['tag'], data['data'], reactors)
            if chunks:
                self.call_reactions(chunks)


class ReactWrap(object):
    '''
    Create a wrapper that executes low data for the reaction system
    '''
    # class-wide cache of clients
    client_cache = None

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
        LowData
        '''
        l_fun = getattr(self, low['state'])
        try:
            f_call = salt.utils.format_call(l_fun, low)
            l_fun(*f_call.get('args', ()), **f_call.get('kwargs', {}))
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
        self.client_cache['local'].cmd_async(*args, **kwargs)

    cmd = local

    def runner(self, _, **kwargs):
        '''
        Wrap RunnerClient for executing :ref:`runner modules <all-salt.runners>`
        '''
        if 'runner' not in self.client_cache:
            self.client_cache['runner'] = salt.runner.RunnerClient(self.opts)
        self.pool.fire_async(self.client_cache['runner'].low, kwargs)

    def wheel(self, _, **kwargs):
        '''
        Wrap Wheel to enable executing :ref:`wheel modules <all-salt.wheel>`
        '''
        if 'wheel' not in self.client_cache:
            self.client_cache['wheel'] = salt.wheel.Wheel(self.opts)
        self.pool.fire_async(self.client_cache['wheel'].low, kwargs)
