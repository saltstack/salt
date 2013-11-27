# -*- coding: utf-8 -*-

'''
tests for pkgrepo states
'''

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import (
    destructiveTest,
    ensure_in_syspath,
)
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils


class PkgrepoTest(integration.ModuleCase,
                  integration.SaltReturnAssertsMixIn):
    '''
    pkgrepo state tests
    '''
    @destructiveTest
    @skipIf(salt.utils.is_windows(), 'minion is windows')
    def test_pkgrepo_01_managed(self):
        '''
        This is a destructive test as it adds a repository.
        '''
        ret = self.run_function('state.sls', mods='pkgrepo.managed')
        # If the below assert fails then no states were run, and the SLS in
        # tests/integration/files/file/base/pkgrepo/managed.sls needs to be
        # corrected.
        self.assertReturnNonEmptySaltType(ret)
        for state_id, state_result in ret.iteritems():
            self.assertSaltTrueReturn(dict([(state_id, state_result)]))

    @destructiveTest
    @skipIf(salt.utils.is_windows(), 'minion is windows')
    def test_pkgrepo_02_absent(self):
        '''
        This is a destructive test as it removes the repository added in the
        above test.
        '''
        ret = self.run_function('state.sls', mods='pkgrepo.absent')
        # If the below assert fails then no states were run, and the SLS in
        # tests/integration/files/file/base/pkgrepo/absent.sls needs to be
        # corrected.
        self.assertReturnNonEmptySaltType(ret)
        for state_id, state_result in ret.iteritems():
            self.assertSaltTrueReturn(dict([(state_id, state_result)]))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(PkgrepoTest)
