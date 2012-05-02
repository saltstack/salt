from saltunittest import TestCase

import salt.modules.rvm as rvm
rvm.__salt__ = {
    'cmd.has_exec': lambda *args, **kwargs: True,
    'cmd.run_all': lambda *args, **kwargs: {'retcode': 0, 'stdout': ''},
    'cmd.retcode': lambda *args, **kwargs: 0
    }

class TestRvmModule(TestCase):
    def test__rvm(self):
        rvm._rvm("install", "1.9.3")
    
    def test_install(self):
        rvm.install()
    
