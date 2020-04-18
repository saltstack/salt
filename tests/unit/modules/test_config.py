# -*- coding: utf-8 -*-
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import fnmatch

# Import Salt libs
import salt.modules.config as config

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.unit import TestCase

DEFAULTS = {
    "test.option.foo": "value of test.option.foo in DEFAULTS",
    "test.option.bar": "value of test.option.bar in DEFAULTS",
    "test.option.baz": "value of test.option.baz in DEFAULTS",
    "test.option": "value of test.option in DEFAULTS",
}


class TestModulesConfig(TestCase, LoaderModuleMockMixin):

    no_match = "test.option.nope"
    opt_name = "test.option.foo"
    wildcard_opt_name = "test.option.b*"

    def setup_loader_modules(self):
        return {
            config: {
                "__opts__": {
                    "test.option.foo": "value of test.option.foo in __opts__",
                    "test.option.bar": "value of test.option.bar in __opts__",
                    "test.option.baz": "value of test.option.baz in __opts__",
                },
                "__pillar__": {
                    "test.option.foo": "value of test.option.foo in __pillar__",
                    "test.option.bar": "value of test.option.bar in __pillar__",
                    "test.option.baz": "value of test.option.baz in __pillar__",
                    "master": {
                        "test.option.foo": "value of test.option.foo in master",
                        "test.option.bar": "value of test.option.bar in master",
                        "test.option.baz": "value of test.option.baz in master",
                    },
                },
                "__grains__": {
                    "test.option.foo": "value of test.option.foo in __grains__",
                    "test.option.bar": "value of test.option.bar in __grains__",
                    "test.option.baz": "value of test.option.baz in __grains__",
                },
            }
        }

    def _wildcard_match(self, data):
        return {x: data[x] for x in fnmatch.filter(data, self.wildcard_opt_name)}

    def test_defaults_only_name(self):
        with patch.dict(config.DEFAULTS, DEFAULTS):
            opt_name = "test.option"
            opt = config.option(opt_name)
            self.assertEqual(opt, config.DEFAULTS[opt_name])

    def test_no_match(self):
        """
        Make sure that the defa
        """
        with patch.dict(config.DEFAULTS, DEFAULTS):
            ret = config.option(self.no_match)
            assert ret == "", ret

            default = "wat"
            ret = config.option(self.no_match, default=default)
            assert ret == default, ret

            ret = config.option(self.no_match, wildcard=True)
            assert ret == {}, ret

            default = {"foo": "bar"}
            ret = config.option(self.no_match, default=default, wildcard=True)
            assert ret == default, ret

            # Should be no match since wildcard=False
            ret = config.option(self.wildcard_opt_name)
            assert ret == "", ret

    def test_omits(self):
        with patch.dict(config.DEFAULTS, DEFAULTS):

            # ********** OMIT NOTHING **********

            # Match should be in __opts__ dict
            ret = config.option(self.opt_name)
            assert ret == config.__opts__[self.opt_name], ret

            # Wildcard match
            ret = config.option(self.wildcard_opt_name, wildcard=True)
            assert ret == self._wildcard_match(config.__opts__), ret

            # ********** OMIT __opts__ **********

            # Match should be in __grains__ dict
            ret = config.option(self.opt_name, omit_opts=True)
            assert ret == config.__grains__[self.opt_name], ret

            # Wildcard match
            ret = config.option(self.wildcard_opt_name, omit_opts=True, wildcard=True)
            assert ret == self._wildcard_match(config.__grains__), ret

            # ********** OMIT __opts__, __grains__ **********

            # Match should be in __pillar__ dict
            ret = config.option(self.opt_name, omit_opts=True, omit_grains=True)
            assert ret == config.__pillar__[self.opt_name], ret

            # Wildcard match
            ret = config.option(
                self.wildcard_opt_name, omit_opts=True, omit_grains=True, wildcard=True
            )
            assert ret == self._wildcard_match(config.__pillar__), ret

            # ********** OMIT __opts__, __grains__, __pillar__ **********

            # Match should be in master opts
            ret = config.option(
                self.opt_name, omit_opts=True, omit_grains=True, omit_pillar=True
            )
            assert ret == config.__pillar__["master"][self.opt_name], ret

            # Wildcard match
            ret = config.option(
                self.wildcard_opt_name,
                omit_opts=True,
                omit_grains=True,
                omit_pillar=True,
                wildcard=True,
            )
            assert ret == self._wildcard_match(config.__pillar__["master"]), ret

            # ********** OMIT ALL THE THINGS **********

            # Match should be in master opts
            ret = config.option(
                self.opt_name,
                omit_opts=True,
                omit_grains=True,
                omit_pillar=True,
                omit_master=True,
            )
            assert ret == config.DEFAULTS[self.opt_name], ret

            # Wildcard match
            ret = config.option(
                self.wildcard_opt_name,
                omit_opts=True,
                omit_grains=True,
                omit_pillar=True,
                omit_master=True,
                wildcard=True,
            )
            assert ret == self._wildcard_match(config.DEFAULTS), ret

            # Match should be in master opts
            ret = config.option(self.opt_name, omit_all=True)
            assert ret == config.DEFAULTS[self.opt_name], ret

            # Wildcard match
            ret = config.option(self.wildcard_opt_name, omit_all=True, wildcard=True)
            assert ret == self._wildcard_match(config.DEFAULTS), ret
