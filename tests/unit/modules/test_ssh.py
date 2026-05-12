import tempfile

import salt.modules.ssh as ssh
import salt.utils.files
import salt.utils.platform
from salt.exceptions import CommandExecutionError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, call, mock_open, patch
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

    def test_set_auth_key_from_file(self):
        """
        Test if set_auth_key_from_file pass the correct options to set_auth_key and
        if multiple keys are supported.
        """
        s_keys_dict = {
            "S1KeyWithSpecialCharactersAndMultipleWordCommentaryXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX=": {
                "enc": "sk-ssh-ed25519@openssh.com",
                "comment": "user@internal.example Multiple Words Commentary",
                "options": [],
                "fingerprint": "c5:6c:6d:47:6e:d6:16:56:60:7b:f6:ab:59:c6:33:03:87:b8:3b:d7:67:7e:37:8a:db:83:8b:b5:48:de:91:c1",
            },
            "S4KeyWithSpecialCharactersAndMultipleWordCommentaryAndOptionsXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX=": {
                "enc": "sk-ssh-ed25519@openssh.com",
                "comment": "user@internal.example Multiple Words Commentary",
                "options": ["no-port-forwarding", "no-pty"],
                "fingerprint": "3a:14:23:b6:db:0a:d7:07:30:30:3b:b4:9a:31:0c:29:9b:c5:fa:5f:5e:5a:7d:fb:4b:44:da:70:02:79:ca:04",
            },
        }
        user = "user"
        config = "authorized_keys_somewhere"
        options = ["no-pty"]
        fingerprint_hash_type = None

        expected_calls_without_options = []
        expected_calls_with_options = []
        for key in s_keys_dict:
            expected_calls_without_options.append(
                call(
                    user,
                    key,
                    enc=s_keys_dict[key]["enc"],
                    comment=s_keys_dict[key]["comment"],
                    options=s_keys_dict[key]["options"],
                    config=config,
                    cache_keys=list(s_keys_dict.keys()),
                    fingerprint_hash_type=fingerprint_hash_type,
                )
            )
            expected_calls_with_options.append(
                call(
                    user,
                    key,
                    enc=s_keys_dict[key]["enc"],
                    comment=s_keys_dict[key]["comment"],
                    options=options,
                    config=config,
                    cache_keys=list(s_keys_dict.keys()),
                    fingerprint_hash_type=fingerprint_hash_type,
                )
            )

        with patch.object(ssh, "set_auth_key", return_value="new") as mock_set_auth_key:
            with patch("os.path.isfile", return_value=True):
                with patch.dict(
                    ssh.__salt__,
                    {"cp.cache_file": MagicMock(return_value="/fakecache/fakefile")},
                ):
                    with patch(
                        "salt.modules.ssh._validate_keys",
                        MagicMock(return_value=s_keys_dict),
                    ):
                        self.assertEqual(
                            ssh.set_auth_key_from_file(
                                "user", source="salt://fakefile", config=config
                            ),
                            "new",
                        )
                        mock_set_auth_key.assert_has_calls(
                            expected_calls_without_options
                        )

                        self.assertEqual(
                            ssh.set_auth_key_from_file(
                                "user",
                                source="salt://fakefile",
                                config=config,
                                options=options,
                            ),
                            "new",
                        )
                        mock_set_auth_key.assert_has_calls(expected_calls_with_options)

    def test_rm_auth_key_from_file(self):
        """
        Test if multiple keys are supported by rm_auth_key_from_file
        """
        s_keys_dict = {
            "S1KeyWithSpecialCharactersAndMultipleWordCommentaryXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX=": {
                "enc": "sk-ssh-ed25519@openssh.com",
                "comment": "user@internal.example Multiple Words Commentary",
                "options": [],
                "fingerprint": "c5:6c:6d:47:6e:d6:16:56:60:7b:f6:ab:59:c6:33:03:87:b8:3b:d7:67:7e:37:8a:db:83:8b:b5:48:de:91:c1",
            },
            "S4KeyWithSpecialCharactersAndMultipleWordCommentaryAndOptionsXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX=": {
                "enc": "sk-ssh-ed25519@openssh.com",
                "comment": "user@internal.example Multiple Words Commentary",
                "options": ["no-port-forwarding", "no-pty"],
                "fingerprint": "3a:14:23:b6:db:0a:d7:07:30:30:3b:b4:9a:31:0c:29:9b:c5:fa:5f:5e:5a:7d:fb:4b:44:da:70:02:79:ca:04",
            },
        }
        user = "user"
        config = "authorized_keys_somewhere"
        fingerprint_hash_type = None

        expected_calls = []
        for key in s_keys_dict:
            expected_calls.append(
                call(
                    user,
                    key,
                    config=config,
                    fingerprint_hash_type=fingerprint_hash_type,
                )
            )

        with patch.object(
            ssh, "rm_auth_key", return_value="Key removed"
        ) as mock_rm_auth_key:
            with patch("os.path.isfile", return_value=True):
                with patch.dict(
                    ssh.__salt__,
                    {"cp.cache_file": MagicMock(return_value="/fakecache/fakefile")},
                ):
                    with patch(
                        "salt.modules.ssh._validate_keys",
                        MagicMock(return_value=s_keys_dict),
                    ):
                        self.assertEqual(
                            ssh.rm_auth_key_from_file(
                                "user", source="salt://fakefile", config=config
                            ),
                            "Key removed",
                        )
                        mock_rm_auth_key.assert_has_calls(expected_calls)

    def test__validate_keys(self):
        """
        Test if keys read from file are correctly validated
        """
        s_keys_dict = {
            "KeyWithSpecialCharactersAndOptionsXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX=": {
                "enc": "sk-ecdsa-sha2-nistp256@openssh.com",
                "comment": "user@internal.example",
                "options": ["no-port-forwarding", "no-pty"],
                "fingerprint": "b4:98:a7:02:bf:0d:1f:0a:c2:96:19:4c:10:7e:7b:51:ad:d7:ee:2c:3e:96:37:58:4d:ab:73:98:db:ee:36:f1",
            },
            "KeyWithoutOptionsXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX=": {
                "enc": "ecdsa-sha2-nistp256",
                "comment": "user@internal.example",
                "options": [],
                "fingerprint": "4e:1f:ba:e6:16:31:56:67:f6:c1:ea:34:0c:b4:83:43:28:2c:5f:e7:c1:95:5c:07:90:6f:70:d5:4d:1b:3e:af",
            },
            "KeyWithoutOptionsAndWithoutCommentsXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX=": {
                "enc": "ecdsa-sha2-nistp384",
                "comment": "",
                "options": [],
                "fingerprint": "3d:55:90:4b:d5:7d:22:03:37:c7:8c:4f:32:8b:5e:a9:77:f8:fd:f7:e4:24:52:87:14:90:b3:d6:c3:d8:57:f0",
            },
            "KeyWithOptionsAndWithoutCommentsXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX=": {
                "enc": "ecdsa-sha2-nistp521",
                "comment": "",
                "options": ["no-port-forwarding", "no-pty"],
                "fingerprint": "a9:7d:6d:00:30:df:28:75:1b:1f:f1:b5:b6:36:3c:82:e4:bf:70:97:bf:6c:a6:e0:9a:b6:37:6b:0d:30:57:e8",
            },
            "KeyWithSpecialCharactersWithoutOptionsXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX=": {
                "enc": "sk-ssh-ed25519@openssh.com",
                "comment": "user@internal.example",
                "options": [],
                "fingerprint": "3e:8b:af:7c:16:12:c6:e2:df:2d:03:16:b7:19:28:b8:3e:65:de:b0:7d:fc:74:06:a9:d6:b1:0f:92:df:7c:cf",
            },
            "KeyWithMultipleWordCommentaryAndNoOptionsXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX=": {
                "enc": "ssh-ed25519",
                "comment": "user@internal.example Multiple Word Commentary",
                "options": [],
                "fingerprint": "29:e8:ef:0d:f4:93:09:13:19:af:66:bf:d0:ca:45:0a:ed:ac:30:e6:3b:41:22:3a:d6:ea:e6:a3:5f:8b:af:07",
            },
            "KeyWithMultipleWordCommentaryAndWithOptionsXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX=": {
                "enc": "ssh-rsa",
                "comment": "user@internal.example Multiple Word Commentary",
                "options": ["no-port-forwarding", "no-pty"],
                "fingerprint": "c7:e2:fb:76:03:ab:f0:11:2d:62:11:33:25:57:1a:1f:88:2d:cc:4f:95:44:bd:2c:79:11:8f:84:d9:75:b5:bf",
            },
        }

        read_file_contents = ""
        for key in s_keys_dict:
            line = f"{s_keys_dict[key]['enc']} {key}"
            if s_keys_dict[key]["options"]:
                options = ",".join(s_keys_dict[key]["options"])
                line = " ".join([options, line])
            if s_keys_dict[key]["comment"]:
                line = " ".join([line, s_keys_dict[key]["comment"]])
            line += "\n"
            read_file_contents += line

        fopen_mock = mock_open(read_data=read_file_contents)
        with patch("salt.utils.files.fopen", fopen_mock):
            assert ssh._validate_keys("keyfile", None) == s_keys_dict

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
