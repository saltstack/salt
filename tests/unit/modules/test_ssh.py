import tempfile

import salt.modules.ssh as ssh
import salt.utils.files
import salt.utils.platform
from salt.exceptions import CommandExecutionError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class SSHAuthKeyTestCase(TestCase, LoaderModuleMockMixin):
    """
    TestCase for salt.modules.ssh
    """

    def setup_loader_modules(self):
        return {
            ssh: {
                "__salt__": {
                    "user.info": lambda u: getattr(self, "user_info_mock", None),
                }
            }
        }

    def tearDown(self):
        try:
            delattr(self, "user_info_mock")
        except AttributeError:
            pass

    def test_expand_user_token(self):
        """
        Test if the %u, %h, and %% tokens are correctly expanded
        """
        output = ssh._expand_authorized_keys_path("/home/%u", "user", "/home/user")
        self.assertEqual(output, "/home/user")

        output = ssh._expand_authorized_keys_path("/home/%h", "user", "/home/user")
        self.assertEqual(output, "/home//home/user")

        output = ssh._expand_authorized_keys_path("%h/foo", "user", "/home/user")
        self.assertEqual(output, "/home/user/foo")

        output = ssh._expand_authorized_keys_path(
            "/srv/%h/aaa/%u%%", "user", "/home/user"
        )
        self.assertEqual(output, "/srv//home/user/aaa/user%")

        user = "dude"
        home = "/home/dude"
        path = "/home/dude%"
        self.assertRaises(
            CommandExecutionError, ssh._expand_authorized_keys_path, path, user, home
        )

        path = "/home/%dude"
        self.assertRaises(
            CommandExecutionError, ssh._expand_authorized_keys_path, path, user, home
        )

    def test_set_auth_key_invalid(self):
        self.user_info_mock = {"home": "/dev/null"}
        # Inserting invalid public key should be rejected
        invalid_key = "AAAAB3NzaC1kc3MAAACBAL0sQ9fJ5bYTEyY"  # missing padding
        self.assertEqual(ssh.set_auth_key("user", invalid_key), "Invalid public key")

    def test_set_auth_key_sk_ed25519_cert(self):
        self.user_info_mock = {"home": "/dev/null"}
        valid_key = (
            "AAAAI3NrLXNzaC1lZDI1NTE5LWNlcnQtdjAxQG9wZW5zc2guY29tAAAAIPMSTMKu"
            "DdipIQl8IA3UXl5WHYcIyF2tfwrri/Wd/oV3AAAAIKuzsywoer6Y7oYtLXse/TKj"
            "VqqKjEpUq+4zMkQ9FEwJAAAABHNzaDoAAAAAAAAAAAAAAAEAAAARbWF4QHNjaHUg"
            "dXNlciBrZXkAAAAHAAAAA21heAAAAABgGcIwAAAAAHLlxlwAAAAAAAAAggAAABVw"
            "ZXJtaXQtWDExLWZvcndhcmRpbmcAAAAAAAAAF3Blcm1pdC1hZ2VudC1mb3J3YXJk"
            "aW5nAAAAAAAAABZwZXJtaXQtcG9ydC1mb3J3YXJkaW5nAAAAAAAAAApwZXJtaXQt"
            "cHR5AAAAAAAAAA5wZXJtaXQtdXNlci1yYwAAAAAAAAAAAAAAMwAAAAtzc2gtZWQy"
            "NTUxOQAAACDI8h3vsne8ZtyH7JRHmkImHXQciefsH4e99ka3HJzKPQAAAFMAAAAL"
            "c3NoLWVkMjU1MTkAAABAHzruY+hPXK2ONt9d2XFUttvdSR7dW9Yy7stru4zopgUb"
            "o0CjTlKyogb7PiRryt5JExT1Wkux1q3oBtyvSdG+Cw=="
        )
        # we expect 'fail', but not 'Invalid public key'
        self.assertEqual(
            ssh.set_auth_key(
                "user", valid_key, enc="sk-ssh-ed25519-cert-v01@openssh.com"
            ),
            "fail",
        )

    def test_replace_auth_key(self):
        """
        Test the _replace_auth_key with some different authorized_keys examples
        """
        # First test a known working example, gathered from the authorized_keys file
        # in the integration test files.
        enc = "ssh-rsa"
        key = (
            "AAAAB3NzaC1yc2EAAAABIwAAAQEAq2A7hRGmdnm9tUDbO9IDSwBK6TbQa+"
            "PXYPCPy6rbTrTtw7PHkccKrpp0yVhp5HdEIcKr6pLlVDBfOLX9QUsyCOV0wzfjIJNl"
            "GEYsdlLJizHhbn2mUjvSAHQqZETYP81eFzLQNnPHt4EVVUh7VfDESU84KezmD5QlWp"
            "XLmvU31/yMf+Se8xhHTvKSCZIFImWwoG6mbUoWf9nzpIoaSjB+weqqUUmpaaasXVal"
            "72J+UX2B+2RPW3RcT0eOzQgqlJL3RKrTJvdsjE3JEAvGq3lGHSZXy28G3skua2SmVi"
            "/w4yCE6gbODqnTWlg7+wC604ydGXA8VJiS5ap43JXiUFFAaQ=="
        )
        options = 'command="/usr/local/lib/ssh-helper"'
        email = "github.com"
        empty_line = "\n"
        comment_line = "# this is a comment\n"

        # Write out the authorized key to a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, mode="w+")
        temp_file.close()

        with salt.utils.files.fopen(temp_file.name, "w") as _fh:
            # Add comment
            _fh.write(comment_line)
            # Add empty line for #41335
            _fh.write(empty_line)
            _fh.write(f"{options} {enc} {key} {email}")

        with patch.dict(ssh.__salt__, {"user.info": MagicMock(return_value={})}):
            with patch(
                "salt.modules.ssh._get_config_file",
                MagicMock(return_value=temp_file.name),
            ):
                ssh._replace_auth_key("foo", key, config=temp_file.name)

        # The previous authorized key should have been replaced by the simpler one
        with salt.utils.files.fopen(temp_file.name) as _fh:
            file_txt = salt.utils.stringutils.to_unicode(_fh.read())
            self.assertIn(enc, file_txt)
            self.assertIn(key, file_txt)
            self.assertNotIn(options, file_txt)
            self.assertNotIn(email, file_txt)

        # Now test a very simple key using ecdsa instead of ssh-rsa and with multiple options
        enc = "ecdsa-sha2-nistp256"
        key = "abcxyz"

        with salt.utils.files.fopen(temp_file.name, "a") as _fh:
            _fh.write(salt.utils.stringutils.to_str(f"{enc} {key}"))

        # Replace the simple key from before with the more complicated options + new email
        # Option example is taken from Pull Request #39855
        options = [
            "no-port-forwarding",
            "no-agent-forwarding",
            "no-X11-forwarding",
            'command="echo \'Please login as the user "ubuntu" rather than the user'
            ' "root".\'',
        ]
        email = "foo@example.com"

        with patch.dict(ssh.__salt__, {"user.info": MagicMock(return_value={})}):
            with patch(
                "salt.modules.ssh._get_config_file",
                MagicMock(return_value=temp_file.name),
            ):
                ssh._replace_auth_key(
                    "foo",
                    key,
                    enc=enc,
                    comment=email,
                    options=options,
                    config=temp_file.name,
                )

        # Assert that the new line was added as-is to the file
        with salt.utils.files.fopen(temp_file.name) as _fh:
            file_txt = salt.utils.stringutils.to_unicode(_fh.read())
            self.assertIn(enc, file_txt)
            self.assertIn(key, file_txt)
            self.assertIn("{} ".format(",".join(options)), file_txt)
            self.assertIn(email, file_txt)
            self.assertIn(empty_line, file_txt)
            self.assertIn(comment_line, file_txt)

        # Now test a another very simple key using sk-ed25519 instead of ssh-rsa and with
        # multiple options
        enc = "sk-ssh-ed25519-cert-v01@openssh.com"
        key = "abcxyz"

        with salt.utils.files.fopen(temp_file.name, "a") as _fh:
            _fh.write(salt.utils.stringutils.to_str(f"{enc} {key}"))

        # Replace the simple key from before with the more complicated options + new email
        # Option example is taken from Pull Request #39855
        options = [
            "no-agent-forwarding",
            'command="echo \'Please login as the user "debian" rather than the user'
            ' "root".\'',
        ]
        email = "foobazbar@example.com"

        with patch.dict(ssh.__salt__, {"user.info": MagicMock(return_value={})}):
            with patch(
                "salt.modules.ssh._get_config_file",
                MagicMock(return_value=temp_file.name),
            ):
                ssh._replace_auth_key(
                    "foo",
                    key,
                    enc=enc,
                    comment=email,
                    options=options,
                    config=temp_file.name,
                )

        with salt.utils.files.fopen(temp_file.name) as _fh:
            file_txt = salt.utils.stringutils.to_unicode(_fh.read())
            # the initial key must have been replaced and no longer present
            self.assertNotIn(f"\n{enc} {key}\n", file_txt)
            # the new key must be present
            self.assertIn(
                "{} {} {} {}".format(",".join(options), enc, key, email), file_txt
            )
            self.assertIn(empty_line, file_txt)
            self.assertIn(comment_line, file_txt)

    def test_rm_auth_key(self):
        """
        Test the rm_auth_key with some different authorized_keys examples
        """

        temp_file = tempfile.NamedTemporaryFile(delete=False, mode="w+")
        temp_file.close()

        options = 'command="echo command"'
        enc = "sk-ssh-ed25519-cert-v01@openssh.com"
        key = "abcxyz"
        email = "foo@example.com"

        with salt.utils.files.fopen(temp_file.name, "w") as _fh:
            _fh.write(salt.utils.stringutils.to_str(f"{options} {enc} {key} {email}"))

        with patch.dict(ssh.__salt__, {"user.info": MagicMock(return_value={})}):
            with patch(
                "salt.modules.ssh._get_config_file",
                MagicMock(return_value=temp_file.name),
            ):
                with patch(
                    "salt.modules.ssh.auth_keys",
                    MagicMock(
                        return_value=salt.utils.files.fopen(temp_file.name, "r").read()
                    ),
                ):
                    self.assertEqual(
                        ssh.rm_auth_key(
                            "foo",
                            f"{key}",
                            config=temp_file.name,
                        ),
                        "Key removed",
                    )

        # Assert that the key was removed
        with salt.utils.files.fopen(temp_file.name) as _fh:
            file_txt = salt.utils.stringutils.to_unicode(_fh.read())
            self.assertNotIn(key, file_txt)
