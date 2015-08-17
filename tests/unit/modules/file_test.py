# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import os
import tempfile
import textwrap

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import MagicMock

ensure_in_syspath('../../')

# Import Salt libs
import salt.utils
from salt.modules import file as filemod
from salt.modules import config as configmod
from salt.modules import cmdmod
from salt.exceptions import CommandExecutionError

filemod.__salt__ = {
    'config.manage_mode': configmod.manage_mode,
    'cmd.run': cmdmod.run,
    'cmd.run_all': cmdmod.run_all
}
filemod.__opts__ = {'test': False}

SED_CONTENT = """test
some
content
/var/lib/foo/app/test
here
"""


class FileReplaceTestCase(TestCase):
    MULTILINE_STRING = textwrap.dedent('''\
        Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nam rhoncus
        enim ac bibendum vulputate. Etiam nibh velit, placerat ac auctor in,
        lacinia a turpis. Nulla elit elit, ornare in sodales eu, aliquam sit
        amet nisl.

        Fusce ac vehicula lectus. Vivamus justo nunc, pulvinar in ornare nec,
        sollicitudin id sem. Pellentesque sed ipsum dapibus, dapibus elit id,
        malesuada nisi.

        Lorem ipsum dolor sit amet, consectetur adipiscing elit. Donec
        venenatis tellus eget massa facilisis, in auctor ante aliquet. Sed nec
        cursus metus. Curabitur massa urna, vehicula id porttitor sed, lobortis
        quis leo.
        ''')

    def setUp(self):
        self.tfile = tempfile.NamedTemporaryFile(delete=False, mode='w+')
        self.tfile.write(self.MULTILINE_STRING)
        self.tfile.close()

    def tearDown(self):
        os.remove(self.tfile.name)

    def test_replace(self):
        filemod.replace(self.tfile.name, r'Etiam', 'Salticus', backup=False)

        with salt.utils.fopen(self.tfile.name, 'r') as fp:
            self.assertIn('Salticus', fp.read())

    def test_replace_append_if_not_found(self):
        '''
        Check that file.replace append_if_not_found works
        '''
        args = {
                'pattern': '#*baz=(?P<value>.*)',
                'repl': 'baz=\\g<value>',
                'append_if_not_found': True,
        }
        base = 'foo=1\nbar=2'
        expected = '{base}\n{repl}\n'.format(base=base, **args)
        # File ending with a newline, no match
        with tempfile.NamedTemporaryFile(mode='w+') as tfile:
            tfile.write(base + '\n')
            tfile.flush()
            filemod.replace(tfile.name, **args)
            with salt.utils.fopen(tfile.name) as tfile2:
                self.assertEqual(tfile2.read(), expected)
        # File not ending with a newline, no match
        with tempfile.NamedTemporaryFile('w+') as tfile:
            tfile.write(base)
            tfile.flush()
            filemod.replace(tfile.name, **args)
            with salt.utils.fopen(tfile.name) as tfile2:
                self.assertEqual(tfile2.read(), expected)
        # A newline should not be added in empty files
        with tempfile.NamedTemporaryFile('w+') as tfile:
            filemod.replace(tfile.name, **args)
            with salt.utils.fopen(tfile.name) as tfile2:
                self.assertEqual(tfile2.read(), args['repl'] + '\n')
        # Using not_found_content, rather than repl
        with tempfile.NamedTemporaryFile('w+') as tfile:
            args['not_found_content'] = 'baz=3'
            expected = '{base}\n{not_found_content}\n'.format(base=base, **args)
            tfile.write(base)
            tfile.flush()
            filemod.replace(tfile.name, **args)
            with salt.utils.fopen(tfile.name) as tfile2:
                self.assertEqual(tfile2.read(), expected)
        # not appending if matches
        with tempfile.NamedTemporaryFile('w+') as tfile:
            base = 'foo=1\n#baz=42\nbar=2\n'
            expected = 'foo=1\nbaz=42\nbar=2\n'
            tfile.write(base)
            tfile.flush()
            filemod.replace(tfile.name, **args)
            with salt.utils.fopen(tfile.name) as tfile2:
                self.assertEqual(tfile2.read(), expected)

    def test_backup(self):
        fext = '.bak'
        bak_file = '{0}{1}'.format(self.tfile.name, fext)

        filemod.replace(self.tfile.name, r'Etiam', 'Salticus', backup=fext)

        self.assertTrue(os.path.exists(bak_file))
        os.unlink(bak_file)

    def test_nobackup(self):
        fext = '.bak'
        bak_file = '{0}{1}'.format(self.tfile.name, fext)

        filemod.replace(self.tfile.name, r'Etiam', 'Salticus', backup=False)

        self.assertFalse(os.path.exists(bak_file))

    def test_dry_run(self):
        before_ctime = os.stat(self.tfile.name).st_mtime
        filemod.replace(self.tfile.name, r'Etiam', 'Salticus', dry_run=True)
        after_ctime = os.stat(self.tfile.name).st_mtime

        self.assertEqual(before_ctime, after_ctime)

    def test_show_changes(self):
        ret = filemod.replace(self.tfile.name,
                              r'Etiam', 'Salticus',
                              show_changes=True)

        self.assertTrue(ret.startswith('---'))  # looks like a diff

    def test_noshow_changes(self):
        ret = filemod.replace(self.tfile.name,
                              r'Etiam', 'Salticus',
                              show_changes=False)

        self.assertIsInstance(ret, bool)

    def test_re_str_flags(self):
        # upper- & lower-case
        filemod.replace(self.tfile.name,
                        r'Etiam', 'Salticus',
                        flags=['MULTILINE', 'ignorecase'])

    def test_re_int_flags(self):
        filemod.replace(self.tfile.name, r'Etiam', 'Salticus', flags=10)

    def test_numeric_repl(self):
        '''
        This test covers cases where the replacement string is numeric, and the
        CLI parser yamlifies it into a numeric type. If not converted back to a
        string type in file.replace, a TypeError occurs when the replacemen is
        attempted. See https://github.com/saltstack/salt/issues/9097 for more
        information.
        '''
        filemod.replace(self.tfile.name, r'Etiam', 123)


