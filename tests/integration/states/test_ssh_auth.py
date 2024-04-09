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

        key1 = (
            # Explicit no ending line break
            "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAAgQC3dd5ACsvJhnIOrn6bSOkX5"
            "KyVDpTYsVAaJj3AmEo6Fr5cHXJFJoJS+Ld8K5vCscPzuXashdYUdrhL1E5Liz"
            "bza+zneQ5AkJ7sn2NXymD6Bbra+infO4NgnQXbGMp/NyY65jbQGqJeQ081iEV"
            "YbDP2zXp6fmrqqmFCaakZfGRbVw== root"
        )
        key2 = (
            "AAAAB3NzaC1yc2EAAAADAQABAAAAgQC7h77HyBPCUDONCs5bI/PrrPwyYJegl0"
            "f9YWLaBofVYOUl/uSv1ux8zjIoLVs4kguY1ihtIoK2kho4YsjNtIaAd6twdua9"
            "oqCg2g/54cIK/8WbIjwnb3LFRgyTG5DFuj+7526EdJycAZvhSzIZYui3RUj4Vp"
            "eMoF7mcB6TIK2/2w=="
        )

        ret = self.run_state(
            "file.managed",
            name=authorized_keys_file,
            user=username,
            makedirs=True,
            contents_newline=False,
            # Explicit no ending line break
            contents=key1,
        )

        ret = self.run_state(
            "ssh_auth.present",
            name=key2,
            enc="ssh-rsa",
            user=username,
            comment=username,
        )
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, {key2: "New"})
        with salt.utils.files.fopen(authorized_keys_file, "r") as fhr:
            self.assertEqual(
                fhr.read(),
                f"{key1}\nssh-rsa {key2} {username}\n",
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
        key_contents = (
            "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAAgQC3dd5ACsvJhnIOrn6bSOkX5"
            "KyVDpTYsVAaJj3AmEo6Fr5cHXJFJoJS+Ld8K5vCscPzuXashdYUdrhL1E5Liz"
            "bza+zneQ5AkJ7sn2NXymD6Bbra+infO4NgnQXbGMp/NyY65jbQGqJeQ081iEV"
            f"YbDP2zXp6fmrqqmFCaakZfGRbVw== {username}\n"
        )

        # Create the keyfile that we expect to get back on the state call
        with salt.utils.files.fopen(
            os.path.join(RUNTIME_VARS.TMP_PRODENV_STATE_TREE, key_fname), "w"
        ) as kfh:
            kfh.write(key_contents)

        # Create a bogus key file on base environment
        with salt.utils.files.fopen(
            os.path.join(RUNTIME_VARS.TMP_STATE_TREE, key_fname), "w"
        ) as kfh:
            kfh.write(
                "ssh-rsa A!AAB3NzaC1yc2EAAAADAQABAAAAgQC3dd5ACsvJhnIOrn6bSOkX5"
                "KyVDpTYsVAaJj3AmEo6Fr5cHXJFJoJS+Ld8K5vCscPzuXashdYUdrhL1E5Liz"
                "bza+zneQ5AkJ7sn2NXymD6Bbra+infO4NgnQXbGMp/NyY65jbQGqJeQ081iEV"
                f"YbDP2zXp6fmrqqmFCaakZfGRbVw== {username}\n"
            )

        ret = self.run_state(
            "ssh_auth.present",
            name="Setup Keys",
            source=f"salt://{key_fname}?saltenv=prod",
            enc="ssh-rsa",
            user=username,
            comment=username,
        )
        self.assertSaltTrueReturn(ret)
        with salt.utils.files.fopen(authorized_keys_file, "r") as fhr:
            self.assertEqual(fhr.read(), key_contents)

        os.unlink(authorized_keys_file)

        ret = self.run_state(
            "ssh_auth.present",
            name="Setup Keys",
            source=f"salt://{key_fname}",
            enc="ssh-rsa",
            user=username,
            comment=username,
            saltenv="prod",
        )
        self.assertSaltTrueReturn(ret)
        with salt.utils.files.fopen(authorized_keys_file, "r") as fhr:
            self.assertEqual(fhr.read(), key_contents)

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
            authf.write(
                "no-pty ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAAgQC3dd5ACsvJhnIOrn6bSOkX5"
                "KyVDpTYsVAaJj3AmEo6Fr5cHXJFJoJS+Ld8K5vCscPzuXashdYUdrhL1E5Liz"
                "bza+zneQ5AkJ7sn2NXymD6Bbra+infO4NgnQXbGMp/NyY65jbQGqJeQ081iEV"
                f"YbDP2zXp6fmrqqmFCaakZfGRbVw== {username}\n"
            )

        # define a public key file to be used as source argument
        with salt.utils.files.fopen(
            os.path.join(RUNTIME_VARS.TMP_STATE_TREE, pub_key_file), "w"
        ) as pubf:
            pubf.write(
                "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAAgQC3dd5ACsvJhnIOrn6bSOkX5"
                "KyVDpTYsVAaJj3AmEo6Fr5cHXJFJoJS+Ld8K5vCscPzuXashdYUdrhL1E5Liz"
                "bza+zneQ5AkJ7sn2NXymD6Bbra+infO4NgnQXbGMp/NyY65jbQGqJeQ081iEV"
                f"YbDP2zXp6fmrqqmFCaakZfGRbVw== {username}\n"
            )

        ret = self.run_state(
            "ssh_auth.present",
            name="Setup Keys With Options",
            source=f"salt://{pub_key_file}",
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
