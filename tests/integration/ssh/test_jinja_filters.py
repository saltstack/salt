# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

from tests.support.case import SSHCase
from tests.support.helpers import slowTest


class SSHJinjaFiltersTest(SSHCase):
    """
    testing Jinja filters are available via state system & salt-ssh
    """

    @slowTest
    def test_dateutils_strftime(self):
        """
        test jinja filter datautils.strftime
        """
        arg = self._arg_str("state.sls", ["jinja_filters.dateutils_strftime"])
        ret = self.run_ssh(arg)
        import salt.utils.json

        ret = salt.utils.json.loads(ret)["localhost"]
        self.assertIn("module_|-test_|-test.echo_|-run", ret)
        self.assertIn("ret", ret["module_|-test_|-test.echo_|-run"]["changes"])
