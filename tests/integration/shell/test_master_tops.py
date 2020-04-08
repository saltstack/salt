# -*- coding: utf-8 -*-
"""
    tests.integration.shell.master_tops
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

from __future__ import absolute_import, print_function, unicode_literals

import pytest


@pytest.mark.windows_whitelisted
def test_custom_tops_gets_utilized(salt_call_cli):
    ret = salt_call_cli.run("state.show_top")
    assert ret.exitcode == 0
    assert "master_tops_test" in ret.stdout
    assert ret.json == {"base": ["core", "master_tops_test"]}
