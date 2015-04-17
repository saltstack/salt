# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import
import os

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import git

# Globals
git.__salt__ = {}
git.__grains__ = {}
git.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class GitTestCase(TestCase):
    '''
        Validate the git state
    '''
    def test_latest(self):
        '''
            Test to make sure the repository is cloned and is up to date
        '''
        arg = ["git@gitlab.example.com:user/website.git"]
        ret = {'changes': {'new': 'git@gitlab.example.com:user/website.git',
                           'revision': None},
               'comment': 'Repository git@gitlab.example.'
               'com:user/website.git cloned to salt',
               'name': 'git@gitlab.example.com:user/website.git',
               'result': True}

        mock = MagicMock(return_value={'result': False, 'comment': '"rev"'
                                       'is not compatible with the "mirror"'
                                       'and "bare" arguments'})
        with patch.object(git, '_fail', mock):
            self.assertDictEqual(git.latest("git@gitlab.example."
                                            "com:user/website.git",
                                            True,
                                            mirror=True,
                                            bare=True),
                                 {'comment': '"rev"is not compatible with the'
                                  ' "mirror"and "bare" arguments',
                                  'result': False})

        mock = MagicMock(return_value={'result': False,
                                       'comment': '"target" option'
                                       ' is required'})
        with patch.object(git, '_fail', mock):
            self.assertDictEqual(git.latest("git@gitlab.example.com:"
                                            "user/website.git"),
                                 {'comment': '"target" option is required',
                                  'result': False})

        with patch.dict(git.__grains__, {"shell": True}):
            mock = MagicMock(return_value={'comment': 'onlyif execution'
                                           ' failed', 'skip_watch': True,
                                           'result': True})
            with patch.object(git, 'mod_run_check', mock):
                self.assertDictEqual(git.latest("git@gitlab.example.com:"
                                                "user/website.git",
                                                target="/usr/share/nginx/prod",
                                                onlyif=True),
                                     {'changes': {},
                                      'comment': 'onlyif execution failed',
                                      'name': 'git@gitlab.example.com:'
                                      'user/website.git',
                                      'result': True,
                                      'skip_watch': True})

            mock = MagicMock(return_value="salt")
            with patch.object(git, 'mod_run_check', mock):
                mock = MagicMock(return_value=True)
                with patch.object(os.path, 'isdir', mock):
                    mock = MagicMock(return_value=Exception)
                    with patch.dict(git.__salt__, {'git.revision': mock}):
                        mock = MagicMock(return_value="salt")
                        with patch.object(git, '_fail', mock):
                            self.assertEqual(git.latest("git@gitl"
                                                        "ab.example.com:user"
                                                        "/website.git",
                                                        target="/usr/share/n"
                                                        "ginx/prod"),
                                             "salt")

                    mock = MagicMock(return_value="salt")
                    with patch.dict(git.__salt__, {'git.revision': mock}):
                        with patch.dict(git.__salt__,
                                        {'git.current_branch': mock}):
                            mock = MagicMock(return_value=None)
                            with patch.dict(git.__salt__,
                                            {'git.ls_remote': mock}):
                                with patch.dict(git.__opts__, {'test': True}):
                                    mock = MagicMock(return_value=["salt"])
                                    with patch.object(git,
                                                      '_neutral_test', mock):
                                        self.assertListEqual(git.latest(arg[0],
                                                                        None,
                                                                        "salt"),
                                                             ["salt"])

                                with patch.dict(git.__opts__, {'test': False}):
                                    mock = MagicMock(return_value=[arg[0]])
                                    with patch.dict(git.__salt__,
                                                    {'git.remote_get': mock}):
                                        mock = MagicMock(return_value=0)
                                        with patch.dict(git.__salt__,
                                                        {'cmd.retcode': mock}):
                                            sub_test_latest(self, arg)

                mock = MagicMock(return_value=False)
                with patch.object(os.path, 'isdir', mock):
                    mock = MagicMock(side_effect=[False, True])
                    with patch.object(os.path, 'isdir', mock):
                        mock = MagicMock(return_value=True)
                        with patch.object(os, 'listdir', mock):
                            mock = MagicMock(return_value=["salt"])
                            with patch.object(git, '_fail', mock):
                                self.assertListEqual(git.latest(arg[0], None,
                                                                "salt"),
                                                     ["salt"])

                    with patch.dict(git.__opts__, {'test': True}):
                        mock = MagicMock(return_value=["salt"])
                        with patch.object(git, '_neutral_test', mock):
                            self.assertListEqual(git.latest(arg[0], None,
                                                            "salt"), ["salt"])

                    with patch.dict(git.__opts__, {'test': False}):
                        mock = MagicMock(side_effect=[Exception, True])
                        with patch.dict(git.__salt__, {'git.clone': mock}):
                            mock = MagicMock(return_value=["salt"])
                            with patch.object(git, '_fail', mock):
                                self.assertListEqual(git.latest(arg[0], None,
                                                                "salt"),
                                                     ["salt"])

                            self.assertEqual(git.latest(arg[0], None, "salt",
                                                        bare=True), ret)

    def test_present(self):
        '''
            Test to make sure the repository is present
        '''
        arg = ["git@gitlab.example.com:user/website.git"]
        ret = [{'changes': {},
                'comment': '',
                'name': 'git@gitlab.example.com:user/website.git',
                'result': True},
               {'changes': {'new repository': 'git@gitlab.example'
                            '.com:user/website.git'},
                'comment': 'Initialized repository git@gitlab.'
                'example.com:user/website.git',
                'name': 'git@gitlab.example.com:user/website.git',
                'result': True}
               ]

        mock = MagicMock(return_value=True)
        with patch.object(os.path, 'isdir', mock):
            with patch.object(os.path, 'isfile', mock):
                self.assertDictEqual(git.present(arg[0], True), ret[0])

            self.assertDictEqual(git.present(arg[0], None), ret[0])

            with patch.object(os, 'listdir', mock):
                mock = MagicMock(return_value=["salt"])
                with patch.object(git, '_fail', mock):
                    self.assertListEqual(git.present(arg[0]), ["salt"])

        mock = MagicMock(return_value=False)
        with patch.object(os.path, 'isdir', mock):
            with patch.dict(git.__opts__, {'test': True}):
                mock = MagicMock(return_value="Dude")
                with patch.object(git, '_neutral_test', mock):
                    self.assertEqual(git.present(arg[0]), "Dude")

            with patch.dict(git.__opts__, {'test': False}):
                with patch.dict(git.__salt__, {'git.init': mock}):
                    self.assertDictEqual(git.present(arg[0]), ret[1])

    def test_config(self):
        '''
            Test to manage a git config setting
        '''
        arg = ["git@gitlab.example.com:user/website.git"]
        ret = [{'changes': {},
                'comment': 'No changes made',
                'name': 'git@gitlab.example.com:user/website.git',
                'result': True}
               ]
        mock = MagicMock(return_value=True)
        with patch.dict(git.__salt__, {'git.config_get': mock}):
            self.assertDictEqual(git.config(arg[0], True), ret[0])

    def test_mod_run_check(self):
        '''
            Test to execute the onlyif and unless logic.
        '''
        ret = [{'comment': 'onlyif execution failed',
                'result': True,
                'skip_watch': True},
               {'comment': 'unless execution succeeded',
                'result': True,
                'skip_watch': True}
               ]
        run_check_cmd_kwargs = {}
        run_check_cmd_kwargs['shell'] = "Salt"
        mock = MagicMock(side_effect=[1, 0])
        with patch.dict(git.__salt__, {'cmd.retcode': mock}):
            self.assertDictEqual(git.mod_run_check(run_check_cmd_kwargs,
                                                   True,
                                                   False),
                                 ret[0])

            self.assertDictEqual(git.mod_run_check(run_check_cmd_kwargs,
                                                   False,
                                                   True),
                                 ret[1])

        self.assertTrue(git.mod_run_check(run_check_cmd_kwargs, False, False))


def sub_test_latest(self, arg):
    '''
        Sub part of test_latest
    '''
    mock = MagicMock(return_value=0)
    with patch.dict(git.__salt__, {'git.checkout': mock}):
        mock = MagicMock(return_value=0)
        with patch.dict(git.__salt__, {'git.config_get': mock}):
            with patch.dict(git.__opts__, {'test': True}):
                mock = MagicMock(return_value="salt")
                with patch.object(git, '_neutral_test', mock):
                    self.assertEqual(git.latest(arg[0],
                                                True,
                                                "salt"),
                                     "salt")

if __name__ == '__main__':
    from integration import run_tests
    run_tests(GitTestCase, needs_daemon=False)
