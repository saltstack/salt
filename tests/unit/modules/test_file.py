# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import os
import shutil
import tempfile
import textwrap

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.paths import TMP
from tests.support.unit import TestCase, skipIf
from tests.support.mock import Mock, MagicMock, patch

# Import Salt libs
import salt.utils
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
                '__grains__': {'kernel': 'Linux'}
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
        base = os.linesep.join(['foo=1', 'bar=2'])

        # File ending with a newline, no match
        with tempfile.NamedTemporaryFile('w+b', delete=False) as tfile:
            tfile.write(salt.utils.to_bytes(base + os.linesep))
            tfile.flush()
        filemod.replace(tfile.name, **args)
        expected = os.linesep.join([base, 'baz=\\g<value>']) + os.linesep
        with salt.utils.fopen(tfile.name) as tfile2:
            self.assertEqual(tfile2.read(), expected)
        os.remove(tfile.name)

        # File not ending with a newline, no match
        with tempfile.NamedTemporaryFile('w+b', delete=False) as tfile:
            tfile.write(salt.utils.to_bytes(base))
            tfile.flush()
        filemod.replace(tfile.name, **args)
        with salt.utils.fopen(tfile.name) as tfile2:
            self.assertEqual(tfile2.read(), expected)
        os.remove(tfile.name)

        # A newline should not be added in empty files
        with tempfile.NamedTemporaryFile('w+b', delete=False) as tfile:
            pass
        filemod.replace(tfile.name, **args)
        expected = args['repl'] + os.linesep
        with salt.utils.fopen(tfile.name) as tfile2:
            self.assertEqual(tfile2.read(), expected)
        os.remove(tfile.name)

        # Using not_found_content, rather than repl
        with tempfile.NamedTemporaryFile('w+b', delete=False) as tfile:
            tfile.write(salt.utils.to_bytes(base))
            tfile.flush()
        args['not_found_content'] = 'baz=3'
        expected = os.linesep.join([base, 'baz=3']) + os.linesep
        filemod.replace(tfile.name, **args)
        with salt.utils.fopen(tfile.name) as tfile2:
            self.assertEqual(tfile2.read(), expected)
        os.remove(tfile.name)

        # not appending if matches
        with tempfile.NamedTemporaryFile('w+b', delete=False) as tfile:
            base = os.linesep.join(['foo=1', 'baz=42', 'bar=2'])
            tfile.write(salt.utils.to_bytes(base))
            tfile.flush()
        expected = base
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
                '__grains__': {'kernel': 'Linux'}
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
                             marker_start='#-- START BLOCK 1',
                             marker_end='#-- END BLOCK 1',
                             content=new_multiline_content,
                             backup=False,
                             append_newline=None)

        with salt.utils.fopen(self.tfile.name, 'rb') as fp:
            filecontent = fp.read()
        self.assertIn(salt.utils.to_bytes(
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
        with salt.utils.fopen(self.tfile.name, 'r') as fp:
            self.assertNotIn('#-- START BLOCK 2'
                             + "\n" + new_content
                             + '#-- END BLOCK 2', fp.read())

        filemod.blockreplace(self.tfile.name,
                             marker_start='#-- START BLOCK 2',
                             marker_end='#-- END BLOCK 2',
                             content=new_content,
                             backup=False,
                             append_if_not_found=True)

        with salt.utils.fopen(self.tfile.name, 'rb') as fp:
            self.assertIn(salt.utils.to_bytes(
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
            tfile.write(salt.utils.to_bytes(base + os.linesep))
            tfile.flush()
        filemod.blockreplace(tfile.name, **args)
        expected = os.linesep.join([base, block])
        with salt.utils.fopen(tfile.name) as tfile2:
            self.assertEqual(tfile2.read(), expected)
        os.remove(tfile.name)

        # File not ending with a newline
        with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as tfile:
            tfile.write(salt.utils.to_bytes(base))
            tfile.flush()
        filemod.blockreplace(tfile.name, **args)
        with salt.utils.fopen(tfile.name) as tfile2:
            self.assertEqual(tfile2.read(), expected)
        os.remove(tfile.name)

        # A newline should not be added in empty files
        with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as tfile:
            pass
        filemod.blockreplace(tfile.name, **args)
        with salt.utils.fopen(tfile.name) as tfile2:
            self.assertEqual(tfile2.read(), block)
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
        with salt.utils.fopen(self.tfile.name, 'rb') as fp:
            self.assertNotIn(salt.utils.to_bytes(
                os.linesep.join([
                    '#-- START BLOCK 2',
                    '{0}#-- END BLOCK 2'.format(new_content)])),
                fp.read())

        filemod.blockreplace(self.tfile.name,
                             marker_start='#-- START BLOCK 2',
                             marker_end='#-- END BLOCK 2',
                             content=new_content,
                             backup=False,
                             prepend_if_not_found=True)

        with salt.utils.fopen(self.tfile.name, 'rb') as fp:
            self.assertTrue(
                fp.read().startswith(salt.utils.to_bytes(
                    os.linesep.join([
                        '#-- START BLOCK 2',
                        '{0}#-- END BLOCK 2'.format(new_content)]))))

    def test_replace_partial_marked_lines(self):
        filemod.blockreplace(self.tfile.name,
                             marker_start='// START BLOCK',
                             marker_end='// END BLOCK',
                             content='new content 1',
                             backup=False)

        with salt.utils.fopen(self.tfile.name, 'r') as fp:
            filecontent = fp.read()
        self.assertIn('new content 1', filecontent)
        self.assertNotIn('to be removed', filecontent)
        self.assertIn('first part of start line', filecontent)
        self.assertNotIn('first part of end line', filecontent)
        self.assertIn('part of start line not removed', filecontent)
        self.assertIn('part of end line not removed', filecontent)

    def test_backup(self):
        fext = '.bak'
        bak_file = '{0}{1}'.format(self.tfile.name, fext)

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

        filemod.blockreplace(self.tfile.name,
                             marker_start='// START BLOCK',
                             marker_end='// END BLOCK',
                             content='new content 3',
                             backup=False)

        self.assertFalse(os.path.exists(bak_file))

    def test_no_modifications(self):
        filemod.blockreplace(self.tfile.name,
                             marker_start='#-- START BLOCK 1',
                             marker_end='#-- END BLOCK 1',
                             content='new content 4',
                             backup=False,
                             append_newline=None)
        before_ctime = os.stat(self.tfile.name).st_mtime
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

    @skipIf(salt.utils.is_windows(), 'SED is not available on Windows')
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
        with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as tfile:
            tfile.write(salt.utils.to_bytes('foo' + os.linesep))
            tfile.flush()
        filemod.append(tfile.name, 'bar')
        expected = os.linesep.join(['foo', 'bar']) + os.linesep
        with salt.utils.fopen(tfile.name) as tfile2:
            self.assertEqual(tfile2.read(), expected)

        # File not ending with a newline
        with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as tfile:
            tfile.write(salt.utils.to_bytes('foo'))
            tfile.flush()
        filemod.append(tfile.name, 'bar')
        with salt.utils.fopen(tfile.name) as tfile2:
            self.assertEqual(tfile2.read(), expected)

        # A newline should be added in empty files
        with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as tfile:
            filemod.append(tfile.name, 'bar')
        with salt.utils.fopen(tfile.name) as tfile2:
            self.assertEqual(tfile2.read(), 'bar' + os.linesep)

    def test_extract_hash(self):
        '''
        Check various hash file formats.
        '''
        # With file name
        with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as tfile:
            tfile.write(salt.utils.to_bytes(
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
            tfile.write(salt.utils.to_bytes(
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
                patch('salt.utils.which', return_value='/bin/patch') as mock_which:
            cmd_mock = MagicMock(return_value='test_retval')
            with patch.dict(filemod.__salt__, {'cmd.run_all': cmd_mock}):
                ret = filemod.patch('/path/to/file', '/path/to/patch')
            cmd = ['/bin/patch', '--forward', '--reject-file=-',
                '-i', '/path/to/patch', '/path/to/file']
            cmd_mock.assert_called_once_with(cmd, python_shell=False)
            self.assertEqual('test_retval', ret)

    def test_patch_dry_run(self):
        with patch('os.path.isdir', return_value=False) as mock_isdir, \
                patch('salt.utils.which', return_value='/bin/patch') as mock_which:
            cmd_mock = MagicMock(return_value='test_retval')
            with patch.dict(filemod.__salt__, {'cmd.run_all': cmd_mock}):
                ret = filemod.patch('/path/to/file', '/path/to/patch', dry_run=True)
            cmd = ['/bin/patch', '--dry-run', '--forward', '--reject-file=-',
                '-i', '/path/to/patch', '/path/to/file']
            cmd_mock.assert_called_once_with(cmd, python_shell=False)
            self.assertEqual('test_retval', ret)

    def test_patch_dir(self):
        with patch('os.path.isdir', return_value=True) as mock_isdir, \
                patch('salt.utils.which', return_value='/bin/patch') as mock_which:
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

    def test_replace_line_in_empty_file(self):
        '''
        Tests that when calling file.line with ``mode=replace``,
        the function doesn't stack trace if the file is empty.
        Should return ``False``.

        See Issue #31135.
        '''
        # Create an empty temporary named file
        empty_file = tempfile.NamedTemporaryFile(delete=False,
                                                 mode='w+')

        # Assert that the file was created and is empty
        self.assertEqual(os.stat(empty_file.name).st_size, 0)

        # Now call the function on the empty file and assert
        # the return is False instead of stack-tracing
        self.assertFalse(filemod.line(empty_file.name,
                                      content='foo',
                                      match='bar',
                                      mode='replace'))

        # Close and remove the file
        empty_file.close()
        os.remove(empty_file.name)

    def test_delete_line_in_empty_file(self):
        '''
        Tests that when calling file.line with ``mode=delete``,
        the function doesn't stack trace if the file is empty.
        Should return ``False``.

        See Issue #38438.
        '''
        # Create an empty temporary named file
        empty_file = tempfile.NamedTemporaryFile(delete=False,
                                                 mode='w+')

        # Assert that the file was created and is empty
        self.assertEqual(os.stat(empty_file.name).st_size, 0)

        # Now call the function on the empty file and assert
        # the return is False instead of stack-tracing
        self.assertFalse(filemod.line(empty_file.name,
                                      content='foo',
                                      match='bar',
                                      mode='delete'))

        # Close and remove the file
        empty_file.close()
        os.remove(empty_file.name)


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
        with salt.utils.fopen(self.myfile, 'w+') as fp:
            fp.write('Hello\n')
        self.addCleanup(os.remove, self.myfile)
        self.addCleanup(delattr, self, 'myfile')

    @skipIf(salt.utils.is_windows(), 'os.symlink is not available on Windows')
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
