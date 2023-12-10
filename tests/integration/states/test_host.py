"""
tests for host state
"""

import logging
import os
import shutil

import pytest

import salt.utils.files
import salt.utils.stringutils
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


@pytest.mark.windows_whitelisted
class HostTest(ModuleCase, SaltReturnAssertsMixin):
    """
    Validate the host state
    """

    @classmethod
    def setUpClass(cls):
        cls.hosts_file = os.path.join(RUNTIME_VARS.TMP, "hosts")

    def __clear_hosts(self):
        """
        Delete the tmp hosts file
        """
        if os.path.isfile(self.hosts_file):
            os.remove(self.hosts_file)

    def setUp(self):
        shutil.copyfile(os.path.join(RUNTIME_VARS.FILES, "hosts"), self.hosts_file)
        self.addCleanup(self.__clear_hosts)
        super().setUp()

    @pytest.mark.slow_test
    def test_present(self):
        """
        host.present
        """
        name = "spam.bacon"
        ip = "10.10.10.10"
        ret = self.run_state("host.present", name=name, ip=ip)
        self.assertSaltTrueReturn(ret)
        with salt.utils.files.fopen(self.hosts_file) as fp_:
            output = salt.utils.stringutils.to_unicode(fp_.read())
            self.assertIn("{}\t\t{}".format(ip, name), output)
