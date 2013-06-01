import sys
import os
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from saltunittest import TestCase, TestLoader, TextTestRunner, skipIf
try:
    from mock import MagicMock, patch
    has_mock = True
except ImportError:
    has_mock = False

import salt.modules.gem as gem
gem.__salt__ = {}


@skipIf(has_mock is False, "mock python module is unavailable")
class TestGemModule(TestCase):

    def test__gem(self):
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(gem.__salt__,
                        {'rvm.is_installed': MagicMock(return_value=False),
                         'cmd.run_all': mock}):
            gem._gem("install rails")
            mock.assert_called_once_with("gem install rails", runas=None)

        mock = MagicMock(return_value=None)
        with patch.dict(gem.__salt__,
                        {'rvm.is_installed': MagicMock(return_value=True),
                         'rvm.do': mock}):
            gem._gem("install rails", ruby="1.9.3")
            mock.assert_called_once_with(
                "1.9.3", "gem install rails", runas=None
            )

    def test_list(self):
        output = '''
actionmailer (2.3.14)
actionpack (2.3.14)
activerecord (2.3.14)
activeresource (2.3.14)
activesupport (3.0.5, 2.3.14)
rake (0.9.2, 0.8.7)
responds_to_parent (1.0.20091013)
sass (3.1.15, 3.1.7)
'''
        mock = MagicMock(return_value=output)
        with patch.object(gem, '_gem', new=mock):
            self.assertEqual(
                {'actionmailer': ['2.3.14'],
                 'actionpack': ['2.3.14'],
                 'activerecord': ['2.3.14'],
                 'activeresource': ['2.3.14'],
                 'activesupport': ['3.0.5', '2.3.14'],
                 'rake': ['0.9.2', '0.8.7'],
                 'responds_to_parent': ['1.0.20091013'],
                 'sass': ['3.1.15', '3.1.7']},
                gem.list())

    def test_sources_list(self):
        output = '''*** CURRENT SOURCES ***

http://rubygems.org/
'''
        mock = MagicMock(return_value=output)
        with patch.object(gem, '_gem', new=mock):
            self.assertEqual(
                ['http://rubygems.org/'], gem.sources_list())


if __name__ == "__main__":
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(TestGemModule)
    TextTestRunner(verbosity=1).run(tests)
