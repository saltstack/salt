# -*- coding: utf-8 -*-
'''
tests.functional.conftest
~~~~~~~~~~~~~~~~~~~~~~~~~

PyTest boilerplate code for Salt functional testing
'''
# pylint: disable=redefined-outer-name

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function
import os
import sys
import time
import shutil
import logging
import functools
import threading

# Import 3rd-party libs
import pytest
import tornado.gen
import tornado.ioloop
import salt.ext.six as six

# Import Salt libs
import salt.minion
import salt.config
import salt.runner
import salt.utils.event
import salt.utils.files
import salt.utils.platform
import salt.utils.verify

# Import testing libs
from tests.support.comparables import StateReturn
from tests.support.runtests import RUNTIME_VARS
from tests.support.sminion import create_sminion

log = logging.getLogger(__name__)


class FunctionalMinion(salt.minion.SMinion):

    def __init__(self, opts, context=None):
        if context is None:
            context = {}
        super(FunctionalMinion, self).__init__(opts, context=context)
        self.__context = context
        self.__loop = None
        self.__listener_thread = None
        self.__event = None
        self.__event_publisher = None

    def start_event_listener(self):
        if self.__listener_thread is None:
            self.__loop = ioloop = tornado.ioloop.IOLoop()
            self.__listener_thread = threading.Thread(target=self._start_event_listener, args=(ioloop,))
            self.__listener_thread.start()

    def _start_event_listener(self, io_loop=None):
        log.info('Starting %r minion event listener', self.opts['id'])
        io_loop.make_current()
        time.sleep(0.025)
        # start up the event publisher, so we can see events during startup
        if self.__event_publisher is None:
            self.__event_publisher = salt.utils.event.AsyncEventPublisher(
                self.opts,
                io_loop=io_loop,
            )
        if self.__event is None:
            self.__event = salt.utils.event.get_event('minion', opts=self.opts, io_loop=io_loop)
        self.__event.subscribe('')
        self.__event.set_event_handler(self.handle_event)
        io_loop.add_callback(log.info, 'Started %r minion event listener', self.opts['id'])
        io_loop.start()
        try:
            io_loop.close(all_fds=True)
        except ValueError:
            pass

    def stop_event_listenter(self):
        log.info('Stopping %r minion event listener', self.opts['id'])
        if self.__event is not None:
            event = self.__event
            self.__event = None
            self.__loop.add_callback(event.remove_event_handler, self.handle_event)
            self.__loop.add_callback(event.unsubscribe, '')
            self.__loop.add_callback(event.destroy)
        if self.__event_publisher is not None:
            event_publisher = self.__event_publisher
            self.__event_publisher = None
            self.__loop.add_callback(event_publisher.close)
        if self.__loop is not None:
            loop = self.__loop
            self.__loop = None
            loop.add_callback(loop.stop)
        if self.__listener_thread is not None:
            self.__listener_thread.join()
            self.__listener_thread = None
            self.__loop = None
        log.info('Stopped %r minion event listener', self.opts['id'])

    @tornado.gen.coroutine
    def handle_event(self, package):
        '''
        Handle an event from the epull_sock (all local minion events)
        '''
        tag, _ = salt.utils.event.SaltEvent.unpack(package)
        log.debug(
            'Minion  \'%s\' is handling event tag \'%s\'',
            self.opts['id'], tag
        )
        handled_tags = (
            'beacons_refresh',
            'grains_refresh',
            'matchers_refresh',
            'manage_schedule',
            'manage_beacons',
            '_minion_mine',
            'module_refresh',
            'pillar_refresh'
        )

        # Run the appropriate function
        for tag_function in handled_tags:
            if tag.startswith(tag_function):
                self.gen_modules(context=self.__context)
                break

    def gen_modules(self, initial_load=False, context=None):
        super(FunctionalMinion, self).gen_modules(initial_load=initial_load, context=context)
        # Make sure state.sls and state.single returns are StateReturn instances for easier comparissons
        self.functions.state.sls = StateModuleCallWrapper(self.functions.state.sls)
        self.functions.state.single = StateModuleCallWrapper(self.functions.state.single)

        # For state execution modules, because we'd have to almost copy/paste what salt.modules.state.single
        # does, we actually "proxy" the call through salt.modules.state.single instead of calling the state
        # execution modules directly.
        # Let's load all modules now
        self.states._load_all()

        # Now, we proxy loaded modules through salt.modules.state.single
        for module_name in list(self.states.loaded_modules):
            for func_name in list(self.states.loaded_modules[module_name]):
                full_func_name = '{}.{}'.format(module_name, func_name)
                replacement_function = functools.partial(self.functions.state.single, full_func_name)
                self.states._dict[full_func_name] = replacement_function
                self.states.loaded_modules[module_name][func_name] = replacement_function
                setattr(self.states.loaded_modules[module_name], func_name, replacement_function)


