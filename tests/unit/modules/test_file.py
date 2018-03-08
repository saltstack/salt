# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import shutil
import tempfile
import textwrap

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.paths import TMP
from tests.support.unit import TestCase, skipIf
from tests.support.mock import MagicMock, Mock, patch, mock_open

try:
    import pytest
except ImportError:
    pytest = None

# Import Salt libs
from salt.ext import six
import salt.config
import salt.loader
import salt.utils.files
import salt.utils.platform
import salt.utils.stringutils
import salt.modules.file as filemod
import salt.modules.config as configmod
import salt.modules.cmdmod as cmdmod
from salt.exceptions import CommandExecutionError
from salt.utils.jinja import SaltCacheLoader

SED_CONTENT = '''test
some
content
/var/lib/foo/app/test
here
'''


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
                '__utils__': {'files.is_text': MagicMock(return_value=True)},
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


class FileBlockReplaceTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {
            filemod: {
                '__salt__': {
                    'config.manage_mode': MagicMock(),
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
                '__utils__': {'files.is_text': MagicMock(return_value=True)},
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
        filemod.blockreplace(self.tfile.name,
                             '#-- START BLOCK 1',
                             '#-- END BLOCK 1',
                             new_multiline_content,
                             backup=False)

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
            '#-- START BLOCK 2',
            '#-- END BLOCK 2',
            new_content,
            append_if_not_found=False,
            backup=False
        )
        with salt.utils.files.fopen(self.tfile.name, 'r') as fp:
            self.assertNotIn(
                '#-- START BLOCK 2' + "\n" + new_content + '#-- END BLOCK 2',
                salt.utils.stringutils.to_unicode(fp.read())
            )

        filemod.blockreplace(self.tfile.name,
                             '#-- START BLOCK 2',
                             '#-- END BLOCK 2',
                             new_content,
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
        filemod.blockreplace(tfile.name, **args)
        with salt.utils.files.fopen(tfile.name) as tfile2:
            self.assertEqual(
                salt.utils.stringutils.to_unicode(tfile2.read()), expected)
        os.remove(tfile.name)

        # A newline should not be added in empty files
        with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as tfile:
            pass
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
            '#-- START BLOCK 2',
            '#-- END BLOCK 2',
            new_content,
            prepend_if_not_found=False,
            backup=False
        )
        with salt.utils.files.fopen(self.tfile.name, 'rb') as fp:
            self.assertNotIn(salt.utils.stringutils.to_bytes(
                os.linesep.join([
                    '#-- START BLOCK 2',
                    '{0}#-- END BLOCK 2'.format(new_content)])),
                fp.read())

        filemod.blockreplace(self.tfile.name,
                             '#-- START BLOCK 2', '#-- END BLOCK 2',
                             new_content,
                             backup=False,
                             prepend_if_not_found=True)

        with salt.utils.files.fopen(self.tfile.name, 'rb') as fp:
            self.assertTrue(
                fp.read().startswith(salt.utils.stringutils.to_bytes(
                    os.linesep.join([
                        '#-- START BLOCK 2',
                        '{0}#-- END BLOCK 2'.format(new_content)]))))

    def test_replace_partial_marked_lines(self):
        filemod.blockreplace(self.tfile.name,
                             '// START BLOCK',
                             '// END BLOCK',
                             'new content 1',
                             backup=False)

        with salt.utils.files.fopen(self.tfile.name, 'r') as fp:
            filecontent = salt.utils.stringutils.to_unicode(fp.read())
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
                '__grains__': {'kernel': 'Linux'}
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
                '__grains__': {'kernel': 'Linux'}
            }
        }

    @patch('os.path.realpath', MagicMock())
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
    def test_line_modecheck_failure(self):
        '''
        Test for file.line for empty or wrong mode.
        Calls unknown or empty mode and expects failure.
        :return:
        '''
        for mode, err_msg in [(None, 'How to process the file'), ('nonsense', 'Unknown mode')]:
            with pytest.raises(CommandExecutionError) as cmd_err:
                filemod.line('foo', mode=mode)
            self.assertIn(err_msg, six.text_type(cmd_err))

    @patch('os.path.realpath', MagicMock())
    @patch('os.path.isfile', MagicMock(return_value=True))
    def test_line_no_content(self):
        '''
        Test for file.line for an empty content when not deleting anything.
        :return:
        '''
        for mode in ['insert', 'ensure', 'replace']:
            with pytest.raises(CommandExecutionError) as cmd_err:
                filemod.line('foo', mode=mode)
            self.assertIn('Content can only be empty if mode is "delete"',
                          six.text_type(cmd_err))

    @patch('os.path.realpath', MagicMock())
    @patch('os.path.isfile', MagicMock(return_value=True))
    @patch('os.stat', MagicMock())
    def test_line_insert_no_location_no_before_no_after(self):
        '''
        Test for file.line for insertion but define no location/before/after.
        :return:
        '''
        files_fopen = mock_open(read_data='test data')
        with patch('salt.utils.files.fopen', files_fopen):
            with pytest.raises(CommandExecutionError) as cmd_err:
                filemod.line('foo', content='test content', mode='insert')
            self.assertIn('"location" or "before/after"',
                          six.text_type(cmd_err))

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

    @patch('os.path.realpath', MagicMock())
    @patch('os.path.isfile', MagicMock(return_value=True))
    @patch('os.stat', MagicMock())
    def test_line_insert_after_no_pattern(self):
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
        files_fopen = mock_open(read_data=file_content)
        with patch('salt.utils.files.fopen', files_fopen):
            atomic_opener = mock_open()
            with patch('salt.utils.atomicfile.atomic_open', atomic_opener):
                filemod.line('foo', content=cfg_content, after='- /srv/salt', mode='insert')
            self.assertEqual(len(atomic_opener().write.call_args_list), 1)
            self.assertEqual(atomic_opener().write.call_args_list[0][0][0],
                             file_modified)

    @patch('os.path.realpath', MagicMock())
    @patch('os.path.isfile', MagicMock(return_value=True))
    @patch('os.stat', MagicMock())
    def test_line_insert_after_pattern(self):
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
        for after_line in ['file_r.*', '.*roots']:
            files_fopen = mock_open(read_data=file_content)
            with patch('salt.utils.files.fopen', files_fopen):
                atomic_opener = mock_open()
                with patch('salt.utils.atomicfile.atomic_open', atomic_opener):
                    filemod.line('foo', content=cfg_content, after=after_line, mode='insert', indent=False)
            self.assertEqual(len(atomic_opener().write.call_args_list), 1)
            self.assertEqual(atomic_opener().write.call_args_list[0][0][0],
                             file_modified)

    @patch('os.path.realpath', MagicMock())
    @patch('os.path.isfile', MagicMock(return_value=True))
    @patch('os.stat', MagicMock())
    def test_line_insert_before(self):
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
        for before_line in ['/srv/salt', '/srv/sa.*t', '/sr.*']:
            files_fopen = mock_open(read_data=file_content)
            with patch('salt.utils.files.fopen', files_fopen):
                atomic_opener = mock_open()
                with patch('salt.utils.atomicfile.atomic_open', atomic_opener):
                    filemod.line('foo', content=cfg_content, before=before_line, mode='insert')
                self.assertEqual(len(atomic_opener().write.call_args_list), 1)
                self.assertEqual(atomic_opener().write.call_args_list[0][0][0],
                                 file_modified)

    @patch('os.path.realpath', MagicMock())
    @patch('os.path.isfile', MagicMock(return_value=True))
    @patch('os.stat', MagicMock())
    def test_line_insert_before_after(self):
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
        for b_line, a_line in [('/srv/sugar', '/srv/salt')]:
            files_fopen = mock_open(read_data=file_content)
            with patch('salt.utils.files.fopen', files_fopen):
                atomic_opener = mock_open()
                with patch('salt.utils.atomicfile.atomic_open', atomic_opener):
                    filemod.line('foo', content=cfg_content, before=b_line, after=a_line, mode='insert')
                self.assertEqual(len(atomic_opener().write.call_args_list), 1)
                self.assertEqual(atomic_opener().write.call_args_list[0][0][0],
                                 file_modified)

    @patch('os.path.realpath', MagicMock())
    @patch('os.path.isfile', MagicMock(return_value=True))
    @patch('os.stat', MagicMock())
    def test_line_insert_start(self):
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
        files_fopen = mock_open(read_data=file_content)
        with patch('salt.utils.files.fopen', files_fopen):
            atomic_opener = mock_open()
            with patch('salt.utils.atomicfile.atomic_open', atomic_opener):
                filemod.line('foo', content=cfg_content, location='start', mode='insert')
            self.assertEqual(len(atomic_opener().write.call_args_list), 1)
            self.assertEqual(atomic_opener().write.call_args_list[0][0][0],
                             file_modified)

    @patch('os.path.realpath', MagicMock())
    @patch('os.path.isfile', MagicMock(return_value=True))
    @patch('os.stat', MagicMock())
    def test_line_insert_end(self):
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
            cfg_content
        ])
        files_fopen = mock_open(read_data=file_content)
        with patch('salt.utils.files.fopen', files_fopen):
            atomic_opener = mock_open()
            with patch('salt.utils.atomicfile.atomic_open', atomic_opener):
                filemod.line('foo', content=cfg_content, location='end', mode='insert')
            self.assertEqual(len(atomic_opener().write.call_args_list), 1)
            self.assertEqual(atomic_opener().write.call_args_list[0][0][0],
                             file_modified)

    @patch('os.path.realpath', MagicMock())
    @patch('os.path.isfile', MagicMock(return_value=True))
    @patch('os.stat', MagicMock())
    def test_line_insert_ensure_before(self):
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
        files_fopen = mock_open(read_data=file_content)
        with patch('salt.utils.files.fopen', files_fopen):
            atomic_opener = mock_open()
            with patch('salt.utils.atomicfile.atomic_open', atomic_opener):
                filemod.line('foo', content=cfg_content, before='exit 0', mode='ensure')
            self.assertEqual(len(atomic_opener().write.call_args_list), 1)
            self.assertEqual(atomic_opener().write.call_args_list[0][0][0],
                             file_modified)

    @patch('os.path.realpath', MagicMock())
    @patch('os.path.isfile', MagicMock(return_value=True))
    @patch('os.stat', MagicMock())
    def test_line_insert_ensure_after(self):
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
        files_fopen = mock_open(read_data=file_content)
        with patch('salt.utils.files.fopen', files_fopen):
            atomic_opener = mock_open()
            with patch('salt.utils.atomicfile.atomic_open', atomic_opener):
                filemod.line('foo', content=cfg_content, after='/etc/init.d/someservice restart', mode='ensure')
            self.assertEqual(len(atomic_opener().write.call_args_list), 1)
            self.assertEqual(atomic_opener().write.call_args_list[0][0][0],
                             file_modified)

    @patch('os.path.realpath', MagicMock())
    @patch('os.path.isfile', MagicMock(return_value=True))
    @patch('os.stat', MagicMock())
    def test_line_insert_ensure_beforeafter_twolines(self):
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
        for (_after, _before) in [(after, before), ('NAME_.*', 'SKEL_.*')]:
            files_fopen = mock_open(read_data=file_content)
            with patch('salt.utils.files.fopen', files_fopen):
                atomic_opener = mock_open()
                with patch('salt.utils.atomicfile.atomic_open', atomic_opener):
                    filemod.line('foo', content=cfg_content, after=_after, before=_before, mode='ensure')
                self.assertEqual(len(atomic_opener().write.call_args_list), 1)
                self.assertEqual(atomic_opener().write.call_args_list[0][0][0],
                                 file_modified)

    @patch('os.path.realpath', MagicMock())
    @patch('os.path.isfile', MagicMock(return_value=True))
    @patch('os.stat', MagicMock())
    def test_line_insert_ensure_beforeafter_twolines_exists(self):
        '''
        Test for file.line for insertion ensuring the line is between two lines where content already exists
        :return:
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
        for (_after, _before) in [(after, before), ('NAME_.*', 'SKEL_.*')]:
            files_fopen = mock_open(read_data=file_content)
            with patch('salt.utils.files.fopen', files_fopen):
                atomic_opener = mock_open()
                with patch('salt.utils.atomicfile.atomic_open', atomic_opener):
                    result = filemod.line('foo', content=cfg_content, after=_after, before=_before, mode='ensure')
                self.assertEqual(len(atomic_opener().write.call_args_list), 0)
                self.assertEqual(result, False)

    @patch('os.path.realpath', MagicMock())
    @patch('os.path.isfile', MagicMock(return_value=True))
    @patch('os.stat', MagicMock())
    def test_line_insert_ensure_beforeafter_rangelines(self):
        '''
        Test for file.line for insertion ensuring the line is between two lines within the range.
        This expected to bring no changes.

        :return:
        '''
        cfg_content = 'EXTRA_GROUPS="dialout cdrom floppy audio video plugdev users"'
        # pylint: disable=W1401
        file_content = 'NAME_REGEX="^[a-z][-a-z0-9_]*\$"\nSETGID_HOME=no\nADD_EXTRA_GROUPS=1\n' \
                       'SKEL_IGNORE_REGEX="dpkg-(old|new|dist|save)"'
        # pylint: enable=W1401
        after, before = file_content.split(os.linesep)[0], file_content.split(os.linesep)[-1]
        for (_after, _before) in [(after, before), ('NAME_.*', 'SKEL_.*')]:
            files_fopen = mock_open(read_data=file_content)
            with patch('salt.utils.files.fopen', files_fopen):
                atomic_opener = mock_open()
                with patch('salt.utils.atomicfile.atomic_open', atomic_opener):
                    with pytest.raises(CommandExecutionError) as cmd_err:
                        filemod.line('foo', content=cfg_content, after=_after, before=_before, mode='ensure')
            self.assertIn(
                'Found more than one line between boundaries "before" and "after"',
                six.text_type(cmd_err))

    @patch('os.path.realpath', MagicMock())
    @patch('os.path.isfile', MagicMock(return_value=True))
    @patch('os.stat', MagicMock())
    def test_line_delete(self):
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
        for content in ['/srv/pepper', '/srv/pepp*', '/srv/p.*', '/sr.*pe.*']:
            files_fopen = mock_open(read_data=file_content)
            with patch('salt.utils.files.fopen', files_fopen):
                atomic_opener = mock_open()
                with patch('salt.utils.atomicfile.atomic_open', atomic_opener):
                    filemod.line('foo', content=content, mode='delete')
                self.assertEqual(len(atomic_opener().write.call_args_list), 1)
                self.assertEqual(atomic_opener().write.call_args_list[0][0][0],
                                 file_modified)

    @patch('os.path.realpath', MagicMock())
    @patch('os.path.isfile', MagicMock(return_value=True))
    @patch('os.stat', MagicMock())
    def test_line_replace(self):
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
        for match in ['/srv/pepper', '/srv/pepp*', '/srv/p.*', '/sr.*pe.*']:
            files_fopen = mock_open(read_data=file_content)
            with patch('salt.utils.files.fopen', files_fopen):
                atomic_opener = mock_open()
                with patch('salt.utils.atomicfile.atomic_open', atomic_opener):
                    filemod.line('foo', content='- /srv/natrium-chloride', match=match, mode='replace')
                self.assertEqual(len(atomic_opener().write.call_args_list), 1)
                self.assertEqual(atomic_opener().write.call_args_list[0][0][0],
                                 file_modified)


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
        self.myfile = os.path.join(TMP, 'myfile')
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
