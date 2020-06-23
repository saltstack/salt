# -*- coding: utf-8 -*-

"""
Test the ssh module
"""
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import re
import shutil
import subprocess

import salt.utils.files
import salt.utils.platform
from tests.support.case import ModuleCase
from tests.support.helpers import (
    destructiveTest,
    requires_salt_modules,
    requires_system_grains,
    skip_if_binaries_missing,
    skip_if_not_root,
    slowTest,
)
from tests.support.runtests import RUNTIME_VARS

GPG_TEST_PRIV_KEY = """-----BEGIN PGP PRIVATE KEY BLOCK-----
Version: GnuPG v2.0.22 (GNU/Linux)

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
=mNsA
-----END PGP PRIVATE KEY BLOCK-----
"""

GPG_TEST_PUB_KEY = """-----BEGIN PGP PUBLIC KEY BLOCK-----
Version: GnuPG v2.0.22 (GNU/Linux)

mQENBF7qopoBCACVyX0rjtcbh1CMu0Od/luO14VvgEZ+u+MJaioiEN6NMU0SscBn
A4/+BSu/f6DPc9MgJBM6AI0O4a7OM00kwZHODT3TykLEJKbL+taObkHcS9j5b5iA
ife+56W8KLEZpYk6uhk9LXMKilc7R01qXgLrDgqx9kGIe/5bC/AtCEW656zOWRPn
1p55oWW2toM7pVkdsOG1UZ43uZq1+iTSuxe+FcH0NU0yPBISFa+x5kuKP+xBa8Ou
n206+NGtnQQJjlbPtce/QrJU3mQP8xgBZBdU7NevxYTyQrkJXwUPqCXevqCU4KKX
c+I+nAJsrvnbdcnBWe5bUvVnpKMOLguxeKtzABEBAAG0YVNhbHRTdGFjayBQYWNr
YWdpbmcgVGVhbSAoVGhpcyBrZXkgaXMgZm9yIHRlc3RpbmcgcGFja2FnZSBzaWdu
aW5nIG9ubHkpIDxwYWNrYWdpbmdAc2FsdHN0YWNrLmNvbT6JATkEEwECACMFAl7q
opoCGwMHCwkIBwMCAQYVCAIJCgsEFgIDAQIeAQIXgAAKCRAfceQnFUySQdC1B/wL
09fhDkhKzgs6jpcBSKHSxMR/dD4l0ehmw82T4mqpoYRGOsWn+b7fCJTGQIWXL/Rr
+hPqV1tKBVRsk3WiRL35xdFThPsWLjjNFz06cZ9VGhp07udimcpcUAQZHMT+OGnC
hDUNYQkTp17u529KvN4Nb3byo8GtjtYSl1V9tPbU8RpMO+c/Kx1Ope1KT8EO+/QE
H4jIwFRh/h9PSbblB18gXCZwvQB5lKiXjWlhG7/FCQpzPEKs/SDgopURD3rgjxie
cpfcLxvGQ4xSdukTLzEXzqM1c6lEd3GL9FsNIfZsm15AujiSzsx91hGsjN6TplCY
EF4Vly94p6ChBtaqpxyBuQENBF7qopoBCADhL6siQvvm18xxQeUC5CKN2A3pfSDi
iehf8/etfSCYls4h1KlZPvcHQz8h45yKvtQF29Ly1HZiFZp+Un+WLx4p+bVp/Ysi
A+L8+McvZhCmXuL5/jui1YX/Lv2gd9nUNTm0UG9I2grT6MsYkK/t0nv/VtocMPkS
6Kc0cuaZnKKKDG4GIhPWbEmkba+YJN/7R6bXaNfvg5BQlvYGI9nnX/OTzqBbYWDG
49nIb5mTGz7tZNXd/l6muana31UVRZEGybl0VJ1NCVEE6uAdEQAog/HiZbuI1ona
6y1lbpGOTAoPmj5bQnx/DAAjfDOl0oRrTOlucStAF8yyv4MPzbrzZd6nABEBAAGJ
AR8EGAECAAkFAl7qopoCGwwACgkQH3HkJxVMkkEl0QgAgqVDZywU6it+X29dZd0y
EwjxtDzu4W2kD86484sqkwtytpAGG6f/UF4s90oIvQx579JdwBPDjckGCLT+SE5i
o0QMQZIRFCSTI2WSil8nnR/HEnT88lNgeMme8MvfP0vjijZpzHaGPOv3dLuHNB0S
QCvz8Skwe6yGgKhUnKX6p2WUG3MTJpA1Ccd/J1JLojtYnkL0U7576icMfZuBlZlc
CBDJpTNeaNG/OGaHwukI1kHM8ZW+hh+8YlFF6rlv04DLrbDHEKQZX2WKT4rNAOFp
mCCvdH7g1yJm9b2crlJuJ3VZl5KI9hQdGpBCcLhcMn3736n0fOURlmx8J6JF/kAu
yQ==
=6abY
-----END PGP PUBLIC KEY BLOCK-----
"""

