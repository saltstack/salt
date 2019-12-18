# -*- coding: utf-8 -*-
'''
tests.unit.utils.test_configparser
==================================

Test the funcs in the custom parsers in salt.utils.configparser
'''
# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import copy
import errno
import logging
import os

log = logging.getLogger(__name__)

# Import Salt Testing Libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase

# Import salt libs
import salt.utils.files
import salt.utils.stringutils
import salt.utils.configparser
import salt.utils.platform
from salt.ext import six

# The user.name param here is intentionally indented with spaces instead of a
# tab to test that we properly load a file with mixed indentation.
ORIG_CONFIG = '''[user]
        name = Артём Анисимов
\temail = foo@bar.com
[remote "origin"]
\turl = https://github.com/terminalmage/salt.git
\tfetch = +refs/heads/*:refs/remotes/origin/*
\tpushurl = git@github.com:terminalmage/salt.git
[color "diff"]
\told = 196
\tnew = 39
[core]
\tpager = less -R
\trepositoryformatversion = 0
\tfilemode = true
\tbare = false
\tlogallrefupdates = true
[alias]
\tmodified = ! git status --porcelain | awk 'match($1, "M"){print $2}'
\tgraph = log --all --decorate --oneline --graph
\thist = log --pretty=format:\\"%h %ad | %s%d [%an]\\" --graph --date=short
[http]
\tsslverify = false'''.split('\n')


