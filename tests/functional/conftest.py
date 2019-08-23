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
import logging

# Import 3rd-party libs
import pytest
import salt.ext.six as six

# Import Salt libs
import salt.minion
import salt.config
import salt.runner
import salt.utils.files
import salt.utils.platform

# Import testing libs
from tests.support.comparables import StateReturn
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


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
    return salt.config.minion_config(conf_file, minion_id=minion_id)


@pytest.fixture(scope='session')
def loader_context_dictionary():
    return {}


@pytest.fixture(scope='session')
def _salt_minion(salt_opts, loader_context_dictionary):
    log.info('Instantiating salt.minion.SMinion')
    __salt_minion = salt.minion.SMinion(salt_opts.copy(), context=loader_context_dictionary)
    for name in ('utils', 'functions', 'serializers', 'returners', 'proxy', 'states', 'rend', 'matchers', 'executors'):
        _attr_dict(getattr(__salt_minion, name))
    log.info('Instantiating salt.minion.SMinion completed')
    return __salt_minion


@pytest.fixture(autouse=True)
def __minion_loader_cleanup(_salt_minion,
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
    _salt_minion.opts = salt_opts_copy
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
def grains(_salt_minion):
    return _salt_minion.opts['grains'].copy()


@pytest.fixture
def pillar(_salt_minion):
    return _salt_minion.opts['pillar'].copy()


@pytest.fixture
def utils(_salt_minion):
    return _salt_minion.utils


@pytest.fixture
def functions(_salt_minion):
    _functions = _salt_minion.functions
    # Make sure state.sls and state.single returns are StateReturn instances for easier comparissons
    _functions.state.sls = StateCallWrapper(_functions.state.sls)
    _functions.state.single = StateCallWrapper(_functions.state.single)
    return _functions


@pytest.fixture
def modules(functions):
    return functions


@pytest.fixture
def serializers(_salt_minion):
    return _salt_minion.serializers


@pytest.fixture
def returners(_salt_minion):
    return _salt_minion.returners


@pytest.fixture
def proxy(_salt_minion):
    return _salt_minion.proxy


@pytest.fixture
def states(_salt_minion):
    return _salt_minion.states


@pytest.fixture
def rend(_salt_minion):
    return _salt_minion.rend


@pytest.fixture
def matchers(_salt_minion):
    return _salt_minion.matchers


@pytest.fixture
def executors(_salt_minion):
    return _salt_minion.executors


@pytest.fixture
def _runner_client(salt_opts, loader_context_dictionary):
    _runners = salt.runner.RunnerClient(salt_opts.copy(), context=loader_context_dictionary)
    return _runners


@pytest.fixture
def runners(_runner_client, loader_context_dictionary):
    yield _runner_client.functions
    loader_context_dictionary.clear()


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
