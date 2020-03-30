# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import shutil
import tempfile
import textwrap

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.helpers import with_tempfile
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import MagicMock, Mock, patch, mock_open, DEFAULT

try:
    import pytest
except ImportError:
    pytest = None

# Import Salt libs
from salt.ext import six
import salt.config
import salt.loader
import salt.utils.data
import salt.utils.files
import salt.utils.platform
import salt.utils.stringutils
import salt.modules.file as filemod
import salt.modules.config as configmod
import salt.modules.cmdmod as cmdmod
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.utils.jinja import SaltCacheLoader

if salt.utils.platform.is_windows():
    import salt.modules.win_file as win_file
    import salt.utils.win_dacl as win_dacl

SED_CONTENT = '''test
some
content
/var/lib/foo/app/test
here
'''


class DummyStat(object):
    st_mode = 33188
    st_ino = 115331251
    st_dev = 44
    st_nlink = 1
    st_uid = 99200001
    st_gid = 99200001
    st_size = 41743
    st_atime = 1552661253
    st_mtime = 1552661253
    st_ctime = 1552661253


class FileReplaceTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        return {
            filemod: {
                '__salt__': {
                    'config.manage_mode': configmod.manage_mode,
                    'cmd.run': cmdmod.run,
                    'cmd.run_all': cmdmod.run_all
                },
                '__opts__': {
                    'test': False,
                    'file_roots': {'base': 'tmp'},
                    'pillar_roots': {'base': 'tmp'},
                    'cachedir': 'tmp',
                    'grains': {},
                },
                '__grains__': {'kernel': 'Linux'},
                '__utils__': {
                    'files.is_text': MagicMock(return_value=True),
                    'stringutils.get_diff': salt.utils.stringutils.get_diff,
                },
            }
        }

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
        del self.tfile

    def test_replace(self):
        filemod.replace(self.tfile.name, r'Etiam', 'Salticus', backup=False)

        with salt.utils.files.fopen(self.tfile.name, 'r') as fp:
            self.assertIn(
                'Salticus',
                salt.utils.stringutils.to_unicode(fp.read())
            )

    def test_replace_append_if_not_found(self):
        '''
        Check that file.replace append_if_not_found works
        '''
        args = {
                'pattern': '#*baz=(?P<value>.*)',
                'repl': 'baz=\\g<value>',
                'append_if_not_found': True,
        }
        base = os.linesep.join(['foo=1', 'bar=2'])

        # File ending with a newline, no match
        with tempfile.NamedTemporaryFile('w+b', delete=False) as tfile:
            tfile.write(salt.utils.stringutils.to_bytes(base + os.linesep))
            tfile.flush()
        filemod.replace(tfile.name, **args)
        expected = os.linesep.join([base, 'baz=\\g<value>']) + os.linesep
        with salt.utils.files.fopen(tfile.name) as tfile2:
            self.assertEqual(
                salt.utils.stringutils.to_unicode(tfile2.read()), expected)
        os.remove(tfile.name)

        # File not ending with a newline, no match
        with tempfile.NamedTemporaryFile('w+b', delete=False) as tfile:
            tfile.write(salt.utils.stringutils.to_bytes(base))
            tfile.flush()
        filemod.replace(tfile.name, **args)
        with salt.utils.files.fopen(tfile.name) as tfile2:
            self.assertEqual(
                salt.utils.stringutils.to_unicode(tfile2.read()), expected)
        os.remove(tfile.name)

        # A newline should not be added in empty files
        with tempfile.NamedTemporaryFile('w+b', delete=False) as tfile:
            pass
        filemod.replace(tfile.name, **args)
        expected = args['repl'] + os.linesep
        with salt.utils.files.fopen(tfile.name) as tfile2:
            self.assertEqual(
                salt.utils.stringutils.to_unicode(tfile2.read()), expected)
        os.remove(tfile.name)

        # Using not_found_content, rather than repl
        with tempfile.NamedTemporaryFile('w+b', delete=False) as tfile:
            tfile.write(salt.utils.stringutils.to_bytes(base))
            tfile.flush()
        args['not_found_content'] = 'baz=3'
        expected = os.linesep.join([base, 'baz=3']) + os.linesep
        filemod.replace(tfile.name, **args)
        with salt.utils.files.fopen(tfile.name) as tfile2:
            self.assertEqual(
                salt.utils.stringutils.to_unicode(tfile2.read()), expected)
        os.remove(tfile.name)

        # not appending if matches
        with tempfile.NamedTemporaryFile('w+b', delete=False) as tfile:
            base = os.linesep.join(['foo=1', 'baz=42', 'bar=2'])
            tfile.write(salt.utils.stringutils.to_bytes(base))
            tfile.flush()
        expected = base
        filemod.replace(tfile.name, **args)
        with salt.utils.files.fopen(tfile.name) as tfile2:
            self.assertEqual(
                salt.utils.stringutils.to_unicode(tfile2.read()), expected)

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

    def test_search_only_return_true(self):
        ret = filemod.replace(self.tfile.name,
                              r'Etiam', 'Salticus',
                              search_only=True)

        self.assertIsInstance(ret, bool)
        self.assertEqual(ret, True)

    def test_search_only_return_false(self):
        ret = filemod.replace(self.tfile.name,
                              r'Etian', 'Salticus',
                              search_only=True)

        self.assertIsInstance(ret, bool)
        self.assertEqual(ret, False)


class FileCommentLineTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {
            filemod: {
                '__salt__': {
                    'config.manage_mode': configmod.manage_mode,
                    'cmd.run': cmdmod.run,
                    'cmd.run_all': cmdmod.run_all
                },
                '__opts__': {
                    'test': False,
                    'file_roots': {'base': 'tmp'},
                    'pillar_roots': {'base': 'tmp'},
                    'cachedir': 'tmp',
                    'grains': {},
                },
                '__grains__': {'kernel': 'Linux'},
                '__utils__': {
                    'files.is_text': MagicMock(return_value=True),
                    'stringutils.get_diff': salt.utils.stringutils.get_diff,
                },
            }
        }

    MULTILINE_STRING = textwrap.dedent('''\
        Lorem
        ipsum
        #dolor
        ''')

    MULTILINE_STRING = os.linesep.join(MULTILINE_STRING.splitlines())

    def setUp(self):
        self.tfile = tempfile.NamedTemporaryFile(delete=False, mode='w+')
        self.tfile.write(self.MULTILINE_STRING)
        self.tfile.close()

    def tearDown(self):
        os.remove(self.tfile.name)
        del self.tfile

    def test_comment_line(self):
        filemod.comment_line(self.tfile.name,
                             '^ipsum')

        with salt.utils.files.fopen(self.tfile.name, 'r') as fp:
            filecontent = fp.read()
        self.assertIn('#ipsum', filecontent)

    def test_comment(self):
        filemod.comment(self.tfile.name,
                             '^ipsum')

        with salt.utils.files.fopen(self.tfile.name, 'r') as fp:
            filecontent = fp.read()
        self.assertIn('#ipsum', filecontent)

    def test_comment_different_character(self):
        filemod.comment_line(self.tfile.name,
                             '^ipsum',
                             '//')

        with salt.utils.files.fopen(self.tfile.name, 'r') as fp:
            filecontent = fp.read()
        self.assertIn('//ipsum', filecontent)

    def test_comment_not_found(self):
        filemod.comment_line(self.tfile.name,
                             '^sit')

        with salt.utils.files.fopen(self.tfile.name, 'r') as fp:
            filecontent = fp.read()
        self.assertNotIn('#sit', filecontent)
        self.assertNotIn('sit', filecontent)

    def test_uncomment(self):
        filemod.uncomment(self.tfile.name,
                          'dolor')

        with salt.utils.files.fopen(self.tfile.name, 'r') as fp:
            filecontent = fp.read()
        self.assertIn('dolor', filecontent)
        self.assertNotIn('#dolor', filecontent)


class FileBlockReplaceTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        if salt.utils.platform.is_windows():
            grains = {'kernel': 'Windows'}
        else:
            grains = {'kernel': 'Linux'}
        opts = {'test': False,
                'file_roots': {'base': 'tmp'},
                'pillar_roots': {'base': 'tmp'},
                'cachedir': 'tmp',
                'grains': grains}

        ret = {
            filemod: {
                '__salt__': {
                    'config.manage_mode': MagicMock(),
                    'cmd.run': cmdmod.run,
                    'cmd.run_all': cmdmod.run_all
                },
                '__opts__': opts,
                '__grains__': grains,
                '__utils__': {
                    'files.is_binary': MagicMock(return_value=False),
                    'files.get_encoding': MagicMock(return_value='utf-8'),
                    'stringutils.get_diff': salt.utils.stringutils.get_diff,
                },
            }
        }
        if salt.utils.platform.is_windows():
            ret.update({
                win_dacl: {'__opts__': opts},
                win_file: {
                    '__utils__': {
                        'dacl.check_perms': win_dacl.check_perms
                    }}})

        return ret

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

    MULTILINE_STRING = os.linesep.join(MULTILINE_STRING.splitlines())

    def setUp(self):
        self.tfile = tempfile.NamedTemporaryFile(delete=False,
                                                 prefix='blockrepltmp',
                                                 mode='w+b')
        self.tfile.write(salt.utils.stringutils.to_bytes(self.MULTILINE_STRING))
        self.tfile.close()

    def tearDown(self):
        os.remove(self.tfile.name)
        del self.tfile

    def test_replace_multiline(self):
        new_multiline_content = os.linesep.join([
            "Who's that then?",
            "Well, how'd you become king, then?",
            "We found them. I'm not a witch.",
            "We shall say 'Ni' again to you, if you do not appease us."
        ])
        if salt.utils.platform.is_windows():
            check_perms_patch = win_file.check_perms
        else:
            check_perms_patch = filemod.check_perms
        with patch.object(filemod, 'check_perms', check_perms_patch):
            filemod.blockreplace(self.tfile.name,
                                 marker_start='#-- START BLOCK 1',
                                 marker_end='#-- END BLOCK 1',
                                 content=new_multiline_content,
                                 backup=False,
                                 append_newline=None)

        with salt.utils.files.fopen(self.tfile.name, 'rb') as fp:
            filecontent = fp.read()
        self.assertIn(salt.utils.stringutils.to_bytes(
            os.linesep.join([
                '#-- START BLOCK 1', new_multiline_content, '#-- END BLOCK 1'])),
            filecontent)
        self.assertNotIn(b'old content part 1', filecontent)
        self.assertNotIn(b'old content part 2', filecontent)

    def test_replace_append(self):
        new_content = "Well, I didn't vote for you."

        self.assertRaises(
            CommandExecutionError,
            filemod.blockreplace,
            self.tfile.name,
            marker_start='#-- START BLOCK 2',
            marker_end='#-- END BLOCK 2',
            content=new_content,
            append_if_not_found=False,
            backup=False
        )
        with salt.utils.files.fopen(self.tfile.name, 'r') as fp:
            self.assertNotIn(
                '#-- START BLOCK 2' + "\n" + new_content + '#-- END BLOCK 2',
                salt.utils.stringutils.to_unicode(fp.read())
            )

        if salt.utils.platform.is_windows():
            check_perms_patch = win_file.check_perms
        else:
            check_perms_patch = filemod.check_perms
        with patch.object(filemod, 'check_perms', check_perms_patch):
            filemod.blockreplace(self.tfile.name,
                                 marker_start='#-- START BLOCK 2',
                                 marker_end='#-- END BLOCK 2',
                                 content=new_content,
                                 backup=False,
                                 append_if_not_found=True)

        with salt.utils.files.fopen(self.tfile.name, 'rb') as fp:
            self.assertIn(salt.utils.stringutils.to_bytes(
                os.linesep.join([
                    '#-- START BLOCK 2',
                    '{0}#-- END BLOCK 2'.format(new_content)])),
                fp.read())

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
        block = os.linesep.join(['#start', 'baz#stop']) + os.linesep
        # File ending with a newline
        with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as tfile:
            tfile.write(salt.utils.stringutils.to_bytes(base + os.linesep))
            tfile.flush()
        if salt.utils.platform.is_windows():
            check_perms_patch = win_file.check_perms
        else:
            check_perms_patch = filemod.check_perms
        with patch.object(filemod, 'check_perms', check_perms_patch):
            filemod.blockreplace(tfile.name, **args)
        expected = os.linesep.join([base, block])
        with salt.utils.files.fopen(tfile.name) as tfile2:
            self.assertEqual(
                salt.utils.stringutils.to_unicode(tfile2.read()), expected)
        os.remove(tfile.name)

        # File not ending with a newline
        with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as tfile:
            tfile.write(salt.utils.stringutils.to_bytes(base))
            tfile.flush()
        if salt.utils.platform.is_windows():
            check_perms_patch = win_file.check_perms
        else:
            check_perms_patch = filemod.check_perms
        with patch.object(filemod, 'check_perms', check_perms_patch):
            filemod.blockreplace(tfile.name, **args)
        with salt.utils.files.fopen(tfile.name) as tfile2:
            self.assertEqual(
                salt.utils.stringutils.to_unicode(tfile2.read()), expected)
        os.remove(tfile.name)

        # A newline should not be added in empty files
        with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as tfile:
            pass
        if salt.utils.platform.is_windows():
            check_perms_patch = win_file.check_perms
        else:
            check_perms_patch = filemod.check_perms
        with patch.object(filemod, 'check_perms', check_perms_patch):
            filemod.blockreplace(tfile.name, **args)
        with salt.utils.files.fopen(tfile.name) as tfile2:
            self.assertEqual(
                salt.utils.stringutils.to_unicode(tfile2.read()), block)
        os.remove(tfile.name)

    def test_replace_prepend(self):
        new_content = "Well, I didn't vote for you."

        self.assertRaises(
            CommandExecutionError,
            filemod.blockreplace,
            self.tfile.name,
            marker_start='#-- START BLOCK 2',
            marker_end='#-- END BLOCK 2',
            content=new_content,
            prepend_if_not_found=False,
            backup=False
        )
        with salt.utils.files.fopen(self.tfile.name, 'rb') as fp:
            self.assertNotIn(salt.utils.stringutils.to_bytes(
                os.linesep.join([
                    '#-- START BLOCK 2',
                    '{0}#-- END BLOCK 2'.format(new_content)])),
                fp.read())

        if salt.utils.platform.is_windows():
            check_perms_patch = win_file.check_perms
        else:
            check_perms_patch = filemod.check_perms
        with patch.object(filemod, 'check_perms', check_perms_patch):
            filemod.blockreplace(self.tfile.name,
                                 marker_start='#-- START BLOCK 2',
                                 marker_end='#-- END BLOCK 2',
                                 content=new_content,
                                 backup=False,
                                 prepend_if_not_found=True)

        with salt.utils.files.fopen(self.tfile.name, 'rb') as fp:
            self.assertTrue(
                fp.read().startswith(salt.utils.stringutils.to_bytes(
                    os.linesep.join([
                        '#-- START BLOCK 2',
                        '{0}#-- END BLOCK 2'.format(new_content)]))))

    def test_replace_partial_marked_lines(self):
        if salt.utils.platform.is_windows():
            check_perms_patch = win_file.check_perms
        else:
            check_perms_patch = filemod.check_perms
        with patch.object(filemod, 'check_perms', check_perms_patch):
            filemod.blockreplace(self.tfile.name,
                                 marker_start='// START BLOCK',
                                 marker_end='// END BLOCK',
                                 content='new content 1',
                                 backup=False)

        with salt.utils.files.fopen(self.tfile.name, 'r') as fp:
            filecontent = salt.utils.stringutils.to_unicode(fp.read())
        self.assertIn('new content 1', filecontent)
        self.assertNotIn('to be removed', filecontent)
        self.assertIn('first part of start line', filecontent)
        self.assertNotIn('first part of end line', filecontent)
        self.assertIn('part of start line not removed', filecontent)
        self.assertIn('part of end line not removed', filecontent)

    def test_backup(self):
        fext = '.bak'
        bak_file = '{0}{1}'.format(self.tfile.name, fext)

        if salt.utils.platform.is_windows():
            check_perms_patch = win_file.check_perms
        else:
            check_perms_patch = filemod.check_perms
        with patch.object(filemod, 'check_perms', check_perms_patch):
            filemod.blockreplace(
                self.tfile.name,
                marker_start='// START BLOCK',
                marker_end='// END BLOCK',
                content='new content 2',
                backup=fext)

        self.assertTrue(os.path.exists(bak_file))
        os.unlink(bak_file)
        self.assertFalse(os.path.exists(bak_file))

        fext = '.bak'
        bak_file = '{0}{1}'.format(self.tfile.name, fext)

        if salt.utils.platform.is_windows():
            check_perms_patch = win_file.check_perms
        else:
            check_perms_patch = filemod.check_perms
        with patch.object(filemod, 'check_perms', check_perms_patch):
            filemod.blockreplace(self.tfile.name,
                                 marker_start='// START BLOCK',
                                 marker_end='// END BLOCK',
                                 content='new content 3',
                                 backup=False)

        self.assertFalse(os.path.exists(bak_file))

    def test_no_modifications(self):
        if salt.utils.platform.is_windows():
            check_perms_patch = win_file.check_perms
        else:
            check_perms_patch = filemod.check_perms
        with patch.object(filemod, 'check_perms', check_perms_patch):
            filemod.blockreplace(self.tfile.name,
                                 marker_start='#-- START BLOCK 1',
                                 marker_end='#-- END BLOCK 1',
                                 content='new content 4',
                                 backup=False,
                                 append_newline=None)
        before_ctime = os.stat(self.tfile.name).st_mtime
        if salt.utils.platform.is_windows():
            check_perms_patch = win_file.check_perms
        else:
            check_perms_patch = filemod.check_perms
        with patch.object(filemod, 'check_perms', check_perms_patch):
            filemod.blockreplace(self.tfile.name,
                                 marker_start='#-- START BLOCK 1',
                                 marker_end='#-- END BLOCK 1',
                                 content='new content 4',
                                 backup=False,
                                 append_newline=None)
        after_ctime = os.stat(self.tfile.name).st_mtime

        self.assertEqual(before_ctime, after_ctime)

    def test_dry_run(self):
        before_ctime = os.stat(self.tfile.name).st_mtime
        filemod.blockreplace(self.tfile.name,
                             marker_start='// START BLOCK',
                             marker_end='// END BLOCK',
                             content='new content 5',
                             dry_run=True)
        after_ctime = os.stat(self.tfile.name).st_mtime

        self.assertEqual(before_ctime, after_ctime)

    def test_show_changes(self):
        if salt.utils.platform.is_windows():
            check_perms_patch = win_file.check_perms
        else:
            check_perms_patch = filemod.check_perms
        with patch.object(filemod, 'check_perms', check_perms_patch):
            ret = filemod.blockreplace(self.tfile.name,
                                       marker_start='// START BLOCK',
                                       marker_end='// END BLOCK',
                                       content='new content 6',
                                       backup=False,
                                       show_changes=True)

            self.assertTrue(ret.startswith('---'))  # looks like a diff

            ret = filemod.blockreplace(self.tfile.name,
                                       marker_start='// START BLOCK',
                                       marker_end='// END BLOCK',
                                       content='new content 7',
                                       backup=False,
                                       show_changes=False)

            self.assertIsInstance(ret, bool)

    def test_unfinished_block_exception(self):
        self.assertRaises(
            CommandExecutionError,
            filemod.blockreplace,
            self.tfile.name,
            marker_start='#-- START BLOCK UNFINISHED',
            marker_end='#-- END BLOCK UNFINISHED',
            content='foobar',
            backup=False
        )


@skipIf(salt.utils.platform.is_windows(), 'Skip on windows')
class FileGrepTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {
            filemod: {
                '__salt__': {
                    'config.manage_mode': configmod.manage_mode,
                    'cmd.run': cmdmod.run,
                    'cmd.run_all': cmdmod.run_all
                },
                '__opts__': {
                    'test': False,
                    'file_roots': {'base': 'tmp'},
                    'pillar_roots': {'base': 'tmp'},
                    'cachedir': 'tmp',
                    'grains': {},
                },
                '__grains__': {'kernel': 'Linux'},
                '__utils__': {
                    'files.is_text': MagicMock(return_value=True),
                    'stringutils.get_diff': salt.utils.stringutils.get_diff,
                },
            }
        }

    MULTILINE_STRING = textwrap.dedent('''\
        Lorem ipsum dolor sit amet, consectetur
        adipiscing elit. Nam rhoncus enim ac
        bibendum vulputate.
        ''')

    MULTILINE_STRING = os.linesep.join(MULTILINE_STRING.splitlines())

    def setUp(self):
        self.tfile = tempfile.NamedTemporaryFile(delete=False, mode='w+')
        self.tfile.write(self.MULTILINE_STRING)
        self.tfile.close()

    def tearDown(self):
        os.remove(self.tfile.name)
        del self.tfile

    def test_grep_query_exists(self):
        result = filemod.grep(self.tfile.name,
                     'Lorem ipsum')

        self.assertTrue(result, None)
        self.assertTrue(result['retcode'] == 0)
        self.assertTrue(result['stdout'] == 'Lorem ipsum dolor sit amet, consectetur')
        self.assertTrue(result['stderr'] == '')

    def test_grep_query_not_exists(self):
        result = filemod.grep(self.tfile.name,
                     'Lorem Lorem')

        self.assertTrue(result['retcode'] == 1)
        self.assertTrue(result['stdout'] == '')
        self.assertTrue(result['stderr'] == '')

    def test_grep_query_exists_with_opt(self):
        result = filemod.grep(self.tfile.name,
                     'Lorem ipsum',
                     '-i')

        self.assertTrue(result, None)
        self.assertTrue(result['retcode'] == 0)
        self.assertTrue(result['stdout'] == 'Lorem ipsum dolor sit amet, consectetur')
        self.assertTrue(result['stderr'] == '')

    def test_grep_query_not_exists_opt(self):
        result = filemod.grep(self.tfile.name,
                     'Lorem Lorem',
                     '-v')

        self.assertTrue(result['retcode'] == 0)
        self.assertTrue(result['stdout'] == FileGrepTestCase.MULTILINE_STRING)
        self.assertTrue(result['stderr'] == '')

    def test_grep_query_too_many_opts(self):
        with self.assertRaisesRegex(SaltInvocationError, '^Passing multiple command line arg') as cm:
            result = filemod.grep(self.tfile.name,
                                  'Lorem Lorem',
                                  '-i -b2')

    def test_grep_query_exists_wildcard(self):
        _file = '{0}*'.format(self.tfile.name)
        result = filemod.grep(_file,
                     'Lorem ipsum')

        self.assertTrue(result, None)
        self.assertTrue(result['retcode'] == 0)
        self.assertTrue(result['stdout'] == 'Lorem ipsum dolor sit amet, consectetur')
        self.assertTrue(result['stderr'] == '')

    def test_grep_file_not_exists_wildcard(self):
        _file = '{0}-junk*'.format(self.tfile.name)
        result = filemod.grep(_file,
                     'Lorem ipsum')

        self.assertTrue(result, None)
        self.assertFalse(result['retcode'] == 0)
        self.assertFalse(result['stdout'] == 'Lorem ipsum dolor sit amet, consectetur')
        _expected_stderr = 'grep: {0}-junk*: No such file or directory'.format(self.tfile.name)
        self.assertTrue(result['stderr'] == _expected_stderr)


class FileModuleTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {
            filemod: {
                '__salt__': {
                    'config.manage_mode': configmod.manage_mode,
                    'cmd.run': cmdmod.run,
                    'cmd.run_all': cmdmod.run_all
                },
                '__opts__': {
                    'test': False,
                    'file_roots': {'base': 'tmp'},
                    'pillar_roots': {'base': 'tmp'},
                    'cachedir': 'tmp',
                    'grains': {},
                },
                '__grains__': {'kernel': 'Linux'},
                '__utils__': {
                    'stringutils.get_diff': salt.utils.stringutils.get_diff,
                },
            }
        }

    @skipIf(salt.utils.platform.is_windows(), 'lsattr is not available on Windows')
    def test_check_file_meta_no_lsattr(self):
        '''
        Ensure that we skip attribute comparison if lsattr(1) is not found
        '''
        source = "salt:///README.md"
        name = "/home/git/proj/a/README.md"
        source_sum = {}
        stats_result = {'size': 22, 'group': 'wheel', 'uid': 0, 'type': 'file',
                        'mode': '0600', 'gid': 0, 'target': name, 'user':
                        'root', 'mtime': 1508356390, 'atime': 1508356390,
                        'inode': 447, 'ctime': 1508356390}
        with patch('salt.modules.file.stats') as m_stats:
            m_stats.return_value = stats_result
            with patch('salt.utils.path.which') as m_which:
                m_which.return_value = None
                result = filemod.check_file_meta(name, name, source, source_sum,
                                                 'root', 'root', '755', None,
                                                 'base')
        self.assertTrue(result, None)

    @skipIf(salt.utils.platform.is_windows(), 'SED is not available on Windows')
    def test_sed_limit_escaped(self):
        with tempfile.NamedTemporaryFile(mode='w+') as tfile:
            tfile.write(SED_CONTENT)
            tfile.seek(0, 0)

            path = tfile.name
            before = '/var/lib/foo'
            after = ''
            limit = '^{0}'.format(before)

            filemod.sed(path, before, after, limit=limit)

            with salt.utils.files.fopen(path, 'r') as newfile:
                self.assertEqual(
                    SED_CONTENT.replace(before, ''),
                    salt.utils.stringutils.to_unicode(newfile.read())
                )

    def test_append_newline_at_eof(self):
        '''
        Check that file.append works consistently on files with and without
        newlines at end of file.
        '''
        # File ending with a newline
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as tfile:
            tfile.write(salt.utils.stringutils.to_bytes('foo' + os.linesep))
            tfile.flush()
        filemod.append(tfile.name, 'bar')
        expected = os.linesep.join(['foo', 'bar', ''])
        with salt.utils.files.fopen(tfile.name) as tfile2:
            new_file = salt.utils.stringutils.to_unicode(tfile2.read())
        self.assertEqual(new_file, expected)

        # File not ending with a newline
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as tfile:
            tfile.write(salt.utils.stringutils.to_bytes('foo'))
            tfile.flush()
        filemod.append(tfile.name, 'bar')
        with salt.utils.files.fopen(tfile.name) as tfile2:
            self.assertEqual(
                salt.utils.stringutils.to_unicode(tfile2.read()), expected)

        # A newline should be added in empty files
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as tfile:
            filemod.append(tfile.name, salt.utils.stringutils.to_str('bar'))
        with salt.utils.files.fopen(tfile.name) as tfile2:
            self.assertEqual(
                salt.utils.stringutils.to_unicode(tfile2.read()),
                'bar' + os.linesep
            )

    def test_extract_hash(self):
        '''
        Check various hash file formats.
        '''
        # With file name
        with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as tfile:
            tfile.write(salt.utils.stringutils.to_bytes(
                'rc.conf ef6e82e4006dee563d98ada2a2a80a27\n'
                'ead48423703509d37c4a90e6a0d53e143b6fc268 example.tar.gz\n'
                'fe05bcdcdc4928012781a5f1a2a77cbb5398e106 ./subdir/example.tar.gz\n'
                'ad782ecdac770fc6eb9a62e44f90873fb97fb26b foo.tar.bz2\n'
            ))
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

        # All the checksums in this test file are sha1 sums. We run this
        # loop three times. The first pass tests auto-detection of hash
        # type by length of the hash. The second tests matching a specific
        # type. The third tests a failed attempt to match a specific type,
        # since sha256 was requested but sha1 is what is in the file.
        for hash_type in ('', 'sha1', 'sha256'):
            # Test the source_hash_name argument. Even though there are
            # matches in the source_hash file for both the file_name and
            # source params, they should be ignored in favor of the
            # source_hash_name.
            file_name = '/example.tar.gz'
            source = 'https://mydomain.tld/foo.tar.bz2?key1=val1&key2=val2'
            source_hash_name = './subdir/example.tar.gz'
            result = filemod.extract_hash(
                tfile.name,
                hash_type,
                file_name,
                source,
                source_hash_name)
            expected = {
                'hsum': 'fe05bcdcdc4928012781a5f1a2a77cbb5398e106',
                'hash_type': 'sha1'
            } if hash_type != 'sha256' else None
            self.assertEqual(result, expected)

            # Test both a file_name and source but no source_hash_name.
            # Even though there are matches for both file_name and
            # source_hash_name, file_name should be preferred.
            file_name = '/example.tar.gz'
            source = 'https://mydomain.tld/foo.tar.bz2?key1=val1&key2=val2'
            source_hash_name = None
            result = filemod.extract_hash(
                tfile.name,
                hash_type,
                file_name,
                source,
                source_hash_name)
            expected = {
                'hsum': 'ead48423703509d37c4a90e6a0d53e143b6fc268',
                'hash_type': 'sha1'
            } if hash_type != 'sha256' else None
            self.assertEqual(result, expected)

            # Test both a file_name and source but no source_hash_name.
            # Since there is no match for the file_name, the source is
            # matched.
            file_name = '/somefile.tar.gz'
            source = 'https://mydomain.tld/foo.tar.bz2?key1=val1&key2=val2'
            source_hash_name = None
            result = filemod.extract_hash(
                tfile.name,
                hash_type,
                file_name,
                source,
                source_hash_name)
            expected = {
                'hsum': 'ad782ecdac770fc6eb9a62e44f90873fb97fb26b',
                'hash_type': 'sha1'
            } if hash_type != 'sha256' else None
            self.assertEqual(result, expected)

        # Hash only, no file name (Maven repo checksum format)
        # Since there is no name match, the first checksum in the file will
        # always be returned, never the second.
        with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as tfile:
            tfile.write(salt.utils.stringutils.to_bytes(
                'ead48423703509d37c4a90e6a0d53e143b6fc268\n'
                'ad782ecdac770fc6eb9a62e44f90873fb97fb26b\n'))
            tfile.flush()

        for hash_type in ('', 'sha1', 'sha256'):
            result = filemod.extract_hash(tfile.name, hash_type, '/testfile')
            expected = {
                'hsum': 'ead48423703509d37c4a90e6a0d53e143b6fc268',
                'hash_type': 'sha1'
            } if hash_type != 'sha256' else None
            self.assertEqual(result, expected)

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

    def test_patch(self):
        with patch('os.path.isdir', return_value=False) as mock_isdir, \
                patch('salt.utils.path.which', return_value='/bin/patch') as mock_which:
            cmd_mock = MagicMock(return_value='test_retval')
            with patch.dict(filemod.__salt__, {'cmd.run_all': cmd_mock}):
                ret = filemod.patch('/path/to/file', '/path/to/patch')
            cmd = ['/bin/patch', '--forward', '--reject-file=-',
                '-i', '/path/to/patch', '/path/to/file']
            cmd_mock.assert_called_once_with(cmd, python_shell=False)
            self.assertEqual('test_retval', ret)

    def test_patch_dry_run(self):
        with patch('os.path.isdir', return_value=False) as mock_isdir, \
                patch('salt.utils.path.which', return_value='/bin/patch') as mock_which:
            cmd_mock = MagicMock(return_value='test_retval')
            with patch.dict(filemod.__salt__, {'cmd.run_all': cmd_mock}):
                ret = filemod.patch('/path/to/file', '/path/to/patch', dry_run=True)
            cmd = ['/bin/patch', '--dry-run', '--forward', '--reject-file=-',
                '-i', '/path/to/patch', '/path/to/file']
            cmd_mock.assert_called_once_with(cmd, python_shell=False)
            self.assertEqual('test_retval', ret)

    def test_patch_dir(self):
        with patch('os.path.isdir', return_value=True) as mock_isdir, \
                patch('salt.utils.path.which', return_value='/bin/patch') as mock_which:
            cmd_mock = MagicMock(return_value='test_retval')
            with patch.dict(filemod.__salt__, {'cmd.run_all': cmd_mock}):
                ret = filemod.patch('/path/to/dir', '/path/to/patch')
            cmd = ['/bin/patch', '--forward', '--reject-file=-',
                '-i', '/path/to/patch', '-d', '/path/to/dir', '--strip=0']
            cmd_mock.assert_called_once_with(cmd, python_shell=False)
            self.assertEqual('test_retval', ret)

    def test_apply_template_on_contents(self):
        '''
        Tests that the templating engine works on string contents
        '''
        contents = 'This is a {{ template }}.'
        defaults = {'template': 'templated file'}
        with patch.object(SaltCacheLoader, 'file_client', Mock()):
            ret = filemod.apply_template_on_contents(
                contents,
                template='jinja',
                context={'opts': filemod.__opts__},
                defaults=defaults,
                saltenv='base')
        self.assertEqual(ret, 'This is a templated file.')

    def test_get_diff(self):

        text1 = textwrap.dedent('''\
            foo
            bar
            baz
            спам
            ''')
        text2 = textwrap.dedent('''\
            foo
            bar
            baz
            яйца
            ''')
        diff_result = textwrap.dedent('''\
            --- text1
            +++ text2
            @@ -1,4 +1,4 @@
             foo
             bar
             baz
            -спам
            +яйца
            ''')

        # The below two variables are 8 bytes of data pulled from /dev/urandom
        binary1 = b'\xd4\xb2\xa6W\xc6\x8e\xf5\x0f'
        binary2 = b',\x13\x04\xa5\xb0\x12\xdf%'

        # pylint: disable=no-self-argument
        class MockFopen(object):
            '''
            Provides a fake filehandle object that has just enough to run
            readlines() as file.get_diff does. Any significant changes to
            file.get_diff may require this class to be modified.
            '''
            def __init__(mockself, path, *args, **kwargs):  # pylint: disable=unused-argument
                mockself.path = path

            def readlines(mockself):  # pylint: disable=unused-argument
                return {
                    'text1': text1.encode('utf8'),
                    'text2': text2.encode('utf8'),
                    'binary1': binary1,
                    'binary2': binary2,
                }[mockself.path].splitlines(True)

            def __enter__(mockself):
                return mockself

            def __exit__(mockself, *args):  # pylint: disable=unused-argument
                pass
        # pylint: enable=no-self-argument

        fopen = MagicMock(side_effect=lambda x, *args, **kwargs: MockFopen(x))
        cache_file = MagicMock(side_effect=lambda x, *args, **kwargs: x.split('/')[-1])

        # Mocks for __utils__['files.is_text']
        mock_text_text = MagicMock(side_effect=[True, True])
        mock_bin_bin = MagicMock(side_effect=[False, False])
        mock_text_bin = MagicMock(side_effect=[True, False])
        mock_bin_text = MagicMock(side_effect=[False, True])

        with patch.dict(filemod.__salt__, {'cp.cache_file': cache_file}), \
                patch.object(salt.utils.files, 'fopen', fopen):

            # Test diffing two text files
            with patch.dict(filemod.__utils__, {'files.is_text': mock_text_text}):

                # Identical files
                ret = filemod.get_diff('text1', 'text1')
                self.assertEqual(ret, '')

                # Non-identical files
                ret = filemod.get_diff('text1', 'text2')
                self.assertEqual(ret, diff_result)

                # Repeat the above test with remote file paths. The expectation
                # is that the cp.cache_file mock will ensure that we are not
                # trying to do an fopen on the salt:// URL, but rather the
                # "cached" file path we've mocked.
                with patch.object(filemod, '_binary_replace',
                                  MagicMock(return_value='')):
                    ret = filemod.get_diff('salt://text1', 'salt://text1')
                    self.assertEqual(ret, '')
                    ret = filemod.get_diff('salt://text1', 'salt://text2')
                    self.assertEqual(ret, diff_result)

            # Test diffing two binary files
            with patch.dict(filemod.__utils__, {'files.is_text': mock_bin_bin}):

                # Identical files
                ret = filemod.get_diff('binary1', 'binary1')
                self.assertEqual(ret, '')

                # Non-identical files
                ret = filemod.get_diff('binary1', 'binary2')
                self.assertEqual(ret, 'Replace binary file')

            # Test diffing a text file with a binary file
            with patch.dict(filemod.__utils__, {'files.is_text': mock_text_bin}):

                ret = filemod.get_diff('text1', 'binary1')
                self.assertEqual(ret, 'Replace text file with binary file')

            # Test diffing a binary file with a text file
            with patch.dict(filemod.__utils__, {'files.is_text': mock_bin_text}):

                ret = filemod.get_diff('binary1', 'text1')
                self.assertEqual(ret, 'Replace binary file with text file')

    def test_stats(self):
        with patch('os.path.expanduser', MagicMock(side_effect=lambda path: path)), \
                patch('os.path.exists', MagicMock(return_value=True)), \
                patch('os.stat', MagicMock(return_value=DummyStat())):
            ret = filemod.stats('dummy', None, True)
            self.assertEqual(ret['mode'], '0644')
            self.assertEqual(ret['type'], 'file')