class FileBlockReplaceTestCase(TestCase):
    MULTILINE_STRING = textwrap.dedent('''\
        Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nam rhoncus
        enim ac bibendum vulputate. Etiam nibh velit, placerat ac auctor in,
        lacinia a turpis. Nulla elit elit, ornare in sodales eu, aliquam sit
        amet nisl.

        Fusce ac vehicula lectus. Vivamus justo nunc, pulvinar in ornare nec,
        sollicitudin id sem. Pellentesque sed ipsum dapibus, dapibus elit id,
        malesuada nisi.

        first part of start line // START BLOCK : part of start line not removed
        to be removed
        first part of end line // END BLOCK : part of end line not removed

        #-- START BLOCK UNFINISHED

        #-- START BLOCK 1
        old content part 1
        old content part 2
        #-- END BLOCK 1

        Lorem ipsum dolor sit amet, consectetur adipiscing elit. Donec
        venenatis tellus eget massa facilisis, in auctor ante aliquet. Sed nec
        cursus metus. Curabitur massa urna, vehicula id porttitor sed, lobortis
        quis leo.
        ''')

    def setUp(self):
        self.tfile = tempfile.NamedTemporaryFile(delete=False,
                                                 prefix='blockrepltmp',
                                                 mode='w+')
        self.tfile.write(self.MULTILINE_STRING)
        self.tfile.close()
        manage_mode_mock = MagicMock()
        filemod.__salt__['config.manage_mode'] = manage_mode_mock

    def tearDown(self):
        os.remove(self.tfile.name)

    def test_replace_multiline(self):
        new_multiline_content = (
            "Who's that then?\nWell, how'd you become king,"
            "then?\nWe found them. I'm not a witch.\nWe shall"
            "say 'Ni' again to you, if you do not appease us."
        )
        filemod.blockreplace(self.tfile.name,
                             '#-- START BLOCK 1',
                             '#-- END BLOCK 1',
                             new_multiline_content,
                             backup=False)

        with salt.utils.fopen(self.tfile.name, 'r') as fp:
            filecontent = fp.read()
        self.assertIn('#-- START BLOCK 1'
                      + "\n" + new_multiline_content
                      + "\n"
                      + '#-- END BLOCK 1', filecontent)
        self.assertNotIn('old content part 1', filecontent)
        self.assertNotIn('old content part 2', filecontent)

    def test_replace_append(self):
        new_content = "Well, I didn't vote for you."

        self.assertRaises(
            CommandExecutionError,
            filemod.blockreplace,
            self.tfile.name,
            '#-- START BLOCK 2',
            '#-- END BLOCK 2',
            new_content,
            append_if_not_found=False,
            backup=False
        )
        with salt.utils.fopen(self.tfile.name, 'r') as fp:
            self.assertNotIn('#-- START BLOCK 2'
                             + "\n" + new_content + "\n"
                             + '#-- END BLOCK 2', fp.read())

        filemod.blockreplace(self.tfile.name,
                             '#-- START BLOCK 2',
                             '#-- END BLOCK 2',
                             new_content,
                             backup=False,
                             append_if_not_found=True)

        with salt.utils.fopen(self.tfile.name, 'r') as fp:
            self.assertIn('#-- START BLOCK 2'
                          + "\n" + new_content
                          + "\n" + '#-- END BLOCK 2', fp.read())

    def test_replace_append_newline_at_eof(self):
        '''
        Check that file.blockreplace works consistently on files with and
        without newlines at end of file.
        '''
        base = 'bar'
        args = {
                'marker_start': '#start',
                'marker_end': '#stop',
                'content': 'baz',
                'append_if_not_found': True,
        }
        block = '{marker_start}\n{content}\n{marker_end}\n'.format(**args)
        expected = base + '\n' + block
        # File ending with a newline
        with tempfile.NamedTemporaryFile(mode='w+') as tfile:
            tfile.write(base + '\n')
            tfile.flush()
            filemod.blockreplace(tfile.name, **args)
            with salt.utils.fopen(tfile.name) as tfile2:
                self.assertEqual(tfile2.read(), expected)
        # File not ending with a newline
        with tempfile.NamedTemporaryFile(mode='w+') as tfile:
            tfile.write(base)
            tfile.flush()
            filemod.blockreplace(tfile.name, **args)
            with salt.utils.fopen(tfile.name) as tfile2:
                self.assertEqual(tfile2.read(), expected)
        # A newline should not be added in empty files
        with tempfile.NamedTemporaryFile(mode='w+') as tfile:
            filemod.blockreplace(tfile.name, **args)
            with salt.utils.fopen(tfile.name) as tfile2:
                self.assertEqual(tfile2.read(), block)

    def test_replace_prepend(self):
        new_content = "Well, I didn't vote for you."

        self.assertRaises(
            CommandExecutionError,
            filemod.blockreplace,
            self.tfile.name,
            '#-- START BLOCK 2',
            '#-- END BLOCK 2',
            new_content,
            prepend_if_not_found=False,
            backup=False
        )
        with salt.utils.fopen(self.tfile.name, 'r') as fp:
            self.assertNotIn(
                '#-- START BLOCK 2' + "\n"
                + new_content + "\n" + '#-- END BLOCK 2',
                fp.read())

        filemod.blockreplace(self.tfile.name,
                             '#-- START BLOCK 2', '#-- END BLOCK 2',
                             new_content,
                             backup=False,
                             prepend_if_not_found=True)

        with salt.utils.fopen(self.tfile.name, 'r') as fp:
            self.assertTrue(
                fp.read().startswith(
                    '#-- START BLOCK 2'
                    + "\n" + new_content
                    + "\n" + '#-- END BLOCK 2'))

    def test_replace_partial_marked_lines(self):
        filemod.blockreplace(self.tfile.name,
                             '// START BLOCK',
                             '// END BLOCK',
                             'new content 1',
                             backup=False)

        with salt.utils.fopen(self.tfile.name, 'r') as fp:
            filecontent = fp.read()
        self.assertIn('new content 1', filecontent)
        self.assertNotIn('to be removed', filecontent)
        self.assertIn('first part of start line', filecontent)
        self.assertIn('first part of end line', filecontent)
        self.assertIn('part of start line not removed', filecontent)
        self.assertIn('part of end line not removed', filecontent)

    def test_backup(self):
        fext = '.bak'
        bak_file = '{0}{1}'.format(self.tfile.name, fext)

        filemod.blockreplace(
            self.tfile.name,
            '// START BLOCK', '// END BLOCK', 'new content 2',
            backup=fext)

        self.assertTrue(os.path.exists(bak_file))
        os.unlink(bak_file)
        self.assertFalse(os.path.exists(bak_file))

        fext = '.bak'
        bak_file = '{0}{1}'.format(self.tfile.name, fext)

        filemod.blockreplace(self.tfile.name,
                             '// START BLOCK', '// END BLOCK', 'new content 3',
                             backup=False)

        self.assertFalse(os.path.exists(bak_file))

    def test_no_modifications(self):
        filemod.blockreplace(self.tfile.name,
                             '// START BLOCK', '// END BLOCK',
                             'new content 4',
                             backup=False)
        before_ctime = os.stat(self.tfile.name).st_mtime
        filemod.blockreplace(self.tfile.name,
                             '// START BLOCK',
                             '// END BLOCK',
                             'new content 4',
                             backup=False)
        after_ctime = os.stat(self.tfile.name).st_mtime

        self.assertEqual(before_ctime, after_ctime)

    def test_dry_run(self):
        before_ctime = os.stat(self.tfile.name).st_mtime
        filemod.blockreplace(self.tfile.name,
                             '// START BLOCK',
                             '// END BLOCK',
                             'new content 5',
                             dry_run=True)
        after_ctime = os.stat(self.tfile.name).st_mtime

        self.assertEqual(before_ctime, after_ctime)

    def test_show_changes(self):
        ret = filemod.blockreplace(self.tfile.name,
                                   '// START BLOCK',
                                   '// END BLOCK',
                                   'new content 6',
                                   backup=False,
                                   show_changes=True)

        self.assertTrue(ret.startswith('---'))  # looks like a diff

        ret = filemod.blockreplace(self.tfile.name,
                                   '// START BLOCK',
                                   '// END BLOCK',
                                   'new content 7',
                                   backup=False,
                                   show_changes=False)

        self.assertIsInstance(ret, bool)

    def test_unfinished_block_exception(self):
        self.assertRaises(
            CommandExecutionError,
            filemod.blockreplace,
            self.tfile.name,
            '#-- START BLOCK UNFINISHED',
            '#-- END BLOCK UNFINISHED',
            'foobar',
            backup=False
        )


