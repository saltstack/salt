# -*- coding: utf-8 -*-

# import Python Libs
from __future__ import absolute_import
import tempfile

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)

# Import Salt Libs
ensure_in_syspath('../../')
from salt.modules import ssh
from salt.exceptions import CommandExecutionError
import salt.utils

ssh.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SSHAuthKeyTestCase(TestCase):
    '''
    TestCase for salt.modules.ssh
    '''
    def test_expand_user_token(self):
        '''
        Test if the %u, %h, and %% tokens are correctly expanded
        '''
        output = ssh._expand_authorized_keys_path('/home/%u', 'user',
                '/home/user')
        self.assertEqual(output, '/home/user')

        output = ssh._expand_authorized_keys_path('/home/%h', 'user',
                '/home/user')
        self.assertEqual(output, '/home//home/user')

        output = ssh._expand_authorized_keys_path('%h/foo', 'user',
                '/home/user')
        self.assertEqual(output, '/home/user/foo')

        output = ssh._expand_authorized_keys_path('/srv/%h/aaa/%u%%', 'user',
                '/home/user')
        self.assertEqual(output, '/srv//home/user/aaa/user%')

        user = 'dude'
        home = '/home/dude'
        path = '/home/dude%'
        self.assertRaises(CommandExecutionError, ssh._expand_authorized_keys_path, path, user, home)

        path = '/home/%dude'
        self.assertRaises(CommandExecutionError, ssh._expand_authorized_keys_path, path, user, home)

    def test_replace_auth_key(self):
        '''
        Test the _replace_auth_key with some different authorized_keys examples
        '''
        # First test a known working example, gathered from the authorized_keys file
        # in the integration test files.
        enc = 'ssh-rsa'
        key = 'AAAAB3NzaC1yc2EAAAABIwAAAQEAq2A7hRGmdnm9tUDbO9IDSwBK6TbQa+' \
              'PXYPCPy6rbTrTtw7PHkccKrpp0yVhp5HdEIcKr6pLlVDBfOLX9QUsyCOV0wzfjIJNl' \
              'GEYsdlLJizHhbn2mUjvSAHQqZETYP81eFzLQNnPHt4EVVUh7VfDESU84KezmD5QlWp' \
              'XLmvU31/yMf+Se8xhHTvKSCZIFImWwoG6mbUoWf9nzpIoaSjB+weqqUUmpaaasXVal' \
              '72J+UX2B+2RPW3RcT0eOzQgqlJL3RKrTJvdsjE3JEAvGq3lGHSZXy28G3skua2SmVi' \
              '/w4yCE6gbODqnTWlg7+wC604ydGXA8VJiS5ap43JXiUFFAaQ=='
        options = 'command="/usr/local/lib/ssh-helper"'
        email = 'github.com'

        # Write out the authorized key to a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, mode='w+')
        temp_file.write('{0} {1} {2} {3}'.format(options, enc, key, email))
        temp_file.close()

        with patch.dict(ssh.__salt__, {'user.info': MagicMock(return_value={})}):
            with patch('salt.modules.ssh._get_config_file', MagicMock(return_value=temp_file.name)):
                ssh._replace_auth_key('foo', key, config=temp_file.name)

        # The previous authorized key should have been replaced by the simpler one
        with salt.utils.fopen(temp_file.name) as _fh:
            file_txt = _fh.read()
            self.assertIn(enc, file_txt)
            self.assertIn(key, file_txt)
            self.assertNotIn(options, file_txt)
            self.assertNotIn(email, file_txt)

        # Now test a very simple key using ecdsa instead of ssh-rsa and with multiple options
        enc = 'ecdsa-sha2-nistp256'
        key = 'abcxyz'

        with salt.utils.fopen(temp_file.name, 'a') as _fh:
            _fh.write('{0} {1}'.format(enc, key))

        # Replace the simple key from before with the more complicated options + new email
        # Option example is taken from Pull Request #39855
        options = ['no-port-forwarding', 'no-agent-forwarding', 'no-X11-forwarding',
                   'command="echo \'Please login as the user \"ubuntu\" rather than the user \"root\".\'']
        email = 'foo@example.com'

        with patch.dict(ssh.__salt__, {'user.info': MagicMock(return_value={})}):
            with patch('salt.modules.ssh._get_config_file', MagicMock(return_value=temp_file.name)):
                ret = ssh._replace_auth_key('foo', key, enc=enc, comment=email, options=options, config=temp_file.name)

        # Assert that the new line was added as-is to the file
        with salt.utils.fopen(temp_file.name) as _fh:
            file_txt = _fh.read()
            self.assertIn(enc, file_txt)
            self.assertIn(key, file_txt)
            self.assertIn('{0} '.format(','.join(options)), file_txt)
            self.assertIn(email, file_txt)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SSHAuthKeyTestCase, needs_daemon=False)