class TestGitConfigParser(TestCase):
    '''
    Tests for salt.utils.configparser.GitConfigParser
    '''
    maxDiff = None
    orig_config = os.path.join(RUNTIME_VARS.TMP, 'test_gitconfig.orig')
    new_config = os.path.join(RUNTIME_VARS.TMP, 'test_gitconfig.new')
    remote = 'remote "origin"'

    def tearDown(self):
        del self.conf
        try:
            os.remove(self.new_config)
        except OSError as exc:
            if exc.errno != errno.ENOENT:
                raise

    def setUp(self):
        if not os.path.exists(self.orig_config):
            with salt.utils.files.fopen(self.orig_config, 'wb') as fp_:
                fp_.write(
                    salt.utils.stringutils.to_bytes(
                        os.linesep.join(ORIG_CONFIG)
                    )
                )
        self.conf = salt.utils.configparser.GitConfigParser()
        with salt.utils.files.fopen(self.orig_config, 'rb') as fp:
            self.conf._read(fp, self.orig_config)

    @classmethod
    def tearDownClass(cls):
        try:
            os.remove(cls.orig_config)
        except OSError as exc:
            if exc.errno != errno.ENOENT:
                raise

    @staticmethod
    def fix_indent(lines):
        '''
        Fixes the space-indented 'user' line, because when we write the config
        object to a file space indentation will be replaced by tab indentation.
        '''
        ret = copy.copy(lines)
        for i, _ in enumerate(ret):
            if ret[i].startswith(salt.utils.configparser.GitConfigParser.SPACEINDENT):
                ret[i] = ret[i].replace(salt.utils.configparser.GitConfigParser.SPACEINDENT, '\t')
        return ret

    @staticmethod
    def get_lines(path):
        with salt.utils.files.fopen(path, 'rb') as fp_:
            return salt.utils.stringutils.to_unicode(fp_.read()).splitlines()

    def _test_write(self, mode):
        kwargs = {'mode': mode}
        if six.PY3 and salt.utils.platform.is_windows() and 'b' not in mode:
            kwargs['encoding'] = 'utf-8'
        with salt.utils.files.fopen(self.new_config, **kwargs) as fp_:
            self.conf.write(fp_)
        self.assertEqual(
            self.get_lines(self.new_config),
            self.fix_indent(ORIG_CONFIG)
        )

    def test_get(self):
        '''
        Test getting an option's value
        '''
        # Numeric values should be loaded as strings
        self.assertEqual(self.conf.get('color "diff"', 'old'), '196')
        # Complex strings should be loaded with their literal quotes and
        # slashes intact
        self.assertEqual(
            self.conf.get('alias', 'modified'),
            """! git status --porcelain | awk 'match($1, "M"){print $2}'"""
        )
        # future lint: disable=non-unicode-string
        self.assertEqual(
            self.conf.get('alias', 'hist'),
            salt.utils.stringutils.to_unicode(
                r"""log --pretty=format:\"%h %ad | %s%d [%an]\" --graph --date=short"""
            )
        )
        # future lint: enable=non-unicode-string

    def test_read_space_indent(self):
        '''
        Test that user.name was successfully loaded despite being indented
        using spaces instead of a tab. Additionally, this tests that the value
        was loaded as a unicode type on PY2.
        '''
        self.assertEqual(self.conf.get('user', 'name'), u'Артём Анисимов')

    def test_set_new_option(self):
        '''
        Test setting a new option in an existing section
        '''
        self.conf.set('http', 'useragent', 'myawesomeagent')
        self.assertEqual(self.conf.get('http', 'useragent'), 'myawesomeagent')

    def test_add_section(self):
        '''
        Test adding a section and adding an item to that section
        '''
        self.conf.add_section('foo')
        self.conf.set('foo', 'bar', 'baz')
        self.assertEqual(self.conf.get('foo', 'bar'), 'baz')

    def test_replace_option(self):
        '''
        Test replacing an existing option
        '''
        # We're also testing the normalization of key names, here. Setting
        # "sslVerify" should actually set an "sslverify" option.
        self.conf.set('http', 'sslVerify', 'true')
        self.assertEqual(self.conf.get('http', 'sslverify'), 'true')

    def test_set_multivar(self):
        '''
        Test setting a multivar and then writing the resulting file
        '''
        orig_refspec = '+refs/heads/*:refs/remotes/origin/*'
        new_refspec = '+refs/tags/*:refs/tags/*'
        # Make sure that the original value is a string
        self.assertEqual(
            self.conf.get(self.remote, 'fetch'),
            orig_refspec
        )
        # Add another refspec
        self.conf.set_multivar(self.remote, 'fetch', new_refspec)
        # The value should now be a list
        self.assertEqual(
            self.conf.get(self.remote, 'fetch'),
            [orig_refspec, new_refspec]
        )
        # Write the config object to a file
        with salt.utils.files.fopen(self.new_config, 'wb') as fp_:
            self.conf.write(fp_)
        # Confirm that the new file was written correctly
        expected = self.fix_indent(ORIG_CONFIG)
        expected.insert(6, '\tfetch = %s' % new_refspec)  # pylint: disable=string-substitution-usage-error
        self.assertEqual(self.get_lines(self.new_config), expected)

    def test_remove_option(self):
        '''
        test removing an option, including all items from a multivar
        '''
        for item in ('fetch', 'pushurl'):
            self.conf.remove_option(self.remote, item)
            # To confirm that the option is now gone, a get should raise an
            # NoOptionError exception.
            self.assertRaises(
                salt.utils.configparser.NoOptionError,
                self.conf.get,
                self.remote,
                item)

    def test_remove_option_regexp(self):
        '''
        test removing an option, including all items from a multivar
        '''
        orig_refspec = '+refs/heads/*:refs/remotes/origin/*'
        new_refspec_1 = '+refs/tags/*:refs/tags/*'
        new_refspec_2 = '+refs/foo/*:refs/foo/*'
        # First, add both refspecs
        self.conf.set_multivar(self.remote, 'fetch', new_refspec_1)
        self.conf.set_multivar(self.remote, 'fetch', new_refspec_2)
        # Make sure that all three values are there
        self.assertEqual(
            self.conf.get(self.remote, 'fetch'),
            [orig_refspec, new_refspec_1, new_refspec_2]
        )
        # If the regex doesn't match, no items should be removed
        self.assertFalse(
            self.conf.remove_option_regexp(
                self.remote,
                'fetch',
                salt.utils.stringutils.to_unicode(r'\d{7,10}')  # future lint: disable=non-unicode-string
            )
        )
        # Make sure that all three values are still there (since none should
        # have been removed)
        self.assertEqual(
            self.conf.get(self.remote, 'fetch'),
            [orig_refspec, new_refspec_1, new_refspec_2]
        )
        # Remove one of the values
        self.assertTrue(
            self.conf.remove_option_regexp(self.remote, 'fetch', 'tags'))
        # Confirm that the value is gone
        self.assertEqual(
            self.conf.get(self.remote, 'fetch'),
            [orig_refspec, new_refspec_2]
        )
        # Remove the other one we added earlier
        self.assertTrue(
            self.conf.remove_option_regexp(self.remote, 'fetch', 'foo'))
        # Since the option now only has one value, it should be a string
        self.assertEqual(self.conf.get(self.remote, 'fetch'), orig_refspec)
        # Remove the last remaining option
        self.assertTrue(
            self.conf.remove_option_regexp(self.remote, 'fetch', 'heads'))
        # Trying to do a get now should raise an exception
        self.assertRaises(
            salt.utils.configparser.NoOptionError,
            self.conf.get,
            self.remote,
            'fetch')

    def test_write(self):
        '''
        Test writing using non-binary filehandle
        '''
        self._test_write(mode='w')

    def test_write_binary(self):
        '''
        Test writing using binary filehandle
        '''
        self._test_write(mode='wb')
