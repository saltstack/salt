# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import salt.utils.stringutils
from salt.pillar.pillar_ldap import _config
from tests.support.unit import TestCase, skipIf


class LdapPillarTestCase(TestCase):
    @skipIf(True, "FASTTEST skip")
    def test__config_returns_str(self):
        conf = {"foo": "bar"}
        assert _config("foo", conf) == salt.utils.stringutils.to_str("bar")

    @skipIf(True, "FASTTEST skip")
    def test__conf_defaults_to_none(self):
        conf = {"foo": "bar"}
        assert _config("bang", conf) is None

    @skipIf(True, "FASTTEST skip")
    def test__conf_returns_str_from_unicode_default(self):
        conf = {"foo": "bar"}
        default = salt.utils.stringutils.to_unicode("bam")
        assert _config("bang", conf, default) == salt.utils.stringutils.to_str("bam")
