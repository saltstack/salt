'''
tests for user state
user absent
user present
user present with custom homedir
'''
import os
from saltunittest import skipIf, destructiveTest
import integration
import grp


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

    def test_user_if_present_with_gid(self):
        # TODO:dc fix failing test. Exception in ret
        ret = self.run_state('user.present', name='nobody', gid="nobody")
        result = ret[next(iter(ret))]['result']
        self.assertTrue(result)

    @destructiveTest
    @skipIf(os.geteuid() is not 0, 'you must be this root to run this test')
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

    @destructiveTest
    @skipIf(os.geteuid() is not 0, 'you must be this root to run this test')
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

    @destructiveTest
    @skipIf(os.geteuid() is not 0, 'you must be this root to run this test')
    def test_user_present_gid_from_name_default(self):
        """
        This is a DESTRUCTIVE TEST it creates a new user on the on the minion.
        This is an integration test. Not all systems will automatically create
        a group of the same name as the user, but I don't have access to any.
        If you run the test and it fails, please fix the code it's testing to
        work on your operating system.
        """
        ret = self.run_state('user.present', name='salt_test',
                             gid_from_name=True, home='/var/lib/salt_test')
        gid = self.run_function('user.info', ['salt_test'])['gid']
        result = ret[next(iter(ret))]['result']
        group_name = grp.getgrgid(gid).gr_name
        self.assertTrue(result)
        self.assertTrue(os.stat('/var/lib/salt_test'))
        self.assertTrue(group_name == 'salt_test')
        ret = self.run_state('user.absent', name='salt_test')

    @destructiveTest
    @skipIf(os.geteuid() is not 0, 'you must be this root to run this test')
    def test_user_present_gid_from_name(self):
        """
        This is a DESTRUCTIVE TEST it creates a new user on the on the minion.
        This is a unit test, NOT an integration test. We create a group of the
        same name as the user beforehand, so it should all run smoothly.
        """
        ret = self.run_state('group.present', name='salt_test')
        ret = self.run_state('user.present', name='salt_test',
                             gid_from_name=True, home='/var/lib/salt_test')
        gid = self.run_function('user.info', ['salt_test'])['gid']
        result = ret[next(iter(ret))]['result']
        group_name = grp.getgrgid(gid).gr_name
        self.assertTrue(result)
        self.assertTrue(os.stat('/var/lib/salt_test'))
        self.assertTrue(group_name == 'salt_test')
        ret = self.run_state('user.absent', name='salt_test')
        ret = self.run_state('group.absent', name='salt_test')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(UserTest)
