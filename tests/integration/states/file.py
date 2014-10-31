# -*- coding: utf-8 -*-

'''
Tests for the file state
'''

# Import python libs
import glob
import grp
import os
import pwd
import shutil
import stat
import tempfile

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

    def test_managed_show_diff_false(self):
        '''
        file.managed test interface
        '''
        name = os.path.join(integration.TMP, 'grail_not_scene33')
        with salt.utils.fopen(name, 'wb') as fp_:
            fp_.write('test_managed_show_diff_false\n')

        ret = self.run_state(
            'file.managed', name=name, source='salt://grail/scene33',
            show_diff=False
        )

        changes = ret.values()[0]['changes']
        self.assertEqual('<show_diff=False>', changes['diff'])

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

        comment = ret.values()[0]['comment']
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
        file.append but create directories if needed as an option
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
            shutil.rmtree(
                os.path.join(integration.TMP, 'issue_1864'),
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
            for name, step in ret.items():
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
            for name, step in ret.items():
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
                    'diff': 'Replace binary file with text file'
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
            for name, step in ret.items():
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
            self.assertEqual(
                ret[next(iter(ret))]['comment'],
                ('Unable to manage file: Source file cannot be the same as '
                    'destination')
            )
        finally:
            os.remove(source)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(FileTest)
