
# Import salt modules
try:
    import integration
except ImportError:
    if __name__ == '__main__':
        import os
        import sys
        sys.path.insert(
            0, os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__), '../../'
                )
            )
        )
    import integration
from salt.modules import config

# Import Salt Testing libs
from salttesting import TestCase


config.__opts__ = {
    "test.option.all": "value of test.option.all in __opts__"
}
config.__pillar__ = {
    "test.option.all": "value of test.option.all in __pillar__",
    "master": {
        "test.option.all": "value of test.option.all in maste"
    }
}

config.DEFAULTS["test.option.all"] = "value of test.option.all in DEFAUTS"
config.DEFAULTS["test.option"] = "value of test.option in DEFAUTS"


class TestModulesConfig(TestCase):
    def test_defaults_only_name(self,):
        opt_name = "test.option"
        opt = config.option(opt_name)
        self.assertEqual(opt, config.DEFAULTS[opt_name])

    def test_omits(self,):
        opt_name = "test.option.all"
        opt = config.option(opt_name, omit_opts=False,
            omit_master=True,
            omit_pillar=True)

        self.assertEqual(opt, config.__opts__[opt_name])

        opt = config.option(opt_name, omit_opts=True,
            omit_master=True,
            omit_pillar=False)

        self.assertEqual(opt, config.__pillar__[opt_name])
        opt = config.option(opt_name, omit_opts=True,
            omit_master=False,
            omit_pillar=True)

        self.assertEqual(opt, config.__pillar__['master'][opt_name])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(TestModulesConfig, needs_daemon=False)
