# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

from tests.support.unit import TestCase
import salt.utils.stringutils


from salt.pillar.pillar_ldap import _config


class LdapPillarTestCase(TestCase):

    def test__config_returns_str(self):
        conf = {'foo': 'bar'}
        assert _config('foo', conf) == salt.utils.stringutils.to_str('bar')

    def test__conf_defaults_to_none(self):
        conf = {'foo': 'bar'}
        assert _config('bang', conf) is None

    def test__conf_returns_str_from_unicode_default(self):
        conf = {'foo': 'bar'}
        default = salt.utils.stringutils.to_unicode('bam')
        assert _config('bang', conf, default) == salt.utils.stringutils.to_str('bam')
