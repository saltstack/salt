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
        io_loop.make_current()
        time.sleep(0.25)
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
        io_loop.start()

    def stop_event_listenter(self):
        if self.__event is not None:
            self.__event.remove_event_handler(self.handle_event)
            self.__event.unsubscribe('')
            self.__event.destroy()
            self.__event = None
        if self.__event_publisher is not None:
            self.__event_publisher.close()
            self.__event_publisher = None
        if self.__loop is not None:
            self.__loop.add_callback(self.__loop.stop)
            self.__listener_thread.join()
            self.__listener_thread = None
            self.__loop.close(all_fds=True)
            self.__loop = None

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


class StateCallWrapper(object):
    def __init__(self, function):
        self._function = function

    def __call__(self, *args, **kwargs):
        result = self._function(*args, **kwargs)
        return StateReturn(result)


def _attr_dict(mod_dict):
    '''
    Create a copy of the incoming dictionary with module.function and module[function]

    '''
    if not isinstance(mod_dict, dict):
        return mod_dict
    mod_dict = dict(__salt__)
    for module_func_name, mod_fun in six.iteritems(mod_dict.copy()):
        mod, fun = module_func_name.split('.', 1)
        if mod not in mod_dict:
            # create an empty object that we can add attributes to
            mod_dict[mod] = lambda: None
        setattr(mod_dict[mod], fun, mod_fun)
    return mod_dict


@pytest.fixture(scope='session')
def salt_opts():
    minion_id = 'functional-tests-minion'
    log.info('Generating functional testing minion configuration')
    root_dir = os.path.join(RUNTIME_VARS.TMP_ROOT_DIR, 'functional')
    conf_dir = os.path.join(root_dir, 'conf')
    conf_file = os.path.join(conf_dir, 'minion')

    minion_opts = salt.config._read_conf_file(os.path.join(RUNTIME_VARS.CONF_DIR, 'minion'))  # pylint: disable=protected-access
    minion_opts['id'] = minion_id
    minion_opts['conf_file'] = conf_file
    minion_opts['root_dir'] = root_dir
    minion_opts['cachedir'] = 'cache'
    minion_opts['user'] = RUNTIME_VARS.RUNNING_TESTS_USER
    minion_opts['pki_dir'] = 'pki'
    minion_opts['hosts.file'] = os.path.join(RUNTIME_VARS.TMP_ROOT_DIR, 'hosts')
    minion_opts['aliases.file'] = os.path.join(RUNTIME_VARS.TMP_ROOT_DIR, 'aliases')
    minion_opts['file_client'] = 'local'
    minion_opts['pillar_roots'] = {
        'base': [
            RUNTIME_VARS.TMP_PILLAR_TREE,
            os.path.join(RUNTIME_VARS.FILES, 'pillar', 'base'),
        ]
    }
    minion_opts['file_roots'] = {
        'base': [
            os.path.join(RUNTIME_VARS.FILES, 'file', 'base'),
            # Let's support runtime created files that can be used like:
            #   salt://my-temp-file.txt
            RUNTIME_VARS.TMP_STATE_TREE
        ],
        # Alternate root to test __env__ choices
        'prod': [
            os.path.join(RUNTIME_VARS.FILES, 'file', 'prod'),
            RUNTIME_VARS.TMP_PRODENV_STATE_TREE
        ]
    }

    # We need to copy the extension modules into the new master root_dir or
    # it will be prefixed by it
    extension_modules_path = os.path.join(root_dir, 'extension_modules')
    if not os.path.exists(extension_modules_path):
        shutil.copytree(
            os.path.join(
                RUNTIME_VARS.FILES, 'extension_modules'
            ),
            extension_modules_path
        )
    minion_opts['extension_modules'] = extension_modules_path

    # Under windows we can't seem to properly create a virtualenv off of another
    # virtualenv, we can on linux but we will still point to the virtualenv binary
    # outside the virtualenv running the test suite, if that's the case.
    try:
        real_prefix = sys.real_prefix
        # The above attribute exists, this is a virtualenv
        if salt.utils.platform.is_windows():
            virtualenv_binary = os.path.join(real_prefix, 'Scripts', 'virtualenv.exe')
        else:
            # We need to remove the virtualenv from PATH or we'll get the virtualenv binary
            # from within the virtualenv, we don't want that
            path = os.environ.get('PATH')
            if path is not None:
                path_items = path.split(os.pathsep)
                for item in path_items[:]:
                    if item.startswith(sys.base_prefix):
                        path_items.remove(item)
                os.environ['PATH'] = os.pathsep.join(path_items)
            virtualenv_binary = salt.utils.which('virtualenv')
            if path is not None:
                # Restore previous environ PATH
                os.environ['PATH'] = path
            if not virtualenv_binary.startswith(real_prefix):
                virtualenv_binary = None
        if virtualenv_binary and not os.path.exists(virtualenv_binary):
            # It doesn't exist?!
            virtualenv_binary = None
    except AttributeError:
        # We're not running inside a virtualenv
        virtualenv_binary = None
    if virtualenv_binary:
        minion_opts['venv_bin'] = virtualenv_binary

    if not os.path.exists(conf_dir):
        os.makedirs(conf_dir)

    with salt.utils.files.fopen(conf_file, 'w') as fp_:
        salt.utils.yaml.safe_dump(minion_opts, fp_, default_flow_style=False)

    log.info('Generating functional testing minion configuration completed.')
    minion_opts = salt.config.minion_config(conf_file, minion_id=minion_id)
    salt.utils.verify.verify_env(
        [
            os.path.join(minion_opts['pki_dir'], 'accepted'),
            os.path.join(minion_opts['pki_dir'], 'rejected'),
            os.path.join(minion_opts['pki_dir'], 'pending'),
            os.path.dirname(minion_opts['log_file']),
            minion_opts['extension_modules'],
            minion_opts['cachedir'],
            minion_opts['sock_dir'],
            RUNTIME_VARS.TMP_STATE_TREE,
            RUNTIME_VARS.TMP_PILLAR_TREE,
            RUNTIME_VARS.TMP_PRODENV_STATE_TREE,
            RUNTIME_VARS.TMP,
        ],
        RUNTIME_VARS.RUNNING_TESTS_USER,
        root_dir=root_dir
    )
    return minion_opts


@pytest.fixture(scope='session')
def loader_context_dictionary():
    return {}


@pytest.fixture(scope='session')
def sminion(salt_opts, loader_context_dictionary):
    log.info('Instantiating salt.minion.SMinion')
    _sminion = FunctionalMinion(salt_opts.copy(), context=loader_context_dictionary)
    for name in ('utils', 'functions', 'serializers', 'returners', 'proxy', 'states', 'rend', 'matchers', 'executors'):
        _attr_dict(getattr(_sminion, name))
    log.info('Instantiating salt.minion.SMinion completed')
    return _sminion


@pytest.fixture(autouse=True)
def __minion_loader_cleanup(sminion,
                            salt_opts,
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
    # Run tests
    yield
    # Clear the context after running the tests
    loader_context_dictionary.clear()
    # Reset the options dictionary
    salt_opts_copy = salt_opts.copy()
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
    # Make sure state.sls and state.single returns are StateReturn instances for easier comparissons
    _functions.state.sls = StateCallWrapper(_functions.state.sls)
    _functions.state.single = StateCallWrapper(_functions.state.single)
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
def _runner_client(salt_opts, loader_context_dictionary):
    _runners = salt.runner.RunnerClient(salt_opts.copy(), context=loader_context_dictionary)
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