@skipIf(pytest is None, 'PyTest required for this set of tests')
class FilemodLineTests(TestCase, LoaderModuleMockMixin):
    '''
    Unit tests for file.line
    '''
    def setUp(self):
        class AnyAttr(object):
            def __getattr__(self, item):
                return 0

            def __call__(self, *args, **kwargs):
                return self
        self._anyattr = AnyAttr()

    def tearDown(self):
        del self._anyattr

    def setup_loader_modules(self):
        return {
            filemod: {
                '__salt__': {
                    'config.manage_mode': configmod.manage_mode,
                    'cmd.run': cmdmod.run,
                    'cmd.run_all': cmdmod.run_all
                },
                '__opts__': {
                    'test': False,
                    'file_roots': {'base': 'tmp'},
                    'pillar_roots': {'base': 'tmp'},
                    'cachedir': 'tmp',
                    'grains': {},
                },
                '__grains__': {'kernel': 'Linux'},
                '__utils__': {
                    'stringutils.get_diff': salt.utils.stringutils.get_diff,
                },
            }
        }

    @staticmethod
    def _get_body(content):
        '''
        The body is written as bytestrings or strings depending on platform.
        This func accepts a string of content and returns the appropriate list
        of strings back.
        '''
        ret = content.splitlines(True)
        if six.PY2 and salt.utils.platform.is_windows():
            return salt.utils.data.encode_list(ret)
        else:
            return salt.utils.data.decode_list(ret, to_str=True)

    @patch('os.path.realpath', MagicMock(wraps=lambda x: x))
    @patch('os.path.isfile', MagicMock(return_value=True))
    def test_delete_line_in_empty_file(self):
        '''
        Tests that when calling file.line with ``mode=delete``,
        the function doesn't stack trace if the file is empty.
        Should return ``False``.

        See Issue #38438.
        '''
        for mode in ['delete', 'replace']:
            _log = MagicMock()
            with patch('salt.utils.files.fopen', mock_open(read_data='')), \
                    patch('os.stat', self._anyattr), \
                    patch('salt.modules.file.log', _log):
                self.assertFalse(filemod.line('/dummy/path', content='foo', match='bar', mode=mode))
            self.assertIn('Cannot find text to {0}'.format(mode),
                          _log.warning.call_args_list[0][0][0])

    @patch('os.path.realpath', MagicMock())
    @patch('os.path.isfile', MagicMock(return_value=True))
    @patch('os.stat', MagicMock())
    def test_line_delete_no_match(self):
        '''
        Tests that when calling file.line with ``mode=delete``,
        with not matching pattern to delete returns False
        :return:
        '''
        file_content = os.linesep.join([
            'file_roots:',
            '  base:',
            '    - /srv/salt',
            '    - /srv/custom'
        ])
        match = 'not matching'
        for mode in ['delete', 'replace']:
            files_fopen = mock_open(read_data=file_content)
            with patch('salt.utils.files.fopen', files_fopen):
                atomic_opener = mock_open()
                with patch('salt.utils.atomicfile.atomic_open', atomic_opener):
                    self.assertFalse(filemod.line('foo', content='foo', match=match, mode=mode))

    @patch('os.path.realpath', MagicMock(wraps=lambda x: x))
    @patch('os.path.isfile', MagicMock(return_value=True))
    def test_line_modecheck_failure(self):
        '''
        Test for file.line for empty or wrong mode.
        Calls unknown or empty mode and expects failure.
        :return:
        '''
        for mode, err_msg in [(None, 'How to process the file'), ('nonsense', 'Unknown mode')]:
            with pytest.raises(CommandExecutionError) as exc_info:
                filemod.line('foo', mode=mode)
            self.assertIn(err_msg, six.text_type(exc_info.value))

    @patch('os.path.realpath', MagicMock(wraps=lambda x: x))
    @patch('os.path.isfile', MagicMock(return_value=True))
    def test_line_no_content(self):
        '''
        Test for file.line for an empty content when not deleting anything.
        :return:
        '''
        for mode in ['insert', 'ensure', 'replace']:
            with pytest.raises(CommandExecutionError) as exc_info:
                filemod.line('foo', mode=mode)
            self.assertIn('Content can only be empty if mode is "delete"',
                          six.text_type(exc_info.value))

    @patch('os.path.realpath', MagicMock(wraps=lambda x: x))
    @patch('os.path.isfile', MagicMock(return_value=True))
    @patch('os.stat', MagicMock())
    def test_line_insert_no_location_no_before_no_after(self):
        '''
        Test for file.line for insertion but define no location/before/after.
        :return:
        '''
        files_fopen = mock_open(read_data='test data')
        with patch('salt.utils.files.fopen', files_fopen):
            with pytest.raises(CommandExecutionError) as exc_info:
                filemod.line('foo', content='test content', mode='insert')
            self.assertIn('"location" or "before/after"',
                          six.text_type(exc_info.value))

    def test_util_starts_till(self):
        '''
        Test for file._starts_till function.

        :return:
        '''
        src = 'here is something'
        self.assertEqual(
            filemod._starts_till(src=src, probe='here quite something else'), 1)
        self.assertEqual(
            filemod._starts_till(src=src, probe='here is something'), 0)
        self.assertEqual(
            filemod._starts_till(src=src, probe='and here is something'), -1)

    @with_tempfile()
    def test_line_insert_after_no_pattern(self, name):
        '''
        Test for file.line for insertion after specific line, using no pattern.

        See issue #38670
        :return:
        '''
        file_content = os.linesep.join([
            'file_roots:',
            '  base:',
            '    - /srv/salt'
        ])
        file_modified = os.linesep.join([
            'file_roots:',
            '  base:',
            '    - /srv/salt',
            '    - /srv/custom'
        ])
        cfg_content = '- /srv/custom'

        isfile_mock = MagicMock(side_effect=lambda x: True if x == name else DEFAULT)
        with patch('os.path.isfile', isfile_mock), \
                patch('os.stat', MagicMock(return_value=DummyStat())), \
                patch('salt.utils.files.fopen', mock_open(read_data=file_content)), \
                patch('salt.utils.atomicfile.atomic_open', mock_open()) as atomic_open_mock:
            filemod.line(name, content=cfg_content, after='- /srv/salt', mode='insert')
            handles = atomic_open_mock.filehandles[name]
            # We should only have opened the file once
            open_count = len(handles)
            assert open_count == 1, open_count
            # We should only have invoked .writelines() once...
            writelines_content = handles[0].writelines_calls
            writelines_count = len(writelines_content)
            assert writelines_count == 1, writelines_count
            # ... with the updated content
            expected = self._get_body(file_modified)
            assert writelines_content[0] == expected, (writelines_content[0], expected)

    @with_tempfile()
    def test_line_insert_after_pattern(self, name):
        '''
        Test for file.line for insertion after specific line, using pattern.

        See issue #38670
        :return:
        '''
        file_content = os.linesep.join([
            'file_boots:',
            '  - /rusty',
            'file_roots:',
            '  base:',
            '    - /srv/salt',
            '    - /srv/sugar'
        ])
        file_modified = os.linesep.join([
            'file_boots:',
            '  - /rusty',
            'file_roots:',
            '  custom:',
            '    - /srv/custom',
            '  base:',
            '    - /srv/salt',
            '    - /srv/sugar'
        ])
        cfg_content = os.linesep.join([
            '  custom:',
            '    - /srv/custom'
        ])
        isfile_mock = MagicMock(side_effect=lambda x: True if x == name else DEFAULT)
        for after_line in ['file_r.*', '.*roots']:
            with patch('os.path.isfile', isfile_mock), \
                    patch('os.stat', MagicMock(return_value=DummyStat())), \
                    patch('salt.utils.files.fopen',
                          mock_open(read_data=file_content)), \
                    patch('salt.utils.atomicfile.atomic_open',
                          mock_open()) as atomic_open_mock:
                filemod.line(name, content=cfg_content, after=after_line, mode='insert', indent=False)
                handles = atomic_open_mock.filehandles[name]
                # We should only have opened the file once
                open_count = len(handles)
                assert open_count == 1, open_count
                # We should only have invoked .writelines() once...
                writelines_content = handles[0].writelines_calls
                writelines_count = len(writelines_content)
                assert writelines_count == 1, writelines_count
                # ... with the updated content
                expected = self._get_body(file_modified)
                # We passed cfg_content with a newline in the middle, so it
                # will be written as two lines in the same element of the list
                # passed to .writelines()
                expected[3] = expected[3] + expected.pop(4)
                assert writelines_content[0] == expected, (writelines_content[0], expected)

    @with_tempfile()
    def test_line_insert_multi_line_content_after_unicode(self, name):
        '''
        Test for file.line for insertion after specific line with Unicode

        See issue #48113
        :return:
        '''
        file_content = 'This is a line{}This is another line'.format(os.linesep)
        file_modified = salt.utils.stringutils.to_str('This is a line{}'
                                                      'This is another line{}'
                                                      'This is a line with unicode Ŷ'.format(
                                                           os.linesep, os.linesep
                                                           )
                                                      )
        cfg_content = "This is a line with unicode Ŷ"
        isfile_mock = MagicMock(side_effect=lambda x: True if x == name else DEFAULT)
        for after_line in ['This is another line']:
            with patch('os.path.isfile', isfile_mock), \
                    patch('os.stat', MagicMock(return_value=DummyStat())), \
                    patch('salt.utils.files.fopen',
                          mock_open(read_data=file_content)), \
                    patch('salt.utils.atomicfile.atomic_open',
                          mock_open()) as atomic_open_mock:
                filemod.line(name, content=cfg_content, after=after_line, mode='insert', indent=False)
                handles = atomic_open_mock.filehandles[name]
                # We should only have opened the file once
                open_count = len(handles)
                assert open_count == 1, open_count
                # We should only have invoked .writelines() once...
                writelines_content = handles[0].writelines_calls
                writelines_count = len(writelines_content)
                assert writelines_count == 1, writelines_count
                # ... with the updated content
                expected = self._get_body(file_modified)
                assert writelines_content[0] == expected, (writelines_content[0], expected)

    @with_tempfile()
    def test_line_insert_before(self, name):
        '''
        Test for file.line for insertion before specific line, using pattern and no patterns.

        See issue #38670
        :return:
        '''
        file_content = os.linesep.join([
            'file_roots:',
            '  base:',
            '    - /srv/salt',
            '    - /srv/sugar'
        ])
        file_modified = os.linesep.join([
            'file_roots:',
            '  base:',
            '    - /srv/custom',
            '    - /srv/salt',
            '    - /srv/sugar'
        ])
        cfg_content = '- /srv/custom'

        isfile_mock = MagicMock(side_effect=lambda x: True if x == name else DEFAULT)
        for before_line in ['/srv/salt', '/srv/sa.*t']:
            with patch('os.path.isfile', isfile_mock), \
                    patch('os.stat', MagicMock(return_value=DummyStat())), \
                    patch('salt.utils.files.fopen',
                          mock_open(read_data=file_content)), \
                    patch('salt.utils.atomicfile.atomic_open',
                          mock_open()) as atomic_open_mock:
                filemod.line(name, content=cfg_content, before=before_line, mode='insert')
                handles = atomic_open_mock.filehandles[name]
                # We should only have opened the file once
                open_count = len(handles)
                assert open_count == 1, open_count
                # We should only have invoked .writelines() once...
                writelines_content = handles[0].writelines_calls
                writelines_count = len(writelines_content)
                assert writelines_count == 1, writelines_count
                # ... with the updated content
                expected = self._get_body(file_modified)
                assert writelines_content[0] == expected, (writelines_content[0], expected)

    @patch('os.path.realpath', MagicMock(wraps=lambda x: x))
    @patch('os.path.isfile', MagicMock(return_value=True))
    @patch('os.stat', MagicMock())
    def test_line_assert_exception_pattern(self):
        '''
        Test for file.line for exception on insert with too general pattern.

        :return:
        '''
        file_content = os.linesep.join([
            'file_roots:',
            '  base:',
            '    - /srv/salt',
            '    - /srv/sugar'
        ])
        cfg_content = '- /srv/custom'
        for before_line in ['/sr.*']:
            files_fopen = mock_open(read_data=file_content)
            with patch('salt.utils.files.fopen', files_fopen):
                atomic_opener = mock_open()
                with patch('salt.utils.atomicfile.atomic_open', atomic_opener):
                    with self.assertRaises(CommandExecutionError) as cm:
                        filemod.line('foo', content=cfg_content, before=before_line, mode='insert')
                    self.assertEqual(cm.exception.strerror,
                                     'Found more than expected occurrences in "before" expression')

    @with_tempfile()
    def test_line_insert_before_after(self, name):
        '''
        Test for file.line for insertion before specific line, using pattern and no patterns.

        See issue #38670
        :return:
        '''
        file_content = os.linesep.join([
            'file_roots:',
            '  base:',
            '    - /srv/salt',
            '    - /srv/pepper',
            '    - /srv/sugar'
        ])
        file_modified = os.linesep.join([
            'file_roots:',
            '  base:',
            '    - /srv/salt',
            '    - /srv/pepper',
            '    - /srv/coriander',
            '    - /srv/sugar'
        ])
        cfg_content = '- /srv/coriander'

        isfile_mock = MagicMock(side_effect=lambda x: True if x == name else DEFAULT)
        for b_line, a_line in [('/srv/sugar', '/srv/salt')]:
            with patch('os.path.isfile', isfile_mock), \
                    patch('os.stat', MagicMock(return_value=DummyStat())), \
                    patch('salt.utils.files.fopen',
                          mock_open(read_data=file_content)), \
                    patch('salt.utils.atomicfile.atomic_open',
                          mock_open()) as atomic_open_mock:
                filemod.line(name, content=cfg_content, before=b_line, after=a_line, mode='insert')
                handles = atomic_open_mock.filehandles[name]
                # We should only have opened the file once
                open_count = len(handles)
                assert open_count == 1, open_count
                # We should only have invoked .writelines() once...
                writelines_content = handles[0].writelines_calls
                writelines_count = len(writelines_content)
                assert writelines_count == 1, writelines_count
                # ... with the updated content
                expected = self._get_body(file_modified)
                assert writelines_content[0] == expected, (writelines_content[0], expected)

    @with_tempfile()
    def test_line_insert_start(self, name):
        '''
        Test for file.line for insertion at the beginning of the file
        :return:
        '''
        cfg_content = 'everything: fantastic'
        file_content = os.linesep.join([
            'file_roots:',
            '  base:',
            '    - /srv/salt',
            '    - /srv/sugar'
        ])
        file_modified = os.linesep.join([
            cfg_content,
            'file_roots:',
            '  base:',
            '    - /srv/salt',
            '    - /srv/sugar'
        ])

        isfile_mock = MagicMock(side_effect=lambda x: True if x == name else DEFAULT)
        with patch('os.path.isfile', isfile_mock), \
                patch('os.stat', MagicMock(return_value=DummyStat())), \
                patch('salt.utils.files.fopen',
                      mock_open(read_data=file_content)), \
                patch('salt.utils.atomicfile.atomic_open',
                      mock_open()) as atomic_open_mock:
            filemod.line(name, content=cfg_content, location='start', mode='insert')
            handles = atomic_open_mock.filehandles[name]
            # We should only have opened the file once
            open_count = len(handles)
            assert open_count == 1, open_count
            # We should only have invoked .writelines() once...
            writelines_content = handles[0].writelines_calls
            writelines_count = len(writelines_content)
            assert writelines_count == 1, writelines_count
            # ... with the updated content
            expected = self._get_body(file_modified)
            assert writelines_content[0] == expected, (writelines_content[0], expected)

    @with_tempfile()
    def test_line_insert_end(self, name):
        '''
        Test for file.line for insertion at the end of the file (append)
        :return:
        '''
        cfg_content = 'everything: fantastic'
        file_content = os.linesep.join([
            'file_roots:',
            '  base:',
            '    - /srv/salt',
            '    - /srv/sugar'
        ])
        file_modified = os.linesep.join([
            'file_roots:',
            '  base:',
            '    - /srv/salt',
            '    - /srv/sugar',
            '    ' + cfg_content
        ])

        isfile_mock = MagicMock(side_effect=lambda x: True if x == name else DEFAULT)
        with patch('os.path.isfile', isfile_mock), \
                patch('os.stat', MagicMock(return_value=DummyStat())), \
                patch('salt.utils.files.fopen',
                      mock_open(read_data=file_content)), \
                patch('salt.utils.atomicfile.atomic_open',
                      mock_open()) as atomic_open_mock:
            filemod.line(name, content=cfg_content, location='end', mode='insert')
            handles = atomic_open_mock.filehandles[name]
            # We should only have opened the file once
            open_count = len(handles)
            assert open_count == 1, open_count
            # We should only have invoked .writelines() once...
            writelines_content = handles[0].writelines_calls
            writelines_count = len(writelines_content)
            assert writelines_count == 1, writelines_count
            # ... with the updated content
            expected = self._get_body(file_modified)
            assert writelines_content[0] == expected, (writelines_content[0], expected)

    @with_tempfile()
    def test_line_insert_ensure_before(self, name):
        '''
        Test for file.line for insertion ensuring the line is before
        :return:
        '''
        cfg_content = '/etc/init.d/someservice restart'
        file_content = os.linesep.join([
            '#!/bin/bash',
            '',
            'exit 0'
        ])
        file_modified = os.linesep.join([
            '#!/bin/bash',
            '',
            cfg_content,
            'exit 0'
        ])

        isfile_mock = MagicMock(side_effect=lambda x: True if x == name else DEFAULT)
        with patch('os.path.isfile', isfile_mock), \
             patch('os.stat', MagicMock(return_value=DummyStat())), \
             patch('salt.utils.files.fopen',
                   mock_open(read_data=file_content)), \
             patch('salt.utils.atomicfile.atomic_open',
                   mock_open()) as atomic_open_mock:
            filemod.line(name, content=cfg_content, before='exit 0', mode='ensure')
            handles = atomic_open_mock.filehandles[name]
            # We should only have opened the file once
            open_count = len(handles)
            assert open_count == 1, open_count
            # We should only have invoked .writelines() once...
            writelines_content = handles[0].writelines_calls
            writelines_count = len(writelines_content)
            assert writelines_count == 1, writelines_count
            # ... with the updated content
            expected = self._get_body(file_modified)
            assert writelines_content[0] == expected, (writelines_content[0], expected)

    @with_tempfile()
    def test_line_insert_duplicate_ensure_before(self, name):
        '''
        Test for file.line for insertion ensuring the line is before
        :return:
        '''
        cfg_content = '/etc/init.d/someservice restart'
        file_content = os.linesep.join([
            '#!/bin/bash',
            '',
            cfg_content,
            'exit 0'
        ])
        file_modified = os.linesep.join([
            '#!/bin/bash',
            '',
            cfg_content,
            'exit 0'
        ])

        isfile_mock = MagicMock(side_effect=lambda x: True if x == name else DEFAULT)
        with patch('os.path.isfile', isfile_mock), \
                patch('os.stat', MagicMock(return_value=DummyStat())), \
                patch('salt.utils.files.fopen',
                      mock_open(read_data=file_content)), \
                patch('salt.utils.atomicfile.atomic_open',
                      mock_open()) as atomic_open_mock:
            filemod.line(name, content=cfg_content, before='exit 0', mode='ensure')
            # If file not modified no handlers in dict
            assert atomic_open_mock.filehandles.get(name) is None

    @with_tempfile()
    def test_line_insert_ensure_before_first_line(self, name):
        '''
        Test for file.line for insertion ensuring the line is before first line
        :return:
        '''
        cfg_content = '#!/bin/bash'
        file_content = os.linesep.join([
            '/etc/init.d/someservice restart',
            'exit 0'
        ])
        file_modified = os.linesep.join([
            cfg_content,
            '/etc/init.d/someservice restart',
            'exit 0'
        ])

        isfile_mock = MagicMock(side_effect=lambda x: True if x == name else DEFAULT)
        with patch('os.path.isfile', isfile_mock), \
                patch('os.stat', MagicMock(return_value=DummyStat())), \
                patch('salt.utils.files.fopen',
                      mock_open(read_data=file_content)), \
                patch('salt.utils.atomicfile.atomic_open',
                      mock_open()) as atomic_open_mock:
            filemod.line(name, content=cfg_content, before='/etc/init.d/someservice restart', mode='ensure')
            handles = atomic_open_mock.filehandles[name]
            # We should only have opened the file once
            open_count = len(handles)
            assert open_count == 1, open_count
            # We should only have invoked .writelines() once...
            writelines_content = handles[0].writelines_calls
            writelines_count = len(writelines_content)
            assert writelines_count == 1, writelines_count
            # ... with the updated content
            expected = self._get_body(file_modified)
            assert writelines_content[0] == expected, (writelines_content[0], expected)

    @with_tempfile()
    def test_line_insert_ensure_after(self, name):
        '''
        Test for file.line for insertion ensuring the line is after
        :return:
        '''
        cfg_content = 'exit 0'
        file_content = os.linesep.join([
            '#!/bin/bash',
            '/etc/init.d/someservice restart'
        ])
        file_modified = os.linesep.join([
            '#!/bin/bash',
            '/etc/init.d/someservice restart',
            cfg_content
        ])

        isfile_mock = MagicMock(side_effect=lambda x: True if x == name else DEFAULT)
        with patch('os.path.isfile', isfile_mock), \
                patch('os.stat', MagicMock(return_value=DummyStat())), \
                patch('salt.utils.files.fopen',
                      mock_open(read_data=file_content)), \
                patch('salt.utils.atomicfile.atomic_open',
                      mock_open()) as atomic_open_mock:
            filemod.line(name, content=cfg_content, after='/etc/init.d/someservice restart', mode='ensure')
            handles = atomic_open_mock.filehandles[name]
            # We should only have opened the file once
            open_count = len(handles)
            assert open_count == 1, open_count
            # We should only have invoked .writelines() once...
            writelines_content = handles[0].writelines_calls
            writelines_count = len(writelines_content)
            assert writelines_count == 1, writelines_count
            # ... with the updated content
            expected = self._get_body(file_modified)
            assert writelines_content[0] == expected, (writelines_content[0], expected)

    @with_tempfile()
    def test_line_insert_duplicate_ensure_after(self, name):
        '''
        Test for file.line for insertion ensuring the line is after
        :return:
        '''
        cfg_content = 'exit 0'
        file_content = os.linesep.join([
            '#!/bin/bash',
            '/etc/init.d/someservice restart',
            cfg_content
        ])
        file_modified = os.linesep.join([
            '#!/bin/bash',
            '/etc/init.d/someservice restart',
            cfg_content
        ])

        isfile_mock = MagicMock(side_effect=lambda x: True if x == name else DEFAULT)
        with patch('os.path.isfile', isfile_mock), \
                patch('os.stat', MagicMock(return_value=DummyStat())), \
                patch('salt.utils.files.fopen',
                      mock_open(read_data=file_content)), \
                patch('salt.utils.atomicfile.atomic_open',
                      mock_open()) as atomic_open_mock:
            filemod.line(name, content=cfg_content, after='/etc/init.d/someservice restart', mode='ensure')
            # If file not modified no handlers in dict
            assert atomic_open_mock.filehandles.get(name) is None

    @with_tempfile()
    def test_line_insert_ensure_beforeafter_twolines(self, name):
        '''
        Test for file.line for insertion ensuring the line is between two lines
        :return:
        '''
        cfg_content = 'EXTRA_GROUPS="dialout cdrom floppy audio video plugdev users"'
        # pylint: disable=W1401
        file_content = os.linesep.join([
            'NAME_REGEX="^[a-z][-a-z0-9_]*\$"',
            'SKEL_IGNORE_REGEX="dpkg-(old|new|dist|save)"'
        ])
        # pylint: enable=W1401
        after, before = file_content.split(os.linesep)
        file_modified = os.linesep.join([after, cfg_content, before])

        isfile_mock = MagicMock(side_effect=lambda x: True if x == name else DEFAULT)
        for (_after, _before) in [(after, before), ('NAME_.*', 'SKEL_.*')]:
            with patch('os.path.isfile', isfile_mock), \
                    patch('os.stat', MagicMock(return_value=DummyStat())), \
                    patch('salt.utils.files.fopen',
                          mock_open(read_data=file_content)), \
                    patch('salt.utils.atomicfile.atomic_open',
                          mock_open()) as atomic_open_mock:
                filemod.line(name, content=cfg_content, after=_after, before=_before, mode='ensure')
                handles = atomic_open_mock.filehandles[name]
                # We should only have opened the file once
                open_count = len(handles)
                assert open_count == 1, open_count
                # We should only have invoked .writelines() once...
                writelines_content = handles[0].writelines_calls
                writelines_count = len(writelines_content)
                assert writelines_count == 1, writelines_count
                # ... with the updated content
                expected = self._get_body(file_modified)
                assert writelines_content[0] == expected, (writelines_content[0], expected)

    @with_tempfile()
    def test_line_insert_ensure_beforeafter_twolines_exists(self, name):
        '''
        Test for file.line for insertion ensuring the line is between two lines
        where content already exists
        '''
        cfg_content = 'EXTRA_GROUPS="dialout"'
        # pylint: disable=W1401
        file_content = os.linesep.join([
            'NAME_REGEX="^[a-z][-a-z0-9_]*\$"',
            'EXTRA_GROUPS="dialout"',
            'SKEL_IGNORE_REGEX="dpkg-(old|new|dist|save)"'
        ])
        # pylint: enable=W1401
        after, before = file_content.split(os.linesep)[0], file_content.split(os.linesep)[2]

        isfile_mock = MagicMock(side_effect=lambda x: True if x == name else DEFAULT)
        for (_after, _before) in [(after, before), ('NAME_.*', 'SKEL_.*')]:
            with patch('os.path.isfile', isfile_mock), \
                    patch('os.stat', MagicMock(return_value=DummyStat())), \
                    patch('salt.utils.files.fopen',
                          mock_open(read_data=file_content)), \
                    patch('salt.utils.atomicfile.atomic_open',
                          mock_open()) as atomic_open_mock:
                result = filemod.line('foo', content=cfg_content, after=_after, before=_before, mode='ensure')
                # We should not have opened the file
                assert not atomic_open_mock.filehandles
                # No changes should have been made
                assert result is False

    @patch('os.path.realpath', MagicMock(wraps=lambda x: x))
    @patch('os.path.isfile', MagicMock(return_value=True))
    @patch('os.stat', MagicMock())
    def test_line_insert_ensure_beforeafter_rangelines(self):
        '''
        Test for file.line for insertion ensuring the line is between two lines
        within the range.  This expected to bring no changes.
        '''
        cfg_content = 'EXTRA_GROUPS="dialout cdrom floppy audio video plugdev users"'
        # pylint: disable=W1401
        file_content = 'NAME_REGEX="^[a-z][-a-z0-9_]*\$"{}SETGID_HOME=no{}ADD_EXTRA_GROUPS=1{}' \
                       'SKEL_IGNORE_REGEX="dpkg-(old|new|dist|save)"'.format(
                           os.linesep, os.linesep, os.linesep
                       )
        # pylint: enable=W1401
        after, before = file_content.split(os.linesep)[0], file_content.split(os.linesep)[-1]
        for (_after, _before) in [(after, before), ('NAME_.*', 'SKEL_.*')]:
            files_fopen = mock_open(read_data=file_content)
            with patch('salt.utils.files.fopen', files_fopen):
                atomic_opener = mock_open()
                with patch('salt.utils.atomicfile.atomic_open', atomic_opener):
                    with pytest.raises(CommandExecutionError) as exc_info:
                        filemod.line('foo', content=cfg_content, after=_after, before=_before, mode='ensure')
            self.assertIn(
                'Found more than one line between boundaries "before" and "after"',
                six.text_type(exc_info.value))

    @with_tempfile()
    def test_line_delete(self, name):
        '''
        Test for file.line for deletion of specific line
        :return:
        '''
        file_content = os.linesep.join([
            'file_roots:',
            '  base:',
            '    - /srv/salt',
            '    - /srv/pepper',
            '    - /srv/sugar'
        ])
        file_modified = os.linesep.join([
            'file_roots:',
            '  base:',
            '    - /srv/salt',
            '    - /srv/sugar'
        ])

        isfile_mock = MagicMock(side_effect=lambda x: True if x == name else DEFAULT)
        for content in ['/srv/pepper', '/srv/pepp*', '/srv/p.*', '/sr.*pe.*']:
            files_fopen = mock_open(read_data=file_content)
            with patch('os.path.isfile', isfile_mock), \
                    patch('os.stat', MagicMock(return_value=DummyStat())), \
                    patch('salt.utils.files.fopen', files_fopen), \
                    patch('salt.utils.atomicfile.atomic_open', mock_open()) as atomic_open_mock:
                filemod.line(name, content=content, mode='delete')
                handles = atomic_open_mock.filehandles[name]
                # We should only have opened the file once
                open_count = len(handles)
                assert open_count == 1, open_count
                # We should only have invoked .writelines() once...
                writelines_content = handles[0].writelines_calls
                writelines_count = len(writelines_content)
                assert writelines_count == 1, writelines_count
                # ... with the updated content
                expected = self._get_body(file_modified)
                assert writelines_content[0] == expected, (writelines_content[0], expected)

    @with_tempfile()
    def test_line_replace(self, name):
        '''
        Test for file.line for replacement of specific line
        :return:
        '''
        file_content = os.linesep.join([
            'file_roots:',
            '  base:',
            '    - /srv/salt',
            '    - /srv/pepper',
            '    - /srv/sugar'
        ])
        file_modified = os.linesep.join([
            'file_roots:',
            '  base:',
            '    - /srv/salt',
            '    - /srv/natrium-chloride',
            '    - /srv/sugar'
        ])

        isfile_mock = MagicMock(side_effect=lambda x: True if x == name else DEFAULT)
        for match in ['/srv/pepper', '/srv/pepp*', '/srv/p.*', '/sr.*pe.*']:
            files_fopen = mock_open(read_data=file_content)
            with patch('os.path.isfile', isfile_mock), \
                    patch('os.stat', MagicMock(return_value=DummyStat())), \
                    patch('salt.utils.files.fopen', files_fopen), \
                    patch('salt.utils.atomicfile.atomic_open', mock_open()) as atomic_open_mock:
                filemod.line(name, content='- /srv/natrium-chloride', match=match, mode='replace')
                handles = atomic_open_mock.filehandles[name]
                # We should only have opened the file once
                open_count = len(handles)
                assert open_count == 1, open_count
                # We should only have invoked .writelines() once...
                writelines_content = handles[0].writelines_calls
                writelines_count = len(writelines_content)
                assert writelines_count == 1, writelines_count
                # ... with the updated content
                expected = self._get_body(file_modified)
                assert writelines_content[0] == expected, (writelines_content[0], expected)


class FileBasicsTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {
            filemod: {
                '__salt__': {
                    'config.manage_mode': configmod.manage_mode,
                    'cmd.run': cmdmod.run,
                    'cmd.run_all': cmdmod.run_all
                },
                '__opts__': {
                    'test': False,
                    'file_roots': {'base': 'tmp'},
                    'pillar_roots': {'base': 'tmp'},
                    'cachedir': 'tmp',
                    'grains': {},
                },
                '__grains__': {'kernel': 'Linux'}
            }
        }

    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)
        self.addCleanup(delattr, self, 'directory')
        with tempfile.NamedTemporaryFile(delete=False, mode='w+') as self.tfile:
            self.tfile.write('Hi hello! I am a file.')
            self.tfile.close()
        self.addCleanup(os.remove, self.tfile.name)
        self.addCleanup(delattr, self, 'tfile')
        self.myfile = os.path.join(RUNTIME_VARS.TMP, 'myfile')
        with salt.utils.files.fopen(self.myfile, 'w+') as fp:
            fp.write(salt.utils.stringutils.to_str('Hello\n'))
        self.addCleanup(os.remove, self.myfile)
        self.addCleanup(delattr, self, 'myfile')

    @skipIf(salt.utils.platform.is_windows(), 'os.symlink is not available on Windows')
    def test_symlink_already_in_desired_state(self):
        os.symlink(self.tfile.name, self.directory + '/a_link')
        self.addCleanup(os.remove, self.directory + '/a_link')
        result = filemod.symlink(self.tfile.name, self.directory + '/a_link')
        self.assertTrue(result)

    @skipIf(salt.utils.platform.is_windows(), 'os.link is not available on Windows')
    def test_hardlink_sanity(self):
        target = os.path.join(self.directory, 'a_hardlink')
        self.addCleanup(os.remove, target)
        result = filemod.link(self.tfile.name, target)
        self.assertTrue(result)

    @skipIf(salt.utils.platform.is_windows(), 'os.link is not available on Windows')
    def test_hardlink_numlinks(self):
        target = os.path.join(self.directory, 'a_hardlink')
        self.addCleanup(os.remove, target)
        result = filemod.link(self.tfile.name, target)
        name_i = os.stat(self.tfile.name).st_nlink
        self.assertTrue(name_i > 1)

    @skipIf(salt.utils.platform.is_windows(), 'os.link is not available on Windows')
    def test_hardlink_working(self):
        target = os.path.join(self.directory, 'a_hardlink')
        self.addCleanup(os.remove, target)
        result = filemod.link(self.tfile.name, target)
        name_i = os.stat(self.tfile.name).st_ino
        target_i = os.stat(target).st_ino
        self.assertTrue(name_i == target_i)

    def test_source_list_for_list_returns_file_from_dict_via_http(self):
        with patch('salt.modules.file.os.remove') as remove:
            remove.return_value = None
            with patch.dict(filemod.__salt__, {'cp.list_master': MagicMock(return_value=[]),
                                               'cp.list_master_dirs': MagicMock(return_value=[]),
                                               'cp.cache_file': MagicMock(return_value='/tmp/http.conf')}):
                ret = filemod.source_list(
                    [{'http://t.est.com/http/httpd.conf': 'filehash'}], '', 'base')
                self.assertEqual(list(ret), ['http://t.est.com/http/httpd.conf', 'filehash'])

    def test_source_list_for_list_returns_existing_file(self):
        with patch.dict(filemod.__salt__, {'cp.list_master': MagicMock(return_value=['http/httpd.conf.fallback']),
                                           'cp.list_master_dirs': MagicMock(return_value=[])}):
            ret = filemod.source_list(['salt://http/httpd.conf',
                                       'salt://http/httpd.conf.fallback'],
                                      'filehash', 'base')
            self.assertEqual(list(ret), ['salt://http/httpd.conf.fallback', 'filehash'])

    def test_source_list_for_list_returns_file_from_other_env(self):
        def list_master(env):
            dct = {'base': [], 'dev': ['http/httpd.conf']}
            return dct[env]

        with patch.dict(filemod.__salt__, {'cp.list_master': MagicMock(side_effect=list_master),
                                           'cp.list_master_dirs': MagicMock(return_value=[])}):
            ret = filemod.source_list(['salt://http/httpd.conf?saltenv=dev',
                                       'salt://http/httpd.conf.fallback'],
                                      'filehash', 'base')
            self.assertEqual(list(ret), ['salt://http/httpd.conf?saltenv=dev', 'filehash'])

    def test_source_list_for_list_returns_file_from_dict(self):
        with patch.dict(filemod.__salt__, {'cp.list_master': MagicMock(return_value=['http/httpd.conf']),
                                           'cp.list_master_dirs': MagicMock(return_value=[])}):
            ret = filemod.source_list(
                [{'salt://http/httpd.conf': ''}], 'filehash', 'base')
            self.assertEqual(list(ret), ['salt://http/httpd.conf', 'filehash'])

    def test_source_list_for_list_returns_existing_local_file_slash(self):
        with patch.dict(filemod.__salt__, {'cp.list_master': MagicMock(return_value=[]),
                                           'cp.list_master_dirs': MagicMock(return_value=[])}):
            ret = filemod.source_list([self.myfile + '-foo',
                                       self.myfile],
                                      'filehash', 'base')
            self.assertEqual(list(ret), [self.myfile, 'filehash'])

    def test_source_list_for_list_returns_existing_local_file_proto(self):
        with patch.dict(filemod.__salt__, {'cp.list_master': MagicMock(return_value=[]),
                                           'cp.list_master_dirs': MagicMock(return_value=[])}):
            ret = filemod.source_list(['file://' + self.myfile + '-foo',
                                       'file://' + self.myfile],
                                      'filehash', 'base')
            self.assertEqual(list(ret), ['file://' + self.myfile, 'filehash'])

    def test_source_list_for_list_returns_local_file_slash_from_dict(self):
        with patch.dict(filemod.__salt__, {'cp.list_master': MagicMock(return_value=[]),
                                           'cp.list_master_dirs': MagicMock(return_value=[])}):
            ret = filemod.source_list(
                [{self.myfile: ''}], 'filehash', 'base')
            self.assertEqual(list(ret), [self.myfile, 'filehash'])

    def test_source_list_for_list_returns_local_file_proto_from_dict(self):
        with patch.dict(filemod.__salt__, {'cp.list_master': MagicMock(return_value=[]),
                                           'cp.list_master_dirs': MagicMock(return_value=[])}):
            ret = filemod.source_list(
                [{'file://' + self.myfile: ''}], 'filehash', 'base')
            self.assertEqual(list(ret), ['file://' + self.myfile, 'filehash'])