GPG_TEST_KEY_PASSPHRASE = "saltstacktestingpackages"
GPG_TEST_KEY_ID = "154C9241"

GPG_AGENT_CONF = """default-cache-ttl 600
default-cache-ttl-ssh 600
max-cache-ttl 600
max-cache-ttl-ssh 600
allow-preset-passphrase
daemon
debug-all
## debug-pinentry
log-file /root/gpg-agent.log
verbose
# PIN entry program
pinentry-program /usr/bin/pinentry-gtk
pinentry-timeout 30
allow-loopback-pinentry
"""
TEST_SYSTEM_USER = "root"
TEST_SYSTEM_GROUP = "root"

log = logging.getLogger(__name__)


def _testrpm_signed(abs_path_named_rpm):
    try:
        rpm_chk_sign = subprocess.Popen(
            ["rpm", "--checksig", "-v", abs_path_named_rpm],
            shell=False,
            close_fds=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).communicate()[0]
    except OSError:
        return False
    if not rpm_chk_sign:
        log.debug("problem checking signatures on rpm")
        return False

    test_string = GPG_TEST_KEY_ID.lower() + ": OK"
    CHECK_KEYID_OK = re.compile(test_string, re.M)
    retrc = CHECK_KEYID_OK.search(rpm_chk_sign.decode())
    log.debug(
        "signed checking, found test_string '{0}' in rpm_chk_sign '{1}', return code '{2}'".format(
            test_string, rpm_chk_sign, retrc
        )
    )
    if retrc:
        return True
    return False


