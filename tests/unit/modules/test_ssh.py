# -*- coding: utf-8 -*-

# import Python Libs
from __future__ import absolute_import
import tempfile

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)

# Import Salt Libs
import salt.utils
import salt.modules.cmdmod
import salt.modules.ssh as ssh
from salt.exceptions import CommandExecutionError


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
        comment_line = '# this is a comment \n'

        # Write out the authorized key to a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, mode='w+')
        temp_file.close()

        with salt.utils.fopen(temp_file.name, 'w') as _fh:
            # Add comment
            _fh.write(comment_line)
            # Add empty line for #41335
            _fh.write(empty_line)
            _fh.write('{0} {1} {2} {3}'.format(options, enc, key, email))

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
                ssh._replace_auth_key('foo', key, enc=enc, comment=email, options=options, config=temp_file.name)

        # Assert that the new line was added as-is to the file
        with salt.utils.fopen(temp_file.name) as _fh:
            file_txt = _fh.read()
            self.assertIn(enc, file_txt)
            self.assertIn(key, file_txt)
            self.assertIn('{0} '.format(','.join(options)), file_txt)
            self.assertIn(email, file_txt)
            self.assertIn(empty_line, file_txt)
            self.assertIn(comment_line, file_txt)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SSHKnownHostTestCase(TestCase, LoaderModuleMockMixin):
    '''
    TestCase for salt.modules.ssh
    '''
    def setup_loader_modules(self):
        return {
            ssh: {
                '__salt__': {
                    'ssh.hash_known_hosts': ssh.hash_known_hosts,
                }
            }
        }

    def setUp(self):
        temp_file = tempfile.NamedTemporaryFile(delete=False, mode='w+')
        temp_file.close()

        self.temp_file_name = temp_file.name
        self.key = 'AAAAB3NzaC1yc2EAAAABIwAAAQEAq2A7hRGmdnm9tUDbO9IDSwBK6TbQa+PXYPCPy6' \
                   'rbTrTtw7PHkccKrpp0yVhp5HdEIcKr6pLlVDBfOLX9QUsyCOV0wzfjIJNlGEYsdlLJ' \
                   'izHhbn2mUjvSAHQqZETYP81eFzLQNnPHt4EVVUh7VfDESU84KezmD5QlWpXLmvU31/' \
                   'yMf+Se8xhHTvKSCZIFImWwoG6mbUoWf9nzpIoaSjB+weqqUUmpaaasXVal72J+UX2B' \
                   '+2RPW3RcT0eOzQgqlJL3RKrTJvdsjE3JEAvGq3lGHSZXy28G3skua2SmVi/w4yCE6g' \
                   'bODqnTWlg7+wC604ydGXA8VJiS5ap43JXiUFFAaQ=='
        self.fingerprints = {
            'md5': '16:27:ac:a5:76:28:2d:36:63:1b:56:4d:eb:df:a6:48',
            'sha256': 'nThbg6kXUpJWGl7E1IGOCspRomTxdCARLviKw6E5SY8',
            'sha256_': '9d:38:5b:83:a9:17:52:92:56:1a:5e:c4:d4:81:8e:0a:' \
                       'ca:51:a2:64:f1:74:20:11:2e:f8:8a:c3:a1:39:49:8f'
        }


    def tearDown(self):
        salt.utils.safe_rm(self.temp_file_name)
        try:
            delattr(self, 'fingerprints')
            delattr(self, 'temp_file_name')
            delattr(self, 'key')
        except AttributeError:
            pass


    def cmd_run_side_effect(self, *args, **kwargs):
        if args[0][0] == 'ssh-keyscan':
            return '# github.com:22 SSH-2.0-libssh_0.7.0\n' \
                   '|1|UFlpWi7zJTnF3YR5VBgJiJ3tXGo=|4uqGHkc2vi2fQ7OEZThf5ncFPDs= ' \
                   'ssh-rsa ' + self.key
        else:
            return salt.modules.cmdmod.run(*args, **kwargs)

    def test_set_known_host(self):
        user = 'root'
        hostname = 'github.com'
        enc = 'ssh-rsa'
        config = self.temp_file_name
        fingerprints = self.fingerprints
        user_info_mock = MagicMock(return_value={'home': '/dev/null'})
        ssh_keyscan_mock = MagicMock(side_effect = self.cmd_run_side_effect)

        values = {
            'user.info': user_info_mock,
            'cmd.run': ssh_keyscan_mock
        }

        expect_result = {
            'old': None,
            'new': {
                'enc': 'ssh-rsa',
                'key': self.key,
                'fingerprint': '',
                'hostname': '|1|UFlpWi7zJTnF3YR5VBgJiJ3tXGo=|4uqGHkc2vi2fQ7OEZThf5ncFPDs='
            },
            'status': 'updated'
        }
        for hash_type in ['md5', 'sha256']:
            with patch.dict(ssh.__salt__, values):
                expect_result['new']['fingerprint'] = fingerprints[hash_type if hash_type == 'md5' else 'sha256_']
                ret = ssh.set_known_host(user=user,
                                    hostname=hostname,
                                    fingerprint=fingerprints[hash_type],
                                    enc=enc,
                                    config=config,
                                    fingerprint_hash_type=hash_type)
                self.assertDictEqual(expect_result, ret)

                expect_result_2 = {'status': 'exists', 'key': self.key}
                ret = ssh.set_known_host(user=user,
                                    hostname=hostname,
                                    key=self.key,
                                    enc=enc,
                                    config=config,
                                    fingerprint_hash_type=hash_type)
                self.assertDictEqual(expect_result_2, ret)

                ret = ssh.set_known_host(user=user,
                                    hostname=hostname,
                                    fingerprint=fingerprints[hash_type],
                                    enc=enc,
                                    config=config,
                                    fingerprint_hash_type=hash_type)
                self.assertDictEqual(expect_result_2, ret)

                with salt.utils.fopen(self.temp_file_name, 'rb+') as seek_fh:
                    seek_fh.truncate(0)

    def test_check_known_host(self):
        user = 'root'
        hostname = 'github.com'
        enc = 'ssh-rsa'
        config = self.temp_file_name
        fingerprints = self.fingerprints
        user_info_mock = MagicMock(return_value={'home': '/dev/null'})
        ssh_keyscan_mock = MagicMock(side_effect = self.cmd_run_side_effect)

        values = {
            'user.info': user_info_mock,
            'cmd.run': ssh_keyscan_mock
        }

        for hash_type in ['md5', 'sha256']:
            with patch.dict(ssh.__salt__, values):
                ret = ssh.check_known_host(user=user,
                                    hostname=hostname,
                                    fingerprint=fingerprints[hash_type],
                                    config=config,
                                    fingerprint_hash_type=hash_type)
                self.assertEqual('add', ret)

                ret = ssh.check_known_host(user=user,
                                    hostname=hostname,
                                    key=self.key,
                                    config=config,
                                    fingerprint_hash_type=hash_type)
                self.assertEqual('add', ret)

                ret = ssh.set_known_host(user=user,
                                    hostname=hostname,
                                    key=self.key,
                                    fingerprint=fingerprints[hash_type],
                                    enc=enc,
                                    config=config,
                                    fingerprint_hash_type=hash_type)

                ret = ssh.check_known_host(user=user,
                                    hostname=hostname,
                                    fingerprint=fingerprints[hash_type],
                                    config=config,
                                    fingerprint_hash_type=hash_type)
                self.assertEqual('exists', ret)

                ret = ssh.check_known_host(user=user,
                                    hostname=hostname,
                                    key=self.key,
                                    config=config,
                                    fingerprint_hash_type=hash_type)
                self.assertEqual('exists', ret)

                ret = ssh.check_known_host(user=user,
                                    hostname=hostname,
                                    fingerprint=fingerprints[hash_type] + ':11',
                                    config=config,
                                    fingerprint_hash_type=hash_type)
                self.assertEqual('update', ret)

                with salt.utils.fopen(self.temp_file_name, 'rb+') as seek_fh:
                    seek_fh.truncate(0)