class StateModuleCallWrapper(object):
    '''
    Wraps salt.modules.state functions
    '''
    def __init__(self, function):
        self._function = function

    def __call__(self, *args, **kwargs):
        result = self._function(*args, **kwargs)
        return StateReturn(result)


@pytest.fixture(scope='session')
def loader_context_dictionary():
    return {}


@pytest.fixture(scope='session')
def sminion(loader_context_dictionary):
    sminion = create_sminion(minion_id='functional-tests-minion',
                             sminion_cls=FunctionalMinion,
                             loader_context=loader_context_dictionary)
    return sminion


@pytest.fixture(autouse=True)
def __minion_loader_cleanup(sminion,
                            loader_context_dictionary,
                            utils,
                            functions,
                            serializers,
                            returners,
                            proxy,
                            states,
                            rend,
                            matchers,
                            executors):
    # Maintain a copy of the sminion opts dictionary to restore after running the tests
    salt_opts_copy = sminion.opts.copy()
    # Run tests
    yield
    # Clear the context after running the tests
    loader_context_dictionary.clear()
    # Reset the options dictionary
    sminion.opts = salt_opts_copy
    utils.opts = salt_opts_copy
    functions.opts = salt_opts_copy
    serializers.opts = salt_opts_copy
    returners.opts = salt_opts_copy
    proxy.opts = salt_opts_copy
    states.opts = salt_opts_copy
    rend.opts = salt_opts_copy
    matchers.opts = salt_opts_copy
    executors.opts = salt_opts_copy


@pytest.fixture
def minion(sminion):
    sminion.start_event_listener()
    yield sminion
    sminion.stop_event_listenter()


@pytest.fixture
def grains(minion):
    return minion.opts['grains'].copy()


@pytest.fixture
def pillar(minion):
    return minion.opts['pillar'].copy()


@pytest.fixture
def utils(minion):
    return minion.utils


@pytest.fixture
def functions(minion):
    _functions = minion.functions
    return _functions


@pytest.fixture
def modules(functions):
    return functions


@pytest.fixture
def serializers(minion):
    return minion.serializers


@pytest.fixture
def returners(minion):
    return minion.returners


@pytest.fixture
def proxy(minion):
    return minion.proxy


@pytest.fixture
def states(minion):
    return minion.states


@pytest.fixture
def rend(minion):
    return minion.rend


@pytest.fixture
def matchers(minion):
    return minion.matchers


@pytest.fixture
def executors(minion):
    return minion.executors


@pytest.fixture
def _runner_client(sminion, loader_context_dictionary):
    _runners = salt.runner.RunnerClient(sminion.opts.copy(), context=loader_context_dictionary)
    return _runners


@pytest.fixture
def runners(_runner_client, salt_opts, loader_context_dictionary):
    yield _runner_client.functions
    # Cleanup
    loader_context_dictionary.clear()
    _runner_client.opts = _runner_client.opts = salt_opts.copy()


def pytest_assertrepr_compare(config, op, left, right):
    if op not in ('==', '!='):
        # Don't even bother, our special assertions involve equality
        return
    explanation = []
    if isinstance(left, StateReturn) or isinstance(right, StateReturn):
        if not isinstance(left, StateReturn):
            left = StateReturn(left)
        if not isinstance(right, StateReturn):
            right = StateReturn(right)
        explanation.extend(left.explain_comparisson_with(right))
    if explanation:
        return explanation
