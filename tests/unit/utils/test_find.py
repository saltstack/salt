# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, unicode_literals, print_function
import os
import sys
import shutil
import tempfile
import stat

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf, TestCase

# Import salt libs
import salt.utils.files
import salt.utils.find

# Import 3rd-party libs
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin
from salt.ext import six
import pytest


class TestFind(TestCase):

    def test_parse_interval(self):
        with pytest.raises(ValueError):
            salt.utils.find._parse_interval('w')
        with pytest.raises(ValueError):
            salt.utils.find._parse_interval('1')
        with pytest.raises(ValueError):
            salt.utils.find._parse_interval('1s1w')
        with pytest.raises(ValueError):
            salt.utils.find._parse_interval('1s1s')

        result, resolution, modifier = salt.utils.find._parse_interval('')
        assert result == 0
        assert resolution is None
        assert modifier == ''

        result, resolution, modifier = salt.utils.find._parse_interval('1s')
        assert result == 1.0
        assert resolution == 1
        assert modifier == ''

        result, resolution, modifier = salt.utils.find._parse_interval('1m')
        assert result == 60.0
        assert resolution == 60
        assert modifier == ''

        result, resolution, modifier = salt.utils.find._parse_interval('1h')
        assert result == 3600.0
        assert resolution == 3600
        assert modifier == ''

        result, resolution, modifier = salt.utils.find._parse_interval('1d')
        assert result == 86400.0
        assert resolution == 86400
        assert modifier == ''

        result, resolution, modifier = salt.utils.find._parse_interval('1w')
        assert result == 604800.0
        assert resolution == 604800
        assert modifier == ''

        result, resolution, modifier = salt.utils.find._parse_interval('1w3d6h')
        assert result == 885600.0
        assert resolution == 3600
        assert modifier == ''

        result, resolution, modifier = salt.utils.find._parse_interval('1m1s')
        assert result == 61.0
        assert resolution == 1
        assert modifier == ''

        result, resolution, modifier = salt.utils.find._parse_interval('1m2s')
        assert result == 62.0
        assert resolution == 1
        assert modifier == ''

        result, resolution, modifier = salt.utils.find._parse_interval('+1d')
        assert result == 86400.0
        assert resolution == 86400
        assert modifier == '+'

        result, resolution, modifier = salt.utils.find._parse_interval('-1d')
        assert result == 86400.0
        assert resolution == 86400
        assert modifier == '-'

    def test_parse_size(self):
        with pytest.raises(ValueError):
            salt.utils.find._parse_size('')
        with pytest.raises(ValueError):
            salt.utils.find._parse_size('1s1s')
        min_size, max_size = salt.utils.find._parse_size('1')
        assert min_size == 1
        assert max_size == 1

        min_size, max_size = salt.utils.find._parse_size('1b')
        assert min_size == 1
        assert max_size == 1

        min_size, max_size = salt.utils.find._parse_size('1k')
        assert min_size == 1024
        assert max_size == 2047

        min_size, max_size = salt.utils.find._parse_size('1m')
        assert min_size == 1048576
        assert max_size == 2097151

        min_size, max_size = salt.utils.find._parse_size('1g')
        assert min_size == 1073741824
        assert max_size == 2147483647

        min_size, max_size = salt.utils.find._parse_size('1t')
        assert min_size == 1099511627776
        assert max_size == 2199023255551

        min_size, max_size = salt.utils.find._parse_size('0m')
        assert min_size == 0
        assert max_size == 1048575

        min_size, max_size = salt.utils.find._parse_size('-1m')
        assert min_size == 0
        assert max_size == 1048576

        min_size, max_size = salt.utils.find._parse_size('+1m')
        assert min_size == 1048576
        assert max_size == sys.maxsize

        min_size, max_size = salt.utils.find._parse_size('+1M')
        assert min_size == 1048576
        assert max_size == sys.maxsize

    def test_option_requires(self):
        option = salt.utils.find.Option()
        assert option.requires() == salt.utils.find._REQUIRES_PATH

    def test_name_option_match(self):
        option = salt.utils.find.NameOption('name', '*.txt')
        assert option.match('', '', '') is None
        assert option.match('', 'hello.txt', '').group() is 'hello.txt'
        assert option.match('', 'HELLO.TXT', '') is None

    def test_iname_option_match(self):
        option = salt.utils.find.InameOption('name', '*.txt')
        assert option.match('', '', '') is None
        assert option.match('', 'hello.txt', '').group() is 'hello.txt'
        assert option.match('', 'HELLO.TXT', '').group() is 'HELLO.TXT'

    def test_regex_option_match(self):
        with pytest.raises(ValueError):
            salt.utils.find.RegexOption('name', '(.*}')

        option = salt.utils.find.RegexOption('name', r'.*\.txt')
        assert option.match('', '', '') is None
        assert option.match('', 'hello.txt', '').group() is 'hello.txt'
        assert option.match('', 'HELLO.TXT', '') is None

    def test_iregex_option_match(self):
        with pytest.raises(ValueError):
            salt.utils.find.IregexOption('name', '(.*}')

        option = salt.utils.find.IregexOption('name', r'.*\.txt')
        assert option.match('', '', '') is None
        assert option.match('', 'hello.txt', '').group() is 'hello.txt'
        assert option.match('', 'HELLO.TXT', '').group() is 'HELLO.TXT'

    def test_type_option_requires(self):
        with pytest.raises(ValueError):
            salt.utils.find.TypeOption('type', 'w')

        option = salt.utils.find.TypeOption('type', 'd')
        assert option.requires() == salt.utils.find._REQUIRES_STAT

    def test_type_option_match(self):
        option = salt.utils.find.TypeOption('type', 'b')
        assert option.match('', '', [stat.S_IFREG]) is False

        option = salt.utils.find.TypeOption('type', 'c')
        assert option.match('', '', [stat.S_IFREG]) is False

        option = salt.utils.find.TypeOption('type', 'd')
        assert option.match('', '', [stat.S_IFREG]) is False

        option = salt.utils.find.TypeOption('type', 'f')
        assert option.match('', '', [stat.S_IFREG]) is True

        option = salt.utils.find.TypeOption('type', 'l')
        assert option.match('', '', [stat.S_IFREG]) is False

        option = salt.utils.find.TypeOption('type', 'p')
        assert option.match('', '', [stat.S_IFREG]) is False

        option = salt.utils.find.TypeOption('type', 's')
        assert option.match('', '', [stat.S_IFREG]) is False

        option = salt.utils.find.TypeOption('type', 'b')
        assert option.match('', '', [stat.S_IFBLK]) is True

        option = salt.utils.find.TypeOption('type', 'c')
        assert option.match('', '', [stat.S_IFCHR]) is True

        option = salt.utils.find.TypeOption('type', 'd')
        assert option.match('', '', [stat.S_IFDIR]) is True

        option = salt.utils.find.TypeOption('type', 'l')
        assert option.match('', '', [stat.S_IFLNK]) is True

        option = salt.utils.find.TypeOption('type', 'p')
        assert option.match('', '', [stat.S_IFIFO]) is True

        option = salt.utils.find.TypeOption('type', 's')
        assert option.match('', '', [stat.S_IFSOCK]) is True

    @skipIf(sys.platform.startswith('win'), 'pwd not available on Windows')
    def test_owner_option_requires(self):
        with pytest.raises(ValueError):
            salt.utils.find.OwnerOption('owner', 'notexist')

        option = salt.utils.find.OwnerOption('owner', 'root')
        assert option.requires() == salt.utils.find._REQUIRES_STAT

    @skipIf(sys.platform.startswith('win'), 'pwd not available on Windows')
    def test_owner_option_match(self):
        option = salt.utils.find.OwnerOption('owner', 'root')
        assert option.match('', '', [0] * 5) is True

        option = salt.utils.find.OwnerOption('owner', '500')
        assert option.match('', '', [500] * 5) is True

    @skipIf(sys.platform.startswith('win'), 'grp not available on Windows')
    def test_group_option_requires(self):
        with pytest.raises(ValueError):
            salt.utils.find.GroupOption('group', 'notexist')

        if sys.platform.startswith(('darwin', 'freebsd', 'openbsd')):
            group_name = 'wheel'
        else:
            group_name = 'root'
        option = salt.utils.find.GroupOption('group', group_name)
        assert option.requires() == salt.utils.find._REQUIRES_STAT

    @skipIf(sys.platform.startswith('win'), 'grp not available on Windows')
    def test_group_option_match(self):
        if sys.platform.startswith(('darwin', 'freebsd', 'openbsd')):
            group_name = 'wheel'
        else:
            group_name = 'root'
        option = salt.utils.find.GroupOption('group', group_name)
        assert option.match('', '', [0] * 6) is True

        option = salt.utils.find.GroupOption('group', '500')
        assert option.match('', '', [500] * 6) is True

    def test_size_option_requires(self):
        with pytest.raises(ValueError):
            salt.utils.find.SizeOption('size', '1s1s')

        option = salt.utils.find.SizeOption('size', '+1G')
        assert option.requires() == salt.utils.find._REQUIRES_STAT

    def test_size_option_match(self):
        option = salt.utils.find.SizeOption('size', '+1k')
        assert option.match('', '', [10000] * 7) is True

        option = salt.utils.find.SizeOption('size', '+1G')
        assert option.match('', '', [10000] * 7) is False

    def test_mtime_option_requires(self):
        with pytest.raises(ValueError):
            salt.utils.find.MtimeOption('mtime', '4g')

        option = salt.utils.find.MtimeOption('mtime', '1d')
        assert option.requires() == salt.utils.find._REQUIRES_STAT

    def test_mtime_option_match(self):
        option = salt.utils.find.MtimeOption('mtime', '-1w')
        assert option.match('', '', [1] * 9) is False

        option = salt.utils.find.MtimeOption('mtime', '-1s')
        assert option.match('', '', [10 ** 10] * 9) is True


