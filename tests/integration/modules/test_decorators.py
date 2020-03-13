# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.case import ModuleCase

import pytest


@pytest.mark.windows_whitelisted
class DecoratorTest(ModuleCase):
    def test_module(self):
        assert self.run_function(
                    'runtests_decorators.working_function'
                    )

    def test_depends(self):
        ret = self.run_function('runtests_decorators.depends')
        assert isinstance(ret, dict)
        assert ret['ret']
        assert isinstance(ret['time'], float)

    def test_missing_depends(self):
        assert {'runtests_decorators.missing_depends_will_fallback': None,
                 'runtests_decorators.missing_depends': "'runtests_decorators.missing_depends' is not available."} == \
                self.run_function('runtests_decorators.missing_depends'
                    )

    def test_bool_depends(self):
        # test True
        assert self.run_function(
                    'runtests_decorators.booldependsTrue'
                    )

        # test False
        assert 'is not available' in \
                self.run_function('runtests_decorators.booldependsFalse'
                    )

    def test_depends_will_not_fallback(self):
        ret = self.run_function('runtests_decorators.depends_will_not_fallback')
        assert isinstance(ret, dict)
        assert ret['ret']
        assert isinstance(ret['time'], float)

    def test_missing_depends_will_fallback(self):
        assert [False, 'fallback'] == \
                self.run_function(
                    'runtests_decorators.missing_depends_will_fallback'
                    )

    def test_command_success_retcode(self):
        ret = self.run_function('runtests_decorators.command_success_retcode')
        assert ret is True

    def test_command_failure_retcode(self):
        ret = self.run_function('runtests_decorators.command_failure_retcode')
        assert ret == \
            "'runtests_decorators.command_failure_retcode' is not available."

    def test_command_success_nonzero_retcode_true(self):
        ret = self.run_function('runtests_decorators.command_success_nonzero_retcode_true')
        assert ret is True

    def test_command_failure_nonzero_retcode_true(self):
        ret = self.run_function('runtests_decorators.command_failure_nonzero_retcode_true')
        assert ret == \
            "'runtests_decorators.command_failure_nonzero_retcode_true' is not available."

    def test_command_success_nonzero_retcode_false(self):
        ret = self.run_function('runtests_decorators.command_success_nonzero_retcode_false')
        assert ret is True

    def test_command_failure_nonzero_retcode_false(self):
        ret = self.run_function('runtests_decorators.command_failure_nonzero_retcode_false')
        assert ret == \
            "'runtests_decorators.command_failure_nonzero_retcode_false' is not available."

    def test_versioned_depend_insufficient(self):
        assert 'is not available' in \
            self.run_function('runtests_decorators.version_depends_false')

    def test_versioned_depend_sufficient(self):
        assert self.run_function('runtests_decorators.version_depends_true')

    def test_versioned_depend_versionless(self):
        assert self.run_function('runtests_decorators.version_depends_versionless_true')
