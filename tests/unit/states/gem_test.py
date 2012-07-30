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

import salt.states.gem as gem
gem.__salt__ = {}
gem.__opts__ = {'test': False}


@skipIf(has_mock is False, "mock python module is unavailable")
class TestGemState(TestCase):

    def test_installed(self):
        gems = ['foo', 'bar']
        gem_list = MagicMock(return_value=gems)
        gem_install_succeeds = MagicMock(return_value=True)
        gem_install_fails = MagicMock(return_value=False)

        with patch.dict(gem.__salt__, {'gem.list': gem_list}):
            with patch.dict(gem.__salt__,
                            {'gem.install': gem_install_succeeds}):
                ret = gem.installed('foo')
                self.assertEqual(True, ret['result'])
                ret = gem.installed('quux')
                self.assertEqual(True, ret['result'])
                gem_install_succeeds.assert_called_once_with(
                    'quux', None, runas=None)

            with patch.dict(gem.__salt__,
                            {'gem.install': gem_install_fails}):
                ret = gem.installed('quux')
                self.assertEqual(False, ret['result'])
                gem_install_fails.assert_called_once_with(
                    'quux', None, runas=None)

    def test_removed(self):
        gems = ['foo', 'bar']
        gem_list = MagicMock(return_value=gems)
        gem_uninstall_succeeds = MagicMock(return_value=True)
        gem_uninstall_fails = MagicMock(return_value=False)
        with patch.dict(gem.__salt__, {'gem.list': gem_list}):
            with patch.dict(gem.__salt__,
                            {'gem.uninstall': gem_uninstall_succeeds}):
                ret = gem.removed('quux')
                self.assertEqual(True, ret['result'])
                ret = gem.removed('foo')
                self.assertEqual(True, ret['result'])
                gem_uninstall_succeeds.assert_called_once_with(
                    'foo', None, runas=None)

            with patch.dict(gem.__salt__,
                            {'gem.uninstall': gem_uninstall_fails}):
                ret = gem.removed('bar')
                self.assertEqual(False, ret['result'])
                gem_uninstall_fails.assert_called_once_with(
                    'bar', None, runas=None)

if __name__ == "__main__":
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(TestGemState)
    TextTestRunner(verbosity=1).run(tests)
