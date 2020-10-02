# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import salt.utils.kickstart as kickstart
from tests.support.unit import TestCase


class KickstartTestCase(TestCase):
    def test_clean_args(self):
        ret = kickstart.clean_args({"foo": "bar", "baz": False})
        assert ret == {"foo": "bar"}, ret