class TestGrepOption(TestCase):

    def setUp(self):
        super(TestGrepOption, self).setUp()
        self.tmpdir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        super(TestGrepOption, self).tearDown()

    def test_grep_option_requires(self):
        with pytest.raises(ValueError):
            salt.utils.find.GrepOption('grep', '(foo)|(bar}')

        option = salt.utils.find.GrepOption('grep', '(foo)|(bar)')
        find = salt.utils.find
        assert option.requires() == (find._REQUIRES_CONTENTS | find._REQUIRES_STAT)

    def test_grep_option_match_regular_file(self):
        hello_file = os.path.join(self.tmpdir, 'hello.txt')
        with salt.utils.files.fopen(hello_file, 'w') as fp_:
            fp_.write(salt.utils.stringutils.to_str('foo'))
        option = salt.utils.find.GrepOption('grep', 'foo')
        assert option.match(self.tmpdir, 'hello.txt', os.stat(hello_file)) == \
            hello_file

        option = salt.utils.find.GrepOption('grep', 'bar')
        assert option.match(self.tmpdir, 'hello.txt', os.stat(hello_file)) is None

    @skipIf(sys.platform.startswith('win'), 'No /dev/null on Windows')
    def test_grep_option_match_dev_null(self):
        option = salt.utils.find.GrepOption('grep', 'foo')
        assert option.match('dev', 'null', os.stat('/dev/null')) is None


