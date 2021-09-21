"""
Test the ssh_auth states
"""

import logging
import os

import pytest
import salt.utils.files
from tests.support.case import ModuleCase
from tests.support.helpers import with_system_user
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.runtests import RUNTIME_VARS

# Setup logging
log = logging.getLogger(__name__)


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

    @pytest.mark.destructive_test
    @with_system_user("issue_60769", on_existing="delete", delete=True)
    @pytest.mark.slow_test
    @pytest.mark.skip_if_not_root
    def test_issue_60769_behavior_using_source_and_options(self, username=None):
        userdetails = self.run_function("user.info", [username])
        user_ssh_dir = os.path.join(userdetails["home"], ".ssh")
        authorized_keys_file = os.path.join(user_ssh_dir, "authorized_keys")
        pub_key_file = "issue_60769.id_rsa.pub"

        # create a prepared authorized_keys file with option
        try:
            os.mkdir(user_ssh_dir)
        except FileExistsError:
            log.debug("folder %s already exists", user_ssh_dir)
        with salt.utils.files.fopen(authorized_keys_file, "w") as authf:
            authf.write("no-pty ssh-rsa AAAAB3NzaC1kc3MAAACBAL0sQ9fJ5bYTEyY== root\n")

        # define a public key file to be used as source argument
        with salt.utils.files.fopen(
            os.path.join(RUNTIME_VARS.TMP_STATE_TREE, pub_key_file), "w"
        ) as pubf:
            pubf.write("ssh-rsa AAAAB3NzaC1kc3MAAACBAL0sQ9fJ5bYTEyY== root\n")

        ret = self.run_state(
            "ssh_auth.present",
            name="Setup Keys With Options",
            source="salt://{}".format(pub_key_file),
            enc="ssh-rsa",
            options=["no-pty"],
            user=username,
            test=True,
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment(
            "All host keys in file salt://issue_60769.id_rsa.pub are already present",
            ret,
        )
