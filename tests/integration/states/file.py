# -*- coding: utf-8 -*-

'''
Tests for the file state
'''

# Import python libs
from __future__ import absolute_import
import glob
import grp
import os
import pwd
import sys
import shutil
import stat
import tempfile
import textwrap
import filecmp
import textwrap

# Import 3rd-party libs
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import (
    destructiveTest,
    ensure_in_syspath,
    with_system_user_and_group
)

ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils

# Import 3rd-party libs
import salt.ext.six as six

STATE_DIR = os.path.join(integration.FILES, 'file', 'base')


class FileTest(integration.ModuleCase, integration.SaltReturnAssertsMixIn):
    '''
    Validate the file state
    '''

    def test_symlink(self):
        '''
        file.symlink
        '''
        name = os.path.join(integration.TMP, 'symlink')
        tgt = os.path.join(integration.TMP, 'target')
        ret = self.run_state('file.symlink', name=name, target=tgt)
        self.assertSaltTrueReturn(ret)

    def test_test_symlink(self):
        '''
        file.symlink test interface
        '''
        name = os.path.join(integration.TMP, 'symlink2')
        tgt = os.path.join(integration.TMP, 'target')
        ret = self.run_state('file.symlink', test=True, name=name, target=tgt)
        self.assertSaltNoneReturn(ret)

    def test_absent_file(self):
        '''
        file.absent
        '''
        name = os.path.join(integration.TMP, 'file_to_kill')
        with salt.utils.fopen(name, 'w+') as fp_:
            fp_.write('killme')
        ret = self.run_state('file.absent', name=name)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(os.path.isfile(name))

    def test_absent_dir(self):
        '''
        file.absent
        '''
        name = os.path.join(integration.TMP, 'dir_to_kill')
        if not os.path.isdir(name):
            # left behind... Don't fail because of this!
            os.makedirs(name)
        ret = self.run_state('file.absent', name=name)
        self.assertSaltTrueReturn(ret)
        self.assertFalse(os.path.isdir(name))

    def test_absent_link(self):
        '''
        file.absent
        '''
        name = os.path.join(integration.TMP, 'link_to_kill')
        if not os.path.islink('{0}.tgt'.format(name)):
            os.symlink(name, '{0}.tgt'.format(name))
        ret = self.run_state('file.absent', name=name)
        try:
            self.assertSaltTrueReturn(ret)
            self.assertFalse(os.path.islink(name))
        finally:
            if os.path.islink('{0}.tgt'.format(name)):
                os.unlink('{0}.tgt'.format(name))

    def test_test_absent(self):
        '''
        file.absent test interface
        '''
        name = os.path.join(integration.TMP, 'file_to_kill')
        with salt.utils.fopen(name, 'w+') as fp_:
            fp_.write('killme')
        ret = self.run_state('file.absent', test=True, name=name)
        try:
            self.assertSaltNoneReturn(ret)
            self.assertTrue(os.path.isfile(name))
        finally:
            os.remove(name)

    def test_managed(self):
        '''
        file.managed
        '''
        name = os.path.join(integration.TMP, 'grail_scene33')
        ret = self.run_state(
            'file.managed', name=name, source='salt://grail/scene33'
        )
        src = os.path.join(
            integration.FILES, 'file', 'base', 'grail', 'scene33'
        )
        with salt.utils.fopen(src, 'r') as fp_:
            master_data = fp_.read()
        with salt.utils.fopen(name, 'r') as fp_:
            minion_data = fp_.read()
        self.assertEqual(master_data, minion_data)
        self.assertSaltTrueReturn(ret)

    def test_managed_file_mode(self):
        '''
        file.managed, correct file permissions
        '''
        desired_mode = 504    # 0770 octal
        name = os.path.join(integration.TMP, 'grail_scene33')
        ret = self.run_state(
            'file.managed', name=name, mode='0770', source='salt://grail/scene33'
        )

        resulting_mode = stat.S_IMODE(
            os.stat(name).st_mode
        )
        self.assertEqual(oct(desired_mode), oct(resulting_mode))
        self.assertSaltTrueReturn(ret)

    def test_managed_file_mode_file_exists_replace(self):
        '''
        file.managed, existing file with replace=True, change permissions
        '''
        initial_mode = 504    # 0770 octal
        desired_mode = 384    # 0600 octal
        name = os.path.join(integration.TMP, 'grail_scene33')
        ret = self.run_state(
            'file.managed', name=name, mode=oct(initial_mode), source='salt://grail/scene33'
        )

        resulting_mode = stat.S_IMODE(
            os.stat(name).st_mode
        )
        self.assertEqual(oct(initial_mode), oct(resulting_mode))

        name = os.path.join(integration.TMP, 'grail_scene33')
        ret = self.run_state(
            'file.managed', name=name, replace=True, mode=oct(desired_mode), source='salt://grail/scene33'
        )
        resulting_mode = stat.S_IMODE(
            os.stat(name).st_mode
        )
        self.assertEqual(oct(desired_mode), oct(resulting_mode))
        self.assertSaltTrueReturn(ret)

    def test_managed_file_mode_file_exists_noreplace(self):
        '''
        file.managed, existing file with replace=False, change permissions
        '''
        initial_mode = 504    # 0770 octal
        desired_mode = 384    # 0600 octal
        name = os.path.join(integration.TMP, 'grail_scene33')
        ret = self.run_state(
            'file.managed', name=name, replace=True, mode=oct(initial_mode), source='salt://grail/scene33'
        )

        ret = self.run_state(
            'file.managed', name=name, replace=False, mode=oct(desired_mode), source='salt://grail/scene33'
        )
        resulting_mode = stat.S_IMODE(
            os.stat(name).st_mode
        )
        self.assertEqual(oct(desired_mode), oct(resulting_mode))
        self.assertSaltTrueReturn(ret)

    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_managed_dir_mode(self):
        '''
        Tests to ensure that file.managed creates directories with the
        permissions requested with the dir_mode argument
        '''
        desired_mode = 511  # 0777 in octal
        name = os.path.join(integration.TMP, 'a', 'managed_dir_mode_test_file')
        desired_owner = 'nobody'
        ret = self.run_state(
            'file.managed',
            name=name,
            source='salt://grail/scene33',
            mode=600,
            makedirs=True,
            user=desired_owner,
            dir_mode=oct(desired_mode)  # 0777
        )
        resulting_mode = stat.S_IMODE(
            os.stat(os.path.join(integration.TMP, 'a')).st_mode
        )
        resulting_owner = pwd.getpwuid(os.stat(os.path.join(integration.TMP, 'a')).st_uid).pw_name
        self.assertEqual(oct(desired_mode), oct(resulting_mode))
        self.assertSaltTrueReturn(ret)
        self.assertEqual(desired_owner, resulting_owner)

    def test_test_managed(self):
        '''
        file.managed test interface
        '''
        name = os.path.join(integration.TMP, 'grail_not_not_scene33')
        ret = self.run_state(
            'file.managed', test=True, name=name, source='salt://grail/scene33'
        )
        self.assertSaltNoneReturn(ret)
        self.assertFalse(os.path.isfile(name))

    def test_managed_show_changes_false(self):
        '''
        file.managed test interface
        '''
        name = os.path.join(integration.TMP, 'grail_not_scene33')
        with salt.utils.fopen(name, 'wb') as fp_:
            fp_.write('test_managed_show_changes_false\n')

        ret = self.run_state(
            'file.managed', name=name, source='salt://grail/scene33',
            show_changes=False
        )

        changes = next(six.itervalues(ret))['changes']
        self.assertEqual('<show_changes=False>', changes['diff'])

    def test_managed_escaped_file_path(self):
        '''
        file.managed test that 'salt://|' protects unusual characters in file path
        '''
        funny_file = tempfile.mkstemp(prefix='?f!le? n@=3&', suffix='.file type')[1]
        funny_file_name = os.path.split(funny_file)[1]
        funny_url = 'salt://|' + funny_file_name
        funny_url_path = os.path.join(STATE_DIR, funny_file_name)

        state_name = 'funny_file'
        state_file_name = state_name + '.sls'
        state_file = os.path.join(STATE_DIR, state_file_name)
        state_key = 'file_|-{0}_|-{0}_|-managed'.format(funny_file)

        try:
            salt.utils.fopen(funny_url_path, 'w').close()
            salt.utils.fopen(state_file, 'w').write(textwrap.dedent('''\
                {0}:
                  file.managed:
                    - source: {1}
                    - makedirs: True
                '''.format(funny_file, funny_url)))

            ret = self.run_function('state.sls', [state_name])
            self.assertTrue(ret[state_key]['result'])

        finally:
            os.remove(state_file)
            os.remove(funny_file)
            os.remove(funny_url_path)

    def test_managed_contents(self):
        '''
        test file.managed with contents that is a boolean, string, integer,
        float, list, and dictionary
        '''
        state_name = 'file-FileTest-test_managed_contents'
        state_filename = state_name + '.sls'
        state_file = os.path.join(STATE_DIR, state_filename)

        managed_files = {}
        state_keys = {}
        for typ in ('bool', 'str', 'int', 'float', 'list', 'dict'):
            managed_files[typ] = tempfile.mkstemp()[1]
            state_keys[typ] = 'file_|-{0} file_|-{1}_|-managed'.format(typ, managed_files[typ])
        try:
            salt.utils.fopen(state_file, 'w').write(textwrap.dedent('''\
                bool file:
                  file.managed:
                    - name: {bool}
                    - contents: True

                str file:
                  file.managed:
                    - name: {str}
                    - contents: Salt was here.

                int file:
                  file.managed:
                    - name: {int}
                    - contents: 340282366920938463463374607431768211456

                float file:
                  file.managed:
                    - name: {float}
                    - contents: 1.7518e-45  # gravitational coupling constant

                list file:
                  file.managed:
                    - name: {list}
                    - contents: [1, 1, 2, 3, 5, 8, 13]

                dict file:
                  file.managed:
                    - name: {dict}
                    - contents:
                        C: charge
                        P: parity
                        T: time
                '''.format(**managed_files)))

            ret = self.run_function('state.sls', [state_name])
            for typ in state_keys:
                self.assertTrue(ret[state_keys[typ]]['result'])
                self.assertIn('diff', ret[state_keys[typ]]['changes'])
        finally:
            os.remove(state_file)
            for typ in managed_files:
                os.remove(managed_files[typ])

    def test_directory(self):
        '''
        file.directory
        '''
        name = os.path.join(integration.TMP, 'a_new_dir')
        ret = self.run_state('file.directory', name=name)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isdir(name))

    def test_test_directory(self):
        '''
        file.directory
        '''
        name = os.path.join(integration.TMP, 'a_not_dir')
        ret = self.run_state('file.directory', test=True, name=name)
        self.assertSaltNoneReturn(ret)
        self.assertFalse(os.path.isdir(name))

    def test_directory_clean(self):
        '''
        file.directory with clean=True
        '''
        name = os.path.join(integration.TMP, 'directory_clean_dir')
        if not os.path.isdir(name):
            os.makedirs(name)

        strayfile = os.path.join(name, 'strayfile')
        salt.utils.fopen(strayfile, 'w').close()

        straydir = os.path.join(name, 'straydir')
        if not os.path.isdir(straydir):
            os.makedirs(straydir)

        salt.utils.fopen(os.path.join(straydir, 'strayfile2'), 'w').close()

        ret = self.run_state('file.directory', name=name, clean=True)
        try:
            self.assertSaltTrueReturn(ret)
            self.assertFalse(os.path.exists(strayfile))
            self.assertFalse(os.path.exists(straydir))
            self.assertTrue(os.path.isdir(name))
        finally:
            shutil.rmtree(name, ignore_errors=True)

    def test_directory_clean_exclude(self):
        '''
        file.directory with clean=True and exclude_pat set
        '''
        name = os.path.join(integration.TMP, 'directory_clean_dir')
        if not os.path.isdir(name):
            os.makedirs(name)

        strayfile = os.path.join(name, 'strayfile')
        salt.utils.fopen(strayfile, 'w').close()

        straydir = os.path.join(name, 'straydir')
        if not os.path.isdir(straydir):
            os.makedirs(straydir)

        strayfile2 = os.path.join(straydir, 'strayfile2')
        salt.utils.fopen(strayfile2, 'w').close()

        keepfile = os.path.join(straydir, 'keepfile')
        salt.utils.fopen(keepfile, 'w').close()

        ret = self.run_state('file.directory',
                             name=name,
                             clean=True,
                             exclude_pat='E@^straydir(|/keepfile)$')

        try:
            self.assertSaltTrueReturn(ret)
            self.assertFalse(os.path.exists(strayfile))
            self.assertFalse(os.path.exists(strayfile2))
            self.assertTrue(os.path.exists(keepfile))
        finally:
            shutil.rmtree(name, ignore_errors=True)

    def test_test_directory_clean_exclude(self):
        '''
        file.directory test with clean=True and exclude_pat set
        '''
        name = os.path.join(integration.TMP, 'directory_clean_dir')
        if not os.path.isdir(name):
            os.makedirs(name)

        strayfile = os.path.join(name, 'strayfile')
        salt.utils.fopen(strayfile, 'w').close()

        straydir = os.path.join(name, 'straydir')
        if not os.path.isdir(straydir):
            os.makedirs(straydir)

        strayfile2 = os.path.join(straydir, 'strayfile2')
        salt.utils.fopen(strayfile2, 'w').close()

        keepfile = os.path.join(straydir, 'keepfile')
        salt.utils.fopen(keepfile, 'w').close()

        ret = self.run_state('file.directory',
                             test=True,
                             name=name,
                             clean=True,
                             exclude_pat='E@^straydir(|/keepfile)$')

        comment = next(six.itervalues(ret))['comment']
        try:
            self.assertSaltNoneReturn(ret)
            self.assertTrue(os.path.exists(strayfile))
            self.assertTrue(os.path.exists(strayfile2))
            self.assertTrue(os.path.exists(keepfile))

            self.assertIn(strayfile, comment)
            self.assertIn(strayfile2, comment)
            self.assertNotIn(keepfile, comment)
        finally:
            shutil.rmtree(name, ignore_errors=True)

    def test_directory_clean_require_in(self):
        '''
        file.directory test with clean=True and require_in file
        '''
        state_name = 'file-FileTest-test_directory_clean_require_in'
        state_filename = state_name + '.sls'
        state_file = os.path.join(STATE_DIR, state_filename)

        directory = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(directory))

        wrong_file = os.path.join(directory, "wrong")
        with open(wrong_file, "w") as fp:
            fp.write("foo")
        good_file = os.path.join(directory, "bar")

        with salt.utils.fopen(state_file, 'w') as fp:
            self.addCleanup(lambda: os.remove(state_file))
            fp.write(textwrap.dedent('''\
                some_dir:
                  file.directory:
                    - name: {directory}
                    - clean: true

                {good_file}:
                  file.managed:
                    - require_in:
                      - file: some_dir
                '''.format(directory=directory, good_file=good_file)))

        ret = self.run_function('state.sls', [state_name])
        self.assertTrue(os.path.exists(good_file))
        self.assertFalse(os.path.exists(wrong_file))

    def test_directory_clean_require_in_with_id(self):
        '''
        file.directory test with clean=True and require_in file with an ID
        different from the file name
        '''
        state_name = 'file-FileTest-test_directory_clean_require_in_with_id'
        state_filename = state_name + '.sls'
        state_file = os.path.join(STATE_DIR, state_filename)

        directory = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(directory))

        wrong_file = os.path.join(directory, "wrong")
        with open(wrong_file, "w") as fp:
            fp.write("foo")
        good_file = os.path.join(directory, "bar")

        with salt.utils.fopen(state_file, 'w') as fp:
            self.addCleanup(lambda: os.remove(state_file))
            fp.write(textwrap.dedent('''\
                some_dir:
                  file.directory:
                    - name: {directory}
                    - clean: true

                some_file:
                  file.managed:
                    - name: {good_file}
                    - require_in:
                      - file: some_dir
                '''.format(directory=directory, good_file=good_file)))

        ret = self.run_function('state.sls', [state_name])
        self.assertTrue(os.path.exists(good_file))
        self.assertFalse(os.path.exists(wrong_file))

    def test_directory_clean_require_with_name(self):
        '''
        file.directory test with clean=True and require with a file state
        relatively to the state's name, not its ID.
        '''
        state_name = 'file-FileTest-test_directory_clean_require_in_with_id'
        state_filename = state_name + '.sls'
        state_file = os.path.join(STATE_DIR, state_filename)

        directory = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(directory))

        wrong_file = os.path.join(directory, "wrong")
        with open(wrong_file, "w") as fp:
            fp.write("foo")
        good_file = os.path.join(directory, "bar")

        with salt.utils.fopen(state_file, 'w') as fp:
            self.addCleanup(lambda: os.remove(state_file))
            fp.write(textwrap.dedent('''\
                some_dir:
                  file.directory:
                    - name: {directory}
                    - clean: true
                    - require:
                      # This requirement refers to the name of the following
                      # state, not its ID.
                      - file: {good_file}

                some_file:
                  file.managed:
                    - name: {good_file}
                '''.format(directory=directory, good_file=good_file)))

        ret = self.run_function('state.sls', [state_name])
        self.assertTrue(os.path.exists(good_file))
        self.assertFalse(os.path.exists(wrong_file))

    def test_recurse(self):
        '''
        file.recurse
        '''
        name = os.path.join(integration.TMP, 'recurse_dir')
        ret = self.run_state('file.recurse', name=name, source='salt://grail')
        try:
            self.assertSaltTrueReturn(ret)
            self.assertTrue(os.path.isfile(os.path.join(name, '36', 'scene')))
        finally:
            if os.path.isdir(name):
                shutil.rmtree(name, ignore_errors=True)

    def test_recurse_specific_env(self):
        '''
        file.recurse passing __env__
        '''
        name = os.path.join(integration.TMP, 'recurse_dir_prod_env')
        ret = self.run_state('file.recurse',
                             name=name,
                             source='salt://holy',
                             __env__='prod')
        try:
            self.assertSaltTrueReturn(ret)
            self.assertTrue(os.path.isfile(os.path.join(name, '32', 'scene')))
        finally:
            if os.path.isdir(name):
                shutil.rmtree(name, ignore_errors=True)

        name = os.path.join(integration.TMP, 'recurse_dir_prod_env')
        ret = self.run_state('file.recurse',
                             name=name,
                             source='salt://holy',
                             saltenv='prod')
        try:
            self.assertSaltTrueReturn(ret)
            self.assertTrue(os.path.isfile(os.path.join(name, '32', 'scene')))
        finally:
            if os.path.isdir(name):
                shutil.rmtree(name, ignore_errors=True)

    def test_test_recurse(self):
        '''
        file.recurse test interface
        '''
        name = os.path.join(integration.TMP, 'recurse_test_dir')
        ret = self.run_state(
            'file.recurse', test=True, name=name, source='salt://grail',
        )
        self.assertSaltNoneReturn(ret)
        self.assertFalse(os.path.isfile(os.path.join(name, '36', 'scene')))
        self.assertFalse(os.path.exists(name))

    def test_test_recurse_specific_env(self):
        '''
        file.recurse test interface
        '''
        name = os.path.join(integration.TMP, 'recurse_test_dir_prod_env')
        ret = self.run_state('file.recurse',
                             test=True,
                             name=name,
                             source='salt://holy',
                             __env__='prod'
        )
        self.assertSaltNoneReturn(ret)
        self.assertFalse(os.path.isfile(os.path.join(name, '32', 'scene')))
        self.assertFalse(os.path.exists(name))

        name = os.path.join(integration.TMP, 'recurse_test_dir_prod_env')
        ret = self.run_state('file.recurse',
                             test=True,
                             name=name,
                             source='salt://holy',
                             saltenv='prod'
        )
        self.assertSaltNoneReturn(ret)
        self.assertFalse(os.path.isfile(os.path.join(name, '32', 'scene')))
        self.assertFalse(os.path.exists(name))

    def test_recurse_template(self):
        '''
        file.recurse with jinja template enabled
        '''
        _ts = 'TEMPLATE TEST STRING'
        name = os.path.join(integration.TMP, 'recurse_template_dir')
        ret = self.run_state(
            'file.recurse', name=name, source='salt://grail',
            template='jinja', defaults={'spam': _ts})
        try:
            self.assertSaltTrueReturn(ret)
            with salt.utils.fopen(os.path.join(name, 'scene33'), 'r') as fp_:
                contents = fp_.read()
            self.assertIn(_ts, contents)
        finally:
            shutil.rmtree(name, ignore_errors=True)

    def test_recurse_clean(self):
        '''
        file.recurse with clean=True
        '''
        name = os.path.join(integration.TMP, 'recurse_clean_dir')
        if not os.path.isdir(name):
            os.makedirs(name)
        strayfile = os.path.join(name, 'strayfile')
        salt.utils.fopen(strayfile, 'w').close()

        # Corner cases: replacing file with a directory and vice versa
        salt.utils.fopen(os.path.join(name, '36'), 'w').close()
        os.makedirs(os.path.join(name, 'scene33'))
        ret = self.run_state(
            'file.recurse', name=name, source='salt://grail', clean=True)
        try:
            self.assertSaltTrueReturn(ret)
            self.assertFalse(os.path.exists(strayfile))
            self.assertTrue(os.path.isfile(os.path.join(name, '36', 'scene')))
            self.assertTrue(os.path.isfile(os.path.join(name, 'scene33')))
        finally:
            shutil.rmtree(name, ignore_errors=True)

    def test_recurse_clean_specific_env(self):
        '''
        file.recurse with clean=True and __env__=prod
        '''
        name = os.path.join(integration.TMP, 'recurse_clean_dir_prod_env')
        if not os.path.isdir(name):
            os.makedirs(name)
        strayfile = os.path.join(name, 'strayfile')
        salt.utils.fopen(strayfile, 'w').close()

        # Corner cases: replacing file with a directory and vice versa
        salt.utils.fopen(os.path.join(name, '32'), 'w').close()
        os.makedirs(os.path.join(name, 'scene34'))
        ret = self.run_state('file.recurse',
                             name=name,
                             source='salt://holy',
                             clean=True,
                             __env__='prod')
        try:
            self.assertSaltTrueReturn(ret)
            self.assertFalse(os.path.exists(strayfile))
            self.assertTrue(os.path.isfile(os.path.join(name, '32', 'scene')))
            self.assertTrue(os.path.isfile(os.path.join(name, 'scene34')))
        finally:
            shutil.rmtree(name, ignore_errors=True)

    def test_replace(self):
        '''
        file.replace
        '''
        name = os.path.join(integration.TMP, 'replace_test')
        with salt.utils.fopen(name, 'w+') as fp_:
            fp_.write('change_me')

        ret = self.run_state('file.replace',
                name=name, pattern='change', repl='salt', backup=False)

        try:
            with salt.utils.fopen(name, 'r') as fp_:
                self.assertIn('salt', fp_.read())

            self.assertSaltTrueReturn(ret)
        finally:
            os.remove(name)

    def test_replace_issue_18612(self):
        '''
        Test the (mis-)behaviour of file.replace as described in #18612:

        Using 'prepend_if_not_found' or 'append_if_not_found' resulted in
        an infinitely growing file as 'file.replace' didn't check beforehand
        whether the changes had already been done to the file

        # Case description:

        The tested file contains one commented line
        The commented line should be uncommented in the end, nothing else should change
        '''
        test_name = 'test_replace_issue_18612'
        path_test = os.path.join(integration.TMP, test_name)

        with salt.utils.fopen(path_test, 'w+') as fp_test_:
            fp_test_.write('# en_US.UTF-8')

        ret = []
        for x in range(0, 3):
            ret.append(self.run_state('file.replace',
                name=path_test, pattern='^# en_US.UTF-8$', repl='en_US.UTF-8', append_if_not_found=True))

        try:
            # ensure, the number of lines didn't change, even after invoking 'file.replace' 3 times
            with salt.utils.fopen(path_test, 'r') as fp_test_:
                self.assertTrue((sum(1 for _ in fp_test_) == 1))

            # ensure, the replacement succeeded
            with salt.utils.fopen(path_test, 'r') as fp_test_:
                self.assertTrue(fp_test_.read().startswith('en_US.UTF-8'))

            # ensure, all runs of 'file.replace' reported success
            for item in ret:
                self.assertSaltTrueReturn(item)
        finally:
            os.remove(path_test)

    def test_replace_issue_18612_prepend(self):
        '''
        Test the (mis-)behaviour of file.replace as described in #18612:

        Using 'prepend_if_not_found' or 'append_if_not_found' resulted in
        an infinitely growing file as 'file.replace' didn't check beforehand
        whether the changes had already been done to the file

        # Case description:

        The tested multfile contains multiple lines not matching the pattern or replacement in any way
        The replacement pattern should be prepended to the file
        '''
        test_name = 'test_replace_issue_18612_prepend'
        path_in = os.path.join(
            integration.FILES, 'file.replace', '{0}.in'.format(test_name)
        )
        path_out = os.path.join(
            integration.FILES, 'file.replace', '{0}.out'.format(test_name)
        )
        path_test = os.path.join(integration.TMP, test_name)

        # create test file based on initial template
        shutil.copyfile(path_in, path_test)

        ret = []
        for x in range(0, 3):
            ret.append(self.run_state('file.replace',
                name=path_test, pattern='^# en_US.UTF-8$', repl='en_US.UTF-8', prepend_if_not_found=True))

        try:
            # ensure, the resulting file contains the expected lines
            self.assertTrue(filecmp.cmp(path_test, path_out))

            # ensure the initial file was properly backed up
            self.assertTrue(filecmp.cmp(path_test + '.bak', path_in))

            # ensure, all runs of 'file.replace' reported success
            for item in ret:
                self.assertSaltTrueReturn(item)
        finally:
            os.remove(path_test)

    def test_replace_issue_18612_append(self):
        '''
        Test the (mis-)behaviour of file.replace as described in #18612:

        Using 'prepend_if_not_found' or 'append_if_not_found' resulted in
        an infinitely growing file as 'file.replace' didn't check beforehand
        whether the changes had already been done to the file

        # Case description:

        The tested multfile contains multiple lines not matching the pattern or replacement in any way
        The replacement pattern should be appended to the file
        '''
        test_name = 'test_replace_issue_18612_append'
        path_in = os.path.join(
            integration.FILES, 'file.replace', '{0}.in'.format(test_name)
        )
        path_out = os.path.join(
            integration.FILES, 'file.replace', '{0}.out'.format(test_name)
        )
        path_test = os.path.join(integration.TMP, test_name)

        # create test file based on initial template
        shutil.copyfile(path_in, path_test)

        ret = []
        for x in range(0, 3):
            ret.append(self.run_state('file.replace',
                name=path_test, pattern='^# en_US.UTF-8$', repl='en_US.UTF-8', append_if_not_found=True))

        try:
            # ensure, the resulting file contains the expected lines
            self.assertTrue(filecmp.cmp(path_test, path_out))

            # ensure the initial file was properly backed up
            self.assertTrue(filecmp.cmp(path_test + '.bak', path_in))

            # ensure, all runs of 'file.replace' reported success
            for item in ret:
                self.assertSaltTrueReturn(item)
        finally:
            os.remove(path_test)

    def test_replace_issue_18612_append_not_found_content(self):
        '''
        Test the (mis-)behaviour of file.replace as described in #18612:

        Using 'prepend_if_not_found' or 'append_if_not_found' resulted in
        an infinitely growing file as 'file.replace' didn't check beforehand
        whether the changes had already been done to the file

        # Case description:

        The tested multfile contains multiple lines not matching the pattern or replacement in any way
        The 'not_found_content' value should be appended to the file
        '''
        test_name = 'test_replace_issue_18612_append_not_found_content'
        path_in = os.path.join(
            integration.FILES, 'file.replace', '{0}.in'.format(test_name)
        )
        path_out = os.path.join(
            integration.FILES, 'file.replace', '{0}.out'.format(test_name)
        )
        path_test = os.path.join(integration.TMP, test_name)

        # create test file based on initial template
        shutil.copyfile(path_in, path_test)

        ret = []
        for x in range(0, 3):
            ret.append(
                self.run_state('file.replace',
                    name=path_test,
                    pattern='^# en_US.UTF-8$',
                    repl='en_US.UTF-8',
                    append_if_not_found=True,
                    not_found_content='THIS LINE WASN\'T FOUND! SO WE\'RE APPENDING IT HERE!'
            ))

        try:
            # ensure, the resulting file contains the expected lines
            self.assertTrue(filecmp.cmp(path_test, path_out))

            # ensure the initial file was properly backed up
            self.assertTrue(filecmp.cmp(path_test + '.bak', path_in))

            # ensure, all runs of 'file.replace' reported success
            for item in ret:
                self.assertSaltTrueReturn(item)
        finally:
            os.remove(path_test)

    def test_replace_issue_18612_change_mid_line_with_comment(self):
        '''
        Test the (mis-)behaviour of file.replace as described in #18612:

        Using 'prepend_if_not_found' or 'append_if_not_found' resulted in
        an infinitely growing file as 'file.replace' didn't check beforehand
        whether the changes had already been done to the file

        # Case description:

        The tested file contains 5 key=value pairs
        The commented key=value pair #foo=bar should be changed to foo=salt
        The comment char (#) in front of foo=bar should be removed
        '''
        test_name = 'test_replace_issue_18612_change_mid_line_with_comment'
        path_in = os.path.join(
            integration.FILES, 'file.replace', '{0}.in'.format(test_name)
        )
        path_out = os.path.join(
            integration.FILES, 'file.replace', '{0}.out'.format(test_name)
        )
        path_test = os.path.join(integration.TMP, test_name)

        # create test file based on initial template
        shutil.copyfile(path_in, path_test)

        ret = []
        for x in range(0, 3):
            ret.append(self.run_state('file.replace',
                name=path_test, pattern='^#foo=bar$', repl='foo=salt', append_if_not_found=True))

        try:
            # ensure, the resulting file contains the expected lines
            self.assertTrue(filecmp.cmp(path_test, path_out))

            # ensure the initial file was properly backed up
            self.assertTrue(filecmp.cmp(path_test + '.bak', path_in))

            # ensure, all 'file.replace' runs reported success
            for item in ret:
                self.assertSaltTrueReturn(item)
        finally:
            os.remove(path_test)

    def test_replace_issue_18841_no_changes(self):
        '''
        Test the (mis-)behaviour of file.replace as described in #18841:

        Using file.replace in a way which shouldn't modify the file at all
        results in changed mtime of the original file and a backup file being created.

        # Case description

        The tested file contains multiple lines
        The tested file contains a line already matching the replacement (no change needed)
        The tested file's content shouldn't change at all
        The tested file's mtime shouldn't change at all
        No backup file should be created
        '''
        test_name = 'test_replace_issue_18841_no_changes'
        path_in = os.path.join(
            integration.FILES, 'file.replace', '{0}.in'.format(test_name)
        )
        path_test = os.path.join(integration.TMP, test_name)

        # create test file based on initial template
        shutil.copyfile(path_in, path_test)

        # get (m|a)time of file
        fstats_orig = os.stat(path_test)

        # define how far we predate the file
        age = 5*24*60*60

        # set (m|a)time of file 5 days into the past
        os.utime(path_test, (fstats_orig.st_mtime-age, fstats_orig.st_atime-age))

        ret = self.run_state('file.replace',
            name=path_test,
            pattern='^hello world$',
            repl='goodbye world',
            show_changes=True,
            flags=['IGNORECASE'],
            backup=False
        )

        # get (m|a)time of file
        fstats_post = os.stat(path_test)

        try:
            # ensure, the file content didn't change
            self.assertTrue(filecmp.cmp(path_in, path_test))

            # ensure no backup file was created
            self.assertFalse(os.path.exists(path_test + '.bak'))

            # ensure the file's mtime didn't change
            self.assertTrue(fstats_post.st_mtime, fstats_orig.st_mtime-age)

            # ensure, all 'file.replace' runs reported success
            self.assertSaltTrueReturn(ret)
        finally:
            os.remove(path_test)

    def test_replace_issue_18841_omit_backup(self):
        '''
        Test the (mis-)behaviour of file.replace as described in #18841:

        Using file.replace in a way which shouldn't modify the file at all
        results in changed mtime of the original file and a backup file being created.

        # Case description

        The tested file contains multiple lines
        The tested file contains a line already matching the replacement (no change needed)
        The tested file's content shouldn't change at all
        The tested file's mtime shouldn't change at all
        No backup file should be created, although backup=False isn't explicitly defined
        '''
        test_name = 'test_replace_issue_18841_omit_backup'
        path_in = os.path.join(
            integration.FILES, 'file.replace', '{0}.in'.format(test_name)
        )
        path_test = os.path.join(integration.TMP, test_name)

        # create test file based on initial template
        shutil.copyfile(path_in, path_test)

        # get (m|a)time of file
        fstats_orig = os.stat(path_test)

        # define how far we predate the file
        age = 5*24*60*60

        # set (m|a)time of file 5 days into the past
        os.utime(path_test, (fstats_orig.st_mtime-age, fstats_orig.st_atime-age))

        ret = self.run_state('file.replace',
            name=path_test,
            pattern='^hello world$',
            repl='goodbye world',
            show_changes=True,
            flags=['IGNORECASE']
        )

        # get (m|a)time of file
        fstats_post = os.stat(path_test)

        try:
            # ensure, the file content didn't change
            self.assertTrue(filecmp.cmp(path_in, path_test))

            # ensure no backup file was created
            self.assertFalse(os.path.exists(path_test + '.bak'))

            # ensure the file's mtime didn't change
            self.assertTrue(fstats_post.st_mtime, fstats_orig.st_mtime-age)

            # ensure, all 'file.replace' runs reported success
            self.assertSaltTrueReturn(ret)
        finally:
            os.remove(path_test)

    def test_comment(self):
        '''
        file.comment
        '''
        name = os.path.join(integration.TMP, 'comment_test')
        try:
            # write a line to file
            with salt.utils.fopen(name, 'w+') as fp_:
                fp_.write('comment_me')
            # comment once
            ret = self.run_state('file.comment', name=name, regex='^comment')
            # result is positive
            self.assertSaltTrueReturn(ret)
            # line is commented
            with salt.utils.fopen(name, 'r') as fp_:
                self.assertTrue(fp_.read().startswith('#comment'))

            # comment twice
            ret = self.run_state('file.comment', name=name, regex='^comment')
            # result is still positive
            self.assertSaltTrueReturn(ret)
            # line is still commented
            with salt.utils.fopen(name, 'r') as fp_:
                self.assertTrue(fp_.read().startswith('#comment'))
        finally:
            os.remove(name)

    def test_test_comment(self):
        '''
        file.comment test interface
        '''
        name = os.path.join(integration.TMP, 'comment_test_test')
        try:
            with salt.utils.fopen(name, 'w+') as fp_:
                fp_.write('comment_me')
            ret = self.run_state(
                'file.comment', test=True, name=name, regex='.*comment.*',
            )
            with salt.utils.fopen(name, 'r') as fp_:
                self.assertNotIn('#comment', fp_.read())
            self.assertSaltNoneReturn(ret)
        finally:
            os.remove(name)

    def test_uncomment(self):
        '''
        file.uncomment
        '''
        name = os.path.join(integration.TMP, 'uncomment_test')
        try:
            with salt.utils.fopen(name, 'w+') as fp_:
                fp_.write('#comment_me')
            ret = self.run_state('file.uncomment', name=name, regex='^comment')
            with salt.utils.fopen(name, 'r') as fp_:
                self.assertNotIn('#comment', fp_.read())
            self.assertSaltTrueReturn(ret)
        finally:
            os.remove(name)

    def test_test_uncomment(self):
        '''
        file.comment test interface
        '''
        name = os.path.join(integration.TMP, 'uncomment_test_test')
        try:
            with salt.utils.fopen(name, 'w+') as fp_:
                fp_.write('#comment_me')
            ret = self.run_state(
                'file.uncomment', test=True, name=name, regex='^comment.*'
            )
            with salt.utils.fopen(name, 'r') as fp_:
                self.assertIn('#comment', fp_.read())
            self.assertSaltNoneReturn(ret)
        finally:
            os.remove(name)

    def test_append(self):
        '''
        file.append
        '''
        name = os.path.join(integration.TMP, 'append_test')
        try:
            with salt.utils.fopen(name, 'w+') as fp_:
                fp_.write('#salty!')
            ret = self.run_state('file.append', name=name, text='cheese')
            with salt.utils.fopen(name, 'r') as fp_:
                self.assertIn('cheese', fp_.read())
            self.assertSaltTrueReturn(ret)
        finally:
            os.remove(name)

    def test_test_append(self):
        '''
        file.append test interface
        '''
        name = os.path.join(integration.TMP, 'append_test_test')
        try:
            with salt.utils.fopen(name, 'w+') as fp_:
                fp_.write('#salty!')
            ret = self.run_state(
                'file.append', test=True, name=name, text='cheese'
            )
            with salt.utils.fopen(name, 'r') as fp_:
                self.assertNotIn('cheese', fp_.read())
            self.assertSaltNoneReturn(ret)
        finally:
            os.remove(name)

    def test_append_issue_1864_makedirs(self):
        '''
        file.append but create directories if needed as an option, and create
        the file if it doesn't exist
        '''
        fname = 'append_issue_1864_makedirs'
        name = os.path.join(integration.TMP, fname)
        try:
            self.assertFalse(os.path.exists(name))
        except AssertionError:
            os.remove(name)
        try:
            # Non existing file get's touched
            if os.path.isfile(name):
                # left over
                os.remove(name)
            ret = self.run_state(
                'file.append', name=name, text='cheese', makedirs=True
            )
            self.assertSaltTrueReturn(ret)
        finally:
            if os.path.isfile(name):
                os.remove(name)

        # Nested directory and file get's touched
        name = os.path.join(integration.TMP, 'issue_1864', fname)
        try:
            ret = self.run_state(
                'file.append', name=name, text='cheese', makedirs=True
            )
            self.assertSaltTrueReturn(ret)
        finally:
            if os.path.isfile(name):
                os.remove(name)

        try:
            # Parent directory exists but file does not and makedirs is False
            ret = self.run_state(
                'file.append', name=name, text='cheese'
            )
            self.assertSaltTrueReturn(ret)
            self.assertTrue(os.path.isfile(name))
        finally:
            shutil.rmtree(
                os.path.join(integration.TMP, 'issue_1864'),
                ignore_errors=True
            )

    def test_prepend_issue_27401_makedirs(self):
        '''
        file.prepend but create directories if needed as an option, and create
        the file if it doesn't exist
        '''
        fname = 'prepend_issue_27401'
        name = os.path.join(integration.TMP, fname)
        try:
            self.assertFalse(os.path.exists(name))
        except AssertionError:
            os.remove(name)
        try:
            # Non existing file get's touched
            if os.path.isfile(name):
                # left over
                os.remove(name)
            ret = self.run_state(
                'file.prepend', name=name, text='cheese', makedirs=True
            )
            self.assertSaltTrueReturn(ret)
        finally:
            if os.path.isfile(name):
                os.remove(name)

        # Nested directory and file get's touched
        name = os.path.join(integration.TMP, 'issue_27401', fname)
        try:
            ret = self.run_state(
                'file.prepend', name=name, text='cheese', makedirs=True
            )
            self.assertSaltTrueReturn(ret)
        finally:
            if os.path.isfile(name):
                os.remove(name)

        try:
            # Parent directory exists but file does not and makedirs is False
            ret = self.run_state(
                'file.prepend', name=name, text='cheese'
            )
            self.assertSaltTrueReturn(ret)
            self.assertTrue(os.path.isfile(name))
        finally:
            shutil.rmtree(
                os.path.join(integration.TMP, 'issue_27401'),
                ignore_errors=True
            )

    def test_touch(self):
        '''
        file.touch
        '''
        name = os.path.join(integration.TMP, 'touch_test')
        ret = self.run_state('file.touch', name=name)
        try:
            self.assertTrue(os.path.isfile(name))
            self.assertSaltTrueReturn(ret)
        finally:
            os.remove(name)

    def test_test_touch(self):
        '''
        file.touch test interface
        '''
        name = os.path.join(integration.TMP, 'touch_test')
        ret = self.run_state('file.touch', test=True, name=name)
        self.assertFalse(os.path.isfile(name))
        self.assertSaltNoneReturn(ret)

    def test_touch_directory(self):
        '''
        file.touch a directory
        '''
        name = os.path.join(integration.TMP, 'touch_test_dir')
        try:
            if not os.path.isdir(name):
                # left behind... Don't fail because of this!
                os.makedirs(name)
        except OSError:
            self.skipTest('Failed to create directory {0}'.format(name))

        self.assertTrue(os.path.isdir(name))
        ret = self.run_state('file.touch', name=name)
        try:
            self.assertSaltTrueReturn(ret)
            self.assertTrue(os.path.isdir(name))
        finally:
            os.removedirs(name)

    def test_issue_2227_file_append(self):
        '''
        Text to append includes a percent symbol
        '''
        # let's make use of existing state to create a file with contents to
        # test against
        tmp_file_append = os.path.join(
            integration.TMP, 'test.append'
        )
        if os.path.isfile(tmp_file_append):
            os.remove(tmp_file_append)
        self.run_function('state.sls', mods='testappend')
        self.run_function('state.sls', mods='testappend.step1')
        self.run_function('state.sls', mods='testappend.step2')

        # Now our real test
        try:
            ret = self.run_function(
                'state.sls', mods='testappend.issue-2227'
            )
            self.assertSaltTrueReturn(ret)
            with salt.utils.fopen(tmp_file_append, 'r') as fp_:
                contents_pre = fp_.read()

            # It should not append text again
            ret = self.run_function(
                'state.sls', mods='testappend.issue-2227'
            )
            self.assertSaltTrueReturn(ret)

            with salt.utils.fopen(tmp_file_append, 'r') as fp_:
                contents_post = fp_.read()

            self.assertEqual(contents_pre, contents_post)
        except AssertionError:
            shutil.copy(tmp_file_append, tmp_file_append + '.bak')
            raise
        finally:
            if os.path.isfile(tmp_file_append):
                os.remove(tmp_file_append)

    def do_patch(self, patch_name='hello', src='Hello\n'):
        if not self.run_function('cmd.has_exec', ['patch']):
            self.skipTest('patch is not installed')
        src_file = os.path.join(integration.TMP, 'src.txt')
        with salt.utils.fopen(src_file, 'w+') as fp:
            fp.write(src)
        ret = self.run_state(
            'file.patch',
            name=src_file,
            source='salt://{0}.patch'.format(patch_name),
            hash='md5=f0ef7081e1539ac00ef5b761b4fb01b3',
        )
        return src_file, ret

    def test_patch(self):
        src_file, ret = self.do_patch()
        self.assertSaltTrueReturn(ret)
        with salt.utils.fopen(src_file) as fp:
            self.assertEqual(fp.read(), 'Hello world\n')

    def test_patch_hash_mismatch(self):
        src_file, ret = self.do_patch('hello_dolly')
        self.assertSaltFalseReturn(ret)
        self.assertInSaltComment(
            'File {0} hash mismatch after patch was applied'.format(src_file),
            ret
        )

    def test_patch_already_applied(self):
        src_file, ret = self.do_patch(src='Hello world\n')
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment('Patch is already applied', ret)

    def test_issue_2401_file_comment(self):
        # Get a path to the temporary file
        tmp_file = os.path.join(integration.TMP, 'issue-2041-comment.txt')
        # Write some data to it
        salt.utils.fopen(tmp_file, 'w').write('hello\nworld\n')
        # create the sls template
        template_lines = [
            '{0}:'.format(tmp_file),
            '  file.comment:',
            '    - regex: ^world'
        ]
        template = '\n'.join(template_lines)
        try:
            ret = self.run_function(
                'state.template_str', [template], timeout=120
            )
            self.assertSaltTrueReturn(ret)
            self.assertNotInSaltComment('Pattern already commented', ret)
            self.assertInSaltComment('Commented lines successfully', ret)

            # This next time, it is already commented.
            ret = self.run_function(
                'state.template_str', [template], timeout=120
            )

            self.assertSaltTrueReturn(ret)
            self.assertInSaltComment('Pattern already commented', ret)
        except AssertionError:
            shutil.copy(tmp_file, tmp_file + '.bak')
            raise
        finally:
            if os.path.isfile(tmp_file):
                os.remove(tmp_file)

    def test_issue_2379_file_append(self):
        # Get a path to the temporary file
        tmp_file = os.path.join(integration.TMP, 'issue-2379-file-append.txt')
        # Write some data to it
        salt.utils.fopen(tmp_file, 'w').write(
            'hello\nworld\n' +          # Some junk
            '#PermitRootLogin yes\n' +  # Commented text
            '# PermitRootLogin yes\n'   # Commented text with space
        )
        # create the sls template
        template_lines = [
            '{0}:'.format(tmp_file),
            '  file.append:',
            '    - text: PermitRootLogin yes'
        ]
        template = '\n'.join(template_lines)
        try:
            ret = self.run_function('state.template_str', [template])

            self.assertSaltTrueReturn(ret)
            self.assertInSaltComment('Appended 1 lines', ret)
        except AssertionError:
            shutil.copy(tmp_file, tmp_file + '.bak')
            raise
        finally:
            if os.path.isfile(tmp_file):
                os.remove(tmp_file)

    def test_issue_2726_mode_kwarg(self):
        testcase_temp_dir = os.path.join(integration.TMP, 'issue_2726')
        # Let's test for the wrong usage approach
        bad_mode_kwarg_testfile = os.path.join(
            testcase_temp_dir, 'bad_mode_kwarg', 'testfile'
        )
        bad_template = [
            '{0}:'.format(bad_mode_kwarg_testfile),
            '  file.recurse:',
            '    - source: salt://testfile',
            '    - mode: 644'
        ]
        try:
            ret = self.run_function(
                'state.template_str', ['\n'.join(bad_template)]
            )
            self.assertSaltFalseReturn(ret)
            self.assertInSaltComment(
                '\'mode\' is not allowed in \'file.recurse\'. Please use '
                '\'file_mode\' and \'dir_mode\'.',
                ret
            )
            self.assertNotInSaltComment(
                'TypeError: managed() got multiple values for keyword '
                'argument \'mode\'',
                ret
            )
        finally:
            if os.path.isdir(testcase_temp_dir):
                shutil.rmtree(testcase_temp_dir)

        # Now, the correct usage approach
        good_mode_kwargs_testfile = os.path.join(
            testcase_temp_dir, 'good_mode_kwargs', 'testappend'
        )
        good_template = [
            '{0}:'.format(good_mode_kwargs_testfile),
            '  file.recurse:',
            '    - source: salt://testappend',
            '    - dir_mode: 744',
            '    - file_mode: 644',
        ]
        try:
            ret = self.run_function(
                'state.template_str', ['\n'.join(good_template)]
            )
            self.assertSaltTrueReturn(ret)
        finally:
            if os.path.isdir(testcase_temp_dir):
                shutil.rmtree(testcase_temp_dir)

    def test_issue_8343_accumulated_require_in(self):
        template_path = os.path.join(integration.TMP_STATE_TREE, 'issue-8343.sls')
        testcase_filedest = os.path.join(integration.TMP, 'issue-8343.txt')
        sls_template = [
            '{0}:',
            '  file.managed:',
            '    - contents: |',
            '                #',
            '',
            'prepend-foo-accumulator-from-pillar:',
            '  file.accumulated:',
            '    - require_in:',
            '      - file: prepend-foo-management',
            '    - filename: {0}',
            '    - text: |',
            '            foo',
            '',
            'append-foo-accumulator-from-pillar:',
            '  file.accumulated:',
            '    - require_in:',
            '      - file: append-foo-management',
            '    - filename: {0}',
            '    - text: |',
            '            bar',
            '',
            'prepend-foo-management:',
            '  file.blockreplace:',
            '    - name: {0}',
            '    - marker_start: "#-- start salt managed zonestart -- PLEASE, DO NOT EDIT"',
            '    - marker_end: "#-- end salt managed zonestart --"',
            "    - content: ''",
            '    - prepend_if_not_found: True',
            "    - backup: '.bak'",
            '    - show_changes: True',
            '',
            'append-foo-management:',
            '  file.blockreplace:',
            '    - name: {0}',
            '    - marker_start: "#-- start salt managed zoneend -- PLEASE, DO NOT EDIT"',
            '    - marker_end: "#-- end salt managed zoneend --"',
            "    - content: ''",
            '    - append_if_not_found: True',
            "    - backup: '.bak2'",
            '    - show_changes: True',
            '']
        with salt.utils.fopen(template_path, 'w') as fp_:
            fp_.write('\n'.join(sls_template).format(testcase_filedest))

        try:
            ret = self.run_function('state.sls', mods='issue-8343')
            for name, step in six.iteritems(ret):
                self.assertSaltTrueReturn({name: step})
            with salt.utils.fopen(testcase_filedest) as fp_:
                contents = fp_.read().split('\n')
            self.assertEqual(
                ['#-- start salt managed zonestart -- PLEASE, DO NOT EDIT',
                 'foo',
                 '',
                 '#-- end salt managed zonestart --',
                 '#',
                 '#-- start salt managed zoneend -- PLEASE, DO NOT EDIT',
                 'bar',
                 '',
                 '#-- end salt managed zoneend --',
                 ''],
                contents
            )
        finally:
            if os.path.isdir(testcase_filedest):
                os.unlink(testcase_filedest)
            for filename in glob.glob('{0}.bak*'.format(testcase_filedest)):
                os.unlink(filename)

    def test_issue_11003_immutable_lazy_proxy_sum(self):
        template_path = os.path.join(integration.TMP_STATE_TREE, 'issue-11003.sls')
        testcase_filedest = os.path.join(integration.TMP, 'issue-11003.txt')
        sls_template = [
            'a{0}:',
            '  file.absent:',
            '    - name: {0}',
            '',
            '{0}:',
            '  file.managed:',
            '    - contents: |',
            '                #',
            '',
            'test-acc1:',
            '  file.accumulated:',
            '    - require_in:',
            '      - file: final',
            '    - filename: {0}',
            '    - text: |',
            '            bar',
            '',
            'test-acc2:',
            '  file.accumulated:',
            '    - watch_in:',
            '      - file: final',
            '    - filename: {0}',
            '    - text: |',
            '            baz',
            '',
            'final:',
            '  file.blockreplace:',
            '    - name: {0}',
            '    - marker_start: "#-- start managed zone PLEASE, DO NOT EDIT"',
            '    - marker_end: "#-- end managed zone"',
            '    - content: \'\'',
            '    - append_if_not_found: True',
            '    - show_changes: True'
        ]

        with salt.utils.fopen(template_path, 'w') as fp_:
            fp_.write('\n'.join(sls_template).format(testcase_filedest))

        try:
            ret = self.run_function('state.sls', mods='issue-11003')
            for name, step in six.iteritems(ret):
                self.assertSaltTrueReturn({name: step})
            with salt.utils.fopen(testcase_filedest) as fp_:
                contents = fp_.read().split('\n')
            self.assertEqual(
                ['#',
                 '#-- start managed zone PLEASE, DO NOT EDIT',
                 'bar',
                 '',
                 'baz',
                 '',
                 '#-- end managed zone',
                 ''],
                contents
            )
        finally:
            if os.path.isdir(testcase_filedest):
                os.unlink(testcase_filedest)
            for filename in glob.glob('{0}.bak*'.format(testcase_filedest)):
                os.unlink(filename)

    def test_issue_8947_utf8_sls(self):
        '''
        Test some file operation with utf-8 chararacters on the sls

        This is more generic than just a file test. Feel free to move
        '''
        # Get a path to the temporary file
        # 한국어 시험 (korean)
        # '\xed\x95\x9c\xea\xb5\xad\xec\x96\xb4 \xec\x8b\x9c\xed\x97\x98' (utf-8)
        # u'\ud55c\uad6d\uc5b4 \uc2dc\ud5d8' (unicode)
        korean_1 = '한국어 시험'
        korean_utf8_1 = ('\xed\x95\x9c\xea\xb5\xad\xec\x96\xb4'
                         ' \xec\x8b\x9c\xed\x97\x98')
        korean_unicode_1 = u'\ud55c\uad6d\uc5b4 \uc2dc\ud5d8'
        korean_2 = '첫 번째 행'
        korean_utf8_2 = '\xec\xb2\xab \xeb\xb2\x88\xec\xa7\xb8 \xed\x96\x89'
        korean_unicode_2 = u'\uccab \ubc88\uc9f8 \ud589'
        korean_3 = '마지막 행'
        korean_utf8_3 = '\xeb\xa7\x88\xec\xa7\x80\xeb\xa7\x89 \xed\x96\x89'
        korean_unicode_3 = u'\ub9c8\uc9c0\ub9c9 \ud589'
        test_file = os.path.join(integration.TMP,
                                 'salt_utf8_tests/'+korean_utf8_1+'.txt'
        )
        template_path = os.path.join(integration.TMP_STATE_TREE, 'issue-8947.sls')
        # create the sls template
        template_lines = [
            '# -*- coding: utf-8 -*-',
            'some-utf8-file-create:',
            '  file.managed:',
            "    - name: '{0}'".format(test_file),
            "    - contents: {0}".format(korean_utf8_1),
            '    - makedirs: True',
            '    - replace: True',
            '    - show_diff: True',
            'some-utf8-file-create2:',
            '  file.managed:',
            "    - name: '{0}'".format(test_file),
            '    - contents: |',
            '       {0}'.format(korean_utf8_2),
            '       {0}'.format(korean_utf8_1),
            '       {0}'.format(korean_utf8_3),
            '    - replace: True',
            '    - show_diff: True',
            'some-utf8-file-exists:',
            '  file.exists:',
            "    - name: '{0}'".format(test_file),
            '    - require:',
            '      - file: some-utf8-file-create2',
            'some-utf8-file-content-test:',
            '  cmd.run:',
            '    - name: \'cat "{0}"\''.format(test_file),
            '    - require:',
            '      - file: some-utf8-file-exists',
            'some-utf8-file-content-remove:',
            '  cmd.run:',
            '    - name: \'rm -f "{0}"\''.format(test_file),
            '    - require:',
            '      - cmd: some-utf8-file-content-test',
            'some-utf8-file-removed:',
            '  file.missing:',
            "    - name: '{0}'".format(test_file),
            '    - require:',
            '      - cmd: some-utf8-file-content-remove',
        ]
        with salt.utils.fopen(template_path, 'w') as fp_:
            fp_.write('\n'.join(template_lines))
        try:
            ret = self.run_function('state.sls', mods='issue-8947')
            if not isinstance(ret, dict):
                raise AssertionError(
                    ('Something went really wrong while testing this sls:'
                    ' {0}').format(repr(ret))
                )
            # difflib produces different output on python 2.6 than on >=2.7
            if sys.version_info < (2, 7):
                utf_diff = '---  \n+++  \n@@ -1,1 +1,3 @@\n'
            else:
                utf_diff = '--- \n+++ \n@@ -1 +1,3 @@\n'
            utf_diff += '+\xec\xb2\xab \xeb\xb2\x88\xec\xa7\xb8 \xed\x96\x89\n \xed\x95\x9c\xea\xb5\xad\xec\x96\xb4 \xec\x8b\x9c\xed\x97\x98\n+\xeb\xa7\x88\xec\xa7\x80\xeb\xa7\x89 \xed\x96\x89\n'
            # using unicode.encode('utf-8') we should get the same as
            # an utf-8 string
            expected = {
                ('file_|-some-utf8-file-create_|-{0}'
                '_|-managed').format(test_file): {
                    'name': '{0}'.format(test_file),
                    '__run_num__': 0,
                    'comment': 'File {0} updated'.format(test_file),
                    'diff': 'New file'
                },
                ('file_|-some-utf8-file-create2_|-{0}'
                '_|-managed').format(test_file): {
                    'name': '{0}'.format(test_file),
                    '__run_num__': 1,
                    'comment': 'File {0} updated'.format(test_file),
                    'diff': utf_diff
                },
                ('file_|-some-utf8-file-exists_|-{0}'
                '_|-exists').format(test_file): {
                    'name': '{0}'.format(test_file),
                    '__run_num__': 2,
                    'comment': 'Path {0} exists'.format(test_file)
                },
                ('cmd_|-some-utf8-file-content-test_|-cat "{0}"'
                 '_|-run').format(test_file): {
                    'name': 'cat "{0}"'.format(test_file),
                    '__run_num__': 3,
                    'comment': 'Command "cat "{0}"" run'.format(test_file),
                    'stdout': '{0}\n{1}\n{2}'.format(
                        korean_unicode_2.encode('utf-8'),
                        korean_unicode_1.encode('utf-8'),
                        korean_unicode_3.encode('utf-8')
                    )
                },
                ('cmd_|-some-utf8-file-content-remove_|-rm -f "{0}"'
                 '_|-run').format(test_file): {
                    'name': 'rm -f "{0}"'.format(test_file),
                    '__run_num__': 4,
                    'comment': 'Command "rm -f "{0}"" run'.format(test_file),
                    'stdout': ''
                },
                ('file_|-some-utf8-file-removed_|-{0}'
                '_|-missing').format(test_file): {
                    'name': '{0}'.format(test_file),
                    '__run_num__': 5,
                    'comment':
                          'Path {0} is missing'.format(test_file),
                }
            }
            result = {}
            for name, step in six.iteritems(ret):
                self.assertSaltTrueReturn({name: step})
                result.update({
                 name: {
                    'name': step['name'],
                    '__run_num__': step['__run_num__'],
                    'comment': step['comment']
                }})
                if 'diff' in step['changes']:
                    result[name]['diff'] = step['changes']['diff']
                if 'stdout' in step['changes']:
                    result[name]['stdout'] = step['changes']['stdout']

            self.maxDiff = None

            self.assertEqual(expected, result)
            cat_id = ('cmd_|-some-utf8-file-content-test_|-cat "{0}"'
                      '_|-run').format(test_file)
            self.assertEqual(
                result[cat_id]['stdout'],
                korean_2 + '\n' + korean_1 + '\n' + korean_3
            )
        finally:
            if os.path.isdir(test_file):
                os.unlink(test_file)
                os.unlink(template_path)

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    @with_system_user_and_group('user12209', 'group12209',
                                on_existing='delete', delete=True)
    def test_issue_12209_follow_symlinks(self, user, group):
        '''
        Ensure that symlinks are properly chowned when recursing (following
        symlinks)
        '''
        tmp_dir = os.path.join(integration.TMP, 'test.12209')

        # Cleanup the path if it already exists
        if os.path.isdir(tmp_dir):
            shutil.rmtree(tmp_dir)
        elif os.path.isfile(tmp_dir):
            os.remove(tmp_dir)

        # Make the directories for this test
        onedir = os.path.join(tmp_dir, 'one')
        twodir = os.path.join(tmp_dir, 'two')
        os.makedirs(onedir)
        os.symlink(onedir, twodir)

        try:
            # Run the state
            ret = self.run_state(
                'file.directory', name=tmp_dir, follow_symlinks=True,
                user=user, group=group, recurse=['user', 'group']
            )
            self.assertSaltTrueReturn(ret)

            # Double-check, in case state mis-reported a True result. Since we are
            # following symlinks, we expect twodir to still be owned by root, but
            # onedir should be owned by the 'issue12209' user.
            onestats = os.stat(onedir)
            twostats = os.lstat(twodir)
            self.assertEqual(pwd.getpwuid(onestats.st_uid).pw_name, user)
            self.assertEqual(pwd.getpwuid(twostats.st_uid).pw_name, 'root')
            self.assertEqual(grp.getgrgid(onestats.st_gid).gr_name, group)
            self.assertEqual(grp.getgrgid(twostats.st_gid).gr_name, 'root')
        finally:
            if os.path.isdir(tmp_dir):
                shutil.rmtree(tmp_dir)

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    @with_system_user_and_group('user12209', 'group12209',
                                on_existing='delete', delete=True)
    def test_issue_12209_no_follow_symlinks(self, user, group):
        '''
        Ensure that symlinks are properly chowned when recursing (not following
        symlinks)
        '''
        tmp_dir = os.path.join(integration.TMP, 'test.12209')

        # Cleanup the path if it already exists
        if os.path.isdir(tmp_dir):
            shutil.rmtree(tmp_dir)
        elif os.path.isfile(tmp_dir):
            os.remove(tmp_dir)

        # Make the directories for this test
        onedir = os.path.join(tmp_dir, 'one')
        twodir = os.path.join(tmp_dir, 'two')
        os.makedirs(onedir)
        os.symlink(onedir, twodir)

        try:
            # Run the state
            ret = self.run_state(
                'file.directory', name=tmp_dir, follow_symlinks=False,
                user=user, group=group, recurse=['user', 'group']
            )
            self.assertSaltTrueReturn(ret)

            # Double-check, in case state mis-reported a True result. Since we
            # are not following symlinks, we expect twodir to now be owned by
            # the 'issue12209' user, just link onedir.
            onestats = os.stat(onedir)
            twostats = os.lstat(twodir)
            self.assertEqual(pwd.getpwuid(onestats.st_uid).pw_name, user)
            self.assertEqual(pwd.getpwuid(twostats.st_uid).pw_name, user)
            self.assertEqual(grp.getgrgid(onestats.st_gid).gr_name, group)
            self.assertEqual(grp.getgrgid(twostats.st_gid).gr_name, group)
        finally:
            if os.path.isdir(tmp_dir):
                shutil.rmtree(tmp_dir)

    def test_template_local_file(self):
        '''
        Test a file.managed state with a local file as the source. Test both
        with the file:// protocol designation prepended, and without it.
        '''
        source = tempfile.mkstemp()[-1]
        dest = tempfile.mkstemp()[-1]
        with salt.utils.fopen(source, 'w') as fp_:
            fp_.write('{{ foo }}\n')

        try:
            for prefix in ('file://', ''):
                ret = self.run_state(
                    'file.managed',
                    name=dest,
                    source=prefix + source,
                    template='jinja',
                    context={'foo': 'Hello world!'}
                )
                self.assertSaltTrueReturn(ret)
        finally:
            os.remove(source)
            os.remove(dest)

    def test_template_local_file_noclobber(self):
        '''
        Test the case where a source file is in the minion's local filesystem,
        and the source path is the same as the destination path.
        '''
        source = tempfile.mkstemp()[-1]
        with salt.utils.fopen(source, 'w') as fp_:
            fp_.write('{{ foo }}\n')

        try:
            ret = self.run_state(
                'file.managed',
                name=source,
                source=source,
                template='jinja',
                context={'foo': 'Hello world!'}
            )
            self.assertSaltFalseReturn(ret)
            self.assertIn(
                ('Source file cannot be the same as destination'),
                ret[next(iter(ret))]['comment'],
            )
        finally:
            os.remove(source)

    def test_issue_25250_force_copy_deletes(self):
        '''
        ensure force option in copy state does not delete target file
        '''
        dest = os.path.join(integration.TMP, 'dest')
        source = os.path.join(integration.TMP, 'source')
        shutil.copyfile(os.path.join(integration.FILES, 'hosts'), source)
        shutil.copyfile(os.path.join(integration.FILES, 'file/base/cheese'), dest)

        self.run_state('file.copy', name=dest, source=source, force=True)
        self.assertTrue(os.path.exists(dest))
        self.assertTrue(filecmp.cmp(source, dest))

        os.remove(source)
        os.remove(dest)

    @destructiveTest
    def test_contents_pillar_with_pillar_list(self):
        '''
        This tests for any regressions for this issue:
        https://github.com/saltstack/salt/issues/30934
        '''
        ret = self.run_function('state.sls', mods='file_contents_pillar')
        self.assertSaltTrueReturn(ret)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(FileTest)
