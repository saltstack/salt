# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import json
import pprint

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import destructiveTest, ensure_in_syspath
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    mock_open,
    patch)

ensure_in_syspath('../../')

# Import third party libs
import yaml

# Import salt libs
import salt.states.file as filestate
import salt.serializers.yaml as yamlserializer
import salt.serializers.json as jsonserializer
import salt.serializers.python as pythonserializer
from salt.exceptions import CommandExecutionError
import salt
import salt.utils
import os
import shutil

filestate.__env__ = 'base'
filestate.__salt__ = {'file.manage_file': False}
filestate.__serializers__ = {
    'yaml.serialize': yamlserializer.serialize,
    'python.serialize': pythonserializer.serialize,
    'json.serialize': jsonserializer.serialize
}
filestate.__opts__ = {'test': False, 'cachedir': ''}
filestate.__instance_id__ = ''
filestate.__grains__ = {}
filestate.__low__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class TestFileState(TestCase):

    def test_serialize(self):
        def returner(contents, *args, **kwargs):
            returner.returned = contents
        returner.returned = None

        filestate.__salt__ = {
            'file.manage_file': returner
        }

        dataset = {
            "foo": True,
            "bar": 42,
            "baz": [1, 2, 3],
            "qux": 2.0
        }

        filestate.serialize('/tmp', dataset)
        self.assertEqual(yaml.load(returner.returned), dataset)

        filestate.serialize('/tmp', dataset, formatter="yaml")
        self.assertEqual(yaml.load(returner.returned), dataset)

        filestate.serialize('/tmp', dataset, formatter="json")
        self.assertEqual(json.loads(returner.returned), dataset)

        filestate.serialize('/tmp', dataset, formatter="python")
        self.assertEqual(returner.returned, pprint.pformat(dataset) + '\n')

    def test_contents_and_contents_pillar(self):
        def returner(contents, *args, **kwargs):
            returner.returned = contents
        returner.returned = None

        filestate.__salt__ = {
            'file.manage_file': returner
        }

        manage_mode_mock = MagicMock()
        filestate.__salt__['config.manage_mode'] = manage_mode_mock

        ret = filestate.managed('/tmp/foo', contents='hi', contents_pillar='foo:bar')
        self.assertEqual(False, ret['result'])

    def test_contents_pillar_doesnt_add_more_newlines(self):
        # make sure the newline
        pillar_value = 'i am the pillar value\n'

        self.run_contents_pillar(pillar_value, expected=pillar_value)

    def run_contents_pillar(self, pillar_value, expected):
        returner = MagicMock(return_value=None)

        filestate.__salt__ = {
            'file.manage_file': returner
        }

        path = '/tmp/foo'
        pillar_path = 'foo:bar'

        # the values don't matter here
        filestate.__salt__['config.manage_mode'] = MagicMock()
        filestate.__salt__['file.source_list'] = MagicMock(return_value=[None, None])
        filestate.__salt__['file.get_managed'] = MagicMock(return_value=[None, None, None])

        # pillar.get should return the pillar_value
        pillar_mock = MagicMock(return_value=pillar_value)
        filestate.__salt__['pillar.get'] = pillar_mock

        ret = filestate.managed(path, contents_pillar=pillar_path)

        # make sure no errors are returned
        self.assertEqual(None, ret)

        # Make sure the contents value matches the expected value.
        # returner.call_args[0] will be an args tuple containing all the args
        # passed to the mocked returner for file.manage_file. Any changes to
        # the arguments for file.manage_file may make this assertion fail.
        # If the test is failing, check the position of the "contents" param
        # in the manage_file() function in salt/modules/file.py, the fix is
        # likely as simple as updating the 2nd index below.
        self.assertEqual(expected, returner.call_args[0][-4])


