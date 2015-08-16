# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, patch

ensure_in_syspath('../../')

# Import Salt libs
from salt.modules import config


config.__opts__ = config.__pillar__ = {}

__opts__ = {
    'test.option.all': 'value of test.option.all in __opts__'
}
__pillar__ = {
    'test.option.all': 'value of test.option.all in __pillar__',
    'master': {
        'test.option.all': 'value of test.option.all in master'
    }
}

DEFAULTS = {
    'test.option.all': 'value of test.option.all in DEFAULTS',
    'test.option': 'value of test.option in DEFAULTS'
}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class TestModulesConfig(TestCase):
    def test_defaults_only_name(self):
        with patch.dict(config.DEFAULTS, DEFAULTS):
            opt_name = 'test.option'
            opt = config.option(opt_name)
            self.assertEqual(opt, config.DEFAULTS[opt_name])

    def test_omits(self):
        with patch.dict(config.DEFAULTS, DEFAULTS):
            with patch.dict(config.__pillar__, __pillar__):
                with patch.dict(config.__opts__, __opts__):
                    opt_name = 'test.option.all'
                    opt = config.option(opt_name,
                                        omit_opts=False,
                                        omit_master=True,
                                        omit_pillar=True)

                    self.assertEqual(opt, config.__opts__[opt_name])

                    opt = config.option(opt_name,
                                        omit_opts=True,
                                        omit_master=True,
                                        omit_pillar=False)

                    self.assertEqual(opt, config.__pillar__[opt_name])
                    opt = config.option(opt_name,
                                        omit_opts=True,
                                        omit_master=False,
                                        omit_pillar=True)

                    self.assertEqual(
                        opt, config.__pillar__['master'][opt_name])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(TestModulesConfig, needs_daemon=False)
