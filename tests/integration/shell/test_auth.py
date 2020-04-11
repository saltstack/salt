# -*- coding: utf-8 -*-
"""
    tests.integration.shell.auth
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import random
import string

# Import Salt libs
import salt.utils.platform

# Import 3rd-party libs
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin
from salt.utils.pycrypto import gen_hash
from tests.support.case import ModuleCase, ShellCase
from tests.support.helpers import (
    destructiveTest,
    requires_salt_modules,
    requires_salt_states,
    skip_if_not_root,
)
from tests.support.mixins import SaltReturnAssertsMixin

# Import Salt Testing libs
from tests.support.unit import skipIf

try:
    import pwd
    import grp
except ImportError:
    pwd, grp = None, None


log = logging.getLogger(__name__)


def gen_password():
    """
    generate a password and hash it
    """
    password = "".join(
        random.choice(string.ascii_letters + string.digits) for _ in range(20)
    )
    hashed_pwd = gen_hash("salt", password, "sha512")

    return password, hashed_pwd


@requires_salt_states("user.absent", "user.present")
@requires_salt_modules("shadow.set_password")
@skip_if_not_root
@skipIf(pwd is None or grp is None, "No crypt module available")
@destructiveTest
class UserAuthTest(ModuleCase, SaltReturnAssertsMixin, ShellCase):
    """
    Test user auth mechanisms
    """

    _call_binary_ = "salt"
    user = "saltdev"

    def setUp(self):
        ret = self.run_state("user.present", name=self.user, createhome=False)
        self.assertSaltTrueReturn(ret)

    def tearDown(self):
        ret = self.run_state("user.absent", name=self.user)
        self.assertSaltTrueReturn(ret)

    def test_pam_auth_valid_user(self):
        """
        test that pam auth mechanism works with a valid user
        """
        password, hashed_pwd = gen_password()

        # set user password
        set_pw_cmd = "shadow.set_password {0} '{1}'".format(
            self.user, password if salt.utils.platform.is_darwin() else hashed_pwd
        )
        self.assertRunCall(set_pw_cmd)

        # test user auth against pam
        cmd = '-a pam "*" test.ping --username {0} --password {1}'.format(
            self.user, password
        )
        resp = self.run_salt(cmd)
        log.debug("resp = %s", resp)
        self.assertIn("minion", [r.strip(": ") for r in resp])

    def test_pam_auth_invalid_user(self):
        """
        test pam auth mechanism errors for an invalid user
        """
        cmd = '-a pam "*" test.ping ' "--username nouser --password {0}".format(
            "abcd1234"
        )
        resp = self.run_salt(cmd)
        self.assertIn("Authentication error occurred", "".join(resp))


@requires_salt_states("group.absent", "group.present", "user.absent", "user.present")
@requires_salt_modules("shadow.set_password", "user.chgroups")
@skip_if_not_root
@skipIf(pwd is None or grp is None, "No crypt module available")
@destructiveTest
class GroupAuthTest(ModuleCase, SaltReturnAssertsMixin, ShellCase):
    """
    Test group auth mechanisms
    """

    _call_binary_ = "salt"

    user = "saltadm"
    group = "saltops"

    def setUp(self):
        ret = self.run_state("group.present", name=self.group)
        self.assertSaltTrueReturn(ret)
        ret = self.run_state(
            "user.present", name=self.user, createhome=False, groups=[self.group]
        )
        self.assertSaltTrueReturn(ret)
        self.assertRunCall(
            "user.chgroups {0} {1} True".format(self.user, self.group), local=True
        )

    def tearDown(self):
        ret0 = self.run_state("user.absent", name=self.user)
        ret1 = self.run_state("group.absent", name=self.group)
        self.assertSaltTrueReturn(ret0)
        self.assertSaltTrueReturn(ret1)

    def test_pam_auth_valid_group(self):
        """
        test that pam auth mechanism works for a valid group
        """
        password, hashed_pwd = gen_password()

        # set user password
        set_pw_cmd = "shadow.set_password {0} '{1}'".format(
            self.user, password if salt.utils.platform.is_darwin() else hashed_pwd
        )
        self.assertRunCall(set_pw_cmd)

        # test group auth against pam: saltadm is not configured in
        # external_auth, but saltops is and saldadm is a member of saltops
        cmd = '-a pam "*" test.ping --username {0} --password {1}'.format(
            self.user, password
        )
        resp = self.run_salt(cmd)
        self.assertIn("minion", [r.strip(": ") for r in resp])