class TestPrintOption(TestCase):

    def setUp(self):
        super(TestPrintOption, self).setUp()
        self.tmpdir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        super(TestPrintOption, self).tearDown()

    def test_print_option_defaults(self):
        option = salt.utils.find.PrintOption('print', '')
        assert option.need_stat is False
        assert option.print_title is False
        assert option.fmt == ['path']

    def test_print_option_requires(self):
        option = salt.utils.find.PrintOption('print', '')
        assert option.requires() == salt.utils.find._REQUIRES_PATH

        option = salt.utils.find.PrintOption('print', 'name')
        assert option.requires() == salt.utils.find._REQUIRES_PATH

        option = salt.utils.find.PrintOption('print', 'path')
        assert option.requires() == salt.utils.find._REQUIRES_PATH

        option = salt.utils.find.PrintOption('print', 'name,path')
        assert option.requires() == salt.utils.find._REQUIRES_PATH

        option = salt.utils.find.PrintOption('print', 'user')
        assert option.requires() == salt.utils.find._REQUIRES_STAT

        option = salt.utils.find.PrintOption('print', 'path user')
        assert option.requires() == salt.utils.find._REQUIRES_STAT

    def test_print_option_execute(self):
        hello_file = os.path.join(self.tmpdir, 'hello.txt')
        with salt.utils.files.fopen(hello_file, 'w') as fp_:
            fp_.write(salt.utils.stringutils.to_str('foo'))

        option = salt.utils.find.PrintOption('print', '')
        assert option.execute('', [0] * 9) == ''

        option = salt.utils.find.PrintOption('print', 'path')
        assert option.execute('test_name', [0] * 9) == 'test_name'

        option = salt.utils.find.PrintOption('print', 'name')
        assert option.execute('test_name', [0] * 9) == 'test_name'

        option = salt.utils.find.PrintOption('print', 'size')
        assert option.execute(hello_file, os.stat(hello_file)) == 3

        option = salt.utils.find.PrintOption('print', 'type')
        assert option.execute(hello_file, os.stat(hello_file)) == 'f'

        option = salt.utils.find.PrintOption('print', 'mode')
        assert option.execute(hello_file, range(10)) == 0

        option = salt.utils.find.PrintOption('print', 'mtime')
        assert option.execute(hello_file, range(10)) == 8

        option = salt.utils.find.PrintOption('print', 'md5')
        assert option.execute(hello_file, os.stat(hello_file)) == \
            'acbd18db4cc2f85cedef654fccc4a4d8'

        option = salt.utils.find.PrintOption('print', 'path name')
        assert option.execute('test_name', [0] * 9) == ['test_name', 'test_name']

        option = salt.utils.find.PrintOption('print', 'size name')
        assert option.execute('test_name', [0] * 9) == [0, 'test_name']

    @skipIf(sys.platform.startswith('win'), "pwd not available on Windows")
    def test_print_user(self):
        option = salt.utils.find.PrintOption('print', 'user')
        assert option.execute('', [0] * 10) == 'root'

        option = salt.utils.find.PrintOption('print', 'user')
        assert option.execute('', [2 ** 31] * 10) == 2 ** 31

    @skipIf(sys.platform.startswith('win'), "grp not available on Windows")
    def test_print_group(self):
        option = salt.utils.find.PrintOption('print', 'group')
        if sys.platform.startswith(('darwin', 'freebsd', 'openbsd')):
            group_name = 'wheel'
        else:
            group_name = 'root'
        assert option.execute('', [0] * 10) == group_name

        # This seems to be not working in Ubuntu 12.04 32 bit
        #option = salt.utils.find.PrintOption('print', 'group')
        #self.assertEqual(option.execute('', [2 ** 31] * 10), 2 ** 31)

    @skipIf(sys.platform.startswith('win'), "no /dev/null on windows")
    def test_print_md5(self):
        option = salt.utils.find.PrintOption('print', 'md5')
        assert option.execute('/dev/null', os.stat('/dev/null')) == ''


