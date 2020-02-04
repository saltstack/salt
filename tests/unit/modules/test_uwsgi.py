# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import MagicMock, Mock, patch

# Import salt libs
import salt.modules.uwsgi as uwsgi


class UwsgiTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        patcher = patch('salt.utils.path.which', Mock(return_value='/usr/bin/uwsgi'))
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
