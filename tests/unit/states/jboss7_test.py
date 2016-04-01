# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt testing libs
from salttesting.unit import skipIf, TestCase
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import Salt libs
from salt.states import jboss7
from salt.exceptions import CommandExecutionError

# Import 3rd-party libs
import salt.ext.six as six

try:
    # will pass if executed along with other tests
    __salt__
except NameError:
    from salt.ext.six.moves import builtins as __builtin__
    # if executed separately we need to export __salt__ dictionary ourselves
    __builtin__.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class JBoss7StateTestCase(TestCase):

    org_module_functions = {}

    def __save_module_functions(self):
        for name, val in six.iteritems(jboss7.__dict__):
            if callable(val):
                self.org_module_functions[name] = val

    def __restore_module_functions(self):
        for name, val in six.iteritems(self.org_module_functions):
            jboss7.__dict__[name] = val

    def setUp(self):
        self.__save_module_functions()
        __salt__['jboss7.read_datasource'] = MagicMock()
        __salt__['jboss7.create_datasource'] = MagicMock()
        __salt__['jboss7.update_datasource'] = MagicMock()
        __salt__['jboss7.remove_datasource'] = MagicMock()
        __salt__['jboss7.remove_datasource'] = MagicMock()
        __salt__['jboss7.read_simple_binding'] = MagicMock()
        __salt__['jboss7.create_simple_binding'] = MagicMock()
        __salt__['jboss7.update_simple_binding'] = MagicMock()

    def tearDown(self):
        self.__restore_module_functions()

    def test_should_create_new_datasource_if_not_exists(self):
        # given
        datasource_properties = {'connection-url': 'jdbc:/old-connection-url'}
        ds_status = {'created': False}

        def read_func(jboss_config, name):
            if ds_status['created']:
                return {'success': True, 'result': datasource_properties}
            else:
                return {'success': False, 'err_code': 'JBAS014807'}

        def create_func(jboss_config, name, datasource_properties):
            ds_status['created'] = True
            return {'success': True}

        __salt__['jboss7.read_datasource'] = MagicMock(side_effect=read_func)
        __salt__['jboss7.create_datasource'] = MagicMock(side_effect=create_func)

        # when
        result = jboss7.datasource_exists(name='appDS', jboss_config={}, datasource_properties=datasource_properties)

        # then
        __salt__['jboss7.create_datasource'].assert_called_with(name='appDS', jboss_config={}, datasource_properties=datasource_properties)
        self.assertFalse(__salt__['jboss7.update_datasource'].called)
        self.assertEqual(result['comment'], 'Datasource created.')

    def test_should_update_the_datasource_if_exists(self):
        ds_status = {'updated': False}

        def read_func(jboss_config, name):
            if ds_status['updated']:
                return {'success': True, 'result': {'connection-url': 'jdbc:/new-connection-url'}}
            else:
                return {'success': True, 'result': {'connection-url': 'jdbc:/old-connection-url'}}

        def update_func(jboss_config, name, new_properties):
            ds_status['updated'] = True
            return {'success': True}

        __salt__['jboss7.read_datasource'] = MagicMock(side_effect=read_func)
        __salt__['jboss7.update_datasource'] = MagicMock(side_effect=update_func)

        result = jboss7.datasource_exists(name='appDS', jboss_config={}, datasource_properties={'connection-url': 'jdbc:/new-connection-url'})

        __salt__['jboss7.update_datasource'].assert_called_with(name='appDS', jboss_config={}, new_properties={'connection-url': 'jdbc:/new-connection-url'})
        self.assertFalse(__salt__['jboss7.create_datasource'].called)
        self.assertEqual(result['comment'], 'Datasource updated.')

    def test_should_recreate_the_datasource_if_specified(self):
        __salt__['jboss7.remove_datasource'].return_value = {
            'success': True
        }
        __salt__['jboss7.read_datasource'].return_value = {
            'success': True,
            'result': {'connection-url': 'jdbc:/same-connection-url'}
        }
        __salt__['jboss7.create_datasource'].return_value = {
            'success': True
        }

        result = jboss7.datasource_exists(name='appDS', jboss_config={}, datasource_properties={'connection-url': 'jdbc:/same-connection-url'}, recreate=True)

        __salt__['jboss7.remove_datasource'].assert_called_with(name='appDS', jboss_config={})
        __salt__['jboss7.create_datasource'].assert_called_with(name='appDS', jboss_config={}, datasource_properties={'connection-url': 'jdbc:/same-connection-url'})
        self.assertEqual(result['changes']['removed'], 'appDS')
        self.assertEqual(result['changes']['created'], 'appDS')

    def test_should_inform_if_the_datasource_has_not_changed(self):
        __salt__['jboss7.read_datasource'].return_value = {
            'success': True,
            'result': {'connection-url': 'jdbc:/old-connection-url'}
        }
        __salt__['jboss7.update_datasource'].return_value = {
            'success': True
        }

        result = jboss7.datasource_exists(name='appDS', jboss_config={}, datasource_properties={'connection-url': 'jdbc:/old-connection-url'})

        __salt__['jboss7.update_datasource'].assert_called_with(name='appDS', jboss_config={}, new_properties={'connection-url': 'jdbc:/old-connection-url'})
        self.assertFalse(__salt__['jboss7.create_datasource'].called)
        self.assertEqual(result['comment'], 'Datasource not changed.')

    def test_should_create_binding_if_not_exists(self):
        # given
        binding_status = {'created': False}

        def read_func(jboss_config, binding_name):
            if binding_status['created']:
                return {'success': True, 'result': {'value': 'DEV'}}
            else:
                return {'success': False, 'err_code': 'JBAS014807'}

        def create_func(jboss_config, binding_name, value):
            binding_status['created'] = True
            return {'success': True}

        __salt__['jboss7.read_simple_binding'] = MagicMock(side_effect=read_func)
        __salt__['jboss7.create_simple_binding'] = MagicMock(side_effect=create_func)

        # when
        result = jboss7.bindings_exist(name='bindings', jboss_config={}, bindings={'env': 'DEV'})

        # then
        __salt__['jboss7.create_simple_binding'].assert_called_with(jboss_config={}, binding_name='env', value='DEV')
        self.assertEqual(__salt__['jboss7.update_simple_binding'].call_count, 0)
        self.assertEqual(result['changes'], {'added': 'env:DEV\n'})
        self.assertEqual(result['comment'], 'Bindings changed.')

    def test_should_update_bindings_if_exists_and_different(self):
        # given
        binding_status = {'updated': False}

        def read_func(jboss_config, binding_name):
            if binding_status['updated']:
                return {'success': True, 'result': {'value': 'DEV2'}}
            else:
                return {'success': True, 'result': {'value': 'DEV'}}

        def update_func(jboss_config, binding_name, value):
            binding_status['updated'] = True
            return {'success': True}

        __salt__['jboss7.read_simple_binding'] = MagicMock(side_effect=read_func)
        __salt__['jboss7.update_simple_binding'] = MagicMock(side_effect=update_func)

        # when
        result = jboss7.bindings_exist(name='bindings', jboss_config={}, bindings={'env': 'DEV2'})

        # then
        __salt__['jboss7.update_simple_binding'].assert_called_with(jboss_config={}, binding_name='env', value='DEV2')
        self.assertEqual(__salt__['jboss7.create_simple_binding'].call_count, 0)
        self.assertEqual(result['changes'], {'changed': 'env:DEV->DEV2\n'})
        self.assertEqual(result['comment'], 'Bindings changed.')

    def test_should_not_update_bindings_if_same(self):
        # given
        __salt__['jboss7.read_simple_binding'].return_value = {'success': True, 'result': {'value': 'DEV2'}}

        # when
        result = jboss7.bindings_exist(name='bindings', jboss_config={}, bindings={'env': 'DEV2'})

        # then
        self.assertEqual(__salt__['jboss7.create_simple_binding'].call_count, 0)
        self.assertEqual(__salt__['jboss7.update_simple_binding'].call_count, 0)
        self.assertEqual(result['changes'], {})
        self.assertEqual(result['comment'], 'Bindings not changed.')

    def test_should_raise_exception_if_cannot_create_binding(self):
        def read_func(jboss_config, binding_name):
            return {'success': False, 'err_code': 'JBAS014807'}

        def create_func(jboss_config, binding_name, value):
            return {'success': False, 'failure-description': 'Incorrect binding name.'}

        __salt__['jboss7.read_simple_binding'] = MagicMock(side_effect=read_func)
        __salt__['jboss7.create_simple_binding'] = MagicMock(side_effect=create_func)

        # when
        try:
            jboss7.bindings_exist(name='bindings', jboss_config={}, bindings={'env': 'DEV2'})
            self.fail('An exception should be thrown')
        except CommandExecutionError as e:
            self.assertEqual(str(e), 'Incorrect binding name.')

    def test_should_raise_exception_if_cannot_update_binding(self):
        def read_func(jboss_config, binding_name):
            return {'success': True, 'result': {'value': 'DEV'}}

        def update_func(jboss_config, binding_name, value):
            return {'success': False, 'failure-description': 'Incorrect binding name.'}

        __salt__['jboss7.read_simple_binding'] = MagicMock(side_effect=read_func)
        __salt__['jboss7.update_simple_binding'] = MagicMock(side_effect=update_func)

        # when
        try:
            jboss7.bindings_exist(name='bindings', jboss_config={}, bindings={'env': '!@#!///some weird value'})
            self.fail('An exception should be thrown')
        except CommandExecutionError as e:
            self.assertEqual(str(e), 'Incorrect binding name.')