class TestFinder(TestCase):

    def setUp(self):
        super(TestFinder, self).setUp()
        self.tmpdir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        super(TestFinder, self).tearDown()

    @skipIf(sys.platform.startswith('win'), 'No /dev/null on Windows')
    def test_init(self):
        finder = salt.utils.find.Finder({})
        assert six.text_type(finder.actions[0].__class__)[-13:-2] == 'PrintOption'
        assert finder.criteria == []

        finder = salt.utils.find.Finder({'_': None})
        assert six.text_type(finder.actions[0].__class__)[-13:-2] == 'PrintOption'
        assert finder.criteria == []

        with pytest.raises(ValueError):
            salt.utils.find.Finder({'': None})
        with pytest.raises(ValueError):
            salt.utils.find.Finder({'name': None})
        with pytest.raises(ValueError):
            salt.utils.find.Finder({'nonexist': 'somevalue'})

        finder = salt.utils.find.Finder({'name': 'test_name'})
        assert six.text_type(finder.actions[0].__class__)[-13:-2] == 'PrintOption'
        assert six.text_type(finder.criteria[0].__class__)[-12:-2] == 'NameOption'

        finder = salt.utils.find.Finder({'iname': 'test_name'})
        assert six.text_type(finder.actions[0].__class__)[-13:-2] == 'PrintOption'
        assert six.text_type(finder.criteria[0].__class__)[-13:-2] == 'InameOption'

        finder = salt.utils.find.Finder({'regex': r'.*\.txt'})
        assert six.text_type(finder.actions[0].__class__)[-13:-2] == 'PrintOption'
        assert six.text_type(finder.criteria[0].__class__)[-13:-2] == 'RegexOption'

        finder = salt.utils.find.Finder({'iregex': r'.*\.txt'})
        assert six.text_type(finder.actions[0].__class__)[-13:-2] == 'PrintOption'
        assert six.text_type(finder.criteria[0].__class__)[-14:-2] == 'IregexOption'

        finder = salt.utils.find.Finder({'type': 'd'})
        assert six.text_type(finder.actions[0].__class__)[-13:-2] == 'PrintOption'
        assert six.text_type(finder.criteria[0].__class__)[-12:-2] == 'TypeOption'

        finder = salt.utils.find.Finder({'owner': 'root'})
        assert six.text_type(finder.actions[0].__class__)[-13:-2] == 'PrintOption'
        assert six.text_type(finder.criteria[0].__class__)[-13:-2] == 'OwnerOption'

        if sys.platform.startswith(('darwin', 'freebsd', 'openbsd')):
            group_name = 'wheel'
        else:
            group_name = 'root'
        finder = salt.utils.find.Finder({'group': group_name})
        assert six.text_type(finder.actions[0].__class__)[-13:-2] == 'PrintOption'
        assert six.text_type(finder.criteria[0].__class__)[-13:-2] == 'GroupOption'

        finder = salt.utils.find.Finder({'size': '+1G'})
        assert six.text_type(finder.actions[0].__class__)[-13:-2] == 'PrintOption'
        assert six.text_type(finder.criteria[0].__class__)[-12:-2] == 'SizeOption'

        finder = salt.utils.find.Finder({'mtime': '1d'})
        assert six.text_type(finder.actions[0].__class__)[-13:-2] == 'PrintOption'
        assert six.text_type(finder.criteria[0].__class__)[-13:-2] == 'MtimeOption'

        finder = salt.utils.find.Finder({'grep': 'foo'})
        assert six.text_type(finder.actions[0].__class__)[-13:-2] == 'PrintOption'
        assert six.text_type(finder.criteria[0].__class__)[-12:-2] == 'GrepOption'

        finder = salt.utils.find.Finder({'print': 'name'})
        assert six.text_type(finder.actions[0].__class__)[-13:-2] == 'PrintOption'
        assert finder.criteria == []

    def test_find(self):
        hello_file = os.path.join(self.tmpdir, 'hello.txt')
        with salt.utils.files.fopen(hello_file, 'w') as fp_:
            fp_.write(salt.utils.stringutils.to_str('foo'))

        finder = salt.utils.find.Finder({})
        assert list(finder.find(self.tmpdir)) == [self.tmpdir, hello_file]

        finder = salt.utils.find.Finder({'mindepth': 1})
        assert list(finder.find(self.tmpdir)) == [hello_file]

        finder = salt.utils.find.Finder({'maxdepth': 0})
        assert list(finder.find(self.tmpdir)) == [self.tmpdir]

        finder = salt.utils.find.Finder({'name': 'hello.txt'})
        assert list(finder.find(self.tmpdir)) == [hello_file]

        finder = salt.utils.find.Finder({'type': 'f', 'print': 'path'})
        assert list(finder.find(self.tmpdir)) == [hello_file]

        finder = salt.utils.find.Finder({'size': '+1G', 'print': 'path'})
        assert list(finder.find(self.tmpdir)) == []

        finder = salt.utils.find.Finder(
            {'name': 'hello.txt', 'print': 'path name'}
        )
        assert list(finder.find(self.tmpdir)) == [[hello_file, 'hello.txt']]

        finder = salt.utils.find.Finder({'name': 'test_name'})
        assert list(finder.find('')) == []
