# -*- coding: utf-8 -*-
'''
Tests for the service state
'''
# Import python libs
from __future__ import absolute_import
import os

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import ensure_in_syspath, destructiveTest
ensure_in_syspath('../../')

# Import salt libs
from integration import ModuleCase, SaltReturnAssertsMixIn


# used to cache the status of whether the package was installed for quick test
# skipping if it was not
PKG_INSTALLED = None


def installed(run_function, package):
    '''
    Install apache prior to running tests so that they may be skipped if the
    package fails to download
    '''
    global PKG_INSTALLED
    if not PKG_INSTALLED:
        run_function('state.single', ['pkg.installed', package])
        PKG_INSTALLED = True if run_function('pkg.version', [package]) else False
    return PKG_INSTALLED


@destructiveTest
@skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
class ServiceTest(ModuleCase,
                  SaltReturnAssertsMixIn):
    '''
    Test service state module
    '''
    def setUp(self):
        '''
        Setup package and service names
        '''
        # Taken from https://github.com/saltstack-formulas/apache-formula/blob/master/apache/map.jinja
        os_family = self.run_function('grains.get', ['os_family'])

        if os_family == 'Debian':
            self.package = 'apache2'
            self.service = 'apache2'
        elif os_family == 'RedHat':
            self.package = 'httpd'
            self.service = 'httpd'
        elif os_family == 'Suse':
            self.package = 'apache2'
            self.service = 'apache2'
        elif os_family == 'FreeBSD':
            self.package = 'apache22'
            self.service = 'apache22'
        elif os_family == 'MacOS':
            self.package = 'homebrew/apache/httpd24'
            self.service = 'org.apache.httpd'
        else:
            self.skipTest('This platform, {0}, has not yet been configured'
                          ' to run this test'.format(os_family))

    def test_aaa_setUp_package(self):
        '''
        Install apache package
        '''
        installed(self.run_function, self.package)

    def test_zzz_tearDown_package(self):
        '''
        Remove apache package
        '''
        # Skip if package was not installed
        if not PKG_INSTALLED:
            self.skipTest('Package containing service used by test was not installed')

        self.run_function('state.single', ['pkg.removed', self.package])

    def test_running(self):
        '''
        Test service.running
        '''
        # Skip test if package was not installed
        if not PKG_INSTALLED:
            self.skipTest('Package containing service used by test was not installed')

        # Configure state parameters
        state_params = [
            'service.running',
            'name={0}'.format(self.service),
        ]

        # Setup initial state, run base test and inductive test
        self.run_function('state.single', ['service.dead', self.service])
        start_ret = self.run_function('state.single', state_params)
        already_ret = self.run_function('state.single', state_params)

        # Validate base state
        self.assertSaltTrueReturn(start_ret)
        self.assertInSaltComment('Started Service {0}'.format(self.service), start_ret)
        self.assertSaltStateChangesEqual(start_ret, {self.service: True})

        # Validate inductive state
        self.assertSaltTrueReturn(already_ret)
        self.assertInSaltComment('The service {0} is already running'.format(self.service), already_ret)
        self.assertSaltStateChangesEqual(already_ret, {})

    def test_running_test(self):
        '''
        Test service.running with test=True
        '''
        # Skip test if package was not installed
        if not PKG_INSTALLED:
            self.skipTest('Package containing service used by test was not installed')

        # Configure state parameters
        state_params = [
            'service.running',
            'name={0}'.format(self.service),
            'test=True',
        ]

        # apply the state in test mode
        self.run_function('state.single', ['service.dead', self.service])
        test_ret = self.run_function('state.single', state_params)
        # Validate test state
        self.assertSaltNoneReturn(test_ret)
        self.assertInSaltComment('Service {0} is set to start'.format(self.service), test_ret)
        self.assertSaltStateChangesEqual(test_ret, {})

    def test_running_enabled(self):
        '''
        Test service.running with enable=True
        '''
        # Skip test if package was not installed
        if not PKG_INSTALLED:
            self.skipTest('Package containing service used by test was not installed')

        # Skip test if functionality not present on system
        for func in 'enable', 'enabled':
            if not self.run_function('sys.doc', ['service.{0}'.format(func)]):
                self.skipTest('service.{0} function is not available on this system'.format(func))

        # Configure state parameters
        enabled_params = [
            'service.running',
            'name={0}'.format(self.service),
            'enable=True',
        ]

        # Apply state with enable parameter True
        self.run_function('state.single', ['service.dead', self.service, 'enable=False'])
        enabled_ret = self.run_function('state.single', enabled_params)
        # Validate enabled state
        self.assertSaltTrueReturn(enabled_ret)
        self.assertInSaltComment('enabled', enabled_ret)
        self.assertSaltStateChangesEqual(enabled_ret, {self.service: True})

        # Apply state a second time with enable parameter True
        self.run_function('state.single', ['service.dead', self.service])
        already_enabled_ret = self.run_function('state.single', enabled_params)
        # Validate enabled state
        self.assertSaltTrueReturn(already_enabled_ret)
        self.assertInSaltComment('already enabled', already_enabled_ret)
        self.assertSaltStateChangesEqual(already_enabled_ret, {self.service: True})

    def test_running_disabled(self):
        '''
        Test service.running with enable=False
        '''
        # Skip test if package was not installed
        if not PKG_INSTALLED:
            self.skipTest('Package containing service used by test was not installed')

        # Skip test if functionality not present on system
        for func in 'disable', 'disabled':
            if not self.run_function('sys.doc', ['service.{0}'.format(func)]):
                self.skipTest('service.{0} function is not available on this system'.format(func))

        # Configure state parameters
        disabled_params = [
            'service.running',
            'name={0}'.format(self.service),
            'enable=False',
        ]

        # Apply state with enable parameter False
        self.run_function('state.single', ['service.dead', self.service, 'enable=True'])
        disabled_ret = self.run_function('state.single', disabled_params)
        # Validate disabled state
        self.assertSaltTrueReturn(disabled_ret)
        self.assertInSaltComment('disabled', disabled_ret)
        self.assertSaltStateChangesEqual(disabled_ret, {self.service: True})

        # Apply state a second time with enable parameter False
        self.run_function('state.single', ['service.dead', self.service])
        already_disabled_ret = self.run_function('state.single', disabled_params)
        self.assertSaltStateChangesEqual(disabled_ret, {self.service: True})
        # Validate disabled state
        self.assertSaltTrueReturn(already_disabled_ret)
        self.assertInSaltComment('already disabled', already_disabled_ret)
        self.assertSaltStateChangesEqual(already_disabled_ret, {self.service: True})

    def test_running_delayed(self):
        '''
        Test service.running with delay
        '''
        # Skip test if package was not installed
        if not PKG_INSTALLED:
            self.skipTest('Package containing service used by test was not installed')

        # Configure state parameters
        init_delay = 6.2832
        delayed_params = [
            'service.running',
            'name={0}'.format(self.service),
            'init_delay={0}'.format(init_delay)
        ]
        state_key = 'service_|-{0}_|-{0}_|-running'.format(self.service)

        # Apply state with init_delay parameter
        self.run_function('state.single', ['service.dead', self.service])
        delayed_ret = self.run_function('state.single', delayed_params)
        # Validate delayed state
        self.assertSaltTrueReturn(delayed_ret)
        self.assertInSaltComment('Delayed return for {0} seconds'.format(init_delay), delayed_ret)
        self.assertSaltStateChangesEqual(delayed_ret, {self.service: True})
        self.assertTrue(delayed_ret[state_key]['duration']/1000 >= init_delay)

    def test_dead(self):
        '''
        Test service.dead
        '''
        # Skip test if package was not installed
        if not PKG_INSTALLED:
            self.skipTest('Package containing service used by test was not installed')

        # Configure state parameters
        state_params = [
            'service.dead',
            'name={0}'.format(self.service),
        ]

        # Setup initial state, run base test and inductive test
        self.run_function('state.single', ['service.running', self.service, 'init_delay=3'])
        kill_ret = self.run_function('state.single', state_params)
        already_ret = self.run_function('state.single', state_params)

        # Validate base state
        self.assertSaltTrueReturn(kill_ret)
        self.assertInSaltComment('Service {0} was killed'.format(self.service), kill_ret)
        self.assertSaltStateChangesEqual(kill_ret, {self.service: True})

        # Validate inductive state
        self.assertSaltTrueReturn(already_ret)
        self.assertInSaltComment('The service {0} is already dead'.format(self.service), already_ret)
        self.assertSaltStateChangesEqual(already_ret, {})

    def test_dead_test(self):
        '''
        Test service.dead with test=True
        '''
        # Skip test if package was not installed
        if not PKG_INSTALLED:
            self.skipTest('Package containing service used by test was not installed')

        # Configure state parameters
        state_params = [
            'service.dead',
            'name={0}'.format(self.service),
            'test=True',
        ]

        # apply the state in test mode
        self.run_function('state.single', ['service.running', self.service, 'init_delay=3'])
        test_ret = self.run_function('state.single', state_params)
        # Validate base state
        self.assertSaltNoneReturn(test_ret)
        self.assertInSaltComment('Service {0} is set to be killed'.format(self.service), test_ret)
        self.assertSaltStateChangesEqual(test_ret, {})

    def test_dead_enabled(self):
        '''
        Test service.dead with enable=True
        '''
        # Skip test if package was not installed
        if not PKG_INSTALLED:
            self.skipTest('Package containing service used by test was not installed')

        # Skip test if functionality not present on system
        for func in 'enable', 'enabled':
            if not self.run_function('sys.doc', ['service.{0}'.format(func)]):
                self.skipTest('service.{0} function is not available on this system'.format(func))

        # Configure state parameters
        enabled_params = [
            'service.dead',
            'name={0}'.format(self.service),
            'enable=True',
        ]

        # Apply state with enable parameter True
        self.run_function('state.single', ['service.running', self.service, 'enable=False', 'init_delay=3'])
        enabled_ret = self.run_function('state.single', enabled_params)
        # Validate enabled state
        self.assertSaltTrueReturn(enabled_ret)
        self.assertInSaltComment('enabled', enabled_ret)
        self.assertSaltStateChangesEqual(enabled_ret, {self.service: True})

        # Apply state a second time with enable parameter True
        self.run_function('state.single', ['service.running', self.service, 'init_delay=3'])
        already_enabled_ret = self.run_function('state.single', enabled_params)
        # Validate enabled state
        self.assertSaltTrueReturn(already_enabled_ret)
        self.assertInSaltComment('already enabled', already_enabled_ret)
        self.assertSaltStateChangesEqual(already_enabled_ret, {self.service: True})

    def test_dead_disabled(self):
        '''
        Test service.dead with enable=False
        '''
        # Skip test if package was not installed
        if not PKG_INSTALLED:
            self.skipTest('Package containing service used by test was not installed')

        # Skip test if functionality not present on system
        for func in 'disable', 'disabled':
            if not self.run_function('sys.doc', ['service.{0}'.format(func)]):
                self.skipTest('service.{0} function is not available on this system'.format(func))

        # Configure state parameters
        disabled_params = [
            'service.dead',
            'name={0}'.format(self.service),
            'enable=False',
        ]

        # Apply state with enable parameter False
        self.run_function('state.single', ['service.running', self.service, 'enable=True', 'init_delay=3'])
        disabled_ret = self.run_function('state.single', disabled_params)
        # Validate disabled state
        self.assertSaltTrueReturn(disabled_ret)
        self.assertInSaltComment('disabled', disabled_ret)
        self.assertSaltStateChangesEqual(disabled_ret, {self.service: True})

        # Apply state a second time with enable parameter False
        self.run_function('state.single', ['service.running', self.service, 'init_delay=3'])
        already_disabled_ret = self.run_function('state.single', disabled_params)
        self.assertSaltStateChangesEqual(disabled_ret, {self.service: True})
        # Validate disabled state
        self.assertSaltTrueReturn(already_disabled_ret)
        self.assertInSaltComment('already disabled', already_disabled_ret)
        self.assertSaltStateChangesEqual(already_disabled_ret, {self.service: True})

    def test_enabled(self):
        '''
        Test service.enabled
        '''
        # Skip test if package was not installed
        if not PKG_INSTALLED:
            self.skipTest('Package containing service used by test was not installed')

        # Skip test if functionality not present on system
        for func in 'enable', 'enabled':
            if not self.run_function('sys.doc', ['service.{0}'.format(func)]):
                self.skipTest('service.{0} function is not available on this system'.format(func))

        # Configure state parameters
        state_params = [
            'service.enabled',
            'name={0}'.format(self.service),
        ]

        # Apply state
        self.run_function('state.single', ['service.disabled', self.service])
        enabled_ret = self.run_function('state.single', state_params)
        # Validate enabled state
        self.assertSaltTrueReturn(enabled_ret)
        self.assertInSaltComment('enabled', enabled_ret)
        self.assertSaltStateChangesEqual(enabled_ret, {self.service: True})

        # Apply state a second time
        already_enabled_ret = self.run_function('state.single', state_params)
        # Validate enabled state
        self.assertSaltTrueReturn(already_enabled_ret)
        self.assertInSaltComment('already enabled', already_enabled_ret)
        self.assertSaltStateChangesEqual(already_enabled_ret, {})

    def test_enabled_test(self):
        '''
        Test service.enabled with test=True
        '''
        # Skip test if package was not installed
        if not PKG_INSTALLED:
            self.skipTest('Package containing service used by test was not installed')

        # Skip test if functionality not present on system
        for func in 'enable', 'enabled':
            if not self.run_function('sys.doc', ['service.{0}'.format(func)]):
                self.skipTest('service.{0} function is not available on this system'.format(func))

        # Configure state parameters
        state_params = [
            'service.enabled',
            'name={0}'.format(self.service),
            'test=True',
        ]

        # apply the state in test mode
        self.run_function('state.single', ['service.disabled', self.service])
        test_ret = self.run_function('state.single', state_params)
        # Validate base state
        self.assertSaltNoneReturn(test_ret)
        self.assertInSaltComment('Service {0} set to be enabled'.format(self.service), test_ret)
        self.assertSaltStateChangesEqual(test_ret, {})

    def test_disabled(self):
        '''
        Test service.disabled
        '''
        # Skip test if package was not installed
        if not PKG_INSTALLED:
            self.skipTest('Package containing service used by test was not installed')

        # Skip test if functionality not present on system
        for func in 'disable', 'disabled':
            if not self.run_function('sys.doc', ['service.{0}'.format(func)]):
                self.skipTest('service.{0} function is not available on this system'.format(func))

        # Configure state parameters
        state_params = [
            'service.disabled',
            'name={0}'.format(self.service),
        ]

        # Apply state
        self.run_function('state.single', ['service.enabled', self.service])
        disabled_ret = self.run_function('state.single', state_params)
        # Validate disabled state
        self.assertSaltTrueReturn(disabled_ret)
        self.assertInSaltComment('disabled', disabled_ret)
        self.assertSaltStateChangesEqual(disabled_ret, {self.service: True})

        # Apply state a second time
        already_disabled_ret = self.run_function('state.single', state_params)
        # Validate disabled state
        self.assertSaltTrueReturn(already_disabled_ret)
        self.assertInSaltComment('already disabled', already_disabled_ret)
        self.assertSaltStateChangesEqual(already_disabled_ret, {})

    def test_disabled_test(self):
        '''
        Test service.disabled with test=True
        '''
        # Skip test if package was not installed
        if not PKG_INSTALLED:
            self.skipTest('Package containing service used by test was not installed')

        # Skip test if functionality not present on system
        for func in 'disable', 'disabled':
            if not self.run_function('sys.doc', ['service.{0}'.format(func)]):
                self.skipTest('service.{0} function is not available on this system'.format(func))

        # Configure state parameters
        state_params = [
            'service.disabled',
            'name={0}'.format(self.service),
            'test=True',
        ]

        # apply the state in test mode
        self.run_function('state.single', ['service.enabled', self.service])
        test_ret = self.run_function('state.single', state_params)
        # Validate base state
        self.assertSaltNoneReturn(test_ret)
        self.assertInSaltComment('Service {0} set to be disabled'.format(self.service), test_ret)
        self.assertSaltStateChangesEqual(test_ret, {})

    def test_mod_watch_test(self):
        '''
        Test service.mod_watch with test=True
        '''
        # Skip test if package was not installed
        if not PKG_INSTALLED:
            self.skipTest('Package containing service used by test was not installed')

        # Configure state parameters
        state_params = [
            'service.mod_watch',
            'name={0}'.format(self.service),
            'sfun=running',
            'test=True',
        ]

        # apply the state in test mode
        self.run_function('state.single', ['service.dead', self.service])
        test_ret = self.run_function('state.single', state_params)
        # Validate base state
        self.assertSaltNoneReturn(test_ret)
        self.assertInSaltComment('Service is set to be started', test_ret)
        self.assertSaltStateChangesEqual(test_ret, {})

    def test_mod_watch_no_sfun(self):
        '''
        Test service.mod_watch without sfun argument
        '''
        # Skip test if package was not installed
        if not PKG_INSTALLED:
            self.skipTest('Package containing service used by test was not installed')

        # Configure state parameters
        state_params = [
            'service.mod_watch',
            'name={0}'.format(self.service),
        ]

        # Apply the state
        mod_watch_ret = self.run_function('state.single', state_params)
        # Validate state return
        self.assertSaltFalseReturn(mod_watch_ret)
        self.assertInSaltComment('sfun must be set to either "running" or "dead"', mod_watch_ret)
        self.assertSaltStateChangesEqual(mod_watch_ret, {})

    def test_mod_watch_running(self):
        '''
        Test service.mod_watch with sfun=running
        '''
        # Skip test if package was not installed
        if not PKG_INSTALLED:
            self.skipTest('Package containing service used by test was not installed')

        # Configure state parameters
        state_params = [
            'service.mod_watch',
            'name={0}'.format(self.service),
            'sfun=running',
        ]

        # Apply state
        self.run_function('state.single', ['service.dead', self.service])
        running_ret = self.run_function('state.single', state_params)
        # Validate state return
        self.assertSaltTrueReturn(running_ret)
        self.assertInSaltComment('Service started', running_ret)
        self.assertSaltStateChangesEqual(running_ret, {self.service: True})

        # Apply state a second time
        already_running_ret = self.run_function('state.single', state_params)
        # Validate disabled state
        self.assertSaltTrueReturn(already_running_ret)
        self.assertInSaltComment('Service restarted', already_running_ret)
        self.assertSaltStateChangesEqual(already_running_ret, {self.service: True})

    def test_mod_watch_running_reload(self):
        '''
        Test service.mod_watch with sfun=running and reload=True
        '''
        # Skip test if package was not installed
        if not PKG_INSTALLED:
            self.skipTest('Package containing service used by test was not installed')

        # Skip test if functionality not present on system
        if not self.run_function('sys.doc', ['service.reload']):
            self.skipTest('service.reload function is not available on this system')

        # Configure state parameters
        state_params = [
            'service.mod_watch',
            'name={0}'.format(self.service),
            'sfun=running',
            'reload=True',
        ]

        # Apply state
        self.run_function('state.single', ['service.running', self.service, 'init_delay=3'])
        state_ret = self.run_function('state.single', state_params)
        # Validate disabled state
        self.assertSaltTrueReturn(state_ret)
        self.assertInSaltComment('Service reloaded', state_ret)
        self.assertSaltStateChangesEqual(state_ret, {self.service: True})

    def test_mod_watch_running_force(self):
        '''
        Test service.mod_watch with sfun=running and force=True
        '''
        # Skip test if package was not installed
        if not PKG_INSTALLED:
            self.skipTest('Package containing service used by test was not installed')

        # Skip test if functionality not present on system
        for func in 'reload', 'force_reload':
            if not self.run_function('sys.doc', ['service.{0}'.format(func)]):
                self.skipTest('service.{0} function is not available on this system'.format(func))

        # Configure state parameters
        state_params = [
            'service.mod_watch',
            'name={0}'.format(self.service),
            'sfun=running',
            'reload=True',
            'force=True',
        ]

        # Apply state
        self.run_function('state.single', ['service.running', self.service, 'init_delay=3'])
        state_ret = self.run_function('state.single', state_params)
        # Validate disabled state
        self.assertSaltTrueReturn(state_ret)
        self.assertInSaltComment('Service forcefully reloaded', state_ret)
        self.assertSaltStateChangesEqual(state_ret, {self.service: True})

    def test_mod_watch_running_full_restart(self):
        '''
        Test service.mod_watch with sfun=running and full_restart=True
        '''
        # Skip test if package was not installed
        if not PKG_INSTALLED:
            self.skipTest('Package containing service used by test was not installed')

        # Skip test if functionality not present on system
        if not self.run_function('sys.doc', ['service.full_restart']):
            self.skipTest('service.full_restart function is not available on this system')

        # Configure state parameters
        state_params = [
            'service.mod_watch',
            'name={0}'.format(self.service),
            'sfun=running',
            'full_restart=True',
        ]

        # Apply state
        self.run_function('state.single', ['service.running', self.service, 'init_delay=3'])
        state_ret = self.run_function('state.single', state_params)
        # Validate state return
        self.assertSaltTrueReturn(state_ret)
        self.assertInSaltComment('Service fully restarted', state_ret)
        self.assertSaltStateChangesEqual(state_ret, {self.service: True})

    def test_mod_watch_running_init_delay(self):
        '''
        Test service.mod_watch with sfun=running and init_delay
        '''
        # Skip test if package was not installed
        if not PKG_INSTALLED:
            self.skipTest('Package containing service used by test was not installed')

        # Configure state parameters
        init_delay = 6.2832
        state_params = [
            'service.mod_watch',
            'name={0}'.format(self.service),
            'sfun=running',
            'init_delay={0}'.format(init_delay),
        ]
        state_key = 'service_|-{0}_|-{0}_|-mod_watch'.format(self.service)

        # Apply state
        self.run_function('state.single', ['service.dead', self.service])
        state_ret = self.run_function('state.single', state_params)
        # Validate state return
        self.assertSaltTrueReturn(state_ret)
        self.assertInSaltComment('Service started', state_ret)
        self.assertSaltStateChangesEqual(state_ret, {self.service: True})
        self.assertTrue(state_ret[state_key]['duration']/1000 >= init_delay)

    def test_mod_watch_dead(self):
        '''
        Test service.mod_watch with sfun=dead
        '''
        # Skip test if package was not installed
        if not PKG_INSTALLED:
            self.skipTest('Package containing service used by test was not installed')

        # Configure state parameters
        state_params = [
            'service.mod_watch',
            'name={0}'.format(self.service),
            'sfun=dead',
        ]

        # Apply state
        self.run_function('state.single', ['service.running', self.service, 'init_delay=3'])
        mod_watch_ret = self.run_function('state.single', state_params)
        # Validate state return
        self.assertSaltTrueReturn(mod_watch_ret)
        self.assertInSaltComment('Service stopped', mod_watch_ret)
        self.assertSaltStateChangesEqual(mod_watch_ret, {self.service: True})

        # Apply state a second time
        already_mod_watch_ret = self.run_function('state.single', state_params)
        # Validate disabled state
        self.assertSaltTrueReturn(already_mod_watch_ret)
        self.assertInSaltComment('Service is already stopped', already_mod_watch_ret)
        self.assertSaltStateChangesEqual(already_mod_watch_ret, {})


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ServiceTest)
