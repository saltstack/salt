'''
tests for user state
user absent
user present
user present with custom homedir
'''
import os

from saltunittest import TestLoader, TextTestRunner, skipIf
import integration
from integration import TestDaemon


class UserTest(integration.ModuleCase):
    '''
    test for user absent
    '''
    def test_user_absent(self):
        ret = self.run_state('user.absent', name='unpossible')
        result = ret[next(iter(ret))]['result']
        self.assertTrue(result)

    def test_user_if_present(self):
        ret = self.run_state('user.present', name='nobody') 
        result = ret[next(iter(ret))]['result']
        self.assertTrue(result)

    @skipIf(not (os.geteuid()==0),'you must be this root to run this test')
    def test_user_not_present(self):
        """
        This is a DESTRUCTIVE TEST it creates a new user on the minion.
        And then destroys that user.
        Assume that it will break any system you run it on.
        """
        ret = self.run_state('user.present', name='salt_test') 
        result = ret[next(iter(ret))]['result']
        self.assertTrue(result)
        ret = self.run_state('user.absent', name='salt_test')

    @skipIf(not (os.geteuid()==0), 'you must be this root to run this test')
    def test_user_present_nondefault(self):
        """
        This is a DESTRUCTIVE TEST it creates a new user on the on the minion.
        """
        ret = self.run_state('user.present', name='salt_test',
                             home='/var/lib/salt_test') 
        result = ret[next(iter(ret))]['result']
        self.assertTrue(result)
        self.assertTrue(os.stat('/var/lib/salt_test'))
        ret = self.run_state('user.absent', name='salt_test')

