# -*- coding: utf-8 -*-
'''
tests.unit.conftest
~~~~~~~~~~~~~~~~~~~

PyTest conftest for unit tests
'''

from __future__ import absolute_import, print_function, unicode_literals
import sys
import copy
import types
import functools

import salt.ext.six as six
import salt.utils.functools
from tests.support.mock import patch
from tests.support.sminion import create_sminion
import pytest


@pytest.fixture(scope='package')
def _sminion_loader_context():
    return {}


@pytest.fixture(scope='package')
def sminion_instance(_sminion_loader_context):
    return create_sminion(minion_id='pytest-mock-loader-minion', context_dict=_sminion_loader_context)


@pytest.fixture(scope='function')
def minion_config(sminion_instance):
    return copy.deepcopy(sminion_instance.opts)


@pytest.fixture(scope='function')
def salt_dunders():
    return (
        '__opts__', '__salt__', '__runner__', '__context__', '__utils__',
        '__ext_pillar__', '__thorium__', '__states__', '__serializers__', '__ret__',
        '__grains__', '__pillar__', '__sdb__',
        # Proxy is commented out on purpose since some code in salt expects a NameError
        # and is most of the time not a required dunder
        # '__proxy__'
    )


@pytest.fixture(scope='function')
def setup_loader_modules():
    return


@pytest.fixture(scope='function')
def mocked_loader(request, setup_loader_modules, salt_dunders, sminion_instance, _sminion_loader_context):
    if setup_loader_modules is None:
        # Nothing to do here
        return
    if not isinstance(setup_loader_modules, dict):
        raise RuntimeError(
            'setup_loader_modules() must return a dictionary where the keys are the '
            'modules that require loader mocking setup and the values, the global module '
            'variables for each of the module being mocked. For example \'__salt__\', '
            '\'__opts__\', etc.'
        )

    # The loader modules were actually setup
    common_module_globals = {
        '__context__': _sminion_loader_context,
        '__salt__': sminion_instance.functions,
        '__utils__': sminion_instance.utils,
        '__ret__': sminion_instance.returners,
        '__proxy__': sminion_instance.proxy,
        '__pillar__': sminion_instance.opts['pillar'],
        #'__ext_pillar__': sminion_instance.opts['pillar']['__ext_pillar__'],
        '__serializers__': sminion_instance.serializers
    }
    for module, globals_to_mock in six.iteritems(setup_loader_modules):
        if not isinstance(module, types.ModuleType):
            raise RuntimeError(
                'The dictionary keys returned by setup_loader_modules() '
                'must be an imported module, not {}'.format(
                    type(module)
                )
            )
        if not isinstance(globals_to_mock, dict):
            raise RuntimeError(
                'The dictionary values returned by setup_loader_modules() '
                'must be a dictionary, not {}'.format(
                    type(globals_to_mock)
                )
            )

        module_globals = common_module_globals.copy()
        for key in salt_dunders:
            if key not in module_globals:
                module_globals[key] = {}

        for key in globals_to_mock:
            if key == 'sys.modules':
                sys_modules = globals_to_mock[key]
                if not isinstance(sys_modules, dict):
                    raise RuntimeError(
                        '\'sys.modules\' must be a dictionary not: {}'.format(
                            type(sys_modules)
                        )
                    )
                patcher = patch.dict(sys.modules, sys_modules)
                patcher.start()

                def cleanup_sys_modules(patcher, sys_modules):
                    patcher.stop()
                    del patcher
                    del sys_modules

                request.addfinalizer(functools.partial(cleanup_sys_modules, patcher, sys_modules))
                continue
            if key not in salt_dunders:
                raise RuntimeError(
                    'Don\'t know how to handle key {}'.format(key)
                )

            mocked_details = globals_to_mock[key]
            for mock_key, mock_data in six.iteritems(mocked_details):
                module_globals[key][mock_key] = mock_data

        # Now that we're done injecting the mocked functions into module_globals,
        # those mocked functions need to be namespaced
        for key in globals_to_mock:
            mocked_details = globals_to_mock[key]
            for mock_key in mocked_details:
                mock_value = mocked_details[mock_key]
                if isinstance(mock_value, types.FunctionType):
                    module_globals[key][mock_key] = salt.utils.functools.namespaced_function(
                        mock_value,
                        module_globals,
                        preserve_context=True
                    )
                    continue
                module_globals[key][mock_key] = mock_value

        for key in module_globals:
            if not hasattr(module, key):
                if key in salt_dunders:
                    setattr(module, key, {})
                else:
                    setattr(module, key, None)
                request.addfinalizer(functools.partial(delattr, module, key))

        patcher = patch.multiple(module, **module_globals)
        patcher.start()

        def cleanup_module_globals(patcher, module_globals):
            patcher.stop()
            del patcher
            del module_globals

        request.addfinalizer(functools.partial(cleanup_module_globals, patcher, module_globals))
    request.addfinalizer(functools.partial(_sminion_loader_context.clear))


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    '''
    called after collection has been performed, may filter or re-order
    the items in-place.

    :param _pytest.main.Session session: the pytest session object
    :param _pytest.config.Config config: pytest config object
    :param List[_pytest.nodes.Item] items: list of item objects
    '''
    for item in items:
        try:
            item.module.setup_loader_modules  # pylint: disable=pointless-statement
            item.fixturenames.append('mocked_loader')
        except AttributeError:
            # This test is not using the pytest mocked loader approach
            continue