@skip_if_binaries_missing(["gpg", "rpm", "createrepo"], check_all=True)
class RPMSignModuleTest(ModuleCase):
    """
    Test the RPM Signing module
    """

    @classmethod
    def setUpClass(cls):
        cls.subsalt_dir = os.path.join(RUNTIME_VARS.TMP, "subsalt")
        cls.gpghome = os.path.join(cls.subsalt_dir, ".gnupg")
        cls.repodir = os.path.join(cls.subsalt_dir, "repodir")

    @requires_salt_modules("gpg")
    def setUp(self):
        """
        Set up the rpm signing module tests
        """
        super(RPMSignModuleTest, self).setUp()
        if not os.path.isdir(self.subsalt_dir):
            os.makedirs(self.subsalt_dir)
        if not os.path.isdir(self.gpghome):
            os.makedirs(self.gpghome)
            os.chmod(self.gpghome, 0o600)
        if not os.path.isdir(self.repodir):
            os.makedirs(self.repodir)

        self.repo_named_rpm = "hello-2.10-1.el7.x86_64.rpm"
        shutil.copy(os.path.join(RUNTIME_VARS.FILES, self.repo_named_rpm), self.repodir)

        gpg_conf_path = os.path.join(self.gpghome, "gpg.conf")
        self.gpg_conf = "use-agent"
        with salt.utils.files.fopen(gpg_conf_path, "wb") as fd:
            fd.write(self.gpg_conf.encode())

        gpg_agent_conf_path = os.path.join(self.gpghome, "gpg-agent.conf")
        self.gpg_agent_conf = GPG_AGENT_CONF
        with salt.utils.files.fopen(gpg_agent_conf_path, "wb") as fd:
            fd.write(self.gpg_agent_conf.encode())

        gpg_pkg_key_pem_path = os.path.join(self.gpghome, "gpg_pkg_key.pem")
        self.gpg_pkg_key_pem = GPG_TEST_PRIV_KEY
        with salt.utils.files.fopen(gpg_pkg_key_pem_path, "wb") as fd:
            fd.write(self.gpg_pkg_key_pem.encode())

        gpg_pkg_key_pub_path = os.path.join(self.gpghome, "gpg_pkg_key.pub")
        self.gpg_pkg_key_pub = GPG_TEST_PUB_KEY
        with salt.utils.files.fopen(gpg_pkg_key_pub_path, "wb") as fd:
            fd.write(self.gpg_pkg_key_pub.encode())

        self.gpg_passphrase = GPG_TEST_KEY_PASSPHRASE
        self.gpg_keyid = GPG_TEST_KEY_ID

    def tearDown(self):
        """
        Tear down the rpm signing module tests
        """
        if os.path.isdir(self.repodir):
            shutil.rmtree(self.repodir)
        if os.path.isdir(self.gpghome):
            shutil.rmtree(self.gpghome)
        if os.path.isdir(self.subsalt_dir):
            shutil.rmtree(self.subsalt_dir)

        super(RPMSignModuleTest, self).tearDown()
        del self.gpg_passphrase
        del self.gpg_keyid
        del self.gpg_pkg_key_pub
        del self.gpg_pkg_key_pem
        del self.gpg_agent_conf
        del self.gpg_conf

    @slowTest
    @skip_if_not_root
    @skip_if_binaries_missing(
        ["gpgconf", "gpg-agent", "/usr/libexec/gpg-preset-passphrase"], check_all=True
    )
    @requires_system_grains
    @destructiveTest
    @requires_salt_modules("pkgbuild.make_repo")
    def test_make_repo_with_gpg_agent(self, grains):
        """
        test make repo, signing rpm
        """
        if not (grains["os_family"] == "RedHat" and grains["osmajorrelease"] >= 8):
            self.skipTest(
                "TODO: test not configured for {0} and major release {1}".format(
                    grains["os_family"], grains["osmajorrelease"]
                )
            )

        pillar = self.run_function("pillar.data")
        self.assertEqual(pillar["gpg_passphrase"], "saltstacktestingpackages")
        self.assertEqual(pillar["gpg_pkg_pub_keyname"], "gpg_pkg_key.pub")

        # launch gpg-agent
        self.run_function(
            "cmd.run", ["gpgconf --kill gpg-agent"], template="jinja", python_shell=True
        )
        gpg_agent_cmd = "gpg-agent --homedir {0} --allow-preset-passphrase --max-cache-ttl 600 --daemon".format(
            self.gpghome
        )
        gpg_tty_info_path = os.path.join(self.gpghome, "gpg_tty_info")
        self.run_function(
            "cmd.run",
            ["{0}".format(gpg_agent_cmd)],
            template="jinja",
            python_shell=True,
        )
        self.run_function(
            "cmd.run",
            [
                "{0}".format(gpg_agent_cmd),
                "GPG_TTY=$(tty) ; export GPG_TTY ; echo $GPG_TTY=$(tty) > {0}".format(
                    gpg_tty_info_path
                ),
            ],
            template="jinja",
            python_shell=True,
        )

        # sign rpm and create repo
        ret = self.run_function(
            "pkgbuild.make_repo",
            repodir=self.repodir,
            keyid=self.gpg_keyid,
            env=None,
            use_passphrase=True,
            gnupghome=self.gpghome,
            runas="root",
            timeout=15.0,
        )

        self.assertNotEqual(ret, {})
        test_rpm_path = os.path.join(self.repodir, self.repo_named_rpm)
        self.assertTrue(_testrpm_signed(test_rpm_path))
        test_repodata_path = os.path.join(self.repodir, "repodata")
        self.assertTrue(os.path.isdir(test_repodata_path))
        test_repomd_xml_path = os.path.join(test_repodata_path, "repomd.xml")
        self.assertTrue(os.path.isfile(test_repomd_xml_path))
        self.run_function(
            "cmd.run", ["gpgconf --kill gpg-agent"], template="jinja", python_shell=True
        )

    @slowTest
    @skip_if_not_root
    @requires_system_grains
    @destructiveTest
    @requires_salt_modules("pkgbuild.make_repo")
    def test_make_repo_no_gpg_agent(self, grains):
        """
        test make repo, signing rpm
        """
        if not (grains["os_family"] == "RedHat" or grains["os_family"] == "Amazon"):
            self.skipTest(
                "TODO: test not configured for {0}".format(grains["os_family"])
            )

        if grains["os_family"] == "RedHat" and grains["osmajorrelease"] >= 8:
            self.skipTest(
                "TODO: test not configured for {0} and major release {1}".format(
                    grains["os_family"], grains["osmajorrelease"]
                )
            )

        if grains["os_family"] == "Amazon" and grains["osmajorrelease"] != 2:
            self.skipTest(
                "TODO: test not configured for {0} and major release {1}".format(
                    grains["os_family"], grains["osmajorrelease"]
                )
            )

        pillar = self.run_function("pillar.data")
        self.assertEqual(pillar["gpg_passphrase"], "saltstacktestingpackages")
        self.assertEqual(pillar["gpg_pkg_pub_keyname"], "gpg_pkg_key.pub")

        # sign rpm and create repo
        ret = self.run_function(
            "pkgbuild.make_repo",
            repodir=self.repodir,
            keyid=self.gpg_keyid,
            env=None,
            use_passphrase=True,
            gnupghome=self.gpghome,
            runas="root",
            timeout=15.0,
        )

        self.assertNotEqual(ret, {})
        test_rpm_path = os.path.join(self.repodir, self.repo_named_rpm)
        self.assertTrue(_testrpm_signed(test_rpm_path))
        test_repodata_path = os.path.join(self.repodir, "repodata")
        self.assertTrue(os.path.isdir(test_repodata_path))
        test_repomd_xml_path = os.path.join(test_repodata_path, "repomd.xml")
        self.assertTrue(os.path.isfile(test_repomd_xml_path))
