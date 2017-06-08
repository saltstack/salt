# # -*- coding: utf-8 -*-

# # Import Python libs
# from __future__ import absolute_import

# # Import Salt Testing libs
# from tests.support.unit import skipIf, TestCase
# from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# # Import salt libs
# import salt.modules.cyg as cyg

# cyg.__salt__ = {}


# @skipIf(NO_MOCK, NO_MOCK_REASON)
# class TestcygModule(TestCase):

#     def test__get_cyg_dir(self):
#         self.assertEqual(cyg._get_cyg_dir(), 'c:\\cygwin64')
#         self.assertEqual(cyg._get_cyg_dir('x86_64'), 'c:\\cygwin64')
#         self.assertEqual(cyg._get_cyg_dir('x86'), 'c:\\cygwin')

#     def test_cyg_install(self):
#         mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
#         with patch.dict(cyg.__salt__,
#                         {'cmd.run_all': mock}):
#             cyg._get_cyg_dir()
#             mock.assert_called_once_with('cyg install dos2unix')

#         mock = MagicMock(return_value=None)
#         with patch.dict(cyg.__salt__,
#                         {'rvm.is_installed': MagicMock(return_value=True),
#                          'rbenv.is_installed': MagicMock(return_value=False),
#                          'rvm.do': mock}):
#             cyg._get_cyg_dir('install dos2unix', ruby='1.9.3')
#             mock.assert_called_once_with(
#                 '1.9.3', 'cyg install dos2unix'
#             )

#         mock = MagicMock(return_value=None)
#         with patch.dict(cyg.__salt__,
#                         {'rvm.is_installed': MagicMock(return_value=False),
#                          'rbenv.is_installed': MagicMock(return_value=True),
#                          'rbenv.do': mock}):
#             cyg._get_cyg_dir('install dos2unix')
#             mock.assert_called_once_with(
#                 'cyg install dos2unix'
#             )

#     def test_install_pre(self):
#         mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
#         with patch.dict(cyg.__salt__,
#                         {'rvm.is_installed': MagicMock(return_value=False),
#                          'rbenv.is_installed': MagicMock(return_value=False),
#                          'cmd.run_all': mock}):
#             cyg.install('dos2unix', pre_releases=True)
#             mock.assert_called_once_with(
#                 'cyg install dos2unix --no-rdoc --no-ri --pre'
#             )

#     def test_list(self):
#         output = '''
# actionmailer (2.3.14)
# actionpack (2.3.14)
# activerecord (2.3.14)
# activeresource (2.3.14)
# activesupport (3.0.5, 2.3.14)
# rake (0.9.2, 0.8.7)
# responds_to_parent (1.0.20091013)
# sass (3.1.15, 3.1.7)
# '''
#         mock = MagicMock(return_value=output)
#         with patch.object(cyg, '_cyg', new=mock):
#             self.assertEqual(
#                 {'actionmailer': ['2.3.14'],
#                  'actionpack': ['2.3.14'],
#                  'activerecord': ['2.3.14'],
#                  'activeresource': ['2.3.14'],
#                  'activesupport': ['3.0.5', '2.3.14'],
#                  'rake': ['0.9.2', '0.8.7'],
#                  'responds_to_parent': ['1.0.20091013'],
#                  'sass': ['3.1.15', '3.1.7']},
#                 cyg.list_())

#     def test_sources_list(self):
#         output = '''*** CURRENT SOURCES ***

# http://rubycygs.org/
# '''
#         mock = MagicMock(return_value=output)
#         with patch.object(cyg, '_cyg', new=mock):
#             self.assertEqual(
#                 ['http://rubycygs.org/'], cyg.sources_list())
