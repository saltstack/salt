# -*- coding: utf-8 -*-
'''
    tests.unit.utils.pkg_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the salt package objects
'''
from salttesting import TestCase
from salt.utils import pkg


class PackageTestCase(TestCase):

    def setUp(self):
        super(PackageTestCase, self).setUp()
        self.cmd_run = lambda x: x
        self.pkg_query_cmd = 'test {0}'

    def test_pkg_nonstring_input(self):
        '''
        a non-string input should result in test pkg failing
        '''
        output = pkg.find_owner(self.cmd_run,
                                self.pkg_query_cmd,
                                None)
        assert 'Error' in output

    def test_pkg_with_no_input(self):
        '''
        no paths should return an exception
        '''
        output = pkg.find_owner(self.cmd_run,
                                self.pkg_query_cmd)
        assert 'Error' in output

    def test_pkg_with_valid_input(self):
        '''
        passing in a list of strings should return a valid dictionary of path->cmd_run result
        '''
        output = pkg.find_owner(self.cmd_run,
                                self.pkg_query_cmd,
                                'foo',
                                'bar')
        assert output == {
            'foo': 'test foo',
            'bar': 'test bar'
        }

    def test_pkg_with_valid_commadelimited_input(self):
        '''
        passing in a string of comma-delimited should return a valid dictionary of path->cmd_run result
        '''
        output = pkg.find_owner(self.cmd_run,
                                self.pkg_query_cmd,
                                'foo,bar')
        assert output == {
            'foo': 'test foo',
            'bar': 'test bar'
        }

if __name__ == '__main__':
    from integration import run_tests
    run_tests(PackageTestCase, needs_daemon=False)
