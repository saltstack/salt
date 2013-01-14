'''
Tests for the file state
'''

# Import python libs
import os
import shutil

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
        name = os.path.join(integration.TMP, 'symlink')
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

    def test_test_managed(self):
        '''
        file.managed test interface
        '''
        name = os.path.join(integration.TMP, 'grail_not_scene33')
        ret = self.run_state(
            'file.managed', test=True, name=name, source='salt://grail/scene33'
        )
        self.assertSaltNoneReturn(ret)
        self.assertFalse(os.path.isfile(name))

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
            self.assertIn(
                _ts,
                salt.utils.fopen(os.path.join(name, 'scene33'), 'r').read()
            )
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

    def test_sed(self):
        '''
        file.sed
        '''
        name = os.path.join(integration.TMP, 'sed_test')
        with salt.utils.fopen(name, 'w+') as fp_:
            fp_.write('change_me')
        ret = self.run_state(
            'file.sed', name=name, before='change', after='salt'
        )
        try:
            with salt.utils.fopen(name, 'r') as fp_:
                self.assertIn('salt', fp_.read())
            self.assertSaltTrueReturn(ret)
        finally:
            os.remove(name)

    def test_test_sed(self):
        '''
        file.sed test integration
        '''
        name = os.path.join(integration.TMP, 'sed_test_test')
        with salt.utils.fopen(name, 'w+') as fp_:
            fp_.write('change_me')
        ret = self.run_state(
            'file.sed', test=True, name=name, before='change', after='salt'
        )
        try:
            with salt.utils.fopen(name, 'r') as fp_:
                self.assertIn('change', fp_.read())
            self.assertSaltNoneReturn(ret)
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
        ret = self.run_state('file.append', name=name, text='cheese')
        self.assertSaltFalseReturn(ret)

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
            self.skipTest("Failed to create directory {0}".format(name))

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
            contents = salt.utils.fopen(tmp_file_append, 'r').read()

            # It should not append text again
            ret = self.run_function(
                'state.sls', mods='testappend.issue-2227'
            )
            self.assertSaltTrueReturn(ret)

            self.assertEqual(
                contents, salt.utils.fopen(tmp_file_append, 'r').read()
            )

        except AssertionError:
            shutil.copy(tmp_file_append, tmp_file_append + '.bak')
            raise
        finally:
            if os.path.isfile(tmp_file_append):
                os.remove(tmp_file_append)

    def do_patch(self, patch_name='hello', src="Hello\n"):
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
            ret, 'File {0} hash mismatch after patch was applied'.format(
                src_file
            )
        )

    def test_patch_already_applied(self):
        src_file, ret = self.do_patch(src='Hello world\n')
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment(ret, 'Patch is already applied')

    def test_issue_2401_file_comment(self):
        # Get a path to the temporary file
        tmp_file = os.path.join(integration.TMP, 'issue-2041-comment.txt')
        # Write some data to it
        salt.utils.fopen(tmp_file, 'w').write('hello\nworld\n')
        # create the sls template
        template_lines = [
            "{0}:".format(tmp_file),
            "  file.comment:",
            "    - regex: ^world"
        ]
        template = '\n'.join(template_lines)
        try:
            ret = self.run_function(
                'state.template_str', [template], timeout=120
            )
            self.assertSaltTrueReturn(ret)
            self.assertNotInSaltComment(ret, 'Pattern already commented')
            self.assertInSaltComment(ret, 'Commented lines successfully')

            # This next time, it is already commented.
            ret = self.run_function(
                'state.template_str', [template], timeout=120
            )

            self.assertSaltTrueReturn(ret)
            self.assertInSaltComment(ret, 'Pattern already commented')
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
            "{0}:".format(tmp_file),
            "  file.append:",
            "    - text: PermitRootLogin yes"
        ]
        template = '\n'.join(template_lines)
        try:
            ret = self.run_function('state.template_str', [template])

            self.assertSaltTrueReturn(ret)
            self.assertInSaltComment(ret, 'Appended 1 lines')
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
                ret,
                '\'mode\' is not allowed in \'file.recurse\'. Please use '
                '\'file_mode\' and \'dir_mode\'.'
            )
            self.assertNotInSaltComment(
                ret,
                'TypeError: managed() got multiple values for keyword '
                'argument \'mode\''
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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(FileTest)
