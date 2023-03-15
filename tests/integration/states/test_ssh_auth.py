"""
Test the ssh_auth states
"""

import os

import pytest

import salt.utils.files
from tests.support.case import ModuleCase
from tests.support.helpers import with_system_user
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.runtests import RUNTIME_VARS


class SSHAuthStateTests(ModuleCase, SaltReturnAssertsMixin):
    @pytest.mark.destructive_test
    @with_system_user("issue_7409", on_existing="delete", delete=True)
    @pytest.mark.slow_test
    @pytest.mark.skip_if_not_root
    def test_issue_7409_no_linebreaks_between_keys(self, username):

        userdetails = self.run_function("user.info", [username])
        user_ssh_dir = os.path.join(userdetails["home"], ".ssh")
        authorized_keys_file = os.path.join(user_ssh_dir, "authorized_keys")

        ret = self.run_state(
            "file.managed",
            name=authorized_keys_file,
            user=username,
            makedirs=True,
            contents_newline=False,
            # Explicit no ending line break
            contents="ssh-rsa AAAAB3NzaC1kc3MAAACBAL0sQ9fJ5bYTEyY== root",
        )

        ret = self.run_state(
            "ssh_auth.present",
            name="AAAAB3NzaC1kcQ9J5bYTEyZ==",
            enc="ssh-rsa",
            user=username,
            comment=username,
        )
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, {"AAAAB3NzaC1kcQ9J5bYTEyZ==": "New"})
        with salt.utils.files.fopen(authorized_keys_file, "r") as fhr:
            self.assertEqual(
                fhr.read(),
                "ssh-rsa AAAAB3NzaC1kc3MAAACBAL0sQ9fJ5bYTEyY== root\n"
                "ssh-rsa AAAAB3NzaC1kcQ9J5bYTEyZ== {}\n".format(username),
            )

    @pytest.mark.destructive_test
    @with_system_user("issue_10198", on_existing="delete", delete=True)
    @pytest.mark.slow_test
    @pytest.mark.skip_if_not_root
    def test_issue_10198_keyfile_from_another_env(self, username=None):
        userdetails = self.run_function("user.info", [username])
        user_ssh_dir = os.path.join(userdetails["home"], ".ssh")
        authorized_keys_file = os.path.join(user_ssh_dir, "authorized_keys")

        key_fname = "issue_10198.id_rsa.pub"

        # Create the keyfile that we expect to get back on the state call
        with salt.utils.files.fopen(
            os.path.join(RUNTIME_VARS.TMP_PRODENV_STATE_TREE, key_fname), "w"
        ) as kfh:
            kfh.write("ssh-rsa AAAAB3NzaC1kcQ9J5bYTEyZ== {}\n".format(username))

        # Create a bogus key file on base environment
        with salt.utils.files.fopen(
            os.path.join(RUNTIME_VARS.TMP_STATE_TREE, key_fname), "w"
        ) as kfh:
            kfh.write("ssh-rsa BAAAB3NzaC1kcQ9J5bYTEyZ== {}\n".format(username))

        ret = self.run_state(
            "ssh_auth.present",
            name="Setup Keys",
            source="salt://{}?saltenv=prod".format(key_fname),
            enc="ssh-rsa",
            user=username,
            comment=username,
        )
        self.assertSaltTrueReturn(ret)
        with salt.utils.files.fopen(authorized_keys_file, "r") as fhr:
            self.assertEqual(
                fhr.read(), "ssh-rsa AAAAB3NzaC1kcQ9J5bYTEyZ== {}\n".format(username)
            )

        os.unlink(authorized_keys_file)

        ret = self.run_state(
            "ssh_auth.present",
            name="Setup Keys",
            source="salt://{}".format(key_fname),
            enc="ssh-rsa",
            user=username,
            comment=username,
            saltenv="prod",
        )
        self.assertSaltTrueReturn(ret)
        with salt.utils.files.fopen(authorized_keys_file, "r") as fhr:
            self.assertEqual(
                fhr.read(), "ssh-rsa AAAAB3NzaC1kcQ9J5bYTEyZ== {}\n".format(username)
            )