class LsattrTests(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {
            filemod: {
                '__salt__': {
                    'cmd.run': cmdmod.run,
                },
            },
        }

    def run(self, result=None):
        patch_aix = patch(
            'salt.utils.platform.is_aix',
            Mock(return_value=False),
        )
        patch_exists = patch(
            'os.path.exists',
            Mock(return_value=True),
        )
        patch_which = patch(
            'salt.utils.path.which',
            Mock(return_value='fnord'),
        )
        with patch_aix, patch_exists, patch_which:
            super(LsattrTests, self).run(result)

    def test_if_lsattr_is_missing_it_should_return_None(self):
        patch_which = patch(
            'salt.utils.path.which',
            Mock(return_value=None),
        )
        with patch_which:
            actual = filemod.lsattr('foo')
            assert actual is None, actual

    def test_on_aix_lsattr_should_be_None(self):
        patch_aix = patch(
            'salt.utils.platform.is_aix',
            Mock(return_value=True),
        )
        with patch_aix:
            # SaltInvocationError will be raised if filemod.lsattr
            # doesn't early exit
            actual = filemod.lsattr('foo')
            self.assertIsNone(actual)

    def test_SaltInvocationError_should_be_raised_when_file_is_missing(self):
        patch_exists = patch(
            'os.path.exists',
            Mock(return_value=False),
        )
        with patch_exists, self.assertRaises(SaltInvocationError):
            filemod.lsattr('foo')

    def test_if_chattr_version_is_less_than_required_flags_should_ignore_extended(self):
        fname = '/path/to/fnord'
        with_extended = textwrap.dedent(
            '''
            aAcCdDeijPsStTu---- {}
            '''
        ).strip().format(fname)
        expected = set('acdijstuADST')
        patch_has_ext = patch(
            'salt.modules.file._chattr_has_extended_attrs',
            Mock(return_value=False),
        )
        patch_run = patch.dict(
            filemod.__salt__,
            {'cmd.run': Mock(return_value=with_extended)},
        )
        with patch_has_ext, patch_run:
            actual = set(filemod.lsattr(fname)[fname])
            msg = 'Actual: {!r} Expected: {!r}'.format(actual, expected)  # pylint: disable=E1322
            assert actual == expected, msg

    def test_if_chattr_version_is_high_enough_then_extended_flags_should_be_returned(self):
        fname = '/path/to/fnord'
        with_extended = textwrap.dedent(
            '''
            aAcCdDeijPsStTu---- {}
            '''
        ).strip().format(fname)
        expected = set('aAcCdDeijPsStTu')
        patch_has_ext = patch(
            'salt.modules.file._chattr_has_extended_attrs',
            Mock(return_value=True),
        )
        patch_run = patch.dict(
            filemod.__salt__,
            {'cmd.run': Mock(return_value=with_extended)},
        )
        with patch_has_ext, patch_run:
            actual = set(filemod.lsattr(fname)[fname])
            msg = 'Actual: {!r} Expected: {!r}'.format(actual, expected)  # pylint: disable=E1322
            assert actual == expected, msg

    def test_if_supports_extended_but_there_are_no_flags_then_none_should_be_returned(self):
        fname = '/path/to/fnord'
        with_extended = textwrap.dedent(
            '''
            ------------------- {}
            '''
        ).strip().format(fname)
        expected = set('')
        patch_has_ext = patch(
            'salt.modules.file._chattr_has_extended_attrs',
            Mock(return_value=True),
        )
        patch_run = patch.dict(
            filemod.__salt__,
            {'cmd.run': Mock(return_value=with_extended)},
        )
        with patch_has_ext, patch_run:
            actual = set(filemod.lsattr(fname)[fname])
            msg = 'Actual: {!r} Expected: {!r}'.format(actual, expected)  # pylint: disable=E1322
            assert actual == expected, msg


# This should create a merge conflict with ChattrVersionTests when
# a merge forward to develop happens. Develop's changes are made
# obsolete by this ChattrTests class, and should be removed in favor
# of this change.
class ChattrTests(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {
            filemod: {
                '__salt__': {
                    'cmd.run': cmdmod.run,
                },
                '__opts__': {
                    'test': False,
                },
            },
        }

    def run(self, result=None):
        patch_aix = patch(
            'salt.utils.platform.is_aix',
            Mock(return_value=False),
        )
        patch_exists = patch(
            'os.path.exists',
            Mock(return_value=True),
        )
        patch_which = patch(
            'salt.utils.path.which',
            Mock(return_value='some/tune2fs'),
        )
        with patch_aix, patch_exists, patch_which:
            super(ChattrTests, self).run(result)

    def test_chattr_version_returns_None_if_no_tune2fs_exists(self):
        patch_which = patch(
            'salt.utils.path.which',
            Mock(return_value=''),
        )
        with patch_which:
            actual = filemod._chattr_version()
            self.assertIsNone(actual)

    def test_on_aix_chattr_version_should_be_None_even_if_tune2fs_exists(self):
        patch_which = patch(
            'salt.utils.path.which',
            Mock(return_value='fnord'),
        )
        patch_aix = patch(
            'salt.utils.platform.is_aix',
            Mock(return_value=True),
        )
        mock_run = MagicMock(return_value='fnord')
        patch_run = patch.dict(filemod.__salt__, {'cmd.run': mock_run})
        with patch_which, patch_aix, patch_run:
            actual = filemod._chattr_version()
            self.assertIsNone(actual)
            mock_run.assert_not_called()

    def test_chattr_version_should_return_version_from_tune2fs(self):
        expected = '1.43.4'
        sample_output = textwrap.dedent(
            '''
            tune2fs 1.43.4 (31-Jan-2017)
            Usage: tune2fs [-c max_mounts_count] [-e errors_behavior] [-f] [-g group]
            [-i interval[d|m|w]] [-j] [-J journal_options] [-l]
            [-m reserved_blocks_percent] [-o [^]mount_options[,...]]
            [-p mmp_update_interval] [-r reserved_blocks_count] [-u user]
            [-C mount_count] [-L volume_label] [-M last_mounted_dir]
            [-O [^]feature[,...]] [-Q quota_options]
            [-E extended-option[,...]] [-T last_check_time] [-U UUID]
            [-I new_inode_size] [-z undo_file] device
            '''
        )
        patch_which = patch(
            'salt.utils.path.which',
            Mock(return_value='fnord'),
        )
        patch_run = patch.dict(
            filemod.__salt__,
            {'cmd.run': MagicMock(return_value=sample_output)},
        )
        with patch_which, patch_run:
            actual = filemod._chattr_version()
            self.assertEqual(actual, expected)

    def test_if_tune2fs_has_no_version_version_should_be_None(self):
        patch_which = patch(
            'salt.utils.path.which',
            Mock(return_value='fnord'),
        )
        patch_run = patch.dict(
            filemod.__salt__,
            {'cmd.run': MagicMock(return_value='fnord')},
        )
        with patch_which, patch_run:
            actual = filemod._chattr_version()
            self.assertIsNone(actual)

    def test_chattr_has_extended_attrs_should_return_False_if_chattr_version_is_None(self):
        patch_chattr = patch(
            'salt.modules.file._chattr_version',
            Mock(return_value=None),
        )
        with patch_chattr:
            actual = filemod._chattr_has_extended_attrs()
            assert not actual, actual

    def test_chattr_has_extended_attrs_should_return_False_if_version_is_too_low(self):
        below_expected = '0.1.1'
        patch_chattr = patch(
            'salt.modules.file._chattr_version',
            Mock(return_value=below_expected),
        )
        with patch_chattr:
            actual = filemod._chattr_has_extended_attrs()
            assert not actual, actual

    def test_chattr_has_extended_attrs_should_return_False_if_version_is_equal_threshold(self):
        threshold = '1.41.12'
        patch_chattr = patch(
            'salt.modules.file._chattr_version',
            Mock(return_value=threshold),
        )
        with patch_chattr:
            actual = filemod._chattr_has_extended_attrs()
            assert not actual, actual

    def test_chattr_has_extended_attrs_should_return_True_if_version_is_above_threshold(self):
        higher_than = '1.41.13'
        patch_chattr = patch(
            'salt.modules.file._chattr_version',
            Mock(return_value=higher_than),
        )
        with patch_chattr:
            actual = filemod._chattr_has_extended_attrs()
            assert actual, actual

    # We're skipping this on Windows as it tests the check_perms function in
    # file.py which is specifically for Linux. The Windows version resides in
    # win_file.py
    @skipIf(salt.utils.platform.is_windows(), 'Skip on Windows')
    def test_check_perms_should_report_no_attr_changes_if_there_are_none(self):
        filename = '/path/to/fnord'
        attrs = 'aAcCdDeijPsStTu'

        higher_than = '1.41.13'
        patch_chattr = patch(
            'salt.modules.file._chattr_version',
            Mock(return_value=higher_than),
        )
        patch_exists = patch(
            'os.path.exists',
            Mock(return_value=True),
        )
        patch_stats = patch(
            'salt.modules.file.stats',
            Mock(return_value={
                'user': 'foo',
                'group': 'bar',
                'mode': '123',
            }),
        )
        patch_run = patch.dict(
            filemod.__salt__,
            {'cmd.run': MagicMock(return_value='--------- '+filename)},
        )
        with patch_chattr, patch_exists, patch_stats, patch_run:
            actual_ret, actual_perms = filemod.check_perms(
                name=filename,
                ret=None,
                user='foo',
                group='bar',
                mode='123',
                attrs=attrs,
                follow_symlinks=False,
            )
            assert actual_ret.get('changes', {}).get('attrs')is None, actual_ret

    # We're skipping this on Windows as it tests the check_perms function in
    # file.py which is specifically for Linux. The Windows version resides in
    # win_file.py
    @skipIf(salt.utils.platform.is_windows(), 'Skip on Windows')
    def test_check_perms_should_report_attrs_new_and_old_if_they_changed(self):
        filename = '/path/to/fnord'
        attrs = 'aAcCdDeijPsStTu'
        existing_attrs = 'aeiu'
        expected = {
            'attrs': {
                'old': existing_attrs,
                'new': attrs,
            },
        }

        higher_than = '1.41.13'
        patch_chattr = patch(
            'salt.modules.file._chattr_version',
            Mock(return_value=higher_than),
        )
        patch_stats = patch(
            'salt.modules.file.stats',
            Mock(return_value={
                'user': 'foo',
                'group': 'bar',
                'mode': '123',
            }),
        )
        patch_cmp = patch(
            'salt.modules.file._cmp_attrs',
            MagicMock(side_effect=[
                filemod.AttrChanges(
                    added='aAcCdDeijPsStTu',
                    removed='',
                ),
                filemod.AttrChanges(
                    None,
                    None,
                ),
            ]),
        )
        patch_chattr = patch(
            'salt.modules.file.chattr',
            MagicMock(),
        )

        def fake_cmd(cmd, *args, **kwargs):
            if cmd == ['lsattr', '/path/to/fnord']:
                return textwrap.dedent(
                    '''
                    {}---- {}
                    '''.format(existing_attrs, filename)
                ).strip()
            else:
                assert False, "not sure how to handle {}".format(cmd)

        patch_run = patch.dict(
            filemod.__salt__,
            {'cmd.run': MagicMock(side_effect=fake_cmd)},
        )
        patch_ver = patch(
            'salt.modules.file._chattr_has_extended_attrs',
            MagicMock(return_value=True),
        )
        with patch_chattr, patch_stats, patch_cmp, patch_run, patch_ver:
            actual_ret, actual_perms = filemod.check_perms(
                name=filename,
                ret=None,
                user='foo',
                group='bar',
                mode='123',
                attrs=attrs,
                follow_symlinks=False,
            )
            self.assertDictEqual(actual_ret['changes'], expected)
