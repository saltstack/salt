# -*- coding: utf-8 -*-
'''
    :codeauthor: Bo Maryniuk <bo@suse.de>
'''

from __future__ import absolute_import, print_function, unicode_literals

from tests.support.unit import skipIf, TestCase
from tests.support.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON

from salt.cli.support.console import IndentOutput
from salt.cli.support.collector import SupportDataCollector
from salt.utils.color import get_colors
from salt.utils.stringutils import to_bytes
import salt.exceptions

try:
    import pytest
except ImportError:
    pytest = None


@skipIf(not bool(pytest), 'Pytest needs to be installed')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltSupportIndentOutputTestCase(TestCase):
    '''
    Unit Tests for the salt-support indent output.
    '''

    def setUp(self):
        '''
        Setup test
        :return:
        '''

        self.message = 'Stubborn processes on dumb terminal'
        self.device = MagicMock()
        self.iout = IndentOutput(device=self.device)
        self.colors = get_colors()

    def tearDown(self):
        '''
        Remove instances after test run
        :return:
        '''
        del self.message
        del self.device
        del self.iout
        del self.colors

    def test_standard_output(self):
        '''
        Test console standard output.
        '''
        self.iout.put(self.message)
        assert self.device.write.called
        assert self.device.write.call_count == 5
        for idx, data in enumerate(['', str(self.colors['CYAN']), self.message, str(self.colors['ENDC']), '\n']):
            assert self.device.write.call_args_list[idx][0][0] == data

    def test_indent_output(self):
        '''
        Test indent distance.
        :return:
        '''
        self.iout.put(self.message, indent=10)
        for idx, data in enumerate([' ' * 10, str(self.colors['CYAN']), self.message, str(self.colors['ENDC']), '\n']):
            assert self.device.write.call_args_list[idx][0][0] == data

    def test_color_config(self):
        '''
        Test color config changes on each ident.
        :return:
        '''

        conf = {0: 'MAGENTA', 2: 'RED', 4: 'WHITE', 6: 'YELLOW'}
        self.iout = IndentOutput(conf=conf, device=self.device)
        for indent in sorted(list(conf.keys())):
            self.iout.put(self.message, indent=indent)

        step = 1
        for ident_key in sorted(list(conf)):
            assert str(self.device.write.call_args_list[step][0][0]) == str(self.colors[conf[ident_key]])
            step += 5


@skipIf(not bool(pytest), 'Pytest needs to be installed')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltSupportCollectorTestCase(TestCase):
    '''
    Collector tests.
    '''
    def setUp(self):
        '''
        Setup the test case
        :return:
        '''
        self.archive_path = '/highway/to/hell'
        self.output_device = MagicMock()
        self.collector = SupportDataCollector(self.archive_path, self.output_device)

    def tearDown(self):
        '''
        Tear down the test case elements
        :return:
        '''
        del self.collector
        del self.archive_path
        del self.output_device

    @patch('salt.cli.support.collector.tarfile.TarFile', MagicMock())
    def test_archive_open(self):
        '''
        Test archive is opened.

        :return:
        '''
        self.collector.open()
        assert self.collector.archive_path == self.archive_path
        with pytest.raises(salt.exceptions.SaltException) as err:
            self.collector.open()
        assert 'Archive already opened' in str(err)

    @patch('salt.cli.support.collector.tarfile.TarFile', MagicMock())
    def test_archive_close(self):
        '''
        Test archive is opened.

        :return:
        '''
        self.collector.open()
        self.collector._flush_content = lambda: None
        self.collector.close()
        assert self.collector.archive_path == self.archive_path
        with pytest.raises(salt.exceptions.SaltException) as err:
            self.collector.close()
        assert 'Archive already closed' in str(err)

    def test_archive_addwrite(self):
        '''
        Test add to the archive a section and write to it.

        :return:
        '''
        archive = MagicMock()
        with patch('salt.cli.support.collector.tarfile.TarFile', archive):
            self.collector.open()
            self.collector.add('foo')
            self.collector.write(title='title', data='data', output='null')
            self.collector._flush_content()

            assert (archive.bz2open().addfile.call_args[1]['fileobj'].read()
                    == to_bytes('title\n-----\n\nraw-content: data\n\n\n\n'))

    @patch('salt.cli.support.collector.open', MagicMock(return_value='path=/dev/null'))
    def test_archive_addlink(self):
        '''
        Test add to the archive a section and link an external file or directory to it.

        :return:
        '''
        archive = MagicMock()
        with patch('salt.cli.support.collector.tarfile.TarFile', archive):
            self.collector.open()
            self.collector.add('foo')
            self.collector.link(title='Backup Path', path='/path/to/backup.config')
            self.collector._flush_content()

            assert archive.bz2open().addfile.call_count == 1
            assert (archive.bz2open().addfile.call_args[1]['fileobj'].read()
                    == to_bytes('Backup Path\n-----------\n\npath=/dev/null\n\n\n'))
