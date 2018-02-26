# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, Mock, patch

# Import salt libs
import salt.modules.uwsgi as uwsgi


@skipIf(NO_MOCK, NO_MOCK_REASON)
class UwsgiTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        patcher = patch('salt.utils.which', Mock(return_value='/usr/bin/uwsgi'))
        patcher.start()
        self.addCleanup(patcher.stop)
        return {uwsgi: {}}

    def test_uwsgi_stats(self):
        socket = "127.0.0.1:5050"
        mock = MagicMock(return_value='{"a": 1, "b": 2}')
        with patch.dict(uwsgi.__salt__, {'cmd.run': mock}):
            result = uwsgi.stats(socket)
            mock.assert_called_once_with(
                ['uwsgi', '--connect-and-read', '{0}'.format(socket)],
                python_shell=False)
            self.assertEqual(result, {'a': 1, 'b': 2})
