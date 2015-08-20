# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Tarjei Husøy <git@thusoy.com>`
'''

# Import Salt Testing Libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import git


class GitTestCase(TestCase):
    '''
    TestCase for salt.modules.git module
    '''

    def test_http_basic_authentication(self):
        '''
            Test that HTTP Basic auth works as intended.
        '''
        # ((user, pass), expected) tuples
        test_inputs = [
            ((None, None), 'https://example.com'),
            (('user', None), 'https://user@example.com'),
            (('user', 'pass'), 'https://user:pass@example.com'),
        ]
        for (user, password), expected in test_inputs:
            kwargs = {
                'https_user': user,
                'https_pass': password,
                'repository': 'https://example.com',
            }
            result = git._add_http_basic_auth(**kwargs)
            self.assertEqual(result, expected)

    def test_https_user_and_pw_is_confidential(self):
        sensitive_outputs = (
            'https://deadbeaf@example.com',
            'https://user:pw@example.com',
        )
        sanitized = 'https://<redacted>@example.com'
        for sensitive_output in sensitive_outputs:
            result = git._remove_sensitive_data(sensitive_output)
            self.assertEqual(result, sanitized)

    def test_git_ssh_user_is_not_treated_as_sensitive(self):
        not_sensitive_outputs = (
            'ssh://user@example.com',
        )
        for not_sensitive_output in not_sensitive_outputs:
            result = git._remove_sensitive_data(not_sensitive_output)
            self.assertEqual(result, not_sensitive_output)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(GitTestCase, needs_daemon=False)
