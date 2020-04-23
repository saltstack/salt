# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function, unicode_literals

import pytest
from salt.ext import six
from tests.support.case import ModuleCase
from tests.support.unit import skipIf


@pytest.mark.windows_whitelisted
class SysModuleTest(ModuleCase):
    """
    Validate the sys module
    """

    @skipIf(True, "SLOWTEST skip")
    def test_valid_docs(self):
        """
        Make sure no functions are exposed that don't have valid docstrings
        """
        ret = self.run_function("runtests_helpers.get_invalid_docs")
        if ret == {"missing_docstring": [], "missing_cli_example": []}:
            return

        if isinstance(ret, six.string_types):
            self.fail(ret)

        self.fail(
            "There are some functions which do not have a docstring or do not "
            "have an example:\nNo docstring:\n{0}\nNo example:\n{1}\n".format(
                "\n".join(["  - {0}".format(f) for f in ret["missing_docstring"]]),
                "\n".join(["  - {0}".format(f) for f in ret["missing_cli_example"]]),
            )
        )
