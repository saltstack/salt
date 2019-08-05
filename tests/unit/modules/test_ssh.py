# -*- coding: utf-8 -*-

# import Python Libs
from __future__ import absolute_import, unicode_literals, print_function
import subprocess
import tempfile

from textwrap import dedent

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, WAR_ROOM_SKIP, TestCase
from tests.support.mock import (
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)

# Import Salt Libs
import salt.utils.files
import salt.utils.platform
import salt.modules.cmdmod as cmd
import salt.modules.ssh as ssh
from salt.exceptions import CommandExecutionError


def _mock_ssh_keyscan(*args, **kwargs):
    if 'ssh-keyscan' in args[0]:
        if '-H' in args[0]:
            return dedent('''
                # home.waynewerner.com:55555 SSH-2.0-OpenSSH_7.4p1 Raspbian-10+deb9u3
                |1|0yq63FhgFbcGawJwr7XyBPEL2Fs=|HkqTDf6bE0p2CMLHyCY7fdH5Uo0= ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDCY7tcbLrsTFPb2je3VFiH9cC9+ac04H0X8BQG7croyqvdUY5zTLmIidXJe6R1zUS7Jqpy/pXwHSB5HWpsMu+ytovPZ/LKl6AiYlcdcpS//QASb7TbcDzHFIlcdCoL5C5TOHXdRKrgIa64akuPMxvXxbgXAHjud+2jK1FhGTBbTkbrWA4xhDukWkswLpCRyHhsNzJd/seP651UDd/3rkrbgFSN9o/4LXZtsEfV3xRfJOaZq5/SW+sDVNlArFgg9EXXOzrKKWkSjS9BnN0hBaK3IyJfUAwppLYHgF0LvcNl4jF38EAU00pkNX5mknGbAFF7OMkcQI9/vkl+jaajv8Q3
                # home.waynewerner.com:55555 SSH-2.0-OpenSSH_7.4p1 Raspbian-10+deb9u3
                |1|F1wCSzHHJMMPw/DAuRJGMKeTwFk=|GKQ9FyLzHqe0n+WaWKWHzzmS5/c= ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBIOEPebJNvI/rqc0ttSuow97J6i8k3YLRF69v1GhF1+gCvM9NW1UQs1gzwB/cLPds9PuwCgyKzUxVqpP7ua41WU=
                # home.waynewerner.com:55555 SSH-2.0-OpenSSH_7.4p1 Raspbian-10+deb9u3
                |1|SZAE/yAB5UH3OOJvkU6ks1yfHO8=|lay+ajhv8yXZ9kke2j86F7RJunw= ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBGI17y+DW7z4q4r13Ewd/WnrorEwQWqaE2unjU1TS7G
            ''').lstrip()
        else:
            return dedent('''
                [example.com]:12345 ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDCY7tcbLrsTFPb2je3VFiH9cC9+ac04H0X8BQG7croyqvdUY5zTLmIidXJe6R1zUS7Jqpy/pXwHSB5HWpsMu+ytovPZ/LKl6AiYlcdcpS//QASb7TbcDzHFIlcdCoL5C5TOHXdRKrgIa64akuPMxvXxbgXAHjud+2jK1FhGTBbTkbrWA4xhDukWkswLpCRyHhsNzJd/seP651UDd/3rkrbgFSN9o/4LXZtsEfV3xRfJOaZq5/SW+sDVNlArFgg9EXXOzrKKWkSjS9BnN0hBaK3IyJfUAwppLYHgF0LvcNl4jF38EAU00pkNX5mknGbAFF7OMkcQI9/vkl+jaajv8Q3
                [example.com]:12345 ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBIOEPebJNvI/rqc0ttSuow97J6i8k3YLRF69v1GhF1+gCvM9NW1UQs1gzwB/cLPds9PuwCgyKzUxVqpP7ua41WU=
                [example.com]:12345 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBGI17y+DW7z4q4r13Ewd/WnrorEwQWqaE2unjU1TS7G
            ''').lstrip()
    else:
        return cmd.run(*args, **kwargs)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SSHAuthKeyTestCase(TestCase, LoaderModuleMockMixin):
    '''
    TestCase for salt.modules.ssh
    '''
    def setup_loader_modules(self):
        return {
            ssh: {
                '__salt__': {
                    'user.info': lambda u: getattr(self, 'user_info_mock', None),
                }
            }
        }

    def tearDown(self):
        try:
            delattr(self, 'user_info_mock')
        except AttributeError:
            pass

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

    def test_set_auth_key_invalid(self):
        self.user_info_mock = {'home': '/dev/null'}
        # Inserting invalid public key should be rejected
        invalid_key = 'AAAAB3NzaC1kc3MAAACBAL0sQ9fJ5bYTEyY'  # missing padding
        self.assertEqual(ssh.set_auth_key('user', invalid_key), 'Invalid public key')

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
        empty_line = '\n'
        comment_line = '# this is a comment\n'

        # Write out the authorized key to a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, mode='w+')
        temp_file.close()

        with salt.utils.files.fopen(temp_file.name, 'w') as _fh:
            # Add comment
            _fh.write(comment_line)
            # Add empty line for #41335
            _fh.write(empty_line)
            _fh.write('{0} {1} {2} {3}'.format(options, enc, key, email))

        with patch.dict(ssh.__salt__, {'user.info': MagicMock(return_value={})}):
            with patch('salt.modules.ssh._get_config_file', MagicMock(return_value=temp_file.name)):
                ssh._replace_auth_key('foo', key, config=temp_file.name)

        # The previous authorized key should have been replaced by the simpler one
        with salt.utils.files.fopen(temp_file.name) as _fh:
            file_txt = salt.utils.stringutils.to_unicode(_fh.read())
            self.assertIn(enc, file_txt)
            self.assertIn(key, file_txt)
            self.assertNotIn(options, file_txt)
            self.assertNotIn(email, file_txt)

        # Now test a very simple key using ecdsa instead of ssh-rsa and with multiple options
        enc = 'ecdsa-sha2-nistp256'
        key = 'abcxyz'

        with salt.utils.files.fopen(temp_file.name, 'a') as _fh:
            _fh.write(salt.utils.stringutils.to_str('{0} {1}'.format(enc, key)))

        # Replace the simple key from before with the more complicated options + new email
        # Option example is taken from Pull Request #39855
        options = ['no-port-forwarding', 'no-agent-forwarding', 'no-X11-forwarding',
                   'command="echo \'Please login as the user \"ubuntu\" rather than the user \"root\".\'']
        email = 'foo@example.com'

        with patch.dict(ssh.__salt__, {'user.info': MagicMock(return_value={})}):
            with patch('salt.modules.ssh._get_config_file', MagicMock(return_value=temp_file.name)):
                ssh._replace_auth_key('foo', key, enc=enc, comment=email, options=options, config=temp_file.name)

        # Assert that the new line was added as-is to the file
        with salt.utils.files.fopen(temp_file.name) as _fh:
            file_txt = salt.utils.stringutils.to_unicode(_fh.read())
            self.assertIn(enc, file_txt)
            self.assertIn(key, file_txt)
            self.assertIn('{0} '.format(','.join(options)), file_txt)
            self.assertIn(email, file_txt)
            self.assertIn(empty_line, file_txt)
            self.assertIn(comment_line, file_txt)

    @skipIf(WAR_ROOM_SKIP, 'WAR ROOM TEMPORARY SKIP')
    @skipIf(not salt.utils.path.which('ssh-keyscan'), 'ssh-keyscan not installed')
    def test_recv_known_hosts_hashed_shoud_be_findable_by_ssh_keygen(self):
        hostname = 'example.com'
        port = 12345
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
            with patch.dict(ssh.__salt__, {'cmd.run': MagicMock(side_effect=_mock_ssh_keyscan)}):
                entries = ssh.recv_known_host_entries(
                    hostname=hostname,
                    port=port,
                    hash_known_hosts=True,
                )
                for entry in entries:
                    print(
                        '{0[hostname]} {0[enc]} {0[key]}'.format(entry),
                        file=temp_file,
                    )
                temp_file.flush()
                result = subprocess.check_output([
                    'ssh-keygen',
                    '-f',
                    temp_file.name,
                    '-F',
                    '[{hostname}]:{port}'.format(hostname=hostname, port=port),
                ])

    @skipIf(True, 'SKIP FAILING TESTS - 4 - 8/5/2019')
    @skipIf(WAR_ROOM_SKIP, 'WAR ROOM TEMPORARY SKIP')
    def test_recv_known_hosts_hashed_should_return_hashed_hostnames(self):
        hostname = 'example.com'
        port = 12345
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
            with patch.dict(ssh.__salt__, {'cmd.run': MagicMock(side_effect=_mock_ssh_keyscan)}):
                entries = ssh.recv_known_host_entries(
                    hostname=hostname,
                    port=port,
                    hash_known_hosts=True,
                )
                hostnames = [e.get('hostname') for e in entries]
                # We better have *some* hostnames, or the next test is
                # irrelevant
                self.assertTrue(bool(hostnames))
                bad_hostnames = [h for h in hostnames if h.startswith(hostname)]
                self.assertFalse(bool(bad_hostnames), bad_hostnames)
