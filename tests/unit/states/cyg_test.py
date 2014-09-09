# # -*- coding: utf-8 -*-

# # Import Salt Testing libs
# from salttesting import skipIf, TestCase
# from salttesting.helpers import ensure_in_syspath
# from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch
# ensure_in_syspath('../../')

# # Late import so mock can do its job
# import salt.states.cyg as cyg
# cyg.__salt__ = {}
# cyg.__opts__ = {'test': False}


# @skipIf(NO_MOCK, NO_MOCK_REASON)
# class TestGemState(TestCase):

#     def test_installed(self):
#         gems = {'foo': ['1.0'], 'bar': ['2.0']}
#         gem_list = MagicMock(return_value=gems)
#         gem_install_succeeds = MagicMock(return_value=True)
#         gem_install_fails = MagicMock(return_value=False)

#         with patch.dict(gem.__salt__, {'gem.list': gem_list}):
#             with patch.dict(gem.__salt__,
#                             {'gem.install': gem_install_succeeds}):
#                 ret = gem.installed('foo')
#                 self.assertEqual(True, ret['result'])
#                 ret = gem.installed('quux')
#                 self.assertEqual(True, ret['result'])
#                 gem_install_succeeds.assert_called_once_with(
#                     'quux', pre_releases=False, ruby=None, runas=None,
#                     version=None, rdoc=False, ri=False
#                 )

#             with patch.dict(gem.__salt__,
#                             {'gem.install': gem_install_fails}):
#                 ret = gem.installed('quux')
#                 self.assertEqual(False, ret['result'])
#                 gem_install_fails.assert_called_once_with(
#                     'quux', pre_releases=False, ruby=None, runas=None,
#                     version=None, rdoc=False, ri=False
#                 )

#     def test_removed(self):
#         gems = ['foo', 'bar']
#         gem_list = MagicMock(return_value=gems)
#         gem_uninstall_succeeds = MagicMock(return_value=True)
#         gem_uninstall_fails = MagicMock(return_value=False)
#         with patch.dict(gem.__salt__, {'gem.list': gem_list}):
#             with patch.dict(gem.__salt__,
#                             {'gem.uninstall': gem_uninstall_succeeds}):
#                 ret = gem.removed('quux')
#                 self.assertEqual(True, ret['result'])
#                 ret = gem.removed('foo')
#                 self.assertEqual(True, ret['result'])
#                 gem_uninstall_succeeds.assert_called_once_with(
#                     'foo', None, runas=None)

#             with patch.dict(gem.__salt__,
#                             {'gem.uninstall': gem_uninstall_fails}):
#                 ret = gem.removed('bar')
#                 self.assertEqual(False, ret['result'])
#                 gem_uninstall_fails.assert_called_once_with(
#                     'bar', None, runas=None)


# if __name__ == '__main__':
#     from integration import run_tests
#     run_tests(TestGemState, needs_daemon=False)