@skipIf(NO_MOCK, NO_MOCK_REASON)
class FileTestCase(TestCase):

    '''
    Test cases for salt.states.file
    '''
    # 'symlink' function tests: 1

    def test_symlink(self):
        '''
        Test to create a symlink.
        '''
        name = '/etc/grub.conf'
        target = '/boot/grub/grub.conf'
        user = 'salt'
        if salt.utils.is_windows():
            group = 'salt'
        else:
            group = 'saltstack'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        mock_t = MagicMock(return_value=True)
        mock_f = MagicMock(return_value=False)
        mock_empty = MagicMock(return_value='')
        mock_uid = MagicMock(return_value='U1001')
        mock_gid = MagicMock(return_value='g1001')
        mock_target = MagicMock(return_value=target)
        mock_user = MagicMock(return_value=user)
        mock_grp = MagicMock(return_value=group)
        mock_os_error = MagicMock(side_effect=OSError)

        with patch.dict(filestate.__salt__, {'config.manage_mode': mock_t}):
            comt = ('Must provide name to file.symlink')
            ret.update({'comment': comt, 'name': ''})
            self.assertDictEqual(filestate.symlink('', target), ret)

        with patch.dict(filestate.__salt__, {'config.manage_mode': mock_t,
                                             'file.user_to_uid': mock_empty,
                                             'file.group_to_gid': mock_empty}):
            comt = ('User {0} does not exist. Group {1} does not exist.'.format(user, group))
            ret.update({'comment': comt, 'name': name})
            self.assertDictEqual(filestate.symlink(name, target, user=user,
                                                   group=group), ret)

        with patch.dict(filestate.__salt__, {'config.manage_mode': mock_t,
                                             'file.user_to_uid': mock_uid,
                                             'file.group_to_gid': mock_gid,
                                             'file.is_link': mock_f}):
            with patch.dict(filestate.__opts__, {'test': True}):
                with patch.object(os.path, 'exists', mock_f):
                    comt = ('Symlink {0} to {1}'
                            ' is set for creation').format(name, target)
                    ret.update({'comment': comt,
                                'result': None,
                                'pchanges': {'new': name}})
                    self.assertDictEqual(filestate.symlink(name, target,
                                                           user=user,
                                                           group=group), ret)

        with patch.dict(filestate.__salt__, {'config.manage_mode': mock_t,
                                             'file.user_to_uid': mock_uid,
                                             'file.group_to_gid': mock_gid,
                                             'file.is_link': mock_f}):
            with patch.dict(filestate.__opts__, {'test': False}):
                with patch.object(os.path, 'isdir', mock_f):
                    with patch.object(os.path, 'exists', mock_f):
                        comt = ('Directory /etc for symlink is not present')
                        ret.update({'comment': comt,
                                    'result': False,
                                    'pchanges': {'new': '/etc/grub.conf'}})
                        self.assertDictEqual(filestate.symlink(name, target,
                                                               user=user,
                                                               group=group), ret)

        with patch.dict(filestate.__salt__, {'config.manage_mode': mock_t,
                                             'file.user_to_uid': mock_uid,
                                             'file.group_to_gid': mock_gid,
                                             'file.is_link': mock_t,
                                             'file.readlink': mock_target}):
            with patch.dict(filestate.__opts__, {'test': False}):
                with patch.object(os.path, 'isdir', mock_t):
                    with patch.object(salt.states.file, '_check_symlink_ownership', mock_t):
                        comt = ('Symlink {0} is present and owned by '
                                '{1}:{2}'.format(name, user, group))
                        ret.update({'comment': comt,
                                    'result': True,
                                    'pchanges': {}})
                        self.assertDictEqual(filestate.symlink(name, target,
                                                               user=user,
                                                               group=group), ret)

        with patch.dict(filestate.__salt__, {'config.manage_mode': mock_t,
                                             'file.user_to_uid': mock_uid,
                                             'file.group_to_gid': mock_gid,
                                             'file.is_link': mock_f,
                                             'file.readlink': mock_target}):
            with patch.dict(filestate.__opts__, {'test': False}):
                with patch.object(os.path, 'isdir', mock_t):
                    with patch.object(os.path, 'lexists', mock_t):
                        comt = ('File exists where the backup target SALT'
                                ' should go')
                        ret.update({'comment': comt,
                                    'result': False,
                                    'pchanges': {'new': name}})
                        self.assertDictEqual(filestate.symlink
                                             (name, target, user=user,
                                              group=group, backupname='SALT'),
                                             ret)

        with patch.dict(filestate.__salt__, {'config.manage_mode': mock_t,
                                             'file.user_to_uid': mock_uid,
                                             'file.group_to_gid': mock_gid,
                                             'file.is_link': mock_f,
                                             'file.readlink': mock_target}):
            with patch.dict(filestate.__opts__, {'test': False}):
                with patch.object(os.path, 'isdir', mock_t):
                    with patch.object(os.path, 'isfile', mock_t):
                        comt = ('File exists where the symlink {0} should be'
                                .format(name))
                        ret.update({'comment': comt, 'result': False})
                        self.assertDictEqual(filestate.symlink
                                             (name, target, user=user,
                                              group=group), ret)

        with patch.dict(filestate.__salt__, {'config.manage_mode': mock_t,
                                             'file.user_to_uid': mock_uid,
                                             'file.group_to_gid': mock_gid,
                                             'file.is_link': mock_f,
                                             'file.readlink': mock_target,
                                             'file.symlink': mock_t,
                                             'user.info': mock_t,
                                             'file.lchown': mock_f}):
            with patch.dict(filestate.__opts__, {'test': False}):
                with patch.object(os.path, 'isdir', MagicMock(side_effect=[True, False])):
                    with patch.object(os.path, 'isfile', mock_t):
                        with patch.object(os.path, 'exists', mock_f):
                            comt = ('File exists where the symlink {0} should be'.format(name))
                            ret.update({'comment': comt, 'result': False})
                            self.assertDictEqual(filestate.symlink
                                                 (name, target, user=user,
                                                  group=group), ret)

        with patch.dict(filestate.__salt__, {'config.manage_mode': mock_t,
                                             'file.user_to_uid': mock_uid,
                                             'file.group_to_gid': mock_gid,
                                             'file.is_link': mock_f,
                                             'file.readlink': mock_target,
                                             'file.symlink': mock_t,
                                             'user.info': mock_t,
                                             'file.lchown': mock_f}):
            with patch.dict(filestate.__opts__, {'test': False}):
                with patch.object(os.path, 'isdir', MagicMock(side_effect=[True, False])):
                    with patch.object(os.path, 'isdir', mock_t):
                        with patch.object(os.path, 'exists', mock_f):
                            comt = ('Directory exists where the symlink {0} should be'.format(name))
                            ret.update({'comment': comt, 'result': False})
                            self.assertDictEqual(filestate.symlink
                                                 (name, target, user=user,
                                                  group=group), ret)

        with patch.dict(filestate.__salt__, {'config.manage_mode': mock_t,
                                             'file.user_to_uid': mock_uid,
                                             'file.group_to_gid': mock_gid,
                                             'file.is_link': mock_f,
                                             'file.readlink': mock_target,
                                             'file.symlink': mock_os_error,
                                             'user.info': mock_t,
                                             'file.lchown': mock_f}):
            with patch.dict(filestate.__opts__, {'test': False}):
                with patch.object(os.path, 'isdir', MagicMock(side_effect=[True, False])):
                    with patch.object(os.path, 'isfile', mock_f):
                        comt = ('Unable to create new symlink {0} -> '
                                '{1}: '.format(name, target))
                        ret.update({'comment': comt, 'result': False})
                        self.assertDictEqual(filestate.symlink
                                             (name, target, user=user,
                                              group=group), ret)

        with patch.dict(filestate.__salt__, {'config.manage_mode': mock_t,
                                             'file.user_to_uid': mock_uid,
                                             'file.group_to_gid': mock_gid,
                                             'file.is_link': mock_f,
                                             'file.readlink': mock_target,
                                             'file.symlink': mock_t,
                                             'user.info': mock_t,
                                             'file.lchown': mock_f,
                                             'file.get_user': mock_user,
                                             'file.get_group': mock_grp}):
            with patch.dict(filestate.__opts__, {'test': False}):
                with patch.object(os.path, 'isdir', MagicMock(side_effect=[True, False])):
                    with patch.object(os.path, 'isfile', mock_f):
                        comt = 'Created new symlink {0} -> {1}'.format(name, target)
                        ret.update({'comment': comt,
                                    'result': True,
                                    'changes': {'new': name}})
                        self.assertDictEqual(filestate.symlink
                                             (name, target, user=user,
                                              group=group), ret)

        with patch.dict(filestate.__salt__, {'config.manage_mode': mock_t,
                                             'file.user_to_uid': mock_uid,
                                             'file.group_to_gid': mock_gid,
                                             'file.is_link': mock_f,
                                             'file.readlink': mock_target,
                                             'file.symlink': mock_t,
                                             'user.info': mock_t,
                                             'file.lchown': mock_f,
                                             'file.get_user': mock_empty,
                                             'file.get_group': mock_empty}):
            with patch.dict(filestate.__opts__, {'test': False}):
                with patch.object(os.path, 'isdir', MagicMock(side_effect=[True, False])):
                    with patch.object(os.path, 'isfile', mock_f):
                        comt = ('Created new symlink {0} -> {1}, '
                                'but was unable to set ownership to '
                                '{2}:{3}'.format(name, target, user, group))
                        ret.update({'comment': comt,
                                    'result': False,
                                    'changes': {'new': name}})
                        self.assertDictEqual(filestate.symlink
                                             (name, target, user=user,
                                              group=group), ret)

    # 'absent' function tests: 1
    def test_absent(self):
        '''
        Test to make sure that the named file or directory is absent.
        '''
        name = '/fake/file.conf'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'pchanges': {},
               'changes': {}}

        mock_t = MagicMock(return_value=True)
        mock_f = MagicMock(return_value=False)
        mock_file = MagicMock(side_effect=[True, CommandExecutionError])
        mock_tree = MagicMock(side_effect=[True, OSError])

        comt = ('Must provide name to file.absent')
        ret.update({'comment': comt, 'name': ''})

        with patch.object(os.path, 'islink', MagicMock(return_value=False)):
            self.assertDictEqual(filestate.absent(''), ret)

            with patch.object(os.path, 'isabs', mock_f):
                comt = ('Specified file {0} is not an absolute path'
                        .format(name))
                ret.update({'comment': comt, 'name': name})
                self.assertDictEqual(filestate.absent(name), ret)

            with patch.object(os.path, 'isabs', mock_t):
                comt = ('Refusing to make "/" absent')
                ret.update({'comment': comt, 'name': '/'})
                self.assertDictEqual(filestate.absent('/'), ret)

            with patch.object(os.path, 'isfile', mock_t):
                with patch.dict(filestate.__opts__, {'test': True}):
                    comt = ('File {0} is set for removal'.format(name))
                    ret.update({'comment': comt,
                                'name': name,
                                'result': None,
                                'pchanges': {'removed': '/fake/file.conf'}})
                    self.assertDictEqual(filestate.absent(name), ret)
                    ret.update({'pchanges': {}})

                with patch.dict(filestate.__opts__, {'test': False}):
                    with patch.dict(filestate.__salt__,
                                    {'file.remove': mock_file}):
                        comt = ('Removed file {0}'.format(name))
                        ret.update({'comment': comt, 'result': True,
                                    'changes': {'removed': name},
                                    'pchanges': {'removed': name}})
                        self.assertDictEqual(filestate.absent(name), ret)

                        comt = ('Removed file {0}'.format(name))
                        ret.update({'comment': '',
                                    'result': False,
                                    'changes': {}})
                        self.assertDictEqual(filestate.absent(name), ret)
                        ret.update({'pchanges': {}})

            with patch.object(os.path, 'isfile', mock_f):
                with patch.object(os.path, 'isdir', mock_t):
                    with patch.dict(filestate.__opts__, {'test': True}):
                        comt = \
                            'Directory {0} is set for removal'.format(name)
                        ret.update({'comment': comt,
                                    'pchanges': {'removed': name},
                                    'result': None})
                        self.assertDictEqual(filestate.absent(name), ret)

                    with patch.dict(filestate.__opts__, {'test': False}):
                        with patch.dict(filestate.__salt__,
                                        {'file.remove': mock_tree}):
                            comt = ('Removed directory {0}'.format(name))
                            ret.update({'comment': comt, 'result': True,
                                        'changes': {'removed': name}})
                            self.assertDictEqual(filestate.absent(name), ret)

                            comt = \
                                'Failed to remove directory {0}'.format(name)
                            ret.update({'comment': comt, 'result': False,
                                        'changes': {}})
                            self.assertDictEqual(filestate.absent(name), ret)
                            ret.update({'pchanges': {}})

                with patch.object(os.path, 'isdir', mock_f):
                    with patch.dict(filestate.__opts__, {'test': True}):
                        comt = ('File {0} is not present'.format(name))
                        ret.update({'comment': comt, 'result': True})
                        self.assertDictEqual(filestate.absent(name), ret)

    # 'exists' function tests: 1

    def test_exists(self):
        '''
        Test to verify that the named file or directory is present or exists.
        '''
        name = '/etc/grub.conf'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {},
               'pchanges': {}}

        mock_t = MagicMock(return_value=True)
        mock_f = MagicMock(return_value=False)

        comt = ('Must provide name to file.exists')
        ret.update({'comment': comt, 'name': ''})
        self.assertDictEqual(filestate.exists(''), ret)

        with patch.object(os.path, 'exists', mock_f):
            comt = ('Specified path {0} does not exist'.format(name))
            ret.update({'comment': comt, 'name': name})
            self.assertDictEqual(filestate.exists(name), ret)

        with patch.object(os.path, 'exists', mock_t):
            comt = ('Path {0} exists'.format(name))
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(filestate.exists(name), ret)

    # 'missing' function tests: 1

    def test_missing(self):
        '''
        Test to verify that the named file or directory is missing.
        '''
        name = '/etc/grub.conf'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        mock_t = MagicMock(return_value=True)
        mock_f = MagicMock(return_value=False)

        comt = ('Must provide name to file.missing')
        ret.update({'comment': comt, 'name': '', 'pchanges': {}})
        self.assertDictEqual(filestate.missing(''), ret)

        with patch.object(os.path, 'exists', mock_t):
            comt = ('Specified path {0} exists'.format(name))
            ret.update({'comment': comt, 'name': name})
            self.assertDictEqual(filestate.missing(name), ret)

        with patch.object(os.path, 'exists', mock_f):
            comt = ('Path {0} is missing'.format(name))
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(filestate.missing(name), ret)

    # 'managed' function tests: 1

    @patch('salt.states.file._load_accumulators',
           MagicMock(return_value=([], [])))
    def test_managed(self):
        '''
        Test to manage a given file, this function allows for a file to be
        downloaded from the salt master and potentially run through a templating
        system.
        '''
        name = '/etc/grub.conf'
        user = 'salt'
        group = 'saltstack'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        mock_t = MagicMock(return_value=True)
        mock_f = MagicMock(return_value=False)
        mock_cmd_fail = MagicMock(return_value={'retcode': 1})
        mock_uid = MagicMock(side_effect=['', 'U12', 'U12', 'U12', 'U12', 'U12',
                                          'U12', 'U12', 'U12', 'U12', 'U12',
                                          'U12', 'U12', 'U12', 'U12', 'U12'])
        mock_gid = MagicMock(side_effect=['', 'G12', 'G12', 'G12', 'G12', 'G12',
                                          'G12', 'G12', 'G12', 'G12', 'G12',
                                          'G12', 'G12', 'G12', 'G12', 'G12'])
        mock_if = MagicMock(side_effect=[True, False, False, False, False,
                                         False, False, False])
        mock_ret = MagicMock(return_value=(ret, None))
        mock_dict = MagicMock(return_value={})
        mock_cp = MagicMock(side_effect=[Exception, True])
        mock_ex = MagicMock(side_effect=[Exception, {'changes': {name: name}},
                                         True, Exception])
        mock_mng = MagicMock(side_effect=[Exception, ('', '', ''), ('', '', ''),
                                          ('', '', True), ('', '', True),
                                          ('', '', ''), ('', '', '')])
        mock_file = MagicMock(side_effect=[CommandExecutionError, ('', ''),
                                           ('', ''), ('', ''), ('', ''),
                                           ('', ''), ('', ''), ('', ''),
                                           ('', '')])
        with patch.dict(filestate.__salt__,
                        {'config.manage_mode': mock_t,
                         'file.user_to_uid': mock_uid,
                         'file.group_to_gid': mock_gid,
                         'file.file_exists': mock_if,
                         'file.check_perms': mock_ret,
                         'file.check_managed_changes': mock_dict,
                         'file.get_managed': mock_mng,
                         'file.source_list': mock_file,
                         'file.copy': mock_cp,
                         'file.manage_file': mock_ex,
                         'cmd.run_all': mock_cmd_fail}):
            comt = ('Must provide name to file.exists')
            ret.update({'comment': comt, 'name': '', 'pchanges': {}})
            self.assertDictEqual(filestate.managed(''), ret)

            with patch.object(os.path, 'isfile', mock_f):
                comt = ('File {0} is not present and is not set for '
                        'creation'.format(name))
                ret.update({'comment': comt, 'name': name, 'result': True})
                self.assertDictEqual(filestate.managed(name, create=False),
                                     ret)

            comt = ('User salt is not available Group saltstack'
                    ' is not available')
            ret.update({'comment': comt, 'result': False})
            self.assertDictEqual(filestate.managed(name, user=user,
                                                   group=group), ret)

            with patch.object(os.path, 'isabs', mock_f):
                comt = ('Specified file {0} is not an absolute path'
                        .format(name))
                ret.update({'comment': comt, 'result': False})
                self.assertDictEqual(filestate.managed(name, user=user,
                                                       group=group), ret)

            with patch.object(os.path, 'isabs', mock_t):
                with patch.object(os.path, 'isdir', mock_t):
                    comt = ('Specified target {0} is a directory'.format(name))
                    ret.update({'comment': comt})
                    self.assertDictEqual(filestate.managed(name, user=user,
                                                           group=group), ret)

                with patch.object(os.path, 'isdir', mock_f):
                    comt = ('Context must be formed as a dict')
                    ret.update({'comment': comt})
                    self.assertDictEqual(filestate.managed(name, user=user,
                                                           group=group,
                                                           context=True), ret)

                    comt = ('Defaults must be formed as a dict')
                    ret.update({'comment': comt})
                    self.assertDictEqual(filestate.managed(name, user=user,
                                                           group=group,
                                                           defaults=True), ret)

                    comt = ('Only one of \'contents\', \'contents_pillar\', '
                            'and \'contents_grains\' is permitted')
                    ret.update({'comment': comt})
                    self.assertDictEqual(filestate.managed
                                         (name, user=user, group=group,
                                          contents='A', contents_grains='B',
                                          contents_pillar='C'), ret)

                    with patch.object(os.path, 'exists', mock_t):
                        with patch.dict(filestate.__opts__, {'test': True}):
                            comt = ('File {0} not updated'.format(name))
                            ret.update({'comment': comt})
                            self.assertDictEqual(filestate.managed
                                                 (name, user=user, group=group,
                                                  replace=False), ret)

                            comt = ('The file {0} is in the correct state'
                                    .format(name))
                            ret.update({'comment': comt, 'result': True})
                            self.assertDictEqual(filestate.managed
                                                 (name, user=user, contents='A',
                                                  group=group), ret)

                    with patch.object(os.path, 'exists', mock_f):
                        with patch.dict(filestate.__opts__,
                                        {'test': False}):
                            comt = ('Unable to manage file: ')
                            ret.update({'comment': comt, 'result': False})
                            self.assertDictEqual(filestate.managed
                                                 (name, user=user, group=group,
                                                  contents='A'), ret)

                            comt = ('Unable to manage file: ')
                            ret.update({'comment': comt, 'result': False})
                            self.assertDictEqual(filestate.managed
                                                 (name, user=user, group=group,
                                                  contents='A'), ret)

                            with patch.object(salt.utils, 'mkstemp',
                                              return_value=name):
                                comt = ('Unable to copy file {0} to {1}: '
                                        .format(name, name))
                                ret.update({'comment': comt, 'result': False})
                                self.assertDictEqual(filestate.managed
                                                     (name, user=user,
                                                      group=group,
                                                      check_cmd='A'), ret)

                            comt = ('Unable to check_cmd file: ')
                            ret.update({'comment': comt, 'result': False})
                            self.assertDictEqual(filestate.managed
                                                 (name, user=user, group=group,
                                                  check_cmd='A'), ret)

                            comt = ('check_cmd execution failed')
                            ret.update({'comment': comt, 'result': False, 'skip_watch': True})
                            ret.pop('pchanges')
                            self.assertDictEqual(filestate.managed
                                                 (name, user=user, group=group,
                                                  check_cmd='A'), ret)

                            comt = ('check_cmd execution failed')
                            ret.update({'comment': True, 'pchanges': {}})
                            ret.pop('skip_watch', None)
                            self.assertDictEqual(filestate.managed
                                                 (name, user=user, group=group),
                                                 ret)

                            self.assertTrue(filestate.managed
                                            (name, user=user, group=group))

                            comt = ('Unable to manage file: ')
                            ret.update({'comment': comt})
                            self.assertDictEqual(filestate.managed
                                                 (name, user=user, group=group),
                                                 ret)

    # 'directory' function tests: 1

    def test_directory(self):
        '''
        Test to ensure that a named directory is present and has the right perms
        '''
        name = '/etc/grub.conf'
        user = 'salt'
        group = 'saltstack'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'pchanges': {},
               'changes': {}}

        comt = ('Must provide name to file.directory')
        ret.update({'comment': comt, 'name': ''})
        self.assertDictEqual(filestate.directory(''), ret)

        mock_t = MagicMock(return_value=True)
        mock_f = MagicMock(return_value=False)
        mock_perms = MagicMock(return_value=(ret, ''))
        mock_uid = MagicMock(side_effect=['', 'U12', 'U12', 'U12', 'U12', 'U12',
                                          'U12', 'U12', 'U12', 'U12', 'U12'])
        mock_gid = MagicMock(side_effect=['', 'G12', 'G12', 'G12', 'G12', 'G12',
                                          'G12', 'G12', 'G12', 'G12', 'G12'])
        with patch.dict(filestate.__salt__, {'config.manage_mode': mock_t,
                                             'file.user_to_uid': mock_uid,
                                             'file.group_to_gid': mock_gid,
                                             'file.stats': mock_f,
                                             'file.check_perms': mock_perms,
                                             'file.mkdir': mock_t}):
            if salt.utils.is_windows():
                comt = ('User salt is not available Group salt'
                        ' is not available')
            else:
                comt = ('User salt is not available Group saltstack'
                        ' is not available')
            ret.update({'comment': comt, 'name': name})
            self.assertDictEqual(filestate.directory(name, user=user,
                                                     group=group), ret)

            with patch.object(os.path, 'isabs', mock_f):
                comt = ('Specified file {0} is not an absolute path'
                        .format(name))
                ret.update({'comment': comt})
                self.assertDictEqual(filestate.directory(name, user=user,
                                                         group=group), ret)

            with patch.object(os.path, 'isabs', mock_t):
                with patch.object(os.path, 'isfile',
                                  MagicMock(side_effect=[True, True, False,
                                                         True, True, True,
                                                         False])):
                    with patch.object(os.path, 'lexists', mock_t):
                        comt = ('File exists where the backup target'
                                ' A should go')
                        ret.update({'comment': comt})
                        self.assertDictEqual(filestate.directory
                                             (name, user=user,
                                              group=group,
                                              backupname='A'), ret)

                    with patch.object(os.path, 'isfile', mock_t):
                        comt = ('Specified location {0} exists and is a file'
                                .format(name))
                        ret.update({'comment': comt})
                        self.assertDictEqual(filestate.directory(name, user=user,
                                                                 group=group), ret)

                    with patch.object(os.path, 'islink', mock_t):
                        comt = ('Specified location {0} exists and is a symlink'
                                .format(name))
                        ret.update({'comment': comt})
                        self.assertDictEqual(filestate.directory(name,
                                                                 user=user,
                                                                 group=group),
                                             ret)

                with patch.object(os.path, 'isfile', mock_f):
                    with patch.dict(filestate.__opts__, {'test': True}):
                        comt = ('The following files will be changed:\n{0}:'
                                ' directory - new\n'.format(name))
                        ret.update({'comment': comt, 'result': None, 'pchanges': {'/etc/grub.conf': {'directory': 'new'}}})
                        self.assertDictEqual(filestate.directory(name,
                                                                 user=user,
                                                                 group=group),
                                             ret)

                    with patch.dict(filestate.__opts__, {'test': False}):
                        with patch.object(os.path, 'isdir', mock_f):
                            comt = ('No directory to create {0} in'
                                    .format(name))
                            ret.update({'comment': comt, 'result': False})
                            self.assertDictEqual(filestate.directory
                                                 (name, user=user, group=group),
                                                 ret)

                        with patch.object(os.path, 'isdir',
                                          MagicMock(side_effect=[True, False, True, True])):
                            comt = ('Failed to create directory {0}'
                                    .format(name))
                            ret.update({'comment': comt, 'result': False})
                            self.assertDictEqual(filestate.directory
                                                 (name, user=user, group=group),
                                                 ret)

                        recurse = ['ignore_files', 'ignore_dirs']
                        with patch.object(os.path, 'isdir', mock_t):
                            self.assertDictEqual(filestate.directory
                                                 (name, user=user,
                                                  recurse=recurse, group=group),
                                                 ret)

                            self.assertDictEqual(filestate.directory
                                                 (name, user=user, group=group),
                                                 ret)

    # 'recurse' function tests: 1

    def test_recurse(self):
        '''
        Test to recurse through a subdirectory on the master
        and copy said subdirectory over to the specified path.
        '''
        name = '/opt/code/flask'
        source = 'salt://code/flask'
        user = 'salt'
        group = 'saltstack'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'pchanges': {},
               'changes': {}}

        comt = ("'mode' is not allowed in 'file.recurse'."
                " Please use 'file_mode' and 'dir_mode'.")
        ret.update({'comment': comt})
        self.assertDictEqual(filestate.recurse(name, source, mode='W'), ret)

        mock_t = MagicMock(return_value=True)
        mock_f = MagicMock(return_value=False)
        mock_uid = MagicMock(return_value='')
        mock_gid = MagicMock(return_value='')
        mock_l = MagicMock(return_value=[])
        mock_emt = MagicMock(side_effect=[[], ['code/flask'], ['code/flask']])
        mock_lst = MagicMock(side_effect=[CommandExecutionError, (source, ''),
                                          (source, ''), (source, '')])
        with patch.dict(filestate.__salt__, {'config.manage_mode': mock_t,
                                             'file.user_to_uid': mock_uid,
                                             'file.group_to_gid': mock_gid,
                                             'file.source_list': mock_lst,
                                             'cp.list_master_dirs': mock_emt,
                                             'cp.list_master': mock_l}):
            comt = ('User salt is not available Group saltstack'
                    ' is not available')
            ret.update({'comment': comt})
            self.assertDictEqual(filestate.recurse(name, source, user=user,
                                                   group=group), ret)

            with patch.object(os.path, 'isabs', mock_f):
                comt = ('Specified file {0} is not an absolute path'
                        .format(name))
                ret.update({'comment': comt})
                self.assertDictEqual(filestate.recurse(name, source), ret)

            with patch.object(os.path, 'isabs', mock_t):
                comt = ("Invalid source '1' (must be a salt:// URI)")
                ret.update({'comment': comt})
                self.assertDictEqual(filestate.recurse(name, 1), ret)

                comt = ("Invalid source '//code/flask' (must be a salt:// URI)")
                ret.update({'comment': comt})
                self.assertDictEqual(filestate.recurse(name, '//code/flask'),
                                     ret)

                comt = ('Recurse failed: ')
                ret.update({'comment': comt})
                self.assertDictEqual(filestate.recurse(name, source), ret)

                comt = ("The directory 'salt://code/flask' does not exist"
                        " on the salt fileserver in saltenv 'base'")
                ret.update({'comment': comt})
                self.assertDictEqual(filestate.recurse(name, source), ret)

                with patch.object(os.path, 'isdir', mock_f):
                    with patch.object(os.path, 'exists', mock_t):
                        comt = ('The path {0} exists and is not a directory'
                                .format(name))
                        ret.update({'comment': comt})
                        self.assertDictEqual(filestate.recurse(name, source),
                                             ret)

                with patch.object(os.path, 'isdir', mock_t):
                    comt = ('The directory {0} is in the correct state'
                            .format(name))
                    ret.update({'comment': comt, 'result': True})
                    self.assertDictEqual(filestate.recurse(name, source), ret)

    # 'replace' function tests: 1

    def test_replace(self):
        '''
        Test to maintain an edit in a file.
        '''
        name = '/etc/grub.conf'
        pattern = ('CentOS +')
        repl = 'salt'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        comt = ('Must provide name to file.replace')
        ret.update({'comment': comt, 'name': '', 'pchanges': {}})
        self.assertDictEqual(filestate.replace('', pattern, repl), ret)

        mock_t = MagicMock(return_value=True)
        mock_f = MagicMock(return_value=False)
        with patch.object(os.path, 'isabs', mock_f):
            comt = ('Specified file {0} is not an absolute path'.format(name))
            ret.update({'comment': comt, 'name': name})
            self.assertDictEqual(filestate.replace(name, pattern, repl), ret)

        with patch.object(os.path, 'isabs', mock_t):
            with patch.object(os.path, 'exists', mock_t):
                with patch.dict(filestate.__salt__, {'file.replace': mock_f}):
                    with patch.dict(filestate.__opts__, {'test': False}):
                        comt = ('No changes needed to be made')
                        ret.update({'comment': comt, 'name': name,
                                    'result': True})
                        self.assertDictEqual(filestate.replace(name, pattern,
                                                               repl), ret)

    # 'blockreplace' function tests: 1

    @patch('salt.states.file._load_accumulators',
           MagicMock(return_value=([], [])))
    def test_blockreplace(self):
        '''
        Test to maintain an edit in a file in a zone
        delimited by two line markers.
        '''
        name = '/etc/hosts'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'pchanges': {},
               'changes': {}}

        comt = ('Must provide name to file.blockreplace')
        ret.update({'comment': comt, 'name': ''})
        self.assertDictEqual(filestate.blockreplace(''), ret)

        mock_t = MagicMock(return_value=True)
        mock_f = MagicMock(return_value=False)
        with patch.object(os.path, 'isabs', mock_f):
            comt = ('Specified file {0} is not an absolute path'.format(name))
            ret.update({'comment': comt, 'name': name})
            self.assertDictEqual(filestate.blockreplace(name), ret)

        with patch.object(os.path, 'isabs', mock_t):
            with patch.dict(filestate.__salt__, {'file.blockreplace': mock_t}):
                with patch.dict(filestate.__opts__, {'test': True}):
                    comt = ('Changes would be made')
                    ret.update({'comment': comt, 'result': None,
                                'changes': {},
                                'pchanges': {'diff': True}})
                    self.assertDictEqual(filestate.blockreplace(name), ret)

    # 'comment' function tests: 1

    @destructiveTest
    def test_comment(self):
        '''
        Test to comment out specified lines in a file.
        '''
        name = '/etc/aliases' if salt.utils.is_darwin() else '/etc/fstab'
        regex = 'bind 127.0.0.1'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'pchanges': {},
               'changes': {}}

        comt = ('Must provide name to file.comment')
        ret.update({'comment': comt, 'name': ''})
        self.assertDictEqual(filestate.comment('', regex), ret)

        mock_t = MagicMock(return_value=True)
        mock_f = MagicMock(return_value=False)
        mock = MagicMock(side_effect=[False, True, False, False])
        with patch.object(os.path, 'isabs', mock_f):
            comt = ('Specified file {0} is not an absolute path'.format(name))
            ret.update({'comment': comt, 'name': name})
            self.assertDictEqual(filestate.comment(name, regex), ret)

        with patch.object(os.path, 'isabs', mock_t):
            with patch.dict(filestate.__salt__,
                            {'file.contains_regex_multiline': mock,
                             'file.search': mock}):
                comt = ('Pattern already commented')
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(filestate.comment(name, regex), ret)

                comt = ('{0}: Pattern not found'.format(regex))
                ret.update({'comment': comt, 'result': False})
                self.assertDictEqual(filestate.comment(name, regex), ret)

            with patch.dict(filestate.__salt__,
                            {'file.contains_regex_multiline': mock_t,
                             'file.search': mock_t,
                             'file.comment': mock_t,
                             'file.comment_line': mock_t}):
                with patch.dict(filestate.__opts__, {'test': True}):
                    comt = ('File {0} is set to be updated'.format(name))
                    ret.update({'comment': comt, 'result': None, 'pchanges': {name: 'updated'}})
                    self.assertDictEqual(filestate.comment(name, regex), ret)

                with patch.dict(filestate.__opts__, {'test': False}):
                    with patch.object(salt.utils, 'fopen',
                                      MagicMock(mock_open())):
                        comt = ('Commented lines successfully')
                        ret.update({'comment': comt, 'result': True})
                        self.assertDictEqual(filestate.comment(name, regex),
                                             ret)

    # 'uncomment' function tests: 1

    @destructiveTest
    def test_uncomment(self):
        '''
        Test to uncomment specified commented lines in a file
        '''
        name = '/etc/aliases' if salt.utils.is_darwin() else '/etc/fstab'
        regex = 'bind 127.0.0.1'

        ret = {'name': name,
               'pchanges': {},
               'result': False,
               'comment': '',
               'changes': {}}

        comt = ('Must provide name to file.uncomment')
        ret.update({'comment': comt, 'name': ''})
        self.assertDictEqual(filestate.uncomment('', regex), ret)

        mock_t = MagicMock(return_value=True)
        mock_f = MagicMock(return_value=False)
        mock = MagicMock(side_effect=[True, False, False, False, True, False,
                                      True, True])
        with patch.object(os.path, 'isabs', mock_f):
            comt = ('Specified file {0} is not an absolute path'.format(name))
            ret.update({'comment': comt, 'name': name})
            self.assertDictEqual(filestate.uncomment(name, regex), ret)

        with patch.object(os.path, 'isabs', mock_t):
            with patch.dict(filestate.__salt__,
                            {'file.contains_regex_multiline': mock,
                             'file.search': mock,
                             'file.uncomment': mock_t,
                             'file.comment_line': mock_t}):
                comt = ('Pattern already uncommented')
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(filestate.uncomment(name, regex), ret)

                comt = ('{0}: Pattern not found'.format(regex))
                ret.update({'comment': comt, 'result': False})
                self.assertDictEqual(filestate.uncomment(name, regex), ret)

                with patch.dict(filestate.__opts__, {'test': True}):
                    comt = ('File {0} is set to be updated'.format(name))
                    ret.update({'comment': comt, 'result': None, 'pchanges': {name: 'updated'}, })
                    self.assertDictEqual(filestate.uncomment(name, regex), ret)

                with patch.dict(filestate.__opts__, {'test': False}):
                    with patch.object(salt.utils, 'fopen',
                                      MagicMock(mock_open())):
                        comt = ('Uncommented lines successfully')
                        ret.update({'comment': comt, 'result': True})
                        self.assertDictEqual(filestate.uncomment(name, regex), ret)

    # 'append' function tests: 1

    def test_append(self):
        '''
        Test to ensure that some text appears at the end of a file.
        '''
        name = '/etc/motd'
        source = ['salt://motd/hr-messages.tmpl']
        sources = ['salt://motd/devops-messages.tmpl']
        text = ['Trust no one unless you have eaten much salt with him.']

        ret = {'name': name,
               'result': False,
               'comment': '',
               'pchanges': {},
               'changes': {}}

        comt = ('Must provide name to file.append')
        ret.update({'comment': comt, 'name': ''})
        self.assertDictEqual(filestate.append(''), ret)

        comt = ('source and sources are mutually exclusive')
        ret.update({'comment': comt, 'name': name})
        self.assertDictEqual(filestate.append(name, source=source,
                                              sources=sources), ret)

        mock_t = MagicMock(return_value=True)
        mock_f = MagicMock(return_value=False)
        mock_err = MagicMock(side_effect=[TypeError, True, True])
        with patch.dict(filestate.__salt__,
                        {'file.directory_exists': mock_f,
                         'file.makedirs': mock_t,
                         'file.stats': mock_f,
                         'cp.get_template': mock_f,
                         'file.contains_regex_multiline': mock_err,
                         'file.search': mock_err}):
            with patch.object(os.path, 'isdir', mock_t):
                comt = ('The following files will be changed:\n/etc:'
                        ' directory - new\n')
                ret.update({'comment': comt, 'name': name, 'pchanges': {'/etc': {'directory': 'new'}}})
                self.assertDictEqual(filestate.append(name, makedirs=True), ret)

            with patch.object(os.path, 'isabs', mock_f):
                comt = ('Specified file {0} is not an absolute path'
                        .format(name))
                ret.update({'comment': comt, 'pchanges': {}})
                self.assertDictEqual(filestate.append(name), ret)

            with patch.object(os.path, 'isabs', mock_t):
                with patch.object(os.path, 'exists', mock_t):
                    comt = ("Failed to load template file {0}".format(source))
                    ret.pop('pchanges')
                    ret.update({'comment': comt, 'name': source, 'data': [], })
                    self.assertDictEqual(filestate.append(name, source=source),
                                         ret)

                    ret.pop('data', None)
                    ret.update({'name': name})
                    with patch.object(salt.utils, 'fopen',
                                      MagicMock(mock_open(read_data=''))):
                        comt = ('No text found to append. Nothing appended')
                        ret.update({'comment': comt, 'pchanges': {}})
                        self.assertDictEqual(filestate.append(name, text=text),
                                             ret)

                        with patch.object(salt.utils, 'istextfile', mock_f):
                            with patch.dict(filestate.__opts__, {'test': True}):
                                change = {'diff': 'Replace binary file'}
                                ret.update({'comment': '', 'result': None,
                                            'changes': change})
                                self.assertDictEqual(filestate.append
                                                     (name, text=text), ret)

                            with patch.dict(filestate.__opts__,
                                            {'test': False}):
                                comt = ('File {0} is in correct state'
                                        .format(name))
                                ret.update({'comment': comt, 'result': True,
                                            'changes': {}})
                                self.assertDictEqual(filestate.append
                                                     (name, text=text), ret)

    # 'prepend' function tests: 1

    def test_prepend(self):
        '''
        Test to ensure that some text appears at the beginning of a file.
        '''
        name = '/etc/motd'
        source = ['salt://motd/hr-messages.tmpl']
        sources = ['salt://motd/devops-messages.tmpl']
        text = ['Trust no one unless you have eaten much salt with him.']

        ret = {'name': name,
               'result': False,
               'comment': '',
               'pchanges': {},
               'changes': {}}

        comt = ('Must provide name to file.prepend')
        ret.update({'comment': comt, 'name': ''})
        self.assertDictEqual(filestate.prepend(''), ret)

        comt = ('source and sources are mutually exclusive')
        ret.update({'comment': comt, 'name': name})
        self.assertDictEqual(filestate.prepend(name, source=source,
                                               sources=sources), ret)

        mock_t = MagicMock(return_value=True)
        mock_f = MagicMock(return_value=False)
        with patch.dict(filestate.__salt__,
                        {'file.directory_exists': mock_f,
                         'file.makedirs': mock_t,
                         'file.stats': mock_f,
                         'cp.get_template': mock_f,
                         'file.contains_regex_multiline': mock_f,
                         'file.search': mock_f,
                         'file.prepend': mock_t}):
            with patch.object(os.path, 'isdir', mock_t):
                comt = ('The following files will be changed:\n/etc:'
                        ' directory - new\n')
                ret.update({'comment': comt, 'name': name, 'pchanges': {'/etc': {'directory': 'new'}}})
                self.assertDictEqual(filestate.prepend(name, makedirs=True),
                                     ret)

            with patch.object(os.path, 'isabs', mock_f):
                comt = ('Specified file {0} is not an absolute path'
                        .format(name))
                ret.update({'comment': comt, 'pchanges': {}})
                self.assertDictEqual(filestate.prepend(name), ret)

            with patch.object(os.path, 'isabs', mock_t):
                with patch.object(os.path, 'exists', mock_t):
                    comt = ("Failed to load template file {0}".format(source))
                    ret.pop('pchanges')
                    ret.update({'comment': comt, 'name': source, 'data': []})
                    self.assertDictEqual(filestate.prepend(name, source=source),
                                         ret)

                    ret.pop('data', None)
                    ret.update({'name': name})
                    with patch.object(salt.utils, 'fopen',
                                      MagicMock(mock_open(read_data=''))):
                        with patch.object(salt.utils, 'istextfile', mock_f):
                            with patch.dict(filestate.__opts__, {'test': True}):
                                change = {'diff': 'Replace binary file'}
                                comt = ('File {0} is set to be updated'
                                        .format(name))
                                ret.update({'comment': comt, 'result': None,
                                    'changes': change, 'pchanges': {}})
                                self.assertDictEqual(filestate.prepend
                                                     (name, text=text), ret)

                            with patch.dict(filestate.__opts__,
                                            {'test': False}):
                                comt = ('Prepended 1 lines')
                                ret.update({'comment': comt, 'result': True,
                                            'changes': {}})
                                self.assertDictEqual(filestate.prepend
                                                     (name, text=text), ret)

    # 'patch' function tests: 1

    def test_patch(self):
        '''
        Test to apply a patch to a file.
        '''
        name = '/opt/file.txt'
        source = 'salt://file.patch'
        ha_sh = 'md5=e138491e9d5b97023cea823fe17bac22'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        comt = ('Must provide name to file.patch')
        ret.update({'comment': comt, 'name': ''})
        self.assertDictEqual(filestate.patch(''), ret)

        comt = ('{0}: file not found'.format(name))
        ret.update({'comment': comt, 'name': name})
        self.assertDictEqual(filestate.patch(name), ret)

        mock_t = MagicMock(return_value=True)
        mock_true = MagicMock(side_effect=[True, False, False, False, False])
        mock_false = MagicMock(side_effect=[False, True, True, True])
        mock_ret = MagicMock(return_value={'retcode': True})
        with patch.object(os.path, 'isabs', mock_t):
            with patch.object(os.path, 'exists', mock_t):
                comt = ('Source is required')
                ret.update({'comment': comt})
                self.assertDictEqual(filestate.patch(name), ret)

                comt = ('Hash is required')
                ret.update({'comment': comt})
                self.assertDictEqual(filestate.patch(name, source=source), ret)

                with patch.dict(filestate.__salt__,
                                {'file.check_hash': mock_true,
                                 'cp.cache_file': mock_false,
                                 'file.patch': mock_ret}):
                    comt = ('Patch is already applied')
                    ret.update({'comment': comt, 'result': True})
                    self.assertDictEqual(filestate.patch(name, source=source,
                                                         hash=ha_sh), ret)

                    comt = ("Unable to cache salt://file.patch"
                            " from saltenv 'base'")
                    ret.update({'comment': comt, 'result': False})
                    self.assertDictEqual(filestate.patch(name, source=source,
                                                         hash=ha_sh), ret)

                    with patch.dict(filestate.__opts__, {'test': True}):
                        comt = ('File /opt/file.txt will be patched')
                        ret.update({'comment': comt, 'result': None,
                                    'changes': {'retcode': True}})
                        self.assertDictEqual(filestate.patch(name,
                                                             source=source,
                                                             hash=ha_sh), ret)

                    with patch.dict(filestate.__opts__, {'test': False}):
                        ret.update({'comment': '', 'result': False})
                        self.assertDictEqual(filestate.patch(name,
                                                             source=source,
                                                             hash=ha_sh), ret)

                        self.assertDictEqual(filestate.patch
                                             (name, source=source, hash=ha_sh,
                                              dry_run_first=False), ret)

    # 'touch' function tests: 1

    def test_touch(self):
        '''
        Test to replicate the 'nix "touch" command to create a new empty
        file or update the atime and mtime of an existing file.
        '''
        name = '/var/log/httpd/logrotate.empty'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        comt = ('Must provide name to file.touch')
        ret.update({'comment': comt, 'name': ''})
        self.assertDictEqual(filestate.touch(''), ret)

        mock_t = MagicMock(return_value=True)
        mock_f = MagicMock(return_value=False)
        with patch.object(os.path, 'isabs', mock_f):
            comt = ('Specified file {0} is not an absolute path'.format(name))
            ret.update({'comment': comt, 'name': name})
            self.assertDictEqual(filestate.touch(name), ret)

        with patch.object(os.path, 'isabs', mock_t):
            with patch.object(os.path, 'exists', mock_f):
                with patch.dict(filestate.__opts__, {'test': True}):
                    comt = ('File {0} is set to be created'.format(name))
                    ret.update({'comment': comt, 'result': None})
                    self.assertDictEqual(filestate.touch(name), ret)

            with patch.dict(filestate.__opts__, {'test': False}):
                with patch.object(os.path, 'isdir', mock_f):
                    comt = ('Directory not present to touch file {0}'
                            .format(name))
                    ret.update({'comment': comt, 'result': False})
                    self.assertDictEqual(filestate.touch(name), ret)

                with patch.object(os.path, 'isdir', mock_t):
                    with patch.dict(filestate.__salt__, {'file.touch': mock_t}):
                        comt = ('Created empty file {0}'.format(name))
                        ret.update({'comment': comt, 'result': True,
                                    'changes': {'new': name}})
                        self.assertDictEqual(filestate.touch(name), ret)

    # 'copy' function tests: 1

    def test_copy(self):
        '''
        Test if the source file exists on the system, copy it to the named file.
        '''
        name = '/tmp/salt'
        source = '/tmp/salt/salt'
        user = 'salt'
        group = 'saltstack'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        comt = ('Must provide name to file.copy')
        ret.update({'comment': comt, 'name': ''})
        self.assertDictEqual(filestate.copy('', source), ret)

        mock_t = MagicMock(return_value=True)
        mock_f = MagicMock(return_value=False)
        mock_uid = MagicMock(side_effect=[''])
        mock_gid = MagicMock(side_effect=[''])
        mock_user = MagicMock(return_value=user)
        mock_grp = MagicMock(return_value=group)
        mock_io = MagicMock(side_effect=IOError)
        with patch.object(os.path, 'isabs', mock_f):
            comt = ('Specified file {0} is not an absolute path'.format(name))
            ret.update({'comment': comt, 'name': name})
            self.assertDictEqual(filestate.copy(name, source), ret)

        with patch.object(os.path, 'isabs', mock_t):
            with patch.object(os.path, 'exists', mock_f):
                comt = ('Source file "{0}" is not present'.format(source))
                ret.update({'comment': comt, 'result': False})
                self.assertDictEqual(filestate.copy(name, source), ret)

            with patch.object(os.path, 'exists', mock_t):
                with patch.dict(filestate.__salt__,
                                {'file.user_to_uid': mock_uid,
                                 'file.group_to_gid': mock_gid,
                                 'file.get_user': mock_user,
                                 'file.get_group': mock_grp,
                                 'file.get_mode': mock_grp,
                                 'file.check_perms': mock_t}):
                    comt = ('User salt is not available Group '
                            'saltstack is not available')
                    ret.update({'comment': comt, 'result': False})
                    self.assertDictEqual(filestate.copy(name, source, user=user,
                                                        group=group), ret)

                    comt1 = ('Failed to delete "{0}" in preparation for'
                             ' forced move'.format(name))
                    comt2 = ('The target file "{0}" exists and will not be '
                             'overwritten'.format(name))
                    comt3 = ('File "{0}" is set to be copied to "{1}"'
                             .format(source, name))
                    with patch.object(os.path, 'isdir', mock_f):
                        with patch.object(os.path, 'lexists', mock_t):
                            with patch.dict(filestate.__opts__,
                                            {'test': False}):
                                with patch.dict(filestate.__salt__,
                                                {'file.remove': mock_io}):
                                    ret.update({'comment': comt1,
                                                'result': False})
                                    self.assertDictEqual(filestate.copy
                                                         (name, source,
                                                          preserve=True,
                                                          force=True), ret)

                                with patch.object(os.path, 'isfile', mock_t):
                                    ret.update({'comment': comt2,
                                                'result': True})
                                    self.assertDictEqual(filestate.copy
                                                         (name, source,
                                                          preserve=True), ret)

                        with patch.object(os.path, 'lexists', mock_f):
                            with patch.dict(filestate.__opts__, {'test': True}):
                                ret.update({'comment': comt3, 'result': None})
                                self.assertDictEqual(filestate.copy
                                                     (name, source,
                                                      preserve=True), ret)

                            with patch.dict(filestate.__opts__, {'test': False}):
                                comt = ('The target directory /tmp is'
                                        ' not present')
                                ret.update({'comment': comt, 'result': False})
                                self.assertDictEqual(filestate.copy
                                                     (name, source,
                                                      preserve=True), ret)

                    with patch.object(os.path, 'isdir', mock_t):
                        with patch.dict(filestate.__opts__, {'test': False}):
                            with patch.object(shutil, 'copy',
                                              MagicMock(side_effect=[IOError,
                                                                     True])):
                                comt = ('Failed to copy "{0}" to "{1}"'
                                        .format(source, name))
                                ret.update({'comment': comt, 'result': False})
                                self.assertDictEqual(filestate.copy
                                                     (name, source,
                                                      preserve=True), ret)

                                comt = ('Copied "{0}" to "{1}"'.format(source,
                                                                       name))
                                ret.update({'comment': comt, 'result': True,
                                            'changes': {name: source}})
                                self.assertDictEqual(filestate.copy
                                                     (name, source,
                                                      preserve=True), ret)

    # 'rename' function tests: 1

    def test_rename(self):
        '''
        Test if the source file exists on the system,
        rename it to the named file.
        '''
        name = '/tmp/salt'
        source = '/tmp/salt/salt'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        comt = ('Must provide name to file.rename')
        ret.update({'comment': comt, 'name': ''})
        self.assertDictEqual(filestate.rename('', source), ret)

        mock_t = MagicMock(return_value=True)
        mock_f = MagicMock(return_value=False)

        mock_lex = MagicMock(side_effect=[False, True, True])
        with patch.object(os.path, 'isabs', mock_f):
            comt = ('Specified file {0} is not an absolute path'.format(name))
            ret.update({'comment': comt, 'name': name})
            self.assertDictEqual(filestate.rename(name, source), ret)

        mock_lex = MagicMock(return_value=False)
        with patch.object(os.path, 'isabs', mock_t):
            with patch.object(os.path, 'lexists', mock_lex):
                comt = ('Source file "{0}" has already been moved out of '
                        'place'.format(source))
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(filestate.rename(name, source), ret)

        mock_lex = MagicMock(side_effect=[True, True, True])
        with patch.object(os.path, 'isabs', mock_t):
            with patch.object(os.path, 'lexists', mock_lex):
                comt = ('The target file "{0}" exists and will not be '
                        'overwritten'.format(name))
                ret.update({'comment': comt, 'result': False})
                self.assertDictEqual(filestate.rename(name, source), ret)

        mock_lex = MagicMock(side_effect=[True, True, True])
        mock_rem = MagicMock(side_effect=IOError)
        with patch.object(os.path, 'isabs', mock_t):
            with patch.object(os.path, 'lexists', mock_lex):
                with patch.dict(filestate.__opts__, {'test': False}):
                    comt = ('Failed to delete "{0}" in preparation for '
                            'forced move'.format(name))
                    with patch.dict(filestate.__salt__,
                                    {'file.remove': mock_rem}):
                        ret.update({'name': name,
                                    'comment': comt,
                                    'result': False})
                        self.assertDictEqual(filestate.rename(name, source,
                                                              force=True), ret)

        mock_lex = MagicMock(side_effect=[True, False, False])
        with patch.object(os.path, 'isabs', mock_t):
            with patch.object(os.path, 'lexists', mock_lex):
                with patch.dict(filestate.__opts__, {'test': True}):
                    comt = ('File "{0}" is set to be moved to "{1}"'
                            .format(source, name))
                    ret.update({'name': name,
                                'comment': comt,
                                'result': None})
                    self.assertDictEqual(filestate.rename(name, source), ret)

        mock_lex = MagicMock(side_effect=[True, False, False])
        with patch.object(os.path, 'isabs', mock_t):
            with patch.object(os.path, 'lexists', mock_lex):
                with patch.object(os.path, 'isdir', mock_f):
                    with patch.dict(filestate.__opts__, {'test': False}):
                        comt = ('The target directory /tmp is not present')
                        ret.update({'name': name,
                                    'comment': comt,
                                    'result': False})
                        self.assertDictEqual(filestate.rename(name, source),
                                             ret)

        mock_lex = MagicMock(side_effect=[True, False, False])
        with patch.object(os.path, 'isabs', mock_t):
            with patch.object(os.path, 'lexists', mock_lex):
                with patch.object(os.path, 'isdir', mock_t):
                    with patch.object(os.path, 'islink', mock_f):
                        with patch.dict(filestate.__opts__, {'test': False}):
                            with patch.object(shutil, 'move',
                                              MagicMock(side_effect=IOError)):
                                comt = ('Failed to move "{0}" to "{1}"'
                                        .format(source, name))
                                ret.update({'name': name,
                                            'comment': comt,
                                            'result': False})
                                self.assertDictEqual(filestate.rename(name,
                                                                      source),
                                                     ret)

        mock_lex = MagicMock(side_effect=[True, False, False])
        with patch.object(os.path, 'isabs', mock_t):
            with patch.object(os.path, 'lexists', mock_lex):
                with patch.object(os.path, 'isdir', mock_t):
                    with patch.object(os.path, 'islink', mock_f):
                        with patch.dict(filestate.__opts__, {'test': False}):
                            with patch.object(shutil, 'move', MagicMock()):
                                comt = ('Moved "{0}" to "{1}"'.format(source,
                                                                      name))
                                ret.update({'name': name,
                                            'comment': comt,
                                            'result': True,
                                            'changes': {name: source}})
                                self.assertDictEqual(filestate.rename(name,
                                                                      source),
                                                     ret)

    # 'accumulated' function tests: 1

    @patch('salt.states.file._load_accumulators',
           MagicMock(return_value=({}, {})))
    @patch('salt.states.file._persist_accummulators',
           MagicMock(return_value=True))
    def test_accumulated(self):
        '''
        Test to prepare accumulator which can be used in template in file.
        '''
        name = 'animals_doing_things'
        filename = '/tmp/animal_file.txt'
        text = ' jumps over the lazy dog.'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        comt = ('Must provide name to file.accumulated')
        ret.update({'comment': comt, 'name': ''})
        self.assertDictEqual(filestate.accumulated('', filename, text), ret)

        comt = ('No text supplied for accumulator')
        ret.update({'comment': comt, 'name': name})
        self.assertDictEqual(filestate.accumulated(name, filename, None), ret)

        with patch.dict(filestate.__low__, {'require_in': 'file',
                                            'watch_in': 'salt',
                                            '__sls__': 'SLS', '__id__': 'ID'}):
            comt = ('Orphaned accumulator animals_doing_things in SLS:ID')
            ret.update({'comment': comt, 'name': name})
            self.assertDictEqual(filestate.accumulated(name, filename, text),
                                 ret)

        with patch.dict(filestate.__low__, {'require_in': [{'file': 'A'}],
                                            'watch_in': [{'B': 'C'}],
                                            '__sls__': 'SLS', '__id__': 'ID'}):
            comt = ('Accumulator {0} for file {1} '
                    'was charged by text'.format(name, filename))
            ret.update({'comment': comt, 'name': name, 'result': True})
            self.assertDictEqual(filestate.accumulated(name, filename, text),
                                 ret)

    # 'serialize' function tests: 1

    def test_serialize(self):
        '''
        Test to serializes dataset and store it into managed file.
        '''
        name = '/etc/dummy/package.json'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        comt = ('Must provide name to file.serialize')
        ret.update({'comment': comt, 'name': ''})
        self.assertDictEqual(filestate.serialize(''), ret)

        mock_t = MagicMock(return_value=True)
        mock_f = MagicMock(return_value=False)
        with patch.object(os.path, 'isfile', mock_f):
            comt = ('File {0} is not present and is not set for '
                    'creation'.format(name))
            ret.update({'comment': comt, 'name': name, 'result': True})
            self.assertDictEqual(filestate.serialize(name, create=False), ret)

        comt = ("Only one of 'dataset' and 'dataset_pillar' is permitted")
        ret.update({'comment': comt, 'result': False})
        self.assertDictEqual(filestate.serialize(name, dataset=True,
                                                 dataset_pillar=True), ret)

        comt = ("Neither 'dataset' nor 'dataset_pillar' was defined")
        ret.update({'comment': comt, 'result': False})
        self.assertDictEqual(filestate.serialize(name), ret)

        with patch.object(os.path, 'isfile', mock_t):
            comt = ('Python format is not supported for merging')
            ret.update({'comment': comt, 'result': False})
            self.assertDictEqual(filestate.serialize(name, dataset=True,
                                                     merge_if_exists=True,
                                                     formatter='python'), ret)

        comt = ('A format is not supported')
        ret.update({'comment': comt, 'result': False})
        self.assertDictEqual(filestate.serialize(name, dataset=True,
                                                 formatter='A'), ret)
        mock_changes = MagicMock(return_value=True)
        mock_no_changes = MagicMock(return_value=False)

        # __opts__['test']=True with changes
        with patch.dict(filestate.__salt__,
                        {'file.check_managed_changes': mock_changes}):
            with patch.dict(filestate.__opts__, {'test': True}):
                comt = ('Dataset will be serialized and stored into {0}'
                        .format(name))
                ret.update({'comment': comt, 'result': None, 'changes': True})
                self.assertDictEqual(
                    filestate.serialize(name, dataset=True,
                                        formatter='python'), ret)

        # __opts__['test']=True without changes
        with patch.dict(filestate.__salt__,
                        {'file.check_managed_changes': mock_no_changes}):
            with patch.dict(filestate.__opts__, {'test': True}):
                comt = ('The file {0} is in the correct state'
                        .format(name))
                ret.update({'comment': comt, 'result': True, 'changes': False})
                self.assertDictEqual(
                    filestate.serialize(name,
                                        dataset=True, formatter='python'), ret)

        mock = MagicMock(return_value=ret)
        with patch.dict(filestate.__opts__, {'test': False}):
            with patch.dict(filestate.__salt__, {'file.manage_file': mock}):
                comt = ('Dataset will be serialized and stored into {0}'
                        .format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(filestate.serialize(name, dataset=True,
                                                         formatter='python'),
                                     ret)

    # 'mknod' function tests: 1

    def test_mknod(self):
        '''
        Test to create a special file similar to the 'nix mknod command.
        '''
        name = '/dev/AA'
        ntype = 'a'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        comt = ('Must provide name to file.mknod')
        ret.update({'comment': comt, 'name': ''})
        self.assertDictEqual(filestate.mknod('', ntype), ret)

        comt = ("Node type unavailable: 'a'. Available node types are "
                "character ('c'), block ('b'), and pipe ('p')")
        ret.update({'comment': comt, 'name': name})
        self.assertDictEqual(filestate.mknod(name, ntype), ret)

    # 'mod_run_check_cmd' function tests: 1

    def test_mod_run_check_cmd(self):
        '''
        Test to execute the check_cmd logic.
        '''
        cmd = 'A'
        filename = 'B'

        ret = {'comment': 'check_cmd execution failed',
               'result': False, 'skip_watch': True}

        mock = MagicMock(side_effect=[{'retcode': 1}, {'retcode': 0}])
        with patch.dict(filestate.__salt__, {'cmd.run_all': mock}):
            self.assertDictEqual(filestate.mod_run_check_cmd(cmd, filename),
                                 ret)

            self.assertTrue(filestate.mod_run_check_cmd(cmd, filename))

if __name__ == '__main__':
    from integration import run_tests
    run_tests(FileTestCase, needs_daemon=False)
    run_tests(TestFileState, needs_daemon=False)