class FileModuleTestCase(TestCase):
    def test_sed_limit_escaped(self):
        with tempfile.NamedTemporaryFile(mode='w+') as tfile:
            tfile.write(SED_CONTENT)
            tfile.seek(0, 0)

            path = tfile.name
            before = '/var/lib/foo'
            after = ''
            limit = '^{0}'.format(before)

            filemod.sed(path, before, after, limit=limit)

            with salt.utils.fopen(path, 'r') as newfile:
                self.assertEqual(
                    SED_CONTENT.replace(before, ''),
                    newfile.read()
                )

    def test_append_newline_at_eof(self):
        '''
        Check that file.append works consistently on files with and without
        newlines at end of file.
        '''
        # File ending with a newline
        with tempfile.NamedTemporaryFile(mode='w+') as tfile:
            tfile.write('foo\n')
            tfile.flush()
            filemod.append(tfile.name, 'bar')
            with salt.utils.fopen(tfile.name) as tfile2:
                self.assertEqual(tfile2.read(), 'foo\nbar\n')
        # File not ending with a newline
        with tempfile.NamedTemporaryFile(mode='w+') as tfile:
            tfile.write('foo')
            tfile.flush()
            filemod.append(tfile.name, 'bar')
            with salt.utils.fopen(tfile.name) as tfile2:
                self.assertEqual(tfile2.read(), 'foo\nbar\n')
        # A newline should not be added in empty files
        with tempfile.NamedTemporaryFile(mode='w+') as tfile:
            filemod.append(tfile.name, 'bar')
            with salt.utils.fopen(tfile.name) as tfile2:
                self.assertEqual(tfile2.read(), 'bar\n')

    def test_extract_hash(self):
        '''
        Check various hash file formats.
        '''
        # With file name
        with tempfile.NamedTemporaryFile(mode='w+') as tfile:
            tfile.write('rc.conf ef6e82e4006dee563d98ada2a2a80a27\n')
            tfile.write(
                'ead48423703509d37c4a90e6a0d53e143b6fc268 example.tar.gz\n')
            tfile.flush()
            result = filemod.extract_hash(tfile.name, '', '/rc.conf')
            self.assertEqual(result, {
                'hsum': 'ef6e82e4006dee563d98ada2a2a80a27',
                'hash_type': 'md5'
            })

            result = filemod.extract_hash(tfile.name, '', '/example.tar.gz')
            self.assertEqual(result, {
                'hsum': 'ead48423703509d37c4a90e6a0d53e143b6fc268',
                'hash_type': 'sha1'
            })
        # Solohash - no file name (Maven repo checksum file format)
        with tempfile.NamedTemporaryFile(mode='w+') as tfile:
            tfile.write('ead48423703509d37c4a90e6a0d53e143b6fc268\n')
            tfile.flush()
            result = filemod.extract_hash(tfile.name, '', '/testfile')
            self.assertEqual(result, {
                'hsum': 'ead48423703509d37c4a90e6a0d53e143b6fc268',
                'hash_type': 'sha1'
            })

    def test_user_to_uid_int(self):
        '''
        Tests if user is passed as an integer
        '''
        user = 5034
        ret = filemod.user_to_uid(user)
        self.assertEqual(ret, user)

    def test_group_to_gid_int(self):
        '''
        Tests if group is passed as an integer
        '''
        group = 5034
        ret = filemod.group_to_gid(group)
        self.assertEqual(ret, group)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(FileModuleTestCase,
              FileReplaceTestCase,
              FileBlockReplaceTestCase,
              needs_daemon=False)
