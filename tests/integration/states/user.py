'''
tests for user state
user absent
user present
user present with custom homedir
'''

from saltunittest import TestLoader, TextTestRunner
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

#    def test_user_present(self):

#    def test_user_present_nondefault(self):

       
